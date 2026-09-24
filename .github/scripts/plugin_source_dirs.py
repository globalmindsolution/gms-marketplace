#!/usr/bin/env python3
"""Print every plugin SOURCE directory in this working tree, one per line.

Why this exists rather than reading the source path out of marketplace.json:
that says where an INSTALL fetches the plugin from, at the entry's `ref`. It
is not necessarily a working-tree location, and the two diverge for the whole
window between a directory move and the release cut that publishes it --
which is exactly when this repo broke twice.

The lint steps in ci.yml (schemas, settings, XSD, hook byte-compile, skill
frontmatter) want the source in THIS tree, so they ask here. They used to
read the entry's `path` and `continue` when the directory was missing, which
turned all five into no-ops the moment that path pointed at a ref-relative
location. A check that silently validates nothing is worse than one that
fails.

So: discover by looking for the marker every plugin has
(<dir>/.claude-plugin/plugin.json), and exit non-zero when none is found,
because a repo with no plugin at all is a defect and not a reason to pass
quietly. Discovery by marker is also why the plugins/acs -> src/acs ->
plugins/acs moves needed no edit here.
"""

import os
import sys

SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def plugin_dirs(root="."):
    found = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        if os.path.basename(dirpath) != ".claude-plugin":
            continue
        if not os.path.exists(os.path.join(dirpath, "plugin.json")):
            continue
        parent = os.path.dirname(dirpath)
        # The repo-root .claude-plugin holds marketplace.json, not a plugin.
        if os.path.abspath(parent) == os.path.abspath(root):
            continue
        found.append(os.path.relpath(parent, root))
    return sorted(found)


if __name__ == "__main__":
    dirs = plugin_dirs()
    if not dirs:
        sys.stderr.write(
            "no plugin source directory found (looked for */.claude-plugin/"
            "plugin.json). If the plugin tree moved, this script is what the "
            "lint steps follow -- fix it here rather than letting them skip.\n")
        sys.exit(1)
    print("\n".join(dirs))
