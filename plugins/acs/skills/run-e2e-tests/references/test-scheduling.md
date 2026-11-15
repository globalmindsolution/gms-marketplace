# Scheduling /acs:run-e2e-tests

`/acs:run-e2e-tests` has no scheduler of its own. It is a pure function of
"which suites, right now", so a scheduled run is an invocation something else
makes at a time it chooses: a cron entry, a scheduled CI workflow, or a Claude
Code routine.

## The recipe

1. Pick the suites. With no flag the run covers every configured suite; one or
   more `--suite <name>` flags narrow it (a nightly suite, say).
2. Invoke the skill headless from the repository's checkout, with acs installed
   and the repo's `.acs/settings.json` present:

   ```bash
   claude -p "/acs:run-e2e-tests --suite nightly"
   ```

3. Let the caller decide when. The skill behaves the same whether a person or a
   schedule invoked it.

## Example snippets

A crontab entry, nightly at 02:17 on the machine that holds the checkout:

```cron
17 2 * * * cd /srv/checkout && claude -p "/acs:run-e2e-tests --suite nightly"
```

A scheduled GitHub Actions job (the runner needs Claude Code and its
credentials):

```yaml
on:
  schedule:
    - cron: "17 2 * * *"
jobs:
  nightly-suites:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: claude -p "/acs:run-e2e-tests --suite nightly"
```

A Claude Code routine whose prompt is `/acs:run-e2e-tests --suite nightly`
does the same without a machine of your own.

## Where results land

Each run writes its results artifact to
`<workspace>/<repo_id>/test-runs/<run-id>/results.json` and leaves it in place;
the newest directory under `test-runs/` is the most recent run. A failing suite
also mints, bumps or links a regression ticket (the skill's Steps 4a and 4b),
so a scheduled failure shows up in the tracker as well as on disk.
