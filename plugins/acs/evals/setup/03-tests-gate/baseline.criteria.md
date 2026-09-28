PASS if, like the reference, the run configures a test command that runs this repo's pytest suite and enforces the coverage target, installs only the tests-and-coverage gate, and reports both.
FAIL if the command does not run pytest or does not enforce a coverage floor, if it installs the convention check or any other gate, or if it asks for anything the request did not leave open.
