"""Write the GitHub release body for one version from plugins/acs/CHANGELOG.md.

release.yml calls this. The body is the version's changelog section, with
Keep-a-Changelog link-reference definitions dropped. GitHub rejects a release
body over 125,000 characters (HTTP 422), which v0.5.0's section exceeded:
the tag was pushed and the release was not created. A section over the limit
is cut at the last entry boundary that fits, and the body ends with a link to
the full section in the CHANGELOG at the release tag.

Usage: release_notes_body.py <version> <repo-url> <out-file>
"""

import re
import sys

CHANGELOG = "plugins/acs/CHANGELOG.md"
# GitHub's limit is 125,000 characters; leave room for the truncation note.
MAX_BODY = 120000


def section(text, version):
    pattern = r"^## \[%s\][^\n]*\n(.*?)(?=^## \[|\Z)" % re.escape(version)
    match = re.search(pattern, text, re.M | re.S)
    if not match:
        return None
    lines = [line for line in match.group(1).splitlines()
             if not re.match(r"^\[[^\]]+\]:\s*\S", line)]
    return "\n".join(lines).strip() + "\n"


def changelog_anchor(heading):
    """GitHub's anchor for a markdown heading."""
    slug = heading.strip().lstrip("#").strip().lower()
    slug = re.sub(r"[^\w\- ]", "", slug)
    return slug.replace(" ", "-")


def truncate(notes, full_url, limit=MAX_BODY):
    if len(notes) <= limit:
        return notes
    note = ("\n\n---\n\nThese notes are cut short: GitHub caps a release body at "
            "125,000 characters. The full section is in the CHANGELOG: %s\n" % full_url)
    budget = limit - len(note)
    lines = notes.splitlines(keepends=True)
    fit, size = 0, 0
    while fit < len(lines) and size + len(lines[fit]) <= budget:
        size += len(lines[fit])
        fit += 1
    # Cut just before the last heading or top-level item that fits, so no
    # entry is cut mid-way.
    cut = next((i for i in range(fit, 0, -1)
                if re.match(r"^(#{1,6} |- )", lines[i])), fit)
    return "".join(lines[:cut]).rstrip() + note


def body(text, version, repo_url):
    notes = section(text, version)
    if notes is None:
        return None
    heading = next(line for line in text.splitlines()
                   if line.startswith("## [%s]" % version))
    full_url = "%s/blob/v%s/%s#%s" % (repo_url.rstrip("/"), version, CHANGELOG,
                                      changelog_anchor(heading))
    return truncate(notes, full_url)


def main(argv):
    version, repo_url, out = argv[1:4]
    with open(CHANGELOG, encoding="utf-8") as fh:
        text = fh.read()
    notes = body(text, version, repo_url)
    if notes is None:
        sys.exit("No '## [%s]' section found in %s — add one before releasing "
                 "(semver discipline: version bump + changelog section ship "
                 "together)." % (version, CHANGELOG))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(notes)
    print("Release notes for v%s: %d characters" % (version, len(notes)))


if __name__ == "__main__":
    main(sys.argv)
