# TABP Toolkit

A Claude Cowork plugin for the TABP team. A home for the team's skills — starting with CV screening, with room to add more.

## Plugin shape

The tabp plugin has grown beyond a simple skills folder. Its full shape is:

- **`skills/`** — Cowork skill definitions (coordinator protocols). `screen-cvs/SKILL.md` now orchestrates a coordinator+subagents flow.
- **`agents/`** — Reusable tabp-namespaced subagent charters spawned by the coordinator: `screen-cv-subagent.md` (Sonnet, one per CV) and `synthesis-subagent.md` (Opus, once per run).
- **`helpers/`** — `tabp_helper.py`: stdlib-only Python helper for atomic `.tabp/` state writes, spin-lock, schema validation, run history, and usage stubs. Invoked via Bash; no external imports.
- **`schemas/`** — JSON Schema contracts for run records, evidence, decisions, history, and lock files. Used by the helper for validation.
- **`.tabp/`** — Per-project state directory (created at runtime in the recruiter's project folder, not in this repo). Holds `runs/<run-id>/run.json`, `evidence-<id>.json`, `decision.json`, `history.json`, and `lock`.

The `screen-cvs` coordinator follows this pattern per run:

1. Calls `tabp_helper.py run-start` (Step 0) to initialise the run record.
2. Fans out one Sonnet subagent per candidate CV in parallel (Step 3a), with each subagent following `agents/screen-cv-subagent.md`.
3. Persists each evidence record via `tabp_helper.py state-write` (Step 3a).
4. Invokes the Opus synthesis subagent once (Step 3a), following `agents/synthesis-subagent.md`.
5. Runs a self-verification pass (Step 5a) before presenting any results.
6. Delivers results only after the self-verification pass finds no blocking findings (Step 6).

If the Cowork runtime denies Bash access, the coordinator falls back to direct file writes (`state_write_mode: "instructed"`). All other steps are unaffected by this degradation.

## Skills

### screen-cvs — Screen CVs against a job description

Screens one CV or a batch of CVs against a job description (JD) and tells you who fits and why.

**What it does**

- Parses the JD into **must-have** and **nice-to-have** requirements.
- Fans out one Sonnet subagent per candidate CV for parallel evidence collection.
- Invokes an Opus synthesis subagent to score, band, and rank the batch.
- Runs a self-verification pass to confirm all evidence is cited and fairness guardrails were followed before presenting results.
- Bands each candidate **Strong / Moderate / Weak** with a **Recommend / Hold / Reject** call.
- Persists all evidence, synthesis, and decision records in the `.tabp/` state directory.

**What you get back**

- An **inline summary** — score, recommendation, top strengths, key gaps, and a short rationale (ranked list first for a batch).
- An **Excel scorecard** — one row per candidate, a column per requirement, overall score, band, recommendation, strengths, gaps, and notes.

**How to use it**

In Cowork, drop in the candidate CV file(s) (PDF or Word) and the job description (a file or pasted text), then ask something like:

- "Screen these CVs against this JD."
- "How well does this resume match the job description?"
- "Rank these candidates for the role and give me a scorecard."

**Built-in fairness guardrails**

The skill scores only job-relevant qualifications and ignores protected characteristics (age, gender, ethnicity, etc.) and their proxies. It treats career gaps neutrally, applies the same criteria to everyone, and flags non-job-relevant requirements in a JD. Results are **decision-support** — the final hiring decision rests with the human recruiter.

## Settings

tabp reads an optional configuration file — `tabp settings.json` — from the
root of the Cowork project folder at skill start. All fields are optional; the
file may be absent, in which case documented defaults apply.

### File location

`<project>/tabp settings.json` — a literal filename with a space, at the
project folder root (NOT inside `.tabp/`). The file is optional and not
committed to this repo; it belongs to the recruiter's project folder.

### Configurable fields

| Field | Default | Description |
|---|---|---|
| `screening_model` | coordinator default Sonnet | Model used for per-CV screening subagents. |
| `synthesis_model` | coordinator default Opus | Model used for the synthesis subagent. |
| `cv_folder` | `./cvs` | Relative path to the CV folder from the project folder. |
| `jd_folder` | `./jds` | Relative path to the JD folder from the project folder. |
| `state_write_mode` | `helper` | How state is written: `helper` (via `tabp_helper.py`) or `instructed` (coordinator writes directly, degraded mode). |

### Observable fallback

When the file is absent or a field is omitted, tabp falls back to the defaults
above. The `settings-read` command reports which keys came from the file
(`from_file`) and which are defaults (`from_default`) so the coordinator can
inform the recruiter. The `settings_source` field in the output envelope is
`"file"` (read), `"absent"` (not found), or `"corrupt"` (found but unreadable).

### Validation

Run this before starting a screening run to confirm the file is structurally
valid:

```
python3 plugins/tabp/helpers/tabp_helper.py settings-validate \
  --project-dir <project-folder>
```

Exit 0: file is absent (no action needed) or valid. Exit 3
(`EXIT_VALIDATION_FAILED`): file exists but is invalid; the error is printed to
stdout as `{"ok": false, "error": "..."}`. The schema contract is in
`plugins/tabp/schemas/settings.schema.json`.

### No secrets

`tabp settings.json` must not contain secrets, passwords, API keys, or a
`workspace_path` key. The validator rejects any such key.


## Inputs & privacy

- **Inputs:** files only (PDF, Word, or pasted text). No external system or ATS connection required.
- **Privacy:** candidate data is treated as confidential and used only for the screening at hand.

## Adding more skills

This plugin is structured to grow. Each new skill lives in its own folder under `skills/`. Subagent charters for a new skill live under `agents/`. Ask Claude to "add a skill to the TABP toolkit" to extend it.
