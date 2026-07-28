"""Digest-chained AgentRoom state journal regressions."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/ai/skills/agent-room-templates/scripts/state_journal.py"
spec = importlib.util.spec_from_file_location("agentroom_state_journal", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot import AgentRoom state journal helper")
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)


class StateJournal(unittest.TestCase):
    def paths(self, root: Path) -> tuple[Path, Path]:
        return root / "runner/state.json", root / "registry/run.state-head.json"

    def state(self, revision: int = 1) -> dict:
        return {
            "schema": "fixture",
            "run_id": "run",
            "state_revision": revision,
            "value": "initial",
        }

    def test_append_chain_rejects_projection_rollback_and_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_path, head_path = self.paths(Path(temp))
            state = self.state()
            journal.initialize(state_path, head_path, state, "run")
            old_projection = state_path.read_bytes()
            state["value"] = "second"
            journal.append(state_path, head_path, state, "run")
            self.assertEqual(state["state_revision"], 2)
            self.assertEqual(
                journal.load(state_path, head_path, "run"), state,
            )

            state_path.write_bytes(old_projection)
            with self.assertRaisesRegex(journal.JournalError, "projection"):
                journal.load(state_path, head_path, "run", recover=True)

            # Restore the authoritative projection, then alter a journal byte.
            state_path.write_text(
                json.dumps(state, indent=2) + "\n", encoding="utf-8",
            )
            latest = sorted(journal.journal_dir(state_path).glob("*.json"))[-1]
            value = json.loads(latest.read_text(encoding="utf-8"))
            value["state"]["value"] = "forged"
            latest.write_text(json.dumps(value) + "\n", encoding="utf-8")
            with self.assertRaises(journal.JournalError):
                journal.load(state_path, head_path, "run", recover=True)

    def test_one_entry_crash_gap_is_completed_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_path, head_path = self.paths(Path(temp))
            state = self.state()
            journal.initialize(state_path, head_path, state, "run")
            records = journal._scan(state_path)
            next_state = copy.deepcopy(state)
            next_state.update({"state_revision": 2, "value": "pending"})
            entry = journal._entry(next_state, records[-1][1])
            entry_digest = journal.digest(entry)
            entry_path = journal.journal_dir(state_path) / (
                "%020d-%s.json" % (entry["revision"], entry_digest[7:])
            )
            journal._exclusive_json(entry_path, entry)

            recovered = journal.load(
                state_path, head_path, "run", recover=True,
            )
            self.assertEqual(recovered, next_state)
            self.assertEqual(
                json.loads(state_path.read_text(encoding="utf-8")), next_state,
            )
            self.assertEqual(
                json.loads(head_path.read_text(encoding="utf-8"))["revision"], 2,
            )


if __name__ == "__main__":
    unittest.main()
