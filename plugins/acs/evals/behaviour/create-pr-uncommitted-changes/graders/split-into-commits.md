---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: 'commit: EVAL-1 [^\n]*\n(?:[^\n]*\n)*?[^\n]*commit: EVAL-1 '
---

Git's own record, not the skill's: HEAD's reflog shows at least two commits
whose subjects carry the ticket id -- the plan splits the slice into its tests
and its code (`{ticket_id} {summary}` subjects). One sweeping commit, or none,
fails.
