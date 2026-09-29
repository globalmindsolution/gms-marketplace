"""Each skill's state fragment declares the `states` keys its Finish writes.

`skills/<name>/state.schema.json` is where a skill declares the `states` keys
it owns (step.py §4.4), but the kernel reads only a fragment's `outcome`
vocabulary -- so nothing noticed when a fragment drifted from its skill.
`analyze-requirements` declared `needs_design` while its Finish writes
`ready_for_planning` and `questions_open`; `create-impl-plan` typed `file_map`
as an array while `acs.py filemap set` returns (and the Finish records) an
object. This pins every skill's Finish example to its own fragment.
"""

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))
from acs_lib import schemasubset  # noqa: E402


def finish_example(skill):
    """The first JSON block after `## Finish` in the skill's SKILL.md that
    carries `states`, or None."""
    with open(os.path.join(PLUGIN, "skills", skill, "SKILL.md"), encoding="utf-8") as fh:
        text = fh.read()
    start = text.find("## Finish")
    if start < 0:
        return None
    for block in re.findall(r"```json\n(.*?)\n\s*```", text[start:], re.S):
        try:
            doc = json.loads(re.sub(r"(?m)^ {3}", "", block))
        except ValueError:
            continue
        if isinstance(doc, dict) and isinstance(doc.get("states"), dict):
            return doc
    return None


def fragment(skill):
    path = os.path.join(PLUGIN, "skills", skill, "state.schema.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class FinishExampleMatchesFragmentTest(unittest.TestCase):

    def pairs(self):
        for skill in sorted(os.listdir(os.path.join(PLUGIN, "skills"))):
            frag, doc = fragment(skill), None
            if frag and "states" in (frag.get("properties") or {}):
                doc = finish_example(skill)
            if doc is not None:
                yield skill, frag["properties"]["states"], doc["states"]

    def test_there_is_something_to_check(self):
        self.assertGreaterEqual(len(list(self.pairs())), 2)

    def test_every_finish_example_satisfies_its_fragment(self):
        for skill, states_schema, states in self.pairs():
            with self.subTest(skill=skill):
                errors = ["%s: %s" % (schemasubset.pointer(node), message)
                          for node, message in schemasubset.schema_errors(states_schema, states)]
                self.assertEqual(errors, [], "the Finish example disagrees with "
                                             "skills/%s/state.schema.json" % skill)

    def test_the_two_drifted_fragments_now_declare_what_their_finish_writes(self):
        analyze = fragment("analyze-requirements")["properties"]["states"]["properties"]
        self.assertEqual(sorted(analyze), ["api_surface", "questions_open", "ready_for_planning"])
        plan = fragment("create-impl-plan")["properties"]["states"]["properties"]
        self.assertEqual(plan["file_map"]["type"], "object")



class NoRetiredStatePathsTest(unittest.TestCase):
    """v0.5.0 moved a skill's state from `<partition>/<skill>-state.json`
    (`runs[]`) to `runs/<run-id>/steps/<skill>/state.json` (`invocations[]`),
    and retired `pipeline-state.json`'s `pipeline.flow`. Twelve skill
    documents kept telling the coordinator to read the old files -- which do
    not exist -- until 2026-09-28."""

    RETIRED = re.compile(r"[a-z0-9-]+-state\.json|runs\[-1\]|pipeline\.flow")

    def test_no_skill_or_agent_names_a_retired_state_path(self):
        hits = []
        for folder in ("skills", "agents"):
            for root, _dirs, names in os.walk(os.path.join(PLUGIN, folder)):
                for name in names:
                    if not name.endswith(".md"):
                        continue
                    path = os.path.join(root, name)
                    with open(path, encoding="utf-8") as fh:
                        for n, line in enumerate(fh, 1):
                            for m in self.RETIRED.finditer(line):
                                if m.group(0) not in ("pipeline-state.json", "step-state.json"):
                                    hits.append("%s:%d %s" % (os.path.relpath(path, PLUGIN),
                                                              n, m.group(0)))
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
