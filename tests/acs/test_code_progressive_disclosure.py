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

#: The four delivery-path legs, cheapest first, and the executor shape each
#: declares. The ITERATION CEILING used to live here, one number per leg; it is
#: `ship.yaml`'s `loops[].max_iterations` now, the same cap on every path,
#: because it was a review property rather than an implementation one (§3.5).
LEGS = {
    "code-trivial": "one, always",
    "code-small": "one, rarely two",
    "code-standard": "one per disjoint file-map partition",
    "code-complex": "one per disjoint file-map partition **+ an integration executor**",
}

#: The shared protocol, split by what a reader needs it for. `verify.md` left
#: with the verifier: the review is `/acs:review-code` and has its own skill.
SHARED = ("protocol.md", "execute.md", "classify.md")

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
                          "VERIFY_ITERATION_CAP", "recommend_stakes",
                          "code-verifier", "validate_xml"):
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
            for name in ("protocol.md", "execute.md"):
                with self.subTest(leg=leg, reference=name):
                    self.assertIn("references/%s" % name, body)


class EachLegDeclaresItsOwnMachineryTest(unittest.TestCase):
    """The point of four bodies is that a reader learns what a path costs from
    the path's own file. A leg that omits its ceiling, or its verifier shape,
    sends them back to a table somewhere else -- which is the indirection the
    split removed."""

    def test_each_leg_states_its_executor_shape(self):
        for leg, shape in LEGS.items():
            with self.subTest(leg=leg):
                self.assertIn(shape, leg_body(leg))

    def test_no_leg_states_an_iteration_ceiling(self):
        """The ceiling is `ship.yaml`'s `loops[].max_iterations`, one cap for
        every path. A leg that restated it would own a second copy of a number
        the workflow decides -- and the four copies used to disagree, 2 on the
        cheap paths and 3 on the deep ones, for reasons that were about the
        REVIEW rather than about implementing."""
        for leg in LEGS:
            with self.subTest(leg=leg):
                body = norm(leg_body(leg))
                self.assertNotIn("execute -> verify rounds", body)
                self.assertNotIn("Iteration ceiling", body)

    def test_the_cheap_paths_do_not_require_plan_approval(self):
        for leg in ("code-trivial", "code-small"):
            with self.subTest(leg=leg):
                self.assertIn("Plan approval is not required", leg_body(leg))

    def test_the_deep_paths_enforce_plan_approval(self):
        """The HOOK enforces it, not the leg: a brake a coordinator applies to
        itself is a brake the coordinator can forget. Each deep leg says so,
        and says what makes an approval stale."""
        for leg in ("code-standard", "code-complex"):
            with self.subTest(leg=leg):
                body = norm(leg_body(leg))
                self.assertIn("**Enforced.**", body)
                self.assertIn("plan-approval.json", body)
                self.assertIn("plan_sha256", body)
                self.assertIn("An edited plan is an unapproved plan", body)

    def test_only_the_complex_path_describes_the_integration_executor(self):
        """This is what now separates `complex` from `standard`. Both partition
        the file map; only `complex` runs a final pass over the SEAMS between
        the partitions -- the concern the four-lens verifier was implicitly
        covering, answered on the implementation side and before the review
        rather than after it."""
        complex_body = norm(leg_body("code-complex"))
        for token in ("integration executor", "union of the partitions' diffs",
                      "intersection of their boundaries"):
            with self.subTest(token=token):
                self.assertIn(token, complex_body)
        for leg in ("code-trivial", "code-small", "code-standard"):
            body = norm(leg_body(leg))
            with self.subTest(leg=leg):
                self.assertNotIn("integration executor", body,
                                 "%s does not run one; carrying the prose is the "
                                 "drift this catches" % leg)

    def test_no_leg_spawns_or_sizes_a_reviewer(self):
        """Every path gets the same review, and the reviewer measures itself
        from the diff. A leg that named a lens count would be declaring a
        property that is not its to declare (§3.6)."""
        for leg in LEGS:
            body = norm(leg_body(leg))
            for token in ("code-verifier", "4 parallel", "verdict merge",
                          "acs:review-code-lens", "spawn the review"):
                with self.subTest(leg=leg, token=token):
                    self.assertNotIn(token, body)
            # Describing the review it will receive is fine and useful; sizing
            # it is not. The reviewer measures the changeset itself.
            self.assertIn("you neither size it nor spawn it", body)

    def test_every_leg_carries_the_loop_contract(self):
        """A leg is half of a loop. On iteration 2+ it answers every confirmed
        finding by id, and there is no third option -- so every leg says so,
        not just the ones a reader happens to open."""
        for leg in LEGS:
            body = norm(leg_body(leg))
            for token in ("resolutions", "resolved_when", "disputed",
                          "since_sha", "verdict.json"):
                with self.subTest(leg=leg, token=token):
                    self.assertIn(token, body)

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
                self.assertNotIn("step start --step code", leg_body(leg),
                                 "Start belongs to references/protocol.md; a leg that "
                                 "restates it owns a second copy that can drift")

    def test_the_shared_protocol_carries_start_branch_and_finish(self):
        body = read(os.path.join(REFERENCES, "protocol.md"))
        for token in ("step start --step code", "## Branch", "## Finish",
                      "## Completion report"):
            with self.subTest(section=token):
                self.assertIn(token, body)

    def test_the_agent_name_lives_in_the_shared_protocol(self):
        """All four legs spawn the same ONE agent -- the verifier left with the
        review -- and they own no agent files themselves, so the name belongs
        in one place."""
        body = read(os.path.join(REFERENCES, "protocol.md"))
        self.assertIn("acs:code-executor", body)
        self.assertNotIn("acs:code-verifier", body)

    def test_no_leg_restates_the_review(self):
        for leg in LEGS:
            with self.subTest(leg=leg):
                body = leg_body(leg)
                self.assertNotIn("**Acceptance-criteria conformance**", body)
                self.assertNotIn("## The dimensions", body)


class TheDispatcherDispatchesTest(unittest.TestCase):

    def test_it_names_a_skill_call_for_every_leg(self):
        body = read(os.path.join(CODE_DIR, "SKILL.md"))
        for leg in LEGS:
            with self.subTest(leg=leg):
                self.assertIn("Skill(acs:%s)" % leg, body)

    def test_it_reads_the_recorded_path_rather_than_judging_by_default(self):
        """The pin is that the dispatcher READS the recorded path, and reads it
        through the CLI. It used to name `plan_contract`, the library module,
        because the SKILL.md open-coded a heredoc around it -- which is the ADR
        0001 violation, not the contract. `acs.py plan path` is the contract."""
        body = norm(read(os.path.join(CODE_DIR, "SKILL.md")))
        self.assertIn('acs.py" plan path', body)
        self.assertNotIn("python3 - <<", body)
        self.assertIn("## Contract", body)
        self.assertIn("judged once, by the plan, and recorded in it", body)

    def test_it_refuses_a_path_passed_as_an_argument(self):
        self.assertIn("Never pass a path as an argument",
                      read(os.path.join(CODE_DIR, "SKILL.md")))

    def test_it_never_implements(self):
        self.assertIn("Never implement", read(os.path.join(CODE_DIR, "SKILL.md")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
