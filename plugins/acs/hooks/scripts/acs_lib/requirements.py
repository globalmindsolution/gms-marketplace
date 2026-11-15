"""acs_lib.requirements — a run's REQUIREMENTS, from whatever carried them (ADR-0128).

Skills receive requirements from the user. A ticket id, documents (paths in the
repo, or files from outside it -- PDFs, images, markdown) and a prompt are only
the CONTAINERS they arrive in, and one invocation may mix them:

    /acs:analyze-requirements SHOP-12 ~/Downloads/spec.pdf "also bulk export"

This module turns that argument text into one normalised record per run:

  parse_sources   the invocation's tokens -> [{kind: ticket|document|prompt}]
  primary_subject the ONE subject run ids, resume-by-ticket and every reader of
                  `run.json.subject` keep keying on (ticket > document > prompt);
                  a mixed invocation also stores the whole list as
                  `subject.sources`
  materialise     `<run>/subject/sources.json`, a copy of every document from
                  outside the repo under `<run>/subject/`, and the generated
                  `<run>/requirements.md` -- idempotent, called by both the
                  Skill pre-hook and `acs.py step start` (hookless hosts too)
  add_sources     a later invocation's new sources, appended (never replaced)
  refine          analyze-requirements' refined criteria, feature(s) and
                  phase, kept in `<run>/requirements-refined.json`, rendered
                  as `## Refined`, and patched onto the ticket when there is one
  summary         the `requirements` block of the step-start context and of
                  `acs.py requirements show`

requirements.md is GENERATED: nothing edits it by hand, and every write path
regenerates it from sources.json, the tickets and the refined record.
"""

import hashlib
import os
import re
import shlex
import shutil

from ._common import GateError, now_iso, read_json, write_json, write_text
from . import doc_layout
from .doc_layout import (architecture_dir, development_dir, feature_dir,  # noqa: F401
                         feature_analysis_path, prd_dir)
from .repo import find_ticket_partition
from .run import load_run, subject_dir

SOURCES_FILENAME = "sources.json"
REQUIREMENTS_FILENAME = "requirements.md"
REFINED_FILENAME = "requirements-refined.json"
SOURCE_KINDS = ("ticket", "document", "prompt")
PHASES = ("discovery", "development")
#: Documents inlined into requirements.md; any other type is cited by the path
#: of its run copy (or its repo path) for the model to Read.
INLINE_EXTENSIONS = (".md", ".markdown", ".mdx", ".txt", ".text", ".rst", ".adoc")
INLINE_MAX_BYTES = 256 * 1024
REFINE_KEYS = ("acceptance_criteria", "features", "feature", "phase")
#: Keys a refined record written before ADR-0139 may still hold: refused on
#: write, ignored on read -- a ticket carries no design flag any more.
RETIRED_REFINE_KEYS = ("needs_design",)
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_GENERATED_LINE = re.compile(r'^generated_at: .*$', re.M)


# ---------------------------------------------------------------------------
# Parsing an invocation
# ---------------------------------------------------------------------------

def _ticket_re(ctx):
    prefix = ((ctx or {}).get("settings") or {}).get("ticket_prefix")
    return re.compile(r"^%s-\d+$" % (re.escape(prefix) if prefix else "[A-Z][A-Z0-9]*"))


def _root(ctx):
    return (ctx or {}).get("checkout_root") or (ctx or {}).get("cwd") or os.getcwd()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _document(token, ctx):
    """The document source a token names, or None when it names no file."""
    root = _root(ctx)
    expanded = os.path.expanduser(token)
    candidates = [expanded] if os.path.isabs(expanded) else [os.path.join(root, expanded)]
    cwd = (ctx or {}).get("cwd")
    if not os.path.isabs(expanded) and cwd and os.path.realpath(cwd) != os.path.realpath(root):
        candidates.append(os.path.join(cwd, expanded))
    for candidate in candidates:
        if os.path.isfile(candidate):
            absolute = os.path.abspath(candidate)
            inside = _inside(absolute, root)
            path = (os.path.relpath(os.path.realpath(absolute), os.path.realpath(root))
                    .replace(os.sep, "/") if inside else token)
            return {"kind": "document", "path": path, "abs": absolute,
                    "sha256": sha256_file(absolute), "inside_repo": inside}
    return None


def _tokens(text):
    try:
        return shlex.split(text)
    except ValueError:  # an unbalanced quote: an apostrophe in a prompt
        return text.split()


#: A skill's own options that take a value (`--base <ref>` for review-code,
#: `--suite <name>` for run-e2e-tests, `--plan <file>` for code, ...): the
#: option and its value are never requirements. Any other `--flag` (or
#: `--flag=value`) is dropped alone.
OPTIONS_WITH_VALUE = frozenset({"--base", "--suite", "--plan", "--run", "--pr", "--ticket",
                                "--title", "--type", "--threshold", "--mode", "--areas",
                                "--since", "--iteration"})


def _requirement_tokens(tokens):
    """(tokens, stripped): the tokens left once a skill's options are removed."""
    out, skip, stripped = [], False, False
    for token in tokens:
        if skip:
            skip = False
            continue
        if token.startswith("--") and len(token) > 2:
            stripped = True
            skip = token in OPTIONS_WITH_VALUE
            continue
        out.append(token)
    return out, stripped


def parse_sources(text, ctx):
    """[{kind: ticket|document|prompt, ...}] for one invocation's argument text.

    Each token is a ticket when it is `<PREFIX>-<n>`, a document when it names
    an existing FILE (repo-relative, absolute or `~`-expanded), and otherwise
    part of the ONE prompt the rest is joined into, in order. A text with no
    ticket and no document is a prompt verbatim, quotes and all -- the exact
    subject a pure prompt invocation always had. A skill's own `--options`
    (OPTIONS_WITH_VALUE, with their values) are never requirements."""
    text = (text or "").strip()
    if not text:
        return []
    ticket_re = _ticket_re(ctx)
    sources, words, seen = [], [], set()
    tokens, stripped = _requirement_tokens(_tokens(text))
    for token in tokens:
        if ticket_re.match(token):
            if ("ticket", token) not in seen:
                seen.add(("ticket", token))
                sources.append({"kind": "ticket", "ticket_id": token})
            continue
        document = _document(token, ctx) if token else None
        if document is not None:
            if ("document", document["sha256"]) not in seen:
                seen.add(("document", document["sha256"]))
                sources.append(document)
            continue
        words.append(token)
    if words:
        prompt = text if not (sources or stripped) else " ".join(words)
        sources.append({"kind": "prompt", "text": prompt})
    return sources


def primary_subject(sources):
    """The run's ONE subject (ticket > document > prompt), or None for no
    sources. A mixed invocation keeps the whole list as `sources` on it."""
    sources = list(sources or ())
    by_kind = {kind: [s for s in sources if s.get("kind") == kind] for kind in SOURCE_KINDS}
    if by_kind["ticket"]:
        subject = {"kind": "ticket", "ticket_id": by_kind["ticket"][0]["ticket_id"]}
    elif by_kind["document"]:
        doc = by_kind["document"][0]
        subject = {"kind": "document", "path": doc["path"], "sha256": doc.get("sha256")}
    elif by_kind["prompt"]:
        subject = {"kind": "prompt", "text": by_kind["prompt"][0]["text"]}
    else:
        return None
    if len(sources) > 1:
        subject["sources"] = [dict(s) for s in sources]
    return subject


def subject_from_text(text, ctx):
    """parse_sources + primary_subject: what `gates.subject_from_payload` and
    `acs_state_commands._subject_from_args` delegate to."""
    subject = primary_subject(parse_sources(text, ctx))
    if subject is None and (text or "").strip():
        # Only a skill's own options (`/acs:review-code --base origin/main`):
        # still a subject, as it always was, so the run opens.
        subject = {"kind": "prompt", "text": text.strip()}
    return subject


def sources_of(subject):
    """The source list a run's subject records: `subject.sources` for a mixed
    invocation, else the one source the subject itself is."""
    subject = subject or {}
    if isinstance(subject.get("sources"), list) and subject["sources"]:
        return [dict(s) for s in subject["sources"] if isinstance(s, dict)]
    kind = subject.get("kind")
    if kind == "ticket" and subject.get("ticket_id"):
        return [{"kind": "ticket", "ticket_id": subject["ticket_id"]}]
    if kind == "document" and subject.get("path"):
        return [{"kind": "document", "path": subject["path"], "sha256": subject.get("sha256")}]
    if kind == "prompt" and subject.get("text"):
        return [{"kind": "prompt", "text": subject["text"]}]
    return []


def ticket_ids(sources):
    return [s["ticket_id"] for s in sources or () if s.get("kind") == "ticket"]


def check_tickets(ctx, sources, skill=None):
    """Refuse a ticket source that names no ticket: a ticket id is a REFERENCE,
    and requirements read from a reference to nothing cannot be read."""
    for ticket_id in ticket_ids(sources):
        tdir, _archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
        if not os.path.isdir(tdir):
            raise GateError(
                "no ticket %s in this repo's workspace — run /acs:create-ticket "
                "to make one, or give /acs:%s a prompt or a document instead."
                % (ticket_id, skill or "<skill>"))


# ---------------------------------------------------------------------------
# The run's record: sources.json, the copies, requirements.md
# ---------------------------------------------------------------------------

def sources_path(rdir):
    return os.path.join(subject_dir(rdir), SOURCES_FILENAME)


def requirements_path(rdir):
    return os.path.join(rdir, REQUIREMENTS_FILENAME)


def refined_path(rdir):
    return os.path.join(rdir, REFINED_FILENAME)


def load_sources(rdir):
    doc = read_json(sources_path(rdir))
    return [e for e in doc if isinstance(e, dict)] if isinstance(doc, list) else []


def load_refined(rdir):
    """The run's refined record; a retired key an older run wrote
    (RETIRED_REFINE_KEYS) is dropped, so no reader can act on it."""
    doc = read_json(refined_path(rdir))
    if not isinstance(doc, dict):
        return {}
    return {k: v for k, v in doc.items() if k not in RETIRED_REFINE_KEYS}


def _entry(rdir, ctx, source, index):
    """The sources.json entry for a parsed source: {kind, ref, sha256, copy}."""
    kind = source.get("kind")
    entry = {"kind": kind, "ref": None, "sha256": None, "copy": None, "added_at": now_iso()}
    if kind == "ticket":
        entry["ref"] = source["ticket_id"]
    elif kind == "prompt":
        entry["ref"] = source["text"]
        entry["sha256"] = _sha_text(source["text"])
    elif kind == "document":
        root = _root(ctx)
        absolute = source.get("abs") or os.path.expanduser(source["path"])
        if not os.path.isabs(absolute):
            absolute = os.path.join(root, absolute)
        inside = source.get("inside_repo")
        if inside is None:
            inside = _inside(absolute, root)
        entry["ref"] = source["path"]
        entry["sha256"] = source.get("sha256") or (
            sha256_file(absolute) if os.path.isfile(absolute) else None)
        if not inside:
            if not os.path.isfile(absolute):
                raise GateError("cannot copy %s into the run: no such file" % source["path"])
            copy = os.path.join(subject_dir(rdir), "%d-%s" % (index, os.path.basename(absolute)))
            os.makedirs(os.path.dirname(copy), exist_ok=True)
            shutil.copyfile(absolute, copy)
            entry["copy"] = copy
    return entry


def _same(entry, source):
    kind = source.get("kind")
    if entry.get("kind") != kind:
        return False
    if kind == "ticket":
        return entry.get("ref") == source.get("ticket_id")
    if kind == "prompt":
        return entry.get("sha256") == _sha_text(source.get("text"))
    return (entry.get("sha256") and entry.get("sha256") == source.get("sha256")) \
        or (not entry.get("copy") and entry.get("ref") == source.get("path"))


def _merge(rdir, ctx, recorded, sources):
    """Append every source not already recorded. Returns the new entries."""
    added = []
    for source in sources or ():
        if source.get("kind") not in SOURCE_KINDS:
            continue
        match = next((e for e in recorded if _same(e, source)), None)
        if match is not None:
            if (source.get("kind") == "document" and source.get("sha256")
                    and match.get("sha256") != source["sha256"] and not match.get("copy")):
                # The same repo document, edited since: one entry, the new digest.
                match["sha256"] = source["sha256"]
                match["updated_at"] = now_iso()
                added.append(match)
            continue
        entry = _entry(rdir, ctx, source, len(recorded) + 1)
        recorded.append(entry)
        added.append(entry)
    return added


def materialise(rdir, ctx, sources=None):
    """Record the run's sources and (re)generate requirements.md. Idempotent:
    a call that adds nothing rewrites nothing. `sources` defaults to the run's
    own subject; a later invocation's new ones go through `add_sources`."""
    doc = load_run(rdir) or {}
    if sources is None:
        sources = sources_of(doc.get("subject"))
    recorded = load_sources(rdir)
    added = _merge(rdir, ctx, recorded, sources)
    if added or not os.path.isfile(sources_path(rdir)):
        write_json(sources_path(rdir), recorded)
    _write_requirements(rdir, ctx, doc, recorded)
    return {"path": requirements_path(rdir), "sources": recorded, "added": added}


def add_sources(rdir, ctx, text, skill=None):
    """A later invocation's sources, appended to the run's record (deduplicated
    by ticket id, digest or prompt text) and the file regenerated. Recorded,
    never silently replaced: an unknown ticket is refused."""
    sources = parse_sources(text, ctx)
    check_tickets(ctx, sources, skill)
    if not os.path.isfile(sources_path(rdir)):
        materialise(rdir, ctx)
    return materialise(rdir, ctx, sources)


# ---------------------------------------------------------------------------
# Tickets as a source
# ---------------------------------------------------------------------------

def _load_ticket(ctx, ticket_id):
    from .tickets import load_ticket
    tdir, _archived = find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    ticket = load_ticket(tdir) if os.path.isdir(tdir) else None
    return tdir, (ticket if isinstance(ticket, dict) else None)


def _tickets(ctx, recorded):
    out = []
    for entry in recorded:
        if entry.get("kind") == "ticket":
            tdir, ticket = _load_ticket(ctx, entry["ref"])
            out.append((entry["ref"], tdir, ticket))
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _fence(text):
    longest = max([len(m) for m in re.findall(r"`+", text or "")] + [2])
    fence = "`" * (longest + 1)
    return [fence + "text", (text or "").rstrip("\n"), fence]


def _criteria_lines(items, start=1):
    lines = []
    for number, item in enumerate(items, start):
        parts = str(item).splitlines() or [""]
        lines.append("- **AC-%d** %s" % (number, parts[0]))
        lines.extend("  " + part for part in parts[1:])
    return lines


def _document_section(entry, ctx):
    ref = entry.get("ref") or "?"
    lines = ["### %s" % ref, ""]
    path = entry.get("copy") or os.path.join(_root(ctx), ref)
    readable = os.path.isfile(path)
    if readable and path.lower().endswith(INLINE_EXTENSIONS) \
            and os.path.getsize(path) <= INLINE_MAX_BYTES:
        try:
            with open(path, encoding="utf-8") as fh:
                return lines + _fence(fh.read()) + [""]
        except (OSError, UnicodeDecodeError):
            pass
    where = "the run copy `%s`" % path if entry.get("copy") else "`%s`" % ref
    if not readable:
        return lines + ["_Not found any more at %s (sha256 %s when recorded)._"
                        % (where, (entry.get("sha256") or "?")[:12]), ""]
    return lines + ["Not inlined (%s): Read %s." % (
        os.path.splitext(path)[1] or "no extension", where), ""]


def render(rdir, ctx, doc, recorded, refined=None):
    """requirements.md for the run, as text."""
    from .artifacts import render_front_matter
    refined = load_refined(rdir) if refined is None else refined
    front = {"run_id": (doc or {}).get("run_id") or os.path.basename(rdir),
             "generated_at": now_iso(),
             "sources": [{"kind": e.get("kind"),
                          "ref": e.get("ref") if e.get("kind") != "prompt" else "prompt",
                          "sha256": e.get("sha256"), "copy": e.get("copy")}
                         for e in recorded]}
    lines = ["---"] + render_front_matter(front) + ["---", "",
             "# Requirements — %s" % front["run_id"], "",
             "_Generated by acs from the sources above; never edited by hand "
             "(`acs.py requirements add|refine` regenerate it)._", ""]
    number = 1
    for ticket_id, _tdir, ticket in _tickets(ctx, recorded):
        lines += ["## Ticket %s" % ticket_id, ""]
        if ticket is None:
            lines += ["_No readable ticket for %s._" % ticket_id, ""]
            continue
        features = ticket.get("features") or []
        lines += ["- title: %s" % (ticket.get("title") or ""),
                  "- type: %s" % (ticket.get("type") or ""),
                  "- features: %s" % (", ".join(features) if features else "none recorded"),
                  "", "### Description", ""]
        lines += (_fence(ticket["description"]) if ticket.get("description")
                  else ["_None._"]) + ["", "### Acceptance criteria", ""]
        criteria = ticket.get("acceptance_criteria") or []
        lines += (_criteria_lines(criteria, number) if criteria else ["_None._"]) + [""]
        number += len(criteria)
    prompts = [e for e in recorded if e.get("kind") == "prompt"]
    if prompts:
        lines += ["## Prompt", ""]
        for entry in prompts:
            lines += _fence(entry.get("ref")) + [""]
    documents = [e for e in recorded if e.get("kind") == "document"]
    if documents:
        lines += ["## Documents", ""]
        for entry in documents:
            lines += _document_section(entry, ctx)
    from .doc_links import default_branch
    lines += render_references(run_references(ctx, rdir, doc, recorded, refined),
                               default_branch(ctx.get("checkout_root")))
    if refined:
        lines += ["## Refined", "",
                  "_Recorded by `acs.py requirements refine` at %s._"
                  % (refined.get("refined_at") or "?"), ""]
        for key in ("feature", "features", "phase"):
            if key in refined:
                value = refined[key]
                if isinstance(value, list):
                    value = ", ".join(value) or "none"
                lines.append("- %s: %s" % (key, value))
        if refined.get("acceptance_criteria"):
            lines += ["", "### Acceptance criteria", ""]
            lines += _criteria_lines(refined["acceptance_criteria"])
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def run_references(ctx, rdir, doc=None, recorded=None, refined=None):
    """The documents this run's subject has in the standard layout (ADR-0140):
    each ticket source's references (`doc_links.references_for_ticket`), else
    -- a ticketless run -- its refined features' (`references_for_features`),
    else []. Local only: no fetch. The Start context's `references` and
    requirements.md's `## References` both come from here, so they cannot
    disagree."""
    from . import doc_links
    doc = doc if doc is not None else (load_run(rdir) or {})
    if recorded is None:
        recorded = load_sources(rdir) or [dict(s, ref=s.get("ticket_id"))
                                          for s in sources_of(doc.get("subject"))]
    refs = []
    try:
        tickets = [t for _id, _d, t in _tickets(ctx, recorded) if t]
        for ticket in tickets:
            refs += doc_links.references_for_ticket(ctx, ticket)
        if not tickets:
            refined = load_refined(rdir) if refined is None else refined
            features = list(refined.get("features") or [])
            if refined.get("feature") and refined["feature"] not in features:
                features.insert(0, refined["feature"])
            if features:
                refs = doc_links.references_for_features(ctx, features)
    except (GateError, OSError):
        return []
    return doc_links.dedupe(refs)


def render_references(refs, default_branch=None):
    """requirements.md's `## References` lines: title, kind, path, and the
    link when the document is on the default branch."""
    lines = ["## References", ""]
    if not refs:
        return lines + ["_No documents for this run's features in the repo yet._", ""]
    for ref in refs:
        title = ref.get("title") or ref.get("path")
        where = "`%s`" % ref.get("path")
        if ref.get("url"):
            lines.append("- [%s](%s) — %s — %s" % (title, ref["url"], ref.get("kind"), where))
        elif ref.get("published"):
            lines.append("- %s — %s — %s" % (title, ref.get("kind"), where))
        else:
            lines.append("- %s — %s — %s — pending: not on %s yet" % (
                title, ref.get("kind"), where,
                "`%s`" % default_branch if default_branch else "the default branch"))
    return lines + [""]


def _write_requirements(rdir, ctx, doc, recorded):
    text = render(rdir, ctx, doc, recorded)
    path = requirements_path(rdir)
    try:
        with open(path, encoding="utf-8") as fh:
            current = fh.read()
    except (OSError, UnicodeDecodeError):
        current = None
    if current is not None and \
            _GENERATED_LINE.sub("", current) == _GENERATED_LINE.sub("", text):
        return path
    write_text(path, text)
    return path


# ---------------------------------------------------------------------------
# Refinement -- analyze-requirements' write-back
# ---------------------------------------------------------------------------

def _validate_refined(data):
    if not isinstance(data, dict):
        raise GateError("refine takes a JSON object")
    retired = sorted(k for k in data if k in RETIRED_REFINE_KEYS)
    if retired:
        raise GateError("refine no longer takes %s: tickets and requirements carry no "
                        "design flag (ADR-0139) -- run /acs:create-tech-design when you "
                        "want a design" % ", ".join(retired))
    unknown = sorted(k for k in data if k not in REFINE_KEYS)
    if unknown:
        raise GateError("refine does not take %s (it takes %s)"
                        % (", ".join(unknown), ", ".join(REFINE_KEYS)))
    criteria = data.get("acceptance_criteria")
    if "acceptance_criteria" in data and not (
            isinstance(criteria, list)
            and all(isinstance(c, str) and c.strip() for c in criteria)):
        raise GateError("acceptance_criteria must be a list of non-empty strings")
    features = data.get("features")
    if "features" in data and not (isinstance(features, list)
                                   and all(isinstance(f, str) and _SLUG_RE.match(f)
                                           for f in features)):
        raise GateError("features must be a list of PRD feature slugs (`acs.py slug`)")
    if "feature" in data and not (isinstance(data["feature"], str)
                                  and _SLUG_RE.match(data["feature"])):
        raise GateError("feature must be one PRD feature slug (`acs.py slug`), got %r"
                        % (data["feature"],))
    if "phase" in data and data["phase"] not in PHASES:
        raise GateError("phase must be one of %s" % ", ".join(PHASES))


def refine(rdir, ctx, data):
    """Store analyze-requirements' refined requirements and regenerate the
    `## Refined` section; when the run has a ticket, patch it too (the same
    merge `acs.py ticket save` makes). Returns a report."""
    from .tickets import save_ticket, update_index
    _validate_refined(data)
    refined = load_refined(rdir)
    refined.update(data)
    refined["refined_at"] = now_iso()
    write_json(refined_path(rdir), refined)
    doc = load_run(rdir) or {}
    if not os.path.isfile(sources_path(rdir)):
        materialise(rdir, ctx)
    else:
        _write_requirements(rdir, ctx, doc, load_sources(rdir))
    patched, fields = None, []
    ticket_id = (doc.get("subject") or {}).get("ticket_id")
    if ticket_id:
        tdir, ticket = _load_ticket(ctx, ticket_id)
        if ticket is not None:
            patch = {k: data[k] for k in ("acceptance_criteria", "features")
                     if k in data}
            if data.get("feature"):
                features = list(patch.get("features", ticket.get("features") or []))
                if data["feature"] not in features:
                    patch["features"] = [data["feature"]] + features
            if patch:
                updated = dict(ticket)
                updated.update(patch)
                save_ticket(tdir, updated)
                update_index(ctx["workspace"], ctx["repo_id"], updated)
                patched, fields = ticket_id, sorted(patch)
    return {"refined": refined, "ticket_patched": patched, "ticket_fields": fields,
            "path": requirements_path(rdir)}


# ---------------------------------------------------------------------------
# Reading -- the `requirements` context block
# ---------------------------------------------------------------------------

def run_feature(ctx, rdir, doc=None, refined=None):
    """The PRD feature this run's documents are filed under, or None: the
    refined `feature`, else the refined `features`' first, else the first
    feature its ticket(s) trace to."""
    refined = load_refined(rdir) if refined is None else refined
    if refined.get("feature"):
        return refined["feature"]
    if refined.get("features"):
        return refined["features"][0]
    doc = doc if doc is not None else (load_run(rdir) or {})
    for ticket_id in ticket_ids(sources_of(doc.get("subject"))):
        _tdir, ticket = _load_ticket(ctx, ticket_id)
        features = (ticket or {}).get("features") or []
        if features:
            return features[0]
    return None


def run_phase(doc, refined=None, rdir=None):
    """`development` for a run being delivered -- it has a ticket, or
    /acs:ship drives it (`driver: ship`) -- else `discovery`. A refined
    `phase` overrides both."""
    refined = (load_refined(rdir) if rdir else {}) if refined is None else refined
    if refined.get("phase") in PHASES:
        return refined["phase"]
    doc = doc or {}
    if ticket_ids(sources_of(doc.get("subject"))) or doc.get("driver") == "ship":
        return "development"
    return "discovery"


def summary(rdir, ctx, doc=None):
    """The `requirements` block: {path, sources, acceptance_criteria, features,
    feature, phase, feature_analysis, refined}."""
    doc = doc if doc is not None else (load_run(rdir) or {})
    recorded = load_sources(rdir) or [dict(s, ref=s.get("ticket_id") or s.get("path")
                                            or s.get("text"))
                                      for s in sources_of(doc.get("subject"))]
    refined = load_refined(rdir)
    tickets = [(tid, t) for tid, _d, t in _tickets(ctx, recorded)]
    criteria, features = [], []
    for ticket_id, ticket in tickets:
        for item in (ticket or {}).get("acceptance_criteria") or []:
            criteria.append({"id": "AC-%d" % (len(criteria) + 1), "text": item,
                             "source": ticket_id})
        for feature in (ticket or {}).get("features") or []:
            if feature not in features:
                features.append(feature)
    if refined.get("acceptance_criteria"):
        criteria = [{"id": "AC-%d" % n, "text": text, "source": "refined"}
                    for n, text in enumerate(refined["acceptance_criteria"], 1)]
    if "features" in refined:
        features = list(refined["features"])
    if refined.get("feature") and refined["feature"] not in features:
        features.insert(0, refined["feature"])
    feature = run_feature(ctx, rdir, doc, refined)
    root = ctx.get("checkout_root")
    living = (doc_layout.existing_feature_analysis(root, feature, ctx.get("settings"))
              if feature and root else None)
    return {"path": requirements_path(rdir), "sources": recorded,
            "acceptance_criteria": criteria, "features": features, "feature": feature,
            "phase": run_phase(doc, refined),
            "feature_analysis": living,
            "refined": bool(refined)}


__all__ = ["parse_sources", "primary_subject", "subject_from_text", "sources_of",
           "check_tickets", "materialise", "add_sources", "refine", "summary",
           "run_references", "render_references",
           "run_feature", "run_phase", "prd_dir", "architecture_dir", "development_dir",
           "feature_dir", "feature_analysis_path", "doc_layout"]
