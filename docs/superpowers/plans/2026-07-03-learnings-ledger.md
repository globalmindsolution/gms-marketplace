# Learnings Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give acs a persistent, repo-tier memory (`learnings.json` + `learn.py`) so sessions stop re-deriving repo facts, with a bounded default-on digest injected at skill-start and the safety rule that provisional learnings never steer agents.

**Architecture:** A new stdlib-only helper `learn.py` (cloned from `clarify.py`) owns an append-only `learnings.json` at the repo tier (beside `tickets-index.json`). New `acs_lib.py` functions provide the path, the confidence-ladder mutation, and the bounded `learnings_digest`. `skill-start.py` adds a `"learnings"` field to the context JSON it already prints. No new always-on hook; capture is wired into `/acs:merge-pr` and `/acs:code` SKILL prose.

**Tech Stack:** Python 3 stdlib only (json, os, argparse, tempfile, datetime). Tests: `unittest` loaded via `importlib.util.spec_from_file_location`, run with `python3 -m unittest`.

## Global Constraints

- **Stdlib only.** No third-party imports; no embeddings. (ADR 0035; `learn.py` mirrors `clarify.py`.)
- **Atomic writes only** via `acs_lib.write_json` — never hand-write JSON. (`acs_lib.py:367`)
- **Timestamps** via `acs_lib.now_iso()` → `"%Y-%m-%dT%H:%M:%SZ"`. (`acs_lib.py:339`)
- **Safety invariant (load-bearing):** a `provisional` learning is NEVER returned by `learnings_digest`. Injection begins at `established`.
- **Bounds:** ≤3 candidates captured per merge; digest ≤ K=7 entries AND ≤ a hard character cap.
- **Confidence ladder:** `provisional` (1 ticket) → `established` (auto, ≥2 distinct `seen_tickets`) → `core` (human `promote`).
- **Test harness:** load the shipped file directly via `importlib.util.spec_from_file_location`, mirroring `tests/acs/test_pr_conventions.py:24-26`. Run: `python3 -m unittest discover -s tests -v`.
- **Repo tier path:** `acs_lib.repo_dir(workspace, repo_id)/learnings.json`. `archive/` is a subdir, so archival never touches the ledger.

---

## File Structure

- `plugins/acs/hooks/scripts/acs_lib.py` (modify) — add `learnings_path`, `LEARNINGS_DIGEST_MAX`, `LEARNINGS_CAPTURE_CAP`, confidence helpers, `learnings_digest`.
- `plugins/acs/hooks/scripts/learn.py` (create) — the CLI helper: `add`, `promote`, `list`.
- `plugins/acs/hooks/scripts/skill-start.py` (modify) — inject `"learnings"` into the context JSON.
- `tests/acs/test_learn.py` (create) — unit tests for `learn.py` + the `acs_lib` helpers.
- `plugins/acs/skills/merge-pr/SKILL.md` (modify) — add the distillation-at-merge capture step (prose).
- `plugins/acs/skills/code/SKILL.md` (modify) — add opportunistic `provisional` capture (prose).

Tasks are ordered so each builds on committed, tested code from the prior one.

---

### Task 1: `acs_lib` foundations — path, constants, confidence ladder

**Files:**
- Modify: `plugins/acs/hooks/scripts/acs_lib.py` (add after `index_path`, ~line 1161)
- Test: `tests/acs/test_learn.py` (create)

**Interfaces:**
- Consumes: `repo_dir(workspace, repo_id)` (`acs_lib.py:645`), `now_iso()` (`acs_lib.py:339`).
- Produces:
  - `learnings_path(workspace, repo_id) -> str`
  - `LEARNINGS_CAPTURE_CAP = 3`, `LEARNINGS_DIGEST_MAX = 7`, `LEARNINGS_DIGEST_CHAR_CAP = 2000`
  - `CONFIDENCE_ORDER = {"provisional": 0, "established": 1, "core": 2}`
  - `bump_confidence(entry) -> entry` — recomputes `confidence` from `len(set(seen_tickets))`: ≥2 distinct → at least `established`; never downgrades `core`.

- [ ] **Step 1: Write the failing test**

Create `tests/acs/test_learn.py`:

```python
"""Unit tests for the learnings ledger: acs_lib helpers + learn.py CLI (ADR 0035).

Loads the shipped files directly via importlib (mirrors test_pr_conventions.py),
so these exercise plugins/acs/hooks/scripts/*, not an installed copy.

Run:  python3 -m unittest discover -s tests -v
"""

import importlib.util
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lib = _load("acs_lib_learn", os.path.join(SCRIPTS, "acs_lib.py"))


class TestConfidenceLadder(unittest.TestCase):
    def test_one_ticket_stays_provisional(self):
        entry = {"confidence": "provisional", "seen_tickets": ["MAR-1"]}
        self.assertEqual(lib.bump_confidence(entry)["confidence"], "provisional")

    def test_two_distinct_tickets_promote_to_established(self):
        entry = {"confidence": "provisional", "seen_tickets": ["MAR-1", "MAR-2"]}
        self.assertEqual(lib.bump_confidence(entry)["confidence"], "established")

    def test_duplicate_ticket_does_not_promote(self):
        entry = {"confidence": "provisional", "seen_tickets": ["MAR-1", "MAR-1"]}
        self.assertEqual(lib.bump_confidence(entry)["confidence"], "provisional")

    def test_core_never_downgrades(self):
        entry = {"confidence": "core", "seen_tickets": ["MAR-1"]}
        self.assertEqual(lib.bump_confidence(entry)["confidence"], "core")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.acs.test_learn -v`
Expected: FAIL with `AttributeError: module 'acs_lib_learn' has no attribute 'bump_confidence'`

- [ ] **Step 3: Write minimal implementation**

In `acs_lib.py`, immediately after the `index_path` function (~line 1161), add:

```python
# ---------------------------------------------------------------------------
# Learnings ledger (ADR 0035) — repo-tier cross-ticket memory
# ---------------------------------------------------------------------------

LEARNINGS_CAPTURE_CAP = 3          # max candidates distilled per merge
LEARNINGS_DIGEST_MAX = 7           # max entries injected at skill-start
LEARNINGS_DIGEST_CHAR_CAP = 2000   # hard char cap on the rendered digest
CONFIDENCE_ORDER = {"provisional": 0, "established": 1, "core": 2}


def learnings_path(workspace, repo_id):
    return os.path.join(repo_dir(workspace, repo_id), "learnings.json")


def bump_confidence(entry):
    """Recompute confidence from distinct seen_tickets. Never downgrades a
    human-promoted 'core'. 1 distinct ticket -> provisional; >=2 -> established."""
    if entry.get("confidence") == "core":
        return entry
    distinct = len(set(entry.get("seen_tickets") or []))
    entry["confidence"] = "established" if distinct >= 2 else "provisional"
    return entry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.acs.test_learn -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/acs/hooks/scripts/acs_lib.py tests/acs/test_learn.py
git commit -m "MAR-N add learnings-ledger acs_lib foundations (path, ladder, bounds)"
```

---

### Task 2: `learn.py add` — append-only capture with de-dup

**Files:**
- Create: `plugins/acs/hooks/scripts/learn.py`
- Test: `tests/acs/test_learn.py` (extend)

**Interfaces:**
- Consumes: `lib.learnings_path`, `lib.bump_confidence`, `lib.write_json`, `lib.read_json`, `lib.now_iso`, `lib.build_context`, `lib.resolve_ticket_id`, `lib.find_ticket_partition`, `lib.repo_partition_id`.
- Produces (module-level, importable in tests):
  - `load_ledger(workspace, repo_id) -> dict` — `{"repo_id", "learnings": [...]}`
  - `normalize(text) -> str` — lowercased, whitespace-collapsed (for de-dup key)
  - `add_entry(ledger, *, kind, trigger, lesson, ticket, finding) -> dict` — appends or de-dups; returns the entry. De-dup key: `(kind, trigger, normalize(lesson))`. On match: append `ticket` to `seen_tickets`, `bump_confidence`, update `updated_at`.

- [ ] **Step 1: Write the failing test**

Append to `tests/acs/test_learn.py` (before the `if __name__` guard):

```python
learn = _load("acs_learn", os.path.join(SCRIPTS, "learn.py"))


class TestAddEntry(unittest.TestCase):
    def _empty(self):
        return {"repo_id": "r", "learnings": []}

    def test_add_creates_provisional_with_id_and_evidence(self):
        ledger = self._empty()
        e = learn.add_entry(ledger, kind="convention", trigger="pr-conventions.py",
                            lesson="Body needs the four exact section headers.",
                            ticket="MAR-3", finding="verifier-iter-2")
        self.assertEqual(e["id"], "L-1")
        self.assertEqual(e["confidence"], "provisional")
        self.assertEqual(e["seen_tickets"], ["MAR-3"])
        self.assertEqual(e["evidence"], {"ticket": "MAR-3", "finding": "verifier-iter-2"})
        self.assertEqual(len(ledger["learnings"]), 1)

    def test_dedup_appends_seen_ticket_and_promotes(self):
        ledger = self._empty()
        learn.add_entry(ledger, kind="convention", trigger="pr-conventions.py",
                        lesson="Body needs the four exact section headers.",
                        ticket="MAR-3", finding="f1")
        e = learn.add_entry(ledger, kind="convention", trigger="pr-conventions.py",
                            lesson="body   NEEDS the four exact SECTION headers.",  # normalizes equal
                            ticket="MAR-9", finding="f2")
        self.assertEqual(len(ledger["learnings"]), 1)          # no duplicate row
        self.assertEqual(e["seen_tickets"], ["MAR-3", "MAR-9"])
        self.assertEqual(e["confidence"], "established")       # 2 distinct tickets

    def test_dedup_same_ticket_does_not_double_count(self):
        ledger = self._empty()
        learn.add_entry(ledger, kind="pitfall", trigger="x", lesson="l",
                        ticket="MAR-3", finding="f1")
        e = learn.add_entry(ledger, kind="pitfall", trigger="x", lesson="l",
                            ticket="MAR-3", finding="f2")
        self.assertEqual(e["seen_tickets"], ["MAR-3"])
        self.assertEqual(e["confidence"], "provisional")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.acs.test_learn -v`
Expected: FAIL — `learn.py` does not exist / `add_entry` undefined.

- [ ] **Step 3: Write minimal implementation**

Create `plugins/acs/hooks/scripts/learn.py`:

```python
#!/usr/bin/env python3
"""learn.py — the repo-tier cross-ticket learnings ledger (ADR 0035).

One append-only ledger per repo at <repo_dir>/learnings.json — acs's memory of
reusable, repo-general facts that survives ticket archival. Cloned from the
per-ticket clarify.py pattern (atomic writes; no hand-edited JSON).

Safety rule: a 'provisional' learning is captured and listable but is NEVER
injected to steer agents (see acs_lib.learnings_digest). A second distinct
ticket (auto) or a human `promote` moves it to established/core first.

Usage:
  learn.py add     --kind convention --trigger pr-conventions.py \\
                   --lesson "..." [--ticket MAR-3] [--finding verifier-iter-2]
  learn.py promote --id L-7 --to core [--ticket MAR-3]
  learn.py list    [--min-confidence established] [--ticket MAR-3]

Kinds: convention | pitfall | architecture | tooling
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib as lib  # noqa: E402

KINDS = ["convention", "pitfall", "architecture", "tooling"]


def load_ledger(workspace, repo_id):
    data = lib.read_json(lib.learnings_path(workspace, repo_id))
    if not isinstance(data, dict) or not isinstance(data.get("learnings"), list):
        data = {"repo_id": repo_id, "learnings": []}
    return data


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def add_entry(ledger, *, kind, trigger, lesson, ticket, finding):
    key = (kind, trigger, normalize(lesson))
    for e in ledger["learnings"]:
        if (e.get("kind"), e.get("trigger"), normalize(e.get("lesson"))) == key:
            if ticket and ticket not in e.setdefault("seen_tickets", []):
                e["seen_tickets"].append(ticket)
            lib.bump_confidence(e)
            e["updated_at"] = lib.now_iso()
            return e
    entry = {
        "id": "L-%d" % (len(ledger["learnings"]) + 1),
        "kind": kind,
        "trigger": trigger,
        "lesson": lesson.strip(),
        "evidence": {"ticket": ticket, "finding": finding},
        "confidence": "provisional",
        "seen_tickets": [ticket] if ticket else [],
        "created_at": lib.now_iso(),
        "updated_at": lib.now_iso(),
    }
    lib.bump_confidence(entry)
    ledger["learnings"].append(entry)
    return entry


def _resolve(explicit_ticket):
    cwd = os.getcwd()
    try:
        ctx = lib.build_context(cwd)
    except lib.GateError as exc:
        sys.stderr.write("acs learn: %s\n" % exc)
        sys.exit(2)
    return ctx["workspace"], ctx["repo_id"]


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("--kind", required=True, choices=KINDS)
    p_add.add_argument("--trigger", required=True)
    p_add.add_argument("--lesson", required=True)
    p_add.add_argument("--ticket")
    p_add.add_argument("--finding")

    p_prom = sub.add_parser("promote")
    p_prom.add_argument("--id", required=True)
    p_prom.add_argument("--to", required=True, choices=["established", "core"])
    p_prom.add_argument("--ticket")

    p_list = sub.add_parser("list")
    p_list.add_argument("--min-confidence", choices=list(lib.CONFIDENCE_ORDER), default="provisional")
    p_list.add_argument("--ticket")

    args = parser.parse_args()
    workspace, repo_id = _resolve(args.ticket)
    ledger = load_ledger(workspace, repo_id)

    if args.cmd == "add":
        entry = add_entry(ledger, kind=args.kind, trigger=args.trigger,
                          lesson=args.lesson, ticket=args.ticket, finding=args.finding)
        lib.write_json(lib.learnings_path(workspace, repo_id), ledger)
        print(json.dumps(entry, indent=2))
        return

    if args.cmd == "promote":
        for e in ledger["learnings"]:
            if e.get("id") == args.id:
                e["confidence"] = args.to
                e["updated_at"] = lib.now_iso()
                lib.write_json(lib.learnings_path(workspace, repo_id), ledger)
                print(json.dumps(e, indent=2))
                return
        sys.stderr.write("acs learn: no entry %s\n" % args.id)
        sys.exit(2)

    if args.cmd == "list":
        floor = lib.CONFIDENCE_ORDER[args.min_confidence]
        wanted = [e for e in ledger["learnings"]
                  if lib.CONFIDENCE_ORDER.get(e.get("confidence"), 0) >= floor]
        print(json.dumps({"repo_id": repo_id, "count": len(wanted), "learnings": wanted}, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.acs.test_learn -v`
Expected: PASS (7 tests total)

- [ ] **Step 5: Commit**

```bash
git add plugins/acs/hooks/scripts/learn.py tests/acs/test_learn.py
git commit -m "MAR-N add learn.py add/promote/list with de-dup and confidence bump"
```

---

### Task 3: `learnings_digest` — the bounded, safe read path

**Files:**
- Modify: `plugins/acs/hooks/scripts/acs_lib.py` (add after `bump_confidence`)
- Test: `tests/acs/test_learn.py` (extend)

**Interfaces:**
- Consumes: `read_json`, `learnings_path`, `CONFIDENCE_ORDER`, `LEARNINGS_DIGEST_MAX`, `LEARNINGS_DIGEST_CHAR_CAP`, `parse_iso` (`acs_lib.py:344`).
- Produces:
  - `learnings_digest(workspace, repo_id, context_text, *, enabled=True, max_entries=LEARNINGS_DIGEST_MAX) -> list[dict]` — selects `established`/`core` entries whose `trigger` substring-appears in `context_text` (case-insensitive), ranks by `(CONFIDENCE_ORDER desc, updated_at desc)`, truncates to `max_entries` and to `LEARNINGS_DIGEST_CHAR_CAP` total lesson chars. Returns `[]` when `enabled` is False. NEVER returns a `provisional` entry.

- [ ] **Step 1: Write the failing test**

Append to `tests/acs/test_learn.py`:

```python
class TestLearningsDigest(unittest.TestCase):
    def _write(self, tmp, entries):
        import json as _json
        os.makedirs(os.path.join(tmp, "r"), exist_ok=True)
        with open(os.path.join(tmp, "r", "learnings.json"), "w") as fh:
            _json.dump({"repo_id": "r", "learnings": entries}, fh)

    def _entry(self, id_, conf, trigger, updated, lesson="L"):
        return {"id": id_, "kind": "convention", "trigger": trigger, "lesson": lesson,
                "confidence": conf, "seen_tickets": [], "updated_at": updated,
                "created_at": updated, "evidence": {}}

    def test_provisional_never_injected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, [self._entry("L-1", "provisional", "pr", "2026-07-01T00:00:00Z")])
            out = lib.learnings_digest(tmp, "r", "touching pr-conventions.py")
            self.assertEqual(out, [])

    def test_established_matching_trigger_is_injected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, [self._entry("L-1", "established", "pr-conventions", "2026-07-01T00:00:00Z")])
            out = lib.learnings_digest(tmp, "r", "editing pr-conventions.py now")
            self.assertEqual([e["id"] for e in out], ["L-1"])

    def test_non_matching_trigger_excluded(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, [self._entry("L-1", "established", "zzz-nomatch", "2026-07-01T00:00:00Z")])
            out = lib.learnings_digest(tmp, "r", "editing pr-conventions.py")
            self.assertEqual(out, [])

    def test_core_ranks_above_established(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, [
                self._entry("L-1", "established", "pr", "2026-07-09T00:00:00Z"),
                self._entry("L-2", "core", "pr", "2026-07-01T00:00:00Z"),
            ])
            out = lib.learnings_digest(tmp, "r", "pr stuff")
            self.assertEqual([e["id"] for e in out], ["L-2", "L-1"])

    def test_max_entries_bound(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, [self._entry("L-%d" % i, "established", "pr", "2026-07-0%dT00:00:00Z" % (i+1))
                              for i in range(9)])
            out = lib.learnings_digest(tmp, "r", "pr", max_entries=7)
            self.assertEqual(len(out), 7)

    def test_disabled_returns_empty(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, [self._entry("L-1", "core", "pr", "2026-07-01T00:00:00Z")])
            self.assertEqual(lib.learnings_digest(tmp, "r", "pr", enabled=False), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.acs.test_learn -v`
Expected: FAIL — `learnings_digest` undefined.

- [ ] **Step 3: Write minimal implementation**

In `acs_lib.py`, after `bump_confidence`, add:

```python
def learnings_digest(workspace, repo_id, context_text, *, enabled=True,
                     max_entries=LEARNINGS_DIGEST_MAX):
    """Bounded, safe read path for skill-start injection. Returns established/core
    entries whose trigger substring-appears (case-insensitive) in context_text,
    ranked confidence-then-recency, capped at max_entries and a total char cap.
    NEVER returns a provisional entry. Returns [] when disabled."""
    if not enabled:
        return []
    data = read_json(learnings_path(workspace, repo_id)) or {}
    haystack = (context_text or "").lower()
    candidates = []
    for e in data.get("learnings", []):
        if CONFIDENCE_ORDER.get(e.get("confidence"), 0) < CONFIDENCE_ORDER["established"]:
            continue  # provisional never injected
        trig = (e.get("trigger") or "").lower()
        if not trig or trig not in haystack:
            continue
        candidates.append(e)

    def sort_key(e):
        dt = parse_iso(e.get("updated_at")) or parse_iso("1970-01-01T00:00:00Z")
        return (CONFIDENCE_ORDER.get(e.get("confidence"), 0), dt)

    candidates.sort(key=sort_key, reverse=True)

    out, chars = [], 0
    for e in candidates:
        if len(out) >= max_entries:
            break
        chars += len(e.get("lesson") or "")
        if chars > LEARNINGS_DIGEST_CHAR_CAP:
            break
        out.append(e)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.acs.test_learn -v`
Expected: PASS (13 tests total)

- [ ] **Step 5: Commit**

```bash
git add plugins/acs/hooks/scripts/acs_lib.py tests/acs/test_learn.py
git commit -m "MAR-N add bounded learnings_digest (provisional never injected)"
```

---

### Task 4: Inject the digest into `skill-start.py`'s context JSON

**Files:**
- Modify: `plugins/acs/hooks/scripts/skill-start.py:209-231` (the main context `print(json.dumps(...))`)
- Test: `tests/acs/test_learn.py` (extend)

**Interfaces:**
- Consumes: `lib.learnings_digest`, the resolved `ctx`, `ticket`, `args.skill`, and `settings`.
- Produces: a new `"learnings"` key in the printed context JSON — a list (possibly empty) from `learnings_digest`. Reads `settings.learnings.enabled` (default True) and `settings.learnings.max_entries` (default `lib.LEARNINGS_DIGEST_MAX`).

- [ ] **Step 1: Write the failing test**

Append to `tests/acs/test_learn.py` a test that calls a small pure helper (added in Step 3) so we don't have to stand up the whole skill-start pipeline:

```python
ss = _load("acs_skill_start", os.path.join(SCRIPTS, "skill-start.py"))


class TestSkillStartDigestField(unittest.TestCase):
    def test_digest_context_text_combines_ticket_and_skill(self):
        ticket = {"id": "MAR-3", "title": "Fix PR gate", "type": "task"}
        text = ss._digest_context_text("code", ticket)
        self.assertIn("fix pr gate", text.lower())
        self.assertIn("code", text.lower())
        self.assertIn("mar-3", text.lower())

    def test_learnings_settings_defaults(self):
        enabled, max_entries = ss._learnings_settings({})
        self.assertTrue(enabled)
        self.assertEqual(max_entries, 7)

    def test_learnings_settings_opt_out(self):
        enabled, _ = ss._learnings_settings({"learnings": {"enabled": False}})
        self.assertFalse(enabled)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.acs.test_learn -v`
Expected: FAIL — `_digest_context_text` / `_learnings_settings` undefined.

- [ ] **Step 3: Write minimal implementation**

In `skill-start.py`, add two module-level helpers above `main()`:

```python
def _digest_context_text(skill, ticket):
    """The haystack learnings triggers are substring-matched against."""
    parts = [skill or "", ticket.get("id") or "", ticket.get("title") or "",
             ticket.get("type") or ""]
    return " ".join(p for p in parts if p)


def _learnings_settings(settings):
    cfg = (settings or {}).get("learnings") or {}
    enabled = cfg.get("enabled", True)
    max_entries = cfg.get("max_entries", lib.LEARNINGS_DIGEST_MAX)
    return enabled, max_entries
```

Then, inside `main()`, immediately before the final `print(json.dumps({...`  (line 209), compute the digest:

```python
    _l_enabled, _l_max = _learnings_settings(ctx["settings"])
    learnings = lib.learnings_digest(
        workspace, repo_id, _digest_context_text(args.skill, ticket),
        enabled=_l_enabled, max_entries=_l_max)
```

And add one line to the printed dict (after `"design": {...},` at line 227):

```python
        "learnings": learnings,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.acs.test_learn -v`
Expected: PASS (16 tests total)

- [ ] **Step 5: Run the full acs suite to confirm no regression**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS (all existing acs tests still green; skill-start still prints valid JSON).

- [ ] **Step 6: Commit**

```bash
git add plugins/acs/hooks/scripts/skill-start.py tests/acs/test_learn.py
git commit -m "MAR-N inject bounded learnings digest into skill-start context JSON"
```

---

### Task 5: Wire capture into SKILL prose (merge-pr + code)

**Files:**
- Modify: `plugins/acs/skills/merge-pr/SKILL.md` (add a distillation step before archival)
- Modify: `plugins/acs/skills/code/SKILL.md` (add opportunistic provisional capture)
- Test: `tests/acs/test_learn.py` (extend — assert the prose contract exists)

**Interfaces:**
- Consumes: the `learn.py add` CLI from Task 2 (called from prose).
- Produces: documented capture behavior. No new code paths — prose instructs the coordinator to shell out to `learn.py add`, honoring `LEARNINGS_CAPTURE_CAP`.

- [ ] **Step 1: Write the failing test**

Append to `tests/acs/test_learn.py`:

```python
class TestSkillProseContract(unittest.TestCase):
    def _read(self, *parts):
        with open(os.path.join(REPO_ROOT, "plugins", "acs", "skills", *parts)) as fh:
            return fh.read()

    def test_merge_pr_documents_distillation(self):
        body = self._read("merge-pr", "SKILL.md")
        self.assertIn("learn.py", body)
        self.assertIn("before archival", body.lower())

    def test_code_documents_opportunistic_capture(self):
        body = self._read("code", "SKILL.md")
        self.assertIn("learn.py", body)
        self.assertIn("provisional", body.lower())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.acs.test_learn -v`
Expected: FAIL — SKILL.md files do not yet mention `learn.py`.

- [ ] **Step 3: Write minimal implementation**

In `plugins/acs/skills/merge-pr/SKILL.md`, in the finalize/archive section (locate the step that runs `post-merge-pr.py` / archives the ticket), add before archival:

```markdown
#### Distill learnings before archival

Before the ticket is archived, capture at most **3** reusable, repo-general
facts from this ticket's `clarifications.json` and verifier findings — the ones
a *future* ticket in this repo would otherwise re-derive. For each, run:

    python3 "$PLUGIN_ROOT/hooks/scripts/learn.py" add \
      --kind <convention|pitfall|architecture|tooling> \
      --trigger "<substring a future task's context will contain, e.g. a filename>" \
      --lesson "<the durable fact, one sentence>" \
      --ticket "<TICKET_ID>" --finding "<evidence, e.g. verifier-iter-2>"

Capture only durable, repo-general facts (conventions, gotchas, architectural
boundaries, tooling quirks) — never ticket-specific detail. If more than 3
qualify, keep the 3 with the strongest evidence and note the rest were dropped.
New facts land as `provisional` and do NOT steer future agents until a second
ticket confirms them (or a human runs `learn.py promote`).
```

In `plugins/acs/skills/code/SKILL.md`, in the reflection-loop / verifier section, add:

```markdown
#### Opportunistic learning capture

When a verifier iteration surfaces a repo-specific gotcha that a future ticket
would hit too, record it as a `provisional` learning (it will not steer any
agent until a second ticket confirms it):

    python3 "$PLUGIN_ROOT/hooks/scripts/learn.py" add \
      --kind pitfall --trigger "<filename or symbol>" \
      --lesson "<the gotcha, one sentence>" \
      --ticket "<TICKET_ID>" --finding "verifier-iter-<n>"

This is optional and best-effort — do not block the loop on it.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.acs.test_learn -v`
Expected: PASS (18 tests total)

- [ ] **Step 5: Run the skill-contract + full suite**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS (test_skill_contracts.py still green with the edited SKILL.md files).

- [ ] **Step 6: Commit**

```bash
git add plugins/acs/skills/merge-pr/SKILL.md plugins/acs/skills/code/SKILL.md tests/acs/test_learn.py
git commit -m "MAR-N wire learnings capture into merge-pr (distill) and code (opportunistic) prose"
```

---

## Self-Review

**1. Spec coverage** (against `docs/design/learnings-ledger.md` + ADR 0035):

| Spec element | Task |
|---|---|
| Repo-tier `learnings.json` beside `tickets-index.json` | Task 1 (`learnings_path`) |
| `learn.py` cloned from `clarify.py`, `add`/`promote`/`list` | Task 2 |
| Entry shape (id/kind/trigger/lesson/evidence/confidence/seen_tickets/timestamps) | Task 2 |
| Confidence ladder + auto-promote at 2 distinct tickets | Task 1 + Task 2 |
| Safety invariant: provisional never injected | Task 3 (tested) |
| Bounded digest (established/core, trigger-match, K=7, char cap, opt-out) | Task 3 + Task 4 |
| Injection at skill-start via context JSON, default-on, opt-out settings | Task 4 |
| Capture: distillation at merge (≤3), opportunistic in code | Task 5 |
| De-dup on (kind, trigger, normalized-lesson) | Task 2 (tested) |
| Testing mirrors clarify pattern, local-only per ADR 0022 | all tasks; no CI LLM calls |

No gaps.

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; every test shows real assertions. SKILL prose uses `<...>` only as documented argument placeholders inside a shell template the coordinator fills at runtime — not plan placeholders.

**3. Type consistency:** `learnings_path`, `bump_confidence`, `learnings_digest`, `CONFIDENCE_ORDER`, `LEARNINGS_DIGEST_MAX`, `LEARNINGS_CAPTURE_CAP` are named identically across Tasks 1/3/4. `add_entry` signature matches its test and its CLI caller in Task 2. `_digest_context_text` / `_learnings_settings` match between Task 4's helper and test.

**Note on ticket id:** steps use `MAR-N` as a placeholder commit prefix — replace `N` with the real ticket id when this ships through the pipeline (rollout-as-epic per ADR 0035). This plan and its design commits are local-only on `design/learnings-ledger`; nothing here pushes or opens a PR.
