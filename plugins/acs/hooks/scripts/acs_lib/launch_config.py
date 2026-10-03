"""acs_lib.launch_config — `.claude/launch.json`, Claude Code's preview-server config.

The Claude Code Desktop app (its Code tab and Browser pane) reads
`<project>/.claude/launch.json` to start, stop and preview a project's dev
servers (https://code.claude.com/docs/en/desktop, "Configure preview servers").
Claude writes one on its own when it detects a dev server; the file is meant to
be committed. /acs:setup offers to write a reviewed one so a team shares the
same servers, and never touches a configuration the repo already has.

Schema, as documented: a top-level `version` (string), an optional `autoVerify`
(bool, default true) and a `configurations` list. Each configuration has a
unique `name` and either `runtimeExecutable` (+ `runtimeArgs`) or `program`
(+ `args`), plus optional `port` (default 3000), `cwd`, `env`, `autoPort` and
`url`. The file may carry comments; this module reads such a file but refuses
to rewrite it, since rewriting would drop them.

Stdlib only; nothing here runs a server.
"""

import json
import os
import re

PATH_PARTS = (".claude", "launch.json")
VERSION = "0.0.1"

#: Configuration keys the docs define. Others are kept on read but refused on write.
CONFIG_KEYS = {"name", "runtimeExecutable", "runtimeArgs", "port", "cwd", "env",
               "autoPort", "program", "args", "url"}

#: Env names that look like credentials: the file is committed, so a value here
#: is published with the repo.
_SECRETISH = re.compile(r"(SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|PRIVATE)", re.I)

#: script text fragment -> the port that tool listens on by default
_PORT_HINTS = (("vite", 5173), ("astro", 4321), ("next", 3000), ("nuxt", 3000),
               ("react-scripts", 3000), ("webpack", 8080), ("ng serve", 4200))


def path(root):
    return os.path.join(root, *PATH_PARTS)


def strip_comments(text):
    """`text` with // and /* */ comments removed, string contents untouched."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
        elif ch == '"':
            in_str = True
            out.append(ch)
            i += 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def read(root):
    """{"exists", "doc", "has_comments", "error"} for the repo's launch.json."""
    p = path(root)
    if not os.path.isfile(p):
        return {"exists": False, "doc": None, "has_comments": False, "error": None}
    try:
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return {"exists": True, "doc": None, "has_comments": False, "error": str(exc)}
    stripped = strip_comments(text)
    try:
        doc = json.loads(stripped)
    except ValueError as exc:
        return {"exists": True, "doc": None, "has_comments": stripped != text,
                "error": "not valid JSON: %s" % exc}
    if not isinstance(doc, dict):
        return {"exists": True, "doc": None, "has_comments": stripped != text,
                "error": "the top level is not an object"}
    return {"exists": True, "doc": doc, "has_comments": stripped != text, "error": None}


def _strings(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def validate_configuration(cfg, where="configuration"):
    """Errors in one configuration; [] when it matches the documented schema."""
    if not isinstance(cfg, dict):
        return ["%s must be an object" % where]
    errors = []
    name = cfg.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("%s needs a non-empty `name`" % where)
    unknown = sorted(set(cfg) - CONFIG_KEYS)
    if unknown:
        errors.append("%s has keys launch.json does not define: %s" % (where, ", ".join(unknown)))
    has_exe = isinstance(cfg.get("runtimeExecutable"), str) and cfg["runtimeExecutable"].strip()
    has_program = isinstance(cfg.get("program"), str) and cfg["program"].strip()
    if not (has_exe or has_program):
        errors.append("%s needs `runtimeExecutable` (with `runtimeArgs`) or `program`" % where)
    for key in ("runtimeArgs", "args"):
        if key in cfg and not _strings(cfg[key]):
            errors.append("%s.%s must be a list of strings" % (where, key))
    port = cfg.get("port")
    if port is not None and (isinstance(port, bool) or not isinstance(port, int)
                             or not 0 < port < 65536):
        errors.append("%s.port must be a whole number from 1 to 65535" % where)
    if "cwd" in cfg and not isinstance(cfg["cwd"], str):
        errors.append("%s.cwd must be a string" % where)
    if "autoPort" in cfg and not isinstance(cfg["autoPort"], bool):
        errors.append("%s.autoPort must be true or false" % where)
    env = cfg.get("env")
    if env is not None and (not isinstance(env, dict)
                            or not all(isinstance(v, str) for v in env.values())):
        errors.append("%s.env must be an object of string values" % where)
    url = cfg.get("url")
    if url is not None and (not isinstance(url, str)
                            or not re.match(r"^https?://[^/@]+(/|$)", url)):
        errors.append("%s.url must be an http(s) address with no user name or password" % where)
    return errors


def validate(doc):
    """Errors in a whole launch.json document; [] when it is usable."""
    if not isinstance(doc, dict):
        return ["launch.json must be an object"]
    errors = []
    if "version" in doc and not isinstance(doc["version"], str):
        errors.append("`version` must be a string")
    if "autoVerify" in doc and not isinstance(doc["autoVerify"], bool):
        errors.append("`autoVerify` must be true or false")
    configs = doc.get("configurations")
    if not isinstance(configs, list):
        return errors + ["`configurations` must be a list"]
    seen = set()
    for i, cfg in enumerate(configs):
        errors.extend(validate_configuration(cfg, "configurations[%d]" % i))
        name = cfg.get("name") if isinstance(cfg, dict) else None
        if isinstance(name, str):
            if name in seen:
                errors.append("configuration name %r is used twice" % name)
            seen.add(name)
    return errors


def secret_warnings(configs):
    """Env names in `configs` that look like credentials."""
    out = []
    for cfg in configs or ():
        for key in ((cfg or {}).get("env") or {}):
            if _SECRETISH.search(key):
                out.append("%s.env.%s looks like a secret; launch.json is committed"
                           % (cfg.get("name"), key))
    return out


def _package_manager(root):
    for lockfile, manager in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
                              ("bun.lockb", "bun"), ("bun.lock", "bun")):
        if os.path.isfile(os.path.join(root, lockfile)):
            return manager
    return "npm"


def candidates(root):
    """Dev-server configurations guessed from the repo, for the user to confirm.

    A guess, not a detection: the port in particular is the tool's default, and
    the conversation shows it before anything is written."""
    out = []
    pkg_path = os.path.join(root, "package.json")
    if os.path.isfile(pkg_path):
        try:
            with open(pkg_path, encoding="utf-8") as fh:
                pkg = json.load(fh)
        except (OSError, ValueError):
            pkg = {}
        scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
        script = next((s for s in ("dev", "start", "serve") if s in scripts), None)
        if script:
            body = str(scripts[script])
            port = next((p for hint, p in _PORT_HINTS if hint in body), 3000)
            name = pkg.get("name") if isinstance(pkg.get("name"), str) and pkg.get("name") \
                else os.path.basename(os.path.abspath(root))
            out.append({"name": name, "runtimeExecutable": _package_manager(root),
                        "runtimeArgs": ["run", script], "port": port})
    if os.path.isfile(os.path.join(root, "manage.py")):
        out.append({"name": "django", "runtimeExecutable": "python3",
                    "runtimeArgs": ["manage.py", "runserver"], "port": 8000})
    if os.path.isfile(os.path.join(root, "bin", "rails")):
        out.append({"name": "rails", "runtimeExecutable": "bin/rails",
                    "runtimeArgs": ["server"], "port": 3000})
    return out


def merge(doc, configurations, auto_verify=None):
    """(new_doc, added, kept): `configurations` added to `doc` by name; a name
    the file already has is kept as it is, never replaced."""
    new = dict(doc or {})
    new.setdefault("version", VERSION)
    existing = list(new.get("configurations") or [])
    names = {c.get("name") for c in existing if isinstance(c, dict)}
    added, kept = [], []
    for cfg in configurations or ():
        if cfg.get("name") in names:
            kept.append(cfg.get("name"))
            continue
        existing.append(cfg)
        names.add(cfg.get("name"))
        added.append(cfg.get("name"))
    new["configurations"] = existing
    if auto_verify is not None:
        new["autoVerify"] = auto_verify
    return new, added, kept


def detect(root):
    """What `acs.py setup detect` reports about launch.json."""
    state = read(root)
    doc = state["doc"] or {}
    configs = doc.get("configurations") if isinstance(doc.get("configurations"), list) else []
    return {
        "path": os.path.join(*PATH_PARTS),
        "exists": state["exists"],
        "error": state["error"],
        "has_comments": state["has_comments"],
        "configurations": [c.get("name") for c in configs if isinstance(c, dict)],
        "problems": validate(state["doc"]) if state["doc"] is not None else [],
        "candidates": [] if configs else candidates(root),
    }


def plan(root, answer):
    """(new_doc or None, report): what applying `answer` would do, refusals in
    `report["errors"]`. `answer` is {"configurations": [...], "autoVerify"?}."""
    report = {"errors": [], "warnings": [], "added": [], "kept": []}
    if not isinstance(answer, dict):
        report["errors"].append("the launch answer must be an object with `configurations`")
        return None, report
    configs = answer.get("configurations") or []
    auto_verify = answer.get("autoVerify")
    if not isinstance(configs, list):
        report["errors"].append("launch.configurations must be a list")
        return None, report
    for i, cfg in enumerate(configs):
        report["errors"].extend(validate_configuration(cfg, "launch.configurations[%d]" % i))
    if auto_verify is not None and not isinstance(auto_verify, bool):
        report["errors"].append("launch.autoVerify must be true or false")
    state = read(root)
    if state["error"]:
        report["errors"].append("%s exists but cannot be read (%s); fix it by hand"
                                % (os.path.join(*PATH_PARTS), state["error"]))
    if report["errors"]:
        return None, report
    new, added, kept = merge(state["doc"], configs, auto_verify)
    report["added"], report["kept"] = added, kept
    report["warnings"].extend(secret_warnings([c for c in configs if c.get("name") in added]))
    changed = new != (state["doc"] or {})
    if changed and state["has_comments"]:
        report["errors"].append(
            "%s has comments, which a rewrite would drop; add %s to it by hand"
            % (os.path.join(*PATH_PARTS), ", ".join(added) or "the change"))
        return None, report
    report["errors"].extend(validate(new))
    if report["errors"]:
        return None, report
    return (new if changed else None), report


def write(root, doc):
    p = path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
