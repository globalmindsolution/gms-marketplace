PASS if, like the reference, the run writes a pre-commit configuration with black and ruff hooks, without invoking acs setup or touching acs files.
FAIL if the run invokes /acs:setup, writes any acs configuration, or does not produce the pre-commit configuration.
