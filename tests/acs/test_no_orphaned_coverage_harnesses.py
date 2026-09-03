"""Guard against regrowth of orphaned cov_*.py coverage harnesses under
tests/acs/ -- MAR-181 deleted the 9 that had accumulated (cov_codeowners.py
and 8 siblings): each was a stdlib-trace coverage harness invoked only by
hand (python3 tests/acs/cov_<name>.py), never by unittest discover, because
none matched discover's default test*.py filename pattern. That mismatch is
the "discovery blind spot" this guard exists to stop from silently regrowing:
a cov_*.py file can sit in the tree forever, claimed as a live gate in prose,
while contributing nothing to the actual `tests.command` run.

Mirrors the detector-plus-self-test style of
tests/acs/test_testing_conventions_guard.py and the glob-scan style of
tests/acs/test_test_naming_convention.py.
"""

import glob
import os
import tempfile
import unittest

TESTS_ACS = os.path.dirname(os.path.abspath(__file__))


def scan_cov_prefixed_files(directory):
    """Sorted list of cov_*.py files directly under `directory`."""
    return sorted(glob.glob(os.path.join(directory, "cov_*.py")))


class TestNoOrphanedCovHarnesses(unittest.TestCase):

    def test_no_cov_prefixed_files_under_tests_acs(self):
        found = scan_cov_prefixed_files(TESTS_ACS)
        self.assertEqual(
            found, [],
            "cov_*.py file(s) found under tests/acs/: %s -- these don't match "
            "unittest discover's test*.py pattern, so they silently never run "
            "as part of tests.command; rename to test_*.py or delete instead "
            "of letting the discovery blind spot regrow" % found)

    def test_detector_fires_on_a_synthetic_cov_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            planted = os.path.join(tmpdir, "cov_example.py")
            with open(planted, "w", encoding="utf-8") as fh:
                fh.write("# throwaway fixture\n")
            self.assertEqual(scan_cov_prefixed_files(tmpdir), [planted])

    def test_detector_silent_on_a_clean_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            clean = os.path.join(tmpdir, "test_example.py")
            with open(clean, "w", encoding="utf-8") as fh:
                fh.write("# throwaway fixture\n")
            self.assertEqual(scan_cov_prefixed_files(tmpdir), [])


if __name__ == "__main__":
    unittest.main()
