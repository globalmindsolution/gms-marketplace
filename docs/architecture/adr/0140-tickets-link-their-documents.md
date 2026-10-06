# 0140 — Tickets link their documents: a `## References` section, found from the standard layout

**Status**: Accepted · **Date**: 2026-10-06

**Amends**: [0088](0088-gh-only-github-transport-and-criticality-classification.md)
(a new `gh` operation, `acs.py tracker refresh`'s `gh issue view` / `gh issue
edit` of an existing issue's body, is classified **non-critical**; `tracker
sync` posts a body that carries the references block) and
[0138](0138-breakdown-ticket-and-typed-ticket-authors.md) (`/acs:breakdown-ticket`
writes each child's `tracker-body.md` before the sync, stores each child's
references, and refreshes the epic's issue).

## Context

A ticket alone lacks the design context its implementation needs. By the time
a story is worked, the repo usually holds the PRD section for its feature, the
feature's living analysis, the HLD views that name it, the feature's living LLD
(`api`, `data`, `flows`, `components`), a tech design and an API contract — its
own or its parent epic's — and, once a run has started, its own analysis, plan
and test cases. Nothing on the ticket said so. Every skill that ran on it
searched the repo for the same documents again, an implementer handed only the
ticket could miss the design entirely, and a reviewer reading the issue in the
tracker saw none of it.

Where a document was named at all, it was named by a local path. A local path
is not clickable in a tracker, and a link to the working tree or to a feature
branch breaks as soon as the branch is deleted, or never resolves for anyone
who has not checked it out.

The documents already sit where the standard layout puts them
(`doc_layout.prd_dir`, `architecture_dir`, `development_dir`, ADR-0120,
ADR-0128, ADR-0133), keyed by the ticket's `features` and its id. So the list
can be derived rather than authored, and it works for a ticket created before
this change as well as for a new one.

## Decision

1. **References are found from the standard layout, never configured or
   chosen.** A new `acs_lib/doc_links.py` derives them:
   `references_for_ticket(ctx, ticket, fetch=False)` returns every document the
   layout holds for the ticket's features — **everything for the feature, with
   no selection step** — as entries `{kind, path, title, status, version,
   published, url}`, deduplicated and ordered by kind, then path:
   - `prd` — `<prd_dir>/prd.md`, its `path` carrying the `#anchor` of the
     heading that names each feature (the slug of the heading text, or a
     "Feature: <name>" heading whose slug equals the feature), else the file;
   - `analysis` — the feature's living analysis, `README.md` first;
   - `hld` — `hld/overview.md` plus the HLD views whose text names the feature;
   - `lld` — the feature's living `lld/<feature>/{api,data,flows,components}/**`,
     no evidence sidecars;
   - `design` — `tech-design.md` and `api-contract.md` under
     `<architecture_dir>/lld/<feature>/<id>/`, for the ticket and for its
     parent epic;
   - `development` — `<development_dir>/<feature>/<id>/`'s `analysis/`,
     `plan.md` and `test-cases.md`.

   A ticket with no `features` falls back to an id glob (`lld/*/<id>/`,
   `<development_dir>/*/<id>/`, the parent's records) and `prd.md`. `status`
   and `version` come from ADR-0122's front matter when a document has it; the
   title is the first H1, else the file name. `references_for_features(ctx,
   features)` returns the same set without a ticket's records, for a ticketless
   feature run.
2. **A link targets the remote default branch.** `web_base(root)` turns
   `remote.origin.url` — ssh, scp-style or https, with or without `.git` and
   `user@` — into `https://<host>/<owner>/<repo>`, and a document's `url` is
   `<base>/blob/<default>/<path>` (GitHub and GitHub Enterprise — `github.com`,
   a `*.ghe.com` host or any host with a `github` label; `/-/blob/` on gitlab
   hosts, `/src/` on bitbucket hosts). `default_branch`
   is one shared helper (`origin/HEAD`, else `main`, else `master`), which
   `setup_wizard.default_branch` now delegates to. A document counts as
   **published** only when it exists on `origin/<default>`; `published(root,
   paths, fetch)` checks it with `ls-tree`, after a best-effort `git fetch`
   when asked. An unpublished document has `url: null` and is listed as
   **pending: not on `<default>` yet**, with no link. A remote on a host acs
   cannot link to gives `web_base: null` with `web_base_reason:
   "no-web-remote"`: its published documents are listed by path, unlinked.
3. **Every ticket has a `## References` section.** All four description
   templates (`templates/{epic,story,task,bug}-default.md`) carry a fixed
   `## References` heading with an empty `<!-- acs:references -->` …
   `<!-- /acs:references -->` marker pair before `## Notes`; the type author
   leaves the markers alone and code fills them. `render_block` writes one line
   per entry — `- [<title>](<url>): <kind>, vN status` when published, ``-
   `<path>`: <kind>, pending: not on `<default>` yet`` when not — or
   `_No documents for this ticket's features yet._`; `apply_block` replaces
   only the text between the markers, adding the heading and markers when a
   body has none. The ticket stores the list as an optional `references`
   array (`ticket.schema.json`; `kind` and `path` required), placed after
   `features`.
4. **The tracker carries real links, and a refresh turns pending into links.**
   `acs.py tracker sync` applies the block to `tracker-body.md` (fresh
   references, with a fetch) before `gh issue create`. A new `acs.py tracker
   refresh (--ticket ID | --pending) [--dry-run]` recomputes a synced ticket's
   references, stores them, and — only when the rendered block differs from
   the issue's — reads the body with `gh issue view`, applies the block and
   writes it back with `gh issue edit --body-file`, touching nothing outside
   the markers. `--pending` covers every open, synced ticket whose stored
   references still hold a pending entry; a ticket on the `local` tracker has
   its references stored and its issue edit skipped. Both run through the existing `gh`
   runner and failure classification; the refresh is **non-critical**
   (ADR-0088): a failure is one finding, never a stop. `record-external.py
   --url` keeps the issue URL the sync returns in `external.url`.
5. **Skills read the list; they do not search for it.** The step-start
   context carries `context.references` — `references_for_ticket` for a ticket
   run (local only, no fetch), `references_for_features` for a ticketless run
   with features, else `[]` — and `requirements.materialise` renders the same
   list as a `## References` section of `<run>/requirements.md`, from the same
   function (`requirements.run_references`), so the two cannot drift. Every hooked skill that runs on a ticket
   reads the documents relevant to its step from `context.references` before
   working and never searches the repo for them. `acs.py ticket references
   (--ticket ID | --features a,b [--parent ID]) [--fetch] [--write] [--render]`
   is the same lookup on the command line.
6. **The ticket skills keep it current.** `/acs:create-ticket` passes the list
   to its type author once `features` are known, shows it in the confirmation
   (pending entries marked), stores it after minting and syncs the block (an
   imported issue, which already exists, is refreshed instead).
   `/acs:breakdown-ticket` stores each child's references, writes each child's
   `tracker-body.md` before the sync — closing the gap where a child had no body
   to sync — and refreshes the epic. `/acs:merge-pr` runs `acs.py tracker
   refresh --pending` after a merge, best-effort, and reports it.

## Consequences

- **No link 404s.** A link exists only for a document already on the default
  branch, so it resolves for anyone who can read the repo, and it survives the
  feature branch's deletion.
- **Pending entries wait for a merge.** A document written on the ticket's own
  branch — its analysis, plan, test cases or a new tech design — is listed as
  pending until its PR lands. `/acs:merge-pr`'s `tracker refresh --pending`
  turns it into a link; a ticket whose documents reach the default branch some
  other way is refreshed with `acs.py tracker refresh --ticket ID`.
- **Old tickets work.** Nothing is migrated: the list is derived from the
  layout and the ticket's `features` and id at read time, so a ticket created
  before this change gets `context.references` and a refreshed issue body;
  `references` is optional, so its `ticket.json` still validates.
- **No selection.** Every document the layout holds for the feature is listed;
  a skill reads the ones relevant to its step. A feature with many LLD files
  gives a long list, which is the accepted cost of never missing one.
- **Only GitHub's issues are edited.** The trackers are `local` and `github`;
  a `local` ticket stores its references and has no issue to refresh. A remote
  on a host acs cannot link to gets paths, never a guessed link.
