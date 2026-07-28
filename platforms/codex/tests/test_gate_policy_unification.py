"""Cross-path production-policy regressions for every project profile."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "plugins/gate/lib/gate_policy.py"
DIRECT_CHECKER_PATH = (
    ROOT / "plugins/gate/skills/production-readiness-reviewer/scripts/"
    "check_evidence.py"
)
AGENTROOM_GATE_PATH = (
    ROOT / "plugins/gate/skills/production-readiness-reviewer/scripts/"
    "validate_gate_evidence.py"
)
ROOM_VALIDATOR_PATH = (
    ROOT / "plugins/ai/skills/agent-room-templates/scripts/validate_rooms.py"
)
RUNTIME_TRUST_PATH = (
    ROOT / "plugins/ai/skills/agent-room-templates/scripts/runtime_trust.py"
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = load(POLICY_PATH, "unified_gate_policy")
direct = load(DIRECT_CHECKER_PATH, "unified_direct_gate")
agentroom = load(AGENTROOM_GATE_PATH, "unified_agentroom_gate")
room_validator = load(ROOM_VALIDATOR_PATH, "unified_room_validator")
runtime_trust = load(RUNTIME_TRUST_PATH, "unified_runtime_trust")


PROFILE_NA_FIXTURES = {
    "public-marketing-site": {"backend", "database"},
    "saas-application": set(),
    "e-commerce": set(),
    "internal-application": {"seo", "analytics"},
    "api-service": {"design", "frontend", "seo", "analytics"},
    "library-package": {
        "design", "frontend", "backend", "database", "performance", "seo",
        "analytics",
    },
}


class UnifiedProductionPolicy(unittest.TestCase):
    def test_all_six_profile_matrices_are_shared(self) -> None:
        self.assertEqual(set(PROFILE_NA_FIXTURES), set(policy.PROFILE_ORDER))
        for profile, expected_na in PROFILE_NA_FIXTURES.items():
            expected_labels = frozenset(
                policy.CATEGORY_LABELS[category] for category in expected_na
            )
            with self.subTest(profile=profile):
                self.assertEqual(policy.PROFILE_NA_ALLOWED[profile], expected_na)
                self.assertEqual(direct.PROFILE_NA_ALLOWED[profile], expected_na)
                self.assertEqual(
                    agentroom.PROFILE_NA_ALLOWED[profile], expected_labels
                )
                self.assertEqual(
                    room_validator.PRODUCTION_PROFILE_NA_ALLOWED[profile],
                    expected_labels,
                )

        # Regression names for the four cells that previously disagreed.
        self.assertNotIn("seo", policy.PROFILE_NA_ALLOWED["saas-application"])
        self.assertNotIn("database", policy.PROFILE_NA_ALLOWED["api-service"])
        self.assertNotIn("monitoring", policy.PROFILE_NA_ALLOWED["library-package"])
        self.assertIn("performance", policy.PROFILE_NA_ALLOWED["library-package"])

    def test_categories_mandatory_controls_and_runtime_copy_are_shared(self) -> None:
        self.assertEqual(tuple(direct.ORDERED_CATEGORIES), policy.CATEGORY_ORDER)
        self.assertEqual(agentroom.CATEGORIES, list(policy.CATEGORY_LABEL_ORDER))
        self.assertEqual(
            room_validator.PRODUCTION_CATEGORIES, policy.CATEGORY_LABEL_ORDER
        )
        self.assertEqual(direct.MANDATORY, policy.MANDATORY)
        self.assertEqual(
            agentroom.MANDATORY_CATEGORIES,
            frozenset(policy.CATEGORY_LABELS[item] for item in policy.MANDATORY),
        )
        self.assertEqual(
            room_validator.PRODUCTION_MANDATORY_CATEGORIES,
            agentroom.MANDATORY_CATEGORIES,
        )
        self.assertEqual(
            runtime_trust.RUNTIME_PATHS["gate_policy"],
            "plugins/gate/lib/gate_policy.py",
        )

    def test_all_profiles_have_identical_denominator_score_and_status(self) -> None:
        status_cases = (
            (6, "BLOCKED"),
            (8, "SAFE WITH WARNINGS"),
            (9, "SAFE TO LAUNCH"),
        )
        evaluators = (
            policy.evaluate_production_gate,
            direct.evaluate_production_gate,
            agentroom.evaluate_production_gate,
        )
        for profile, expected_na in PROFILE_NA_FIXTURES.items():
            expected_applicable = tuple(
                category for category in policy.CATEGORY_ORDER
                if category not in expected_na
            )
            for score, expected_status in status_cases:
                scores = {category: score for category in policy.CATEGORY_ORDER}
                summaries = [
                    evaluate(scores, profile, expected_na)
                    for evaluate in evaluators
                ]
                with self.subTest(
                    profile=profile, score=score, status=expected_status
                ):
                    self.assertEqual(summaries[1:], summaries[:-1])
                    summary = summaries[0]
                    self.assertEqual(
                        summary["applicable_categories"], expected_applicable
                    )
                    self.assertEqual(
                        summary["applicable_category_count"],
                        len(expected_applicable),
                    )
                    self.assertEqual(
                        summary["applicable_max"], len(expected_applicable) * 10
                    )
                    self.assertEqual(
                        summary["total_score"], len(expected_applicable) * score
                    )
                    self.assertEqual(summary["normalized_score"], score * 10)
                    self.assertEqual(summary["launch_status"], expected_status)

    def test_warning_and_category_floor_use_the_shared_status_decision(self) -> None:
        scores = {category: 9 for category in policy.CATEGORY_ORDER}
        scores["testing"] = 6
        # 123/140 normalizes to 88, but an applicable category below seven
        # still prevents SAFE TO LAUNCH.
        expected = policy.evaluate_production_gate(scores, "saas-application")
        self.assertEqual(expected["normalized_score"], 88)
        self.assertEqual(expected["launch_status"], "SAFE WITH WARNINGS")
        for evaluate in (
            direct.evaluate_production_gate,
            agentroom.evaluate_production_gate,
        ):
            self.assertEqual(
                evaluate(scores, "saas-application"), expected
            )

        scores["testing"] = 9
        warned = policy.evaluate_production_gate(
            scores, "saas-application", warnings=("accepted risk",)
        )
        self.assertEqual(warned["launch_status"], "SAFE WITH WARNINGS")

    def test_score_and_status_contracts_fail_closed(self) -> None:
        for value, count in ((True, 14), (140, True), (-1, 14), (141, 14),
                             (10, -1), (10, 15)):
            with self.subTest(value=value, count=count):
                with self.assertRaises(ValueError):
                    policy.normalized_score(value, count)
        self.assertEqual(policy.normalized_score(0, 0), 0)
        with self.assertRaises(ValueError):
            policy.expected_launch_status(101, (10,))
        with self.assertRaises(ValueError):
            policy.expected_launch_status(80, ())
        with self.assertRaises(ValueError):
            policy.expected_launch_status(80, (True,))
        self.assertEqual(
            policy.expected_launch_status(80, (8,), blockers=("open",)),
            "BLOCKED",
        )

    def test_evaluator_rejects_profile_matrix_and_score_shape_drift(self) -> None:
        scores = {category: 10 for category in policy.CATEGORY_ORDER}
        with self.assertRaises(ValueError):
            policy.evaluate_production_gate(scores, "unknown")
        with self.assertRaises(ValueError):
            policy.evaluate_production_gate({}, "saas-application")
        with self.assertRaises(ValueError):
            policy.evaluate_production_gate(
                scores, "saas-application", not_applicable=("unknown",)
            )
        with self.assertRaises(ValueError):
            policy.evaluate_production_gate(
                scores, "saas-application", not_applicable=("design",)
            )
        scores["testing"] = 11
        with self.assertRaises(ValueError):
            policy.evaluate_production_gate(scores, "saas-application")

    def test_command_policy_helpers_reject_unsafe_shapes(self) -> None:
        self.assertEqual(
            policy._safe_http_url_shape("https://example.test/a"),
            (True, None),
        )
        for unsafe in (
            "ftp://example.test/a",
            "https://user:pass@example.test/a",
            "https://example.test/a#fragment",
            "https://example.test/a?api_key=secret",
        ):
            with self.subTest(url=unsafe):
                self.assertFalse(policy._safe_http_url_shape(unsafe)[0])
        self.assertEqual(policy._norm_exe("python"), "python")
        self.assertEqual(policy._norm_exe("PYTHON.EXE"), "python")
        self.assertTrue(policy._is_py(sys.executable, ROOT))
        self.assertTrue(policy.resolve_executable(sys.executable, ROOT)[0])
        self.assertIsNotNone(policy.canonical_helper("check_headers.py"))
        self.assertIsNone(policy.canonical_helper("does-not-exist"))


if __name__ == "__main__":
    unittest.main()
