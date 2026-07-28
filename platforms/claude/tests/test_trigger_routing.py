"""Trigger-collision regression tests (T-012, T-013).

Skills are selected by their `description`, so two skills that advertise the
same trigger vocabulary compete and the model picks arbitrarily. Two clusters
had collided badly:

  T-012  site-doctor's `seo-optimization` claimed the whole trigger surface of
         six dedicated seo-plugin skills, and the only cross-reference between
         the plugins was factually wrong (it called seo-optimization a
         "single-page check" when `seo-page` is the single-URL skill).

  T-013  four skills across three plugins all claimed ship-readiness language
         ("is it ready to ship", "preflight", "production ready", "can I ship
         this") with no cross-references at all.

These tests assert the resolution structurally: each skill states a positive
entry condition, states negative conditions naming the neighbours it defers to,
and does not claim a trigger phrase that another skill owns. They are text
contracts, not a live model evaluation -- selection itself cannot be asserted
offline -- so they check the routing information the model is given.
"""
import io
import os
import re
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)


def description(*parts):
    path = os.path.join(REPO, *parts)
    with io.open(path, encoding="utf-8") as stream:
        text = stream.read()
    block = FRONTMATTER.match(text).group(1)
    for line in block.split("\n"):
        if line.startswith("description:"):
            return line[len("description:"):].strip()
    raise AssertionError("no description in %s" % path)


def body(*parts):
    path = os.path.join(REPO, *parts)
    with io.open(path, encoding="utf-8") as stream:
        return stream.read()


SEO_OPT = ("plugins", "site-doctor", "skills", "seo-optimization", "SKILL.md")
SEO_ORCH = ("plugins", "seo", "skills", "seo", "SKILL.md")
SEO_PAGE = ("plugins", "seo", "skills", "seo-page", "SKILL.md")

READINESS = {
    "production-readiness-reviewer":
        ("plugins", "gate", "skills", "production-readiness-reviewer",
         "SKILL.md"),
    "quality-gatekeeper":
        ("plugins", "gate", "skills", "quality-gatekeeper", "SKILL.md"),
    "devops-engineer":
        ("plugins", "release", "skills", "devops-engineer", "SKILL.md"),
    "website-audit":
        ("plugins", "site-doctor", "skills", "website-audit", "SKILL.md"),
}


class SeoTriggerSeparation(unittest.TestCase):
    """T-012."""

    def test_seo_optimization_defers_to_every_specialist_it_used_to_claim(self):
        desc = description(*SEO_OPT)
        self.assertIn("Do NOT use", desc)
        for specialist in ("seo-schema", "seo-sitemap", "seo-hreflang",
                           "seo-geo", "seo-technical", "seo-page"):
            self.assertIn(specialist, desc,
                          "seo-optimization must name %s as the owner of that "
                          "request" % specialist)

    def test_seo_optimization_states_when_it_IS_the_right_skill(self):
        """A negative-only description would make the skill unreachable."""
        desc = description(*SEO_OPT)
        self.assertIn("Use when", desc)
        self.assertIn("not installed", desc.lower())

    def test_orchestrator_no_longer_mislabels_seo_optimization(self):
        """The old text called seo-optimization a "single-page check"."""
        desc = description(*SEO_ORCH)
        self.assertNotIn("seo-optimization single-page check", desc)
        self.assertIn("seo-page", desc,
                      "the orchestrator must point single-URL work at seo-page")
        text = body(*SEO_ORCH)
        self.assertNotIn("fast single-page/single-template check", text)
        self.assertIn("**seo-page** is the single-URL skill", text)

    def test_single_url_requests_route_to_seo_page_only(self):
        page = description(*SEO_PAGE).lower()
        self.assertIn("single-page", page)
        # Neither neighbour may advertise itself as the single-URL skill.
        # Only the POSITIVE half counts: "Do NOT use for a single URL" is the
        # correct deferral and must not be read as a claim.
        for parts in (SEO_OPT, SEO_ORCH):
            head = description(*parts).partition("Do NOT use")[0].lower()
            self.assertNotIn("use for a single url", head)
            self.assertNotIn("single-url skill", head)

    def test_specialist_topics_have_exactly_one_positive_claimant(self):
        """A topic owned by a specialist must not be claimed as a trigger by
        the generalist -- it may only appear behind its 'Do NOT use' clause."""
        desc = description(*SEO_OPT)
        head, _, deferral = desc.partition("Do NOT use")
        self.assertTrue(deferral, "seo-optimization lost its deferral clause")
        for owned in ("hreflang", "XML sitemaps", "GEO/AEO"):
            self.assertNotIn(
                owned, head,
                "%r is a specialist trigger and must sit behind the "
                "'Do NOT use' clause, not in the positive triggers" % owned)


class ShipReadinessSeparation(unittest.TestCase):
    """T-013."""

    def test_each_skill_names_the_other_three(self):
        for name, parts in READINESS.items():
            desc = description(*parts)
            others = [n for n in READINESS if n != name]
            for other in others:
                self.assertIn(
                    other, desc,
                    "%s must say when to defer to %s" % (name, other))

    def test_each_skill_has_an_exclusive_positive_condition(self):
        for name, parts in READINESS.items():
            desc = description(*parts)
            self.assertRegex(desc, r"Use (ONLY )?wh",
                             "%s has no positive entry condition" % name)
            self.assertIn("Do NOT use", desc,
                          "%s has no negative entry condition" % name)

    def test_the_scored_verdict_is_claimed_by_exactly_one_skill(self):
        scorers = [n for n, p in READINESS.items()
                   if re.search(r"14 categories", description(*p))]
        self.assertEqual(scorers, ["production-readiness-reviewer"])

    def test_website_audit_no_longer_claims_launch_readiness(self):
        """It used to trigger on "is this production ready" and
        "pre-launch checklist", which belong to the gate plugin."""
        desc = description(*READINESS["website-audit"])
        head, _, deferral = desc.partition("Do NOT use")
        self.assertTrue(deferral)
        for phrase in ("is this production ready", "pre-launch checklist"):
            self.assertNotIn(phrase, head,
                             "website-audit still claims %r" % phrase)

    def test_devops_engineer_claims_artifacts_not_verdicts(self):
        desc = description(*READINESS["devops-engineer"])
        head, _, deferral = desc.partition("Do NOT use")
        self.assertTrue(deferral)
        self.assertNotIn("am I ready to ship", head)
        for artifact in ("rollback plan", "deployment plan", "CI pipeline",
                         "preflight"):
            self.assertIn(artifact.split()[0].lower(), head.lower(), artifact)

    def test_checkpoint_and_score_do_not_share_a_trigger_phrase(self):
        gate = description(*READINESS["quality-gatekeeper"])
        score = description(*READINESS["production-readiness-reviewer"])
        gate_head = gate.partition("Do NOT use")[0]
        score_head = score.partition("Do NOT use")[0]
        for phrase in ('"can I ship this"', "ready to merge",
                       "ready to deploy"):
            self.assertNotIn(phrase, score_head,
                             "the scorer claims a checkpoint phrase")
        for phrase in ("launch readiness", "how ready are we"):
            self.assertNotIn(phrase, gate_head,
                             "the checkpoint claims a scoring phrase")

    def test_intentional_orchestration_is_preserved(self):
        """quality-gatekeeper still delegates the fourth mode to the scorer,
        and devops-engineer still backs /gate:before-merge."""
        self.assertIn("production-readiness-reviewer",
                      body(*READINESS["quality-gatekeeper"]))
        self.assertIn("/gate:before-merge",
                      body(*READINESS["devops-engineer"]))


if __name__ == "__main__":
    unittest.main()
