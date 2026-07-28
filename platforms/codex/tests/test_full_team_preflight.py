"""Full Team version and selected-room capability preflight tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "plugins/full-team/skills/full-team-orchestrator/scripts/preflight.py"
)
CONTRACT = (
    ROOT / "plugins/full-team/skills/full-team-orchestrator/"
    "references/component-plugins.json"
)
ROOM = (
    ROOT / "plugins/ai/skills/agent-room-templates/agentsrooms/"
    "full-team-website.json"
)


spec = importlib.util.spec_from_file_location("full_team_preflight", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load Full Team preflight")
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class FullTeamPreflight(unittest.TestCase):
    def test_current_suite_and_complete_room_pass(self):
        result = preflight.preflight(ROOT, ROOM, CONTRACT)
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["components_checked"], 18)
        self.assertGreater(result["commands_checked"], 50)
        self.assertIn("0 problem(s)", result["validator_output"])

    def test_hardening_integrates_seo_and_animation(self):
        room = json.loads(ROOM.read_text(encoding="utf-8"))
        doctor = next(seat for seat in room["seats"] if seat["id"] == "site_doctor")
        self.assertIn("$site-doctor-animation", doctor["commands"])
        self.assertIn("$seo-audit", doctor["commands"])
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        seo = next(item for item in contract["components"] if item["plugin"] == "seo")
        self.assertEqual(seo["representative_skill"], "seo")

    def test_version_skew_and_missing_room_command_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
            contract["components"][0]["minimum_version"] = "99.0.0"
            contract_path = root / "components.json"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            room = json.loads(ROOM.read_text(encoding="utf-8"))
            room["seats"][1]["commands"].append("$missing-preflight-skill")
            room_path = root / "room.json"
            room_path.write_text(json.dumps(room), encoding="utf-8")
            result = preflight.preflight(ROOT, room_path, contract_path)
            self.assertEqual(result["status"], "FAIL")
            text = "\n".join(result["failures"])
            self.assertIn("below required 99.0.0", text)
            self.assertIn("codex plugin add ai@solo-suite-codex", text)
            self.assertIn("$missing-preflight-skill", text)
        self.assertIn("validator rejected", text)

    def test_contract_uses_current_codex_release_floor(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(
            {item["minimum_version"] for item in contract["components"]},
            {"1.0.27"},
        )

    def test_verify_delegates_to_native_preflight_and_uses_codex_installer(self):
        verify = (
            ROOT / "plugins/full-team/skills/full-team-verify/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("full-team-orchestrator/scripts/preflight.py", verify)
        self.assertIn("codex plugin add <plugin-name>@solo-suite-codex", verify)
        self.assertNotIn("/plugin install", verify)

    def test_authoritative_flow_and_compatibility_alias_are_explicit(self):
        orchestrator = (
            ROOT / "plugins/full-team/skills/full-team-orchestrator/SKILL.md"
        ).read_text(encoding="utf-8")
        solo = (
            ROOT / "plugins/solo/skills/solo-full-team-dev/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("authoritative", orchestrator.lower())
        self.assertIn("$solo-full-team-dev", orchestrator)
        self.assertIn("delegates", solo.lower())
        self.assertIn("full-team-orchestrator", solo)
        self.assertNotIn("room-*", solo)

    def test_active_docs_do_not_claim_per_role_agent_files(self):
        paths = list((ROOT / "plugins").glob("**/*.md")) + [
            ROOT / "README.md",
            ROOT / "CHANGELOG.md",
        ]
        offenders = [
            str(path.relative_to(ROOT))
            for path in paths
            if "room-*" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
