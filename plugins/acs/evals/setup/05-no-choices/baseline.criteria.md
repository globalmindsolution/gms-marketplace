PASS if, like the reference, the run writes nothing and asks the user to choose a ticket prefix (or keep the default) and whether to install CI checks.
FAIL if the run configures anything without asking, or asks for a workspace location, which setup does not ask for.
