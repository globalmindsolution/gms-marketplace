"""acs_docs_commands — `acs.py docs <verb>`: where a document goes, and the
user's saved answers that decide it (ADR-0132).

    acs.py docs where [--doc <name>] [--run R]
    acs.py docs decide [--share yes|no --scope user|team|run]
                       [--location KIND=PATH ...] [--doc <name>] [--run R]

`<name>` is a per-run document (analysis.md, plan.md, test-cases.md,
design.md, api-contract.md) or a living one (living:prd, living:architecture).
`where` is read-only: the destination, the saved share choice and its scope,
how the folder was resolved (setting | discovered | default), and `needs` --
the questions still open (`share`, `location`). Every writer runs it before
its first write and asks what `needs` names in its one grouped ask. Without
`--doc` it prints every document's `where`, the share choice and the three
folders' {path, source} -- /acs:setup's view.

`decide` records the answers: `--share` into `.acs/settings.local.json`
(scope `user`, this machine; made gitignored through `.git/info/exclude` when
nothing ignores it yet) or `.acs/settings.json` (scope `team`), and
`--scope run` records it for this run only (`<run>/docs-choice.json`, nothing
saved -- the headless answer, which takes precedence for that run), and
`--location KIND=PATH` (KIND: prd, architecture, development) as
`docs.<kind>_dir` in `.acs/settings.json`. Each file is merged -- only the keys
set here change; a missing file is created. It prints the new `where` (for
`--doc`, else for every document) and what it wrote.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402
from acs_cli import context_or_die, die, emit, run_or_die  # noqa: E402
from acs_lib import doc_layout, doc_share  # noqa: E402
from acs_lib.settings import docs_path_problem  # noqa: E402

LOCATION_KINDS = doc_layout.KINDS


def _run(command, explicit):
    """(ctx, rdir or None): `--run` names one; else this checkout's current
    run when it has one; else no run (living documents and the share choice
    are answered without one)."""
    if explicit:
        _run_id, rdir, ctx = run_or_die(command, explicit)
        return ctx, rdir
    ctx = context_or_die(command)
    run_id = lib.current_run_id(ctx)
    if run_id:
        rdir = lib.run_dir(lib.repo_dir(ctx["workspace"], ctx["repo_id"]), run_id)
        if lib.load_run(rdir) is not None:
            return ctx, rdir
    return ctx, None


def _where(command, ctx, rdir, doc):
    try:
        return doc_share.where(ctx, doc, rdir)
    except lib.GateError as exc:
        die(command, str(exc))


def _overview(command, ctx, rdir):
    try:
        return doc_share.overview(ctx, rdir)
    except lib.GateError as exc:
        die(command, str(exc))


def cmd_docs_where(args):
    ctx, rdir = _run("docs where", args.run)
    if args.doc:
        emit(dict(_where("docs where", ctx, rdir, args.doc), ok=True))
    else:
        emit(dict(_overview("docs where", ctx, rdir), ok=True))


def _parse_locations(values):
    """{kind: path} from `KIND=PATH` (KIND may also be spelled `<kind>_dir`)."""
    out = {}
    for raw in values or ():
        kind, sep, path = raw.partition("=")
        kind = kind.strip()
        if kind.endswith("_dir"):
            kind = kind[:-4]
        if not sep or kind not in LOCATION_KINDS:
            die("docs decide", "--location takes KIND=PATH with KIND one of %s; got %r"
                % (", ".join(LOCATION_KINDS), raw))
        problem = docs_path_problem(path)
        if problem:
            die("docs decide", "--location %s: the folder %s" % (kind, problem))
        out[kind] = path.replace("\\", "/").strip().strip("/") or "."
    return out


def _ensure_local_ignored(local_file):
    """Keep `.acs/settings.local.json` out of git: nothing to do when a rule
    already ignores it, else the untracked `.git/info/exclude` layer (the repo's
    own .gitignore is the user's, and /acs:setup's to change)."""
    import setup_wizard
    root = os.path.dirname(os.path.dirname(local_file))
    rel = doc_share.LOCAL_SETTINGS.replace(os.sep, "/")
    if setup_wizard.is_ignored(rel, root):
        return "already ignored"
    common = setup_wizard._git(["rev-parse", "--git-common-dir"], root) or ".git"
    if not os.path.isabs(common):
        common = os.path.join(root, common)
    setup_wizard.append_line_once(os.path.join(common, "info", "exclude"), rel)
    return ".git/info/exclude"


def _write(path, updates):
    import setup_wizard
    try:
        changed, _merged = setup_wizard.merge_json_file(path, updates)
    except setup_wizard.UnreadableSettings:
        die("docs decide", "%s exists but is not readable JSON -- fix it by hand; "
                           "nothing was written" % path)
    return changed


def cmd_docs_decide(args):
    if (args.share is None) != (args.scope is None):
        die("docs decide", "--share and --scope go together: --share yes|no --scope "
                           "user|team|run (user: this machine, .acs/settings.local.json; "
                           "team: .acs/settings.json; run: this run only, nothing saved)")
    locations = _parse_locations(args.location)
    if args.share is None and not locations:
        die("docs decide", "nothing to record: pass --share yes|no --scope user|team|run "
                           "and/or --location KIND=PATH")
    if args.doc and args.doc not in doc_share.DOC_CHOICES:
        die("docs decide", "unknown document %r (one of %s)"
            % (args.doc, ", ".join(doc_share.DOC_CHOICES)))
    ctx, rdir = _run("docs decide", args.run)
    if args.scope == "run" and rdir is None:
        die("docs decide", "--scope run records the choice in a run, and there is none: "
                           "name it with --run, or start one first")
    try:
        files = doc_share.scope_files(ctx["checkout_root"])
    except lib.GateError as exc:
        die("docs decide", str(exc))
    plan = {}  # file -> (scope, {docs key: value})
    written = []
    if args.scope == "run":
        written.append({"scope": "run", "changed": True, "keys": ["share_run_documents"],
                        "file": doc_share.record_run_choice(rdir, args.share == "yes")})
    elif args.share is not None:
        plan.setdefault(files[args.scope], (args.scope, {}))[1][
            "share_run_documents"] = args.share == "yes"
    for kind, path in sorted(locations.items()):
        plan.setdefault(files["team"], ("team", {}))[1][doc_layout.KIND_SETTINGS[kind]] = path
    for path, (scope, docs) in plan.items():
        entry = {"scope": scope, "file": path, "changed": _write(path, {"docs": docs}),
                 "keys": sorted("docs.%s" % key for key in docs)}
        if scope == "user":
            entry["ignored_via"] = _ensure_local_ignored(path)
        written.append(entry)
    ctx = context_or_die("docs decide")  # re-read the cascade the files now form
    warnings = []
    if args.share is not None and args.scope != "run":
        value, _scope, source = doc_share.share_source(ctx["checkout_root"])
        if value != (args.share == "yes"):
            warnings.append("the saved answer is overridden by %s, which sets "
                            "docs.share_run_documents to %s and takes precedence"
                            % (source, str(value).lower()))
    out = {"ok": True, "written": written, "warnings": warnings}
    if args.doc:
        out.update(_where("docs decide", ctx, rdir, args.doc))
    else:
        out.update(_overview("docs decide", ctx, rdir))
    emit(out)


def add_parser(group):
    """Register `docs` and its verbs on acs.py's top-level subparsers."""
    docs = group("docs", help="where a document goes: shared or local, and its "
                              "folder (ADR-0132)")
    sub = docs.add_subparsers(dest="cmd")

    where = sub.add_parser("where", help="read-only: a document's destination and "
                                         "the questions still open")
    where.add_argument("--doc", choices=doc_share.DOC_CHOICES,
                       help="one document; without it, every document plus the share "
                            "choice and the three folders")
    where.add_argument("--run", help="a run other than this checkout's current one")
    where.set_defaults(func=cmd_docs_where)

    decide = sub.add_parser("decide", help="record the user's answers in the settings")
    decide.add_argument("--share", choices=("yes", "no"),
                        help="share run documents in the repo (yes) or keep them local (no)")
    decide.add_argument("--scope", choices=doc_share.SCOPES,
                        help="user: this machine (.acs/settings.local.json); "
                             "team: .acs/settings.json; run: this run only, nothing "
                             "saved (when the user cannot be asked)")
    decide.add_argument("--location", action="append", metavar="KIND=PATH",
                        help="a docs folder, KIND one of %s; saved as docs.<kind>_dir "
                             "in .acs/settings.json (repeatable)" % ", ".join(LOCATION_KINDS))
    decide.add_argument("--doc", help="print this document's new `where`")
    decide.add_argument("--run", help="a run other than this checkout's current one")
    decide.set_defaults(func=cmd_docs_decide)
    return docs
