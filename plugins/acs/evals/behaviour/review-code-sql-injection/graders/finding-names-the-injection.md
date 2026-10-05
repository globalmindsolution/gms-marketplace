---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/verdict.json }
pattern: 'inject|parameteri[sz]|placeholder|bound param|bind param|string[- ]format|interpolat'
flags: i
---

The blocking finding is about the seeded security defect: the email is
interpolated into the SQL instead of being passed as a bound parameter. A
verdict whose only finding is about something else (style, docs, the missing
index) names none of these.
