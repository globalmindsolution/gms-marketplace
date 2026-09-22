# The delivery-ticket PR — label, title, body, self-check, open

Open this at the **Push & PR** step of any product-level skill that ships its
work on its own delivery ticket: `/acs:create-prd`, `/acs:create-architecture`,
`/acs:create-docs`, `/acs:create-project`, `/acs:standardize-project`. Each of
them reaches this same point by a different route and leaves it the same way,
so the mechanics live here once rather than five times.

**What this file does NOT decide**, because it genuinely differs per skill and
getting it wrong is how a delivery PR goes bad:

- **What to stage.** Each skill scopes its own commit — one doc tree, one doc
  set's path, the whole scaffold, or exactly the allowlist a verifier
  confirmed. `/acs:create-project` stages `git add -A` because a scaffold is
  new files by definition; `/acs:standardize-project` explicitly forbids that
  same command, because a broad add would sweep up source it is not allowed to
  touch. Those two rules contradict each other on purpose. Take your own.
- **The branch and its slug**, which your skill renders from
  `settings.formats.branch_name` before its first executor writes.
- **Anything your skill does after the PR is open** — watching CI, appending a
  section to the body, or opening one PR per set rather than one per run.

Everything below is the same on every one of those paths.

## 1. Label and title

Render the title with the helper — NOT LLM prose composition — capturing its
stdout as `<rendered title>`:

```bash
gh label create ACS --description "Created by the acs pipeline" 2>/dev/null || true
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" render-title \
  --template "<settings.formats.pr_title>" --ticket-id <ticket_id> --type <ticket.type> \
  --title "<delivery ticket's title>" --summary "<summary>" --external-key "<ticket.external.key or empty>" \
  --provider "<ticket.external.provider or empty>"
```

The title renders `settings.formats.pr_title` (default `[{ticket_id}] {title}`).
The label already existing is not an error — that is what the `|| true` is for.

## 2. Body

The body comes from `settings.formats.pr_description_template`: built-in name
`pr-default` -> `${CLAUDE_PLUGIN_ROOT}/templates/pr-default.md`; otherwise
`<checkout_root>/.acs/templates/<name>.md`; otherwise an absolute path. Fill
its placeholders from `ticket.json` and the verifier result — never from
conversation memory. Conversation memory is the one source that cannot be
re-derived later, so a body filled from it is a body nobody can check.

## 3. Pre-open self-check

Before `gh pr create`, self-check the rendered title and filled body with the
helper's `check` subcommand (a deterministic CLI call, never a spawned
subagent):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pr-conventions.py" check \
  --title "<rendered title>" --body-file <body.md> --require-label ACS \
  --pr-title-format "<settings.formats.pr_title>" \
  --sections "<settings.enforcement.pr_description_sections, comma-joined>" \
  --ticket-prefix <settings.ticket_prefix>
```

On pass, proceed to `gh pr create` unchanged. On failure, this check
blocks/retries: apply a bounded local re-render/re-check (up to 2 attempts)
rather than opening a non-conforming PR; if still failing after the bounded
retries, STOP — do not call `gh pr create` — surface the blocking finding with
the failing heading(s)/detail(s) in the result document.

The self-check exists because the CI convention gate runs the same rules
against the opened PR. Failing here costs a re-render; failing there costs a
red check on a PR a reviewer is already looking at.

## 4. Open it

```bash
gh pr create --base <default-branch> --head <branch> --title "<rendered title>" --body-file <body.md> --label ACS
```

## 5. Record it

Record `{number, url, branch}` for the result document. The post-hook moves the
delivery ticket to `in_review`; `/acs:merge-pr` later lands it like any other
ticket. Merging stays a user action — never invoke `/acs:merge-pr` yourself.
