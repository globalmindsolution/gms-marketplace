"""/acs:code is four legs over one shared protocol, and both halves must hold.

ADR-0095 split /acs:code's 750-line body into four delivery-path legs --
`code-trivial`, `code-small`, `code-standard`, `code-complex` -- plus four
shared references under `skills/code/references/`. `/acs:code` itself became a
dispatcher. A split like this fails silently in three ways, and each one costs
nothing at load time and everything at the moment it matters:

1. **A pointer that does not resolve.** A leg says to read
   `${CLAUDE_PLUGIN_ROOT}/skills/code/references/<file>.md`; if that file is
   renamed or moved, the leg is a protocol with a hole in it and nothing says so.
2. **A rule that lands in no file.** The shared protocol was carved out of one
   body. A section dropped in the carve is not a failing test anywhere unless
   something asserts the contract as a WHOLE -- SKILL.md plus what it points at.
3. **Drift between the legs.** Four bodies describing one machinery will
   diverge: one leg gains a rule, three do not, and which is authoritative
   becomes a guess.

So what is pinned here is not line counts -- those are a means -- but the
properties that keep the split honest: every pointer resolves, every leg
carries its OWN machinery explicitly, the shared protocol is shared rather than
copied, and the dispatcher dispatches to all four.

Note what is deliberately NOT asserted: that any file is under a particular
length. The <500-line guidance suits skills Claude *consults*; a `code` leg is
a coordinator protocol *executed* start to finish, so most of its body is hot
path by construction. The saving that matters here is machinery, not bytes: a
trivial ticket runs one executor and one verifier where a complex one runs
parallel executors and four merged lenses.

Stdlib-only. Run:  python3 -m unittest tests.acs.test_code_progressive_disclosure -v
"""

import os
import re
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
SKILLS = os.path.join(PLUGIN, "skills")
CODE_DIR = os.path.join(SKILLS, "code")
REFERENCES = os.path.join(CODE_DIR, "references")

#: The four delivery-path legs, cheapest first, and the ceiling each declares.
LEGS = {"code-trivial": 2, "code-small": 2, "code-standard": 3, "code-complex": 3}

#: The shared protocol, split by what a reader needs it for.
SHARED = ("protocol.md", "execute.md", "verify.md", "classify.md")

#: The one pointer spelling that resolves wherever the plugin is installed.
POINTER = re.compile(
    r"\$\{CLAUDE_PLUGIN_ROOT\}/skills/([a-z0-9-]+)/references/([A-Za-z0-9_.-]+\.md)")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def leg_body(name):
    return read(os.path.join(SKILLS, name, "SKILL.md"))


def norm(text):
    return re.sub(r"\s+", " ", text)


class TheSharedProtocolExistsTest(unittest.TestCase):

    def test_every_shared_reference_is_present(self):
        for name in SHARED:
            with self.subTest(reference=name):
                self.assertTrue(os.path.isfile(os.path.join(REFERENCES, name)),
                                "%s is pointed at by the legs; it must exist" % name)

    def test_the_retired_lane_reference_is_gone(self):
        """`lane-changes.md` held the escalation and de-escalation branches.
        ADR-0095 retired both mechanisms, so the file must not linger: a
        reference nobody points at is a rule nobody applies but everybody
        still finds."""
        self.assertFalse(os.path.isfile(os.path.join(REFERENCES, "lane-changes.md")))

    def test_no_reference_describes_the_retired_machinery(self):
        for name in SHARED:
            body = read(os.path.join(REFERENCES, name))
            for token in ("derive_lane", "verify_depth", "escalate_lane", "guard_axes",
                          "VERIFY_ITERATION_CAP", "recommend_stakes"):
                with self.subTest(reference=name, symbol=token):
                    self.assertNotIn(token, body)


class EveryPointerResolvesTest(unittest.TestCase):
    """The failure this class exists for is silent: a pointer to a file that
    is not there costs nothing until the run that needs it."""

    def test_every_pointer_in_every_leg_names_a_file_that_exists(self):
        for leg in LEGS:
            for skill, filename in POINTER.findall(leg_body(leg)):
                target = os.path.join(SKILLS, skill, "references", filename)
                with self.subTest(leg=leg, pointer=filename):
                    self.assertTrue(os.path.isfile(target),
                                    "%s points at %s, which does not exist" % (leg, target))

    def test_the_dispatcher_pointer_resolves_too(self):
        body = read(os.path.join(CODE_DIR, "SKILL.md"))
        found = POINTER.findall(body)
        self.assertTrue(found, "/acs:code must point at the classification rubric")
        for skill, filename in found:
            self.assertTrue(os.path.isfile(os.path.join(SKILLS, skill, "references", filename)))

    def test_no_bare_relative_pointer_survives(self):
        """A bare `references/x.md` has no defined base when a coordinator
        resolves it at runtime, so it reads as present and resolves to nothing."""
        for leg in list(LEGS) + ["code"]:
            body = leg_body(leg) if leg in LEGS else read(os.path.join(CODE_DIR, "SKILL.md"))
            for name in SHARED:
                with self.subTest(skill=leg, reference=name):
                    self.assertNotIn("`references/%s`" % name, body)

    def test_every_leg_says_to_read_the_shared_protocol(self):
        """A reference nobody is told to open is a deleted section with extra
        steps. Each leg must point at the three it runs on."""
        for leg in LEGS:
            body = leg_body(leg)
            for name in ("protocol.md", "execute.md", "verify.md"):
                with self.subTest(leg=leg, reference=name):
                    self.assertIn("references/%s" % name, body)


class EachLegDeclaresItsOwnMachineryTest(unittest.TestCase):
    """The point of four bodies is that a reader learns what a path costs from
    the path's own file. A leg that omits its ceiling, or its verifier shape,
    sends them back to a table somewhere else -- which is the indirection the
    split removed."""

    def test_each_leg_states_its_iteration_ceiling(self):
        for leg, ceiling in LEGS.items():
            with self.subTest(leg=leg):
                self.assertIn("**%d** execute -> verify rounds" % ceiling, leg_body(leg))

    def test_the_cheap_paths_do_not_require_plan_approval(self):
        for leg in ("code-trivial", "code-small"):
            with self.subTest(leg=leg):
                self.assertIn("Plan approval is not required", leg_body(leg))

    def test_the_deep_paths_run_plan_approval_themselves(self):
        """/acs:create-impl-plan cannot run it: it produces the artifact the
        path is judged from, so no path exists yet when it finishes."""
        for leg in ("code-standard", "code-complex"):
            with self.subTest(leg=leg):
                body = leg_body(leg)
                self.assertIn("plan-approval.py", body)
                self.assertIn("Plan approval is enforced", body)

    def test_only_the_complex_path_describes_the_multi_lens_spawn(self):
        """The three single-verifier paths may (and do) say they spawn NO lens —
        that is the useful negative. What they must not carry is the spawn
        itself: four parallel verifiers, the lens-scoped artifacts, the merge."""
        complex_body = norm(leg_body("code-complex"))
        for token in ("4 parallel `acs:code-verifier` subagents", "verdict merge",
                      "iter-<n>-verify-lens-"):
            with self.subTest(token=token):
                self.assertIn(token, complex_body)
        for leg in ("code-trivial", "code-small", "code-standard"):
            body = norm(leg_body(leg))
            for token in ("4 parallel", "verdict merge", "iter-<n>-verify-lens-"):
                with self.subTest(leg=leg, token=token):
                    self.assertNotIn(token, body,
                                     "%s is a single-verifier path; carrying the "
                                     "multi-lens spawn is the drift this catches" % leg)
            self.assertIn("no lens constraint", body,
                          "%s should say plainly that it spawns no lens" % leg)

    def test_only_the_deep_paths_carry_the_ship_context_boundary(self):
        for leg in ("code-standard", "code-complex"):
            with self.subTest(leg=leg):
                self.assertIn("full_verify_stop", leg_body(leg))
        for leg in ("code-trivial", "code-small"):
            with self.subTest(leg=leg):
                self.assertNotIn("full_verify_stop", leg_body(leg))

    def test_no_leg_re_derives_its_own_path(self):
        """A leg is dispatched TO. One that decided its own path would make the
        recorded judgement advisory, which is the whole thing ADR-0095 fixed."""
        for leg in LEGS:
            with self.subTest(leg=leg):
                self.assertIn("never chosen by hand", leg_body(leg))


class TheSharedProtocolIsSharedNotCopiedTest(unittest.TestCase):
    """Four copies of one protocol is the duplication ADR-0094 removed from the
    doc sets. These pin that the carve-out actually carved."""

    def test_the_legs_do_not_restate_the_start_command(self):
        for leg in LEGS:
            with self.subTest(leg=leg):
                self.assertNotIn("skill-start.py --skill code", leg_body(leg),
                                 "Start belongs to references/protocol.md; a leg that "
                                 "restates it owns a second copy that can drift")

    def test_the_shared_protocol_carries_start_branch_and_finish(self):
        body = read(os.path.join(REFERENCES, "protocol.md"))
        for token in ("skill-start.py --skill code", "## Branch", "## Finish",
                      "## Completion report"):
            with self.subTest(section=token):
                self.assertIn(token, body)

    def test_the_agent_names_live_in_the_shared_protocol(self):
        """All four legs spawn the same two agents; they declare no agents of
        their own in phases.yaml, so the names belong in one place."""
        body = read(os.path.join(REFERENCES, "protocol.md"))
        for agent in ("acs:code-executor", "acs:code-verifier"):
            with self.subTest(agent=agent):
                self.assertIn(agent, body)

    def test_no_leg_restates_the_review_dimensions(self):
        for leg in LEGS:
            with self.subTest(leg=leg):
                self.assertNotIn("**Acceptance-criteria conformance**", leg_body(leg))


class TheDispatcherDispatchesTest(unittest.TestCase):

    def test_it_names_a_skill_call_for_every_leg(self):
        body = read(os.path.join(CODE_DIR, "SKILL.md"))
        for leg in LEGS:
            with self.subTest(leg=leg):
                self.assertIn("Skill(acs:%s)" % leg, body)

    def test_it_reads_the_recorded_path_rather_than_judging_by_default(self):
        body = norm(read(os.path.join(CODE_DIR, "SKILL.md")))
        self.assertIn("recorded_delivery_path", body)
        self.assertIn("judged once, from the plan, and recorded", body)

    def test_it_refuses_a_path_passed_as_an_argument(self):
        self.assertIn("Never pass a path as an argument",
                      read(os.path.join(CODE_DIR, "SKILL.md")))

    def test_it_never_implements(self):
        self.assertIn("Never implement", read(os.path.join(CODE_DIR, "SKILL.md")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
