#!/usr/bin/env python3
"""Install THIS checkout's acs as a plugin whose cache can never go stale.

The problem
-----------
Claude Code caches an installed plugin at
``<cache>/<marketplace>/<plugin>/<version>`` and records that path in
``installed_plugins.json``. ``plugins/acs/.claude-plugin/plugin.json`` declares
``0.4.9`` -- the same string the released tag declares -- so installing this
working tree resolves to the directory the RELEASE already occupies. The
install short-circuits, the stale release is served, and nothing says so. That
version collision is also why the eval suite had to grow a skill-surface
fingerprint: the version string alone does not tell two builds apart.

The fix
-------
Give the working tree a version no release can collide with, derived from the
tree's own contents:

    0.4.10-dev.<12 hex of a hash over every file under plugins/acs>

Edit any byte of the plugin and the version changes, so the cache key changes,
so a stale hit is impossible by construction rather than by remembering to
clear anything. Identical content reinstalls to the same place and is a no-op.

What it touches
---------------
Only the cache directory for the dev version, plus this plugin's entry in
``installed_plugins.json``. The released ``0.4.9`` install is never modified,
and ``--uninstall`` removes every dev version and restores whatever real
install was recorded before the first dev install. The working tree is read
ONLY -- `plugin.json`'s version is rewritten in the staged copy, never here.

    python3 scripts/dev_install.py            # install this tree
    python3 scripts/dev_install.py --status   # what is installed right now
    python3 scripts/dev_install.py --uninstall

`--cache-root` points the whole thing at a throwaway directory, which is how
its own tests run without touching a real Claude install.

Note for the eval suite: it does not need this. `measure_skills.py` passes
`--plugin-dir` and never reads the cache at all. This is for hands-on
sessions, where the plugin has to be genuinely installed.
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_SRC = os.path.join(REPO_ROOT, "plugins", "acs")
MARKETPLACE = "gms-marketplace"
PLUGIN = "acs"
KEY = "%s@%s" % (PLUGIN, MARKETPLACE)
#: Dev versions sort BELOW this release, so a dev install never looks newer
#: than a real one. Bump it when the next release is cut.
NEXT_RELEASE = "0.4.10"
DEV_PREFIX = "%s-dev." % NEXT_RELEASE

#: Directories whose contents say nothing about the plugin's behaviour.
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}


def default_cache_root():
    return os.path.join(os.path.expanduser("~"), ".claude", "plugins")


def tree_hash(root):
    """A stable digest of every file under `root`.

    Path and content both feed the hash, so a rename is a change. Sorted, so
    the digest does not depend on directory-iteration order.
    """
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(".pyc"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(1 << 16)
                    if not chunk:
                        break
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def dev_version(root=PLUGIN_SRC):
    return DEV_PREFIX + tree_hash(root)[:12]


def is_dev(version):
    return bool(version) and version.startswith(DEV_PREFIX)


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path, doc):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _entries(registry):
    return registry.setdefault("plugins", {}).setdefault(KEY, [])


def stage(version, cache_root):
    """Copy the working tree into the cache under `version`. Returns the path."""
    dest = os.path.join(cache_root, "cache", MARKETPLACE, PLUGIN, version)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(PLUGIN_SRC, dest,
                    ignore=shutil.ignore_patterns(*SKIP_DIRS, "*.pyc"))
    # The staged COPY carries the dev version; the working tree is untouched,
    # so this never shows up as a repo change or lands in a commit.
    manifest_path = os.path.join(dest, ".claude-plugin", "plugin.json")
    manifest = _read_json(manifest_path, None)
    if manifest is None:
        raise SystemExit("dev-install: %s has no readable plugin.json" % PLUGIN_SRC)
    manifest["version"] = version
    _write_json(manifest_path, manifest)
    return dest


def install(cache_root, quiet=False):
    version = dev_version()
    registry_path = os.path.join(cache_root, "installed_plugins.json")
    registry = _read_json(registry_path, {"version": 2, "plugins": {}})
    entries = _entries(registry)

    # Remember the real install once, so --uninstall can put it back.
    kept = [e for e in entries if not is_dev(e.get("version"))]
    previous = registry.setdefault("__dev_install_backup__", {})
    if KEY not in previous and kept:
        previous[KEY] = kept

    dest = stage(version, cache_root)
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ")
    entry = {"scope": "user", "installPath": dest, "version": version,
             "installedAt": now, "lastUpdated": now, "devInstall": True,
             "devSource": PLUGIN_SRC}

    # Exactly one dev version at a time: an older one is dead weight and, worse,
    # a second candidate for the loader to choose between.
    removed = prune(cache_root, keep=version, registry=registry)
    # The dev entry is the ONLY one listed while it is active. Leaving the
    # release entry alongside it would ask the loader to choose between two
    # installs of the same plugin, and "whichever semver ranks higher" is a
    # rule to depend on only if you have read that loader. Its cache directory
    # is never touched, and `previous` above holds the entry verbatim, so
    # --uninstall puts it back exactly as it was.
    registry["plugins"][KEY] = [entry]
    _write_json(registry_path, registry)

    if not quiet:
        print("installed  %s" % version)
        print("  from     %s" % PLUGIN_SRC)
        print("  at       %s" % dest)
        if removed:
            print("  replaced %s" % ", ".join(removed))
        shadowed = [e["version"] for e in kept]
        if shadowed:
            print("  replaces %s as the active install (its files are kept; "
                  "--uninstall restores it)" % ", ".join(shadowed))
        print("\nOpen a NEW session to pick it up. Re-run after any edit: the "
              "version tracks the\ncontents, so a changed tree always installs "
              "to a fresh path.")
    return version, dest


def prune(cache_root, keep=None, registry=None):
    """Delete every staged dev version except `keep`. Returns what went."""
    base = os.path.join(cache_root, "cache", MARKETPLACE, PLUGIN)
    removed = []
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if not is_dev(name) or name == keep:
            continue
        shutil.rmtree(os.path.join(base, name), ignore_errors=True)
        removed.append(name)
    if registry is not None:
        entries = _entries(registry)
        registry["plugins"][KEY] = [
            e for e in entries
            if not (is_dev(e.get("version")) and e.get("version") != keep)]
    return removed


def uninstall(cache_root, quiet=False):
    registry_path = os.path.join(cache_root, "installed_plugins.json")
    registry = _read_json(registry_path, {"version": 2, "plugins": {}})
    removed = prune(cache_root, keep=None, registry=registry)

    backup = registry.get("__dev_install_backup__", {})
    restored = backup.pop(KEY, None)
    if restored:
        registry["plugins"][KEY] = restored
    elif not registry["plugins"].get(KEY):
        registry["plugins"].pop(KEY, None)
    if not backup:
        registry.pop("__dev_install_backup__", None)
    _write_json(registry_path, registry)

    if not quiet:
        if removed:
            print("removed   %s" % ", ".join(removed))
        else:
            print("nothing to remove — no dev install present")
        if restored:
            print("restored  %s" % ", ".join(e["version"] for e in restored))
    return removed


def status(cache_root):
    registry = _read_json(os.path.join(cache_root, "installed_plugins.json"),
                          {"plugins": {}})
    entries = registry.get("plugins", {}).get(KEY, [])
    want = dev_version()
    print("this tree  %s" % want)
    if not entries:
        print("installed  (nothing)")
    for e in entries:
        mark = "  <- this tree" if e.get("version") == want else ""
        kind = "dev" if is_dev(e.get("version")) else "release"
        print("installed  %-28s %-7s %s%s"
              % (e.get("version"), kind, e.get("installPath", ""), mark))
    if not any(e.get("version") == want for e in entries):
        print("\nOut of date — run `python3 scripts/dev_install.py` to install "
              "this tree.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uninstall", action="store_true",
                    help="remove every dev install and restore the release")
    ap.add_argument("--status", action="store_true",
                    help="what is installed, and whether it matches this tree")
    ap.add_argument("--cache-root", default=None,
                    help="plugins root to act on (default: ~/.claude/plugins)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    cache_root = args.cache_root or default_cache_root()
    if not os.path.isdir(PLUGIN_SRC):
        sys.stderr.write("dev-install: no plugin at %s\n" % PLUGIN_SRC)
        return 2
    if args.status:
        return status(cache_root)
    if args.uninstall:
        uninstall(cache_root, args.quiet)
        return 0
    install(cache_root, args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
