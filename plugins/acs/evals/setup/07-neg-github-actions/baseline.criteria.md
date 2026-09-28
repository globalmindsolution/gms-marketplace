PASS if, like the reference, the run writes a GitHub Actions workflow that runs pytest on push and pull request, without invoking acs setup or touching acs files.
FAIL if the run invokes /acs:setup, writes any acs configuration, or does not produce the workflow.
