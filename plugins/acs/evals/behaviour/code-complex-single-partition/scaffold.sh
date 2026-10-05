#!/usr/bin/env bash
# /acs:code on a ticket whose approved plan records `delivery_path: complex`
# for a SECURITY boundary that lives in ONE partition: merchant API keys are
# stored hashed and verified in constant time, all in src/shop/auth.py. The
# complex leg owes an integration implementer only when more than one
# partition ran -- "a plan with a single partition has no seams between
# partitions, and skips it" -- so this run spawns one un-sliced implementer
# and no integration pass.
#
# The plan is produced the way /acs:create-impl-plan produces one, through the
# plugin's own writers wherever one exists:
#   acs.py step start --step create-impl-plan   (run, lock, pointer, ledger)
#   the draft at runs/EVAL-1/steps/create-impl-plan/plan.md (the planner's
#     Write; no CLI writer exists for its bytes)
#   acs.py filemap set --skill code --iteration 1 (the map the guard enforces)
#   the published copy in docs/tickets/EVAL-1/, left uncommitted on main
#   post-create-impl-plan.py (finishes the step, releases the lock)
# and then APPROVED through the sole writer of plan-approval.json, `acs.py plan
# check`, which the complex path's pre-hook requires.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Store merchant API keys hashed" story false \
  "Merchant API keys are about to be persisted; a leaked table must not leak usable keys."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["hash_key(key) returns a salted hash that never contains the key", "verify_key(key, stored) is true only for the key that was hashed", "verify_key compares digests in constant time"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null

acs step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
draft="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/plan.md"
cat > "$draft" <<'MD'
# Plan — EVAL-1 Store merchant API keys hashed

A security boundary: how a merchant's API key is stored and checked. Small in
files, deep in stakes -- one module, but a wrong comparison or an unsalted
hash is an irreversible leak once keys are persisted.

## Approach

New `src/shop/auth.py`, standard library only:

- `hash_key(key)` returns `"<salt-hex>$<digest-hex>"`: a random 16-byte salt
  from `secrets.token_bytes` and `hashlib.pbkdf2_hmac("sha256", key, salt,
  200_000)`. The key itself never appears in the result.
- `verify_key(key, stored)` re-derives the digest with the stored salt and
  compares with `hmac.compare_digest` -- never `==`.

Rejected: plain `sha256(key)`, because it is unsalted and fast to brute-force.

## Test strategy

`tests/test_auth.py`, written first and failing:

- AC-1: `hash_key("k-123")` does not contain `k-123`; two calls differ (salt).
- AC-2: `verify_key` accepts the hashed key and rejects any other.
- AC-3: `verify_key` calls `hmac.compare_digest` (patched to observe it).

Run: `python3 -m pytest -q tests/test_auth.py`. Coverage target: 90% of
`src/shop/auth.py`, measured by the review's final gate.

## Risks

- Timing: an `==` on digests leaks how many leading bytes matched.
- Irreversibility: once keys are stored, a weak scheme cannot be re-hashed
  without every merchant rotating their key.

## Contract
delivery_path: complex
owes:
  api_contract: false
  test_cases: false
  e2e: false
  reason: "a security boundary: credential storage and verification, irreversible once keys are persisted"

### Executor tasks & file map
- task 1: src/shop/auth.py, tests/test_auth.py
MD
acs filemap set --skill code --iteration 1 --task 1 \
  --file src/shop/auth.py --file tests/test_auth.py > /dev/null
mkdir -p docs/tickets/EVAL-1
cp "$draft" docs/tickets/EVAL-1/plan.md
result="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/result.json"
cat > "$result" <<'JSON'
{"status": "completed", "summary": "plan published; one executor task on a security boundary",
 "states": {"plan_path": "docs/tickets/EVAL-1/plan.md", "plan_approved": false,
            "file_map": {"1": ["src/shop/auth.py", "tests/test_auth.py"]}},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" --result-file "$result" > /dev/null 2>&1
# The human's approval, through its sole writer. Refuse to seed an unapproved
# deep-path plan: the case would then measure the pre-hook, not the leg.
# (Captured first: `| grep -q` under pipefail can SIGPIPE the writer.)
approval="$(acs plan check --run EVAL-1)"
grep -q '"plan_approved": true' <<<"$approval"
