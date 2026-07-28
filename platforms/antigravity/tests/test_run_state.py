"""update_run_state.py — the formal run-state-v1 contract (v1.0.17).

The helper is the ONLY writer of .solo/run-state/<run_id>.json. Verified
here: exact lowercase keys, run_id/SHA format validation, git-derived
SHAs (no flag can supply one), monotonic base -> integration -> final
transitions, the frozen final_sha, atomic replacement, schema validation
of both reads and writes, and fail-closed behavior on dirty trees,
tracked runtime state, corrupt state files, and non-git roots."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "plugins", "gate", "skills",
                       "production-readiness-reviewer", "scripts")
URS_PY = os.path.join(SCRIPTS, "update_run_state.py")
GP_PY = os.path.join(REPO, "plugins", "gate", "lib", "gate_policy.py")
SCHEMA = os.path.join(REPO, "plugins", "gate", "skills",
                      "production-readiness-reviewer", "schema",
                      "run-state-v1.schema.json")

gspec = importlib.util.spec_from_file_location("gp_rs", GP_PY)
gp = importlib.util.module_from_spec(gspec)
gspec.loader.exec_module(gp)
uspec = importlib.util.spec_from_file_location("update_run_state_test", URS_PY)
urs_module = importlib.util.module_from_spec(uspec)
uspec.loader.exec_module(urs_module)
xfspec = importlib.util.spec_from_file_location(
    "exe_fixtures_rs", os.path.join(REPO, "tests", "exe_fixtures.py"))
xf = importlib.util.module_from_spec(xfspec)
xfspec.loader.exec_module(xf)


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=cwd,
                          capture_output=True, text=True, timeout=30)


class RunStateHelper(unittest.TestCase):
    RUN_ID = "ftw-42"

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="run-state-")
        self.addCleanup(xf.force_rmtree, self.root)
        with open(os.path.join(self.root, "a.txt"), "w") as f:
            f.write("one\n")
        with open(os.path.join(self.root, ".gitignore"), "w") as f:
            f.write(".solo/gate-evidence/\n.solo/run-state/\n")
        git(self.root, "init", "-q", ".")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")
        self.head = git(self.root, "rev-parse", "HEAD").stdout.strip()

    def urs(self, *args, run_id=None):
        rid = self.RUN_ID if run_id is None else run_id
        return subprocess.run(
            [sys.executable, URS_PY, "--root", self.root,
             "--run-id", rid] + list(args),
            capture_output=True, text=True, timeout=60)

    def state_path(self):
        return os.path.join(self.root, ".solo", "run-state",
                            "%s.json" % self.RUN_ID)

    def state(self):
        with open(self.state_path(), encoding="utf-8") as f:
            return json.load(f)

    def commit_more(self):
        with open(os.path.join(self.root, "a.txt"), "a") as f:
            f.write("more\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "more")
        return git(self.root, "rev-parse", "HEAD").stdout.strip()

    # ---- shape + schema ------------------------------------------------------
    def test_canonical_object_exact_lowercase_keys(self):
        self.assertEqual(self.urs("init").returncode, 0)
        self.assertEqual(self.urs("advance", "base").returncode, 0)
        st = self.state()
        self.assertEqual(st["schema"], "run-state-v1")
        self.assertEqual(st["run_id"], self.RUN_ID)
        self.assertEqual(st["base_sha"], self.head)
        self.assertEqual(sorted(st), ["base_sha", "run_id", "schema"])
        # the shipped schema itself accepts the produced object
        with open(SCHEMA, encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(gp.schema_validate(st, schema), [])
        # uppercase / legacy keys are schema violations
        for bad_key in ("BASE_SHA", "FINAL_SHA", "baseSha", "extra"):
            bad = dict(st)
            bad[bad_key] = "f" * 40
            self.assertTrue(gp.schema_validate(bad, schema), bad_key)

    def test_run_id_format_validated(self):
        for bad in ("", "-leading", "has space", "a" * 65, "x/../y"):
            r = self.urs("init", run_id=bad)
            self.assertEqual(r.returncode, 2, (bad, r.stdout))

    def test_sha_format_is_full_lowercase_hex(self):
        self.assertEqual(self.urs("advance", "final").returncode, 0)
        st = self.state()
        self.assertRegex(st["final_sha"], r"^[0-9a-f]{40}$")

    # ---- derived SHAs, monotonic transitions ---------------------------------
    def test_shas_are_derived_never_supplied(self):
        """No flag exists to pass a SHA — argparse refuses."""
        for extra in (["advance", "base", "--sha", "a" * 40],
                      ["advance", "base", "a" * 40],
                      ["--sha", "a" * 40, "advance", "base"]):
            r = self.urs(*extra)
            self.assertEqual(r.returncode, 2, (extra, r.stdout, r.stderr))
        self.assertFalse(os.path.exists(self.state_path()))

    def test_monotonic_order_and_set_once(self):
        self.assertEqual(self.urs("advance", "base").returncode, 0)
        self.assertEqual(self.urs("advance", "integration").returncode, 0)
        self.assertEqual(self.urs("advance", "final").returncode, 0)
        # rewind attempts are refused once a later field exists
        r = self.urs("advance", "base")
        self.assertEqual(r.returncode, 2)
        self.assertIn("MONOTONIC", r.stdout)
        r = self.urs("advance", "integration")
        self.assertEqual(r.returncode, 2)
        # idempotent same-HEAD re-advance of the newest field is a no-op
        r = self.urs("advance", "final")
        self.assertEqual(r.returncode, 0)
        self.assertIn("no-op", r.stdout)

    def test_set_field_never_changes_at_new_head(self):
        self.assertEqual(self.urs("advance", "base").returncode, 0)
        self.commit_more()
        r = self.urs("advance", "base")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("never changes", r.stdout)
        self.assertEqual(self.state()["base_sha"], self.head)

    def test_frozen_final_sha_never_rewritten(self):
        self.assertEqual(self.urs("advance", "final").returncode, 0)
        new_head = self.commit_more()
        r = self.urs("advance", "final")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("FROZEN", r.stdout)
        st = self.state()
        self.assertEqual(st["final_sha"], self.head)
        self.assertNotEqual(st["final_sha"], new_head)

    def test_verify_binds_to_current_head(self):
        self.assertEqual(self.urs("advance", "final").returncode, 0)
        self.assertEqual(self.urs("verify", "final").returncode, 0)
        self.assertEqual(self.urs("verify", "base").returncode, 1)
        self.commit_more()
        r = self.urs("verify", "final")
        self.assertEqual(r.returncode, 1)
        self.assertIn("VERIFY FAILED", r.stdout)

    # ---- atomicity + fail-closed ---------------------------------------------
    def test_atomic_replacement_leaves_no_temp_files(self):
        self.assertEqual(self.urs("advance", "base").returncode, 0)
        self.assertEqual(self.urs("advance", "final").returncode, 0)
        names = os.listdir(os.path.dirname(self.state_path()))
        self.assertEqual([n for n in names if ".tmp." in n], [], names)

    def test_dirty_tree_refuses_advance(self):
        with open(os.path.join(self.root, "a.txt"), "a") as f:
            f.write("drift\n")
        r = self.urs("advance", "base")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("not clean", r.stdout)
        self.assertFalse(os.path.exists(self.state_path()))

    def test_corrupt_or_foreign_state_fails_closed(self):
        os.makedirs(os.path.dirname(self.state_path()), exist_ok=True)
        with open(self.state_path(), "w") as f:
            f.write("{not json")
        self.assertEqual(self.urs("advance", "base").returncode, 2)
        with open(self.state_path(), "w") as f:
            json.dump({"schema": "run-state-v1", "run_id": "other-run"}, f)
        r = self.urs("advance", "base")
        self.assertEqual(r.returncode, 2)
        self.assertIn("run_id", r.stdout)
        with open(self.state_path(), "w") as f:
            json.dump({"schema": "run-state-v1", "run_id": self.RUN_ID,
                       "FINAL_SHA": "a" * 40}, f)
        r = self.urs("advance", "base")
        self.assertEqual(r.returncode, 2)
        self.assertIn("run-state-v1", r.stdout)

    def test_non_git_root_refused(self):
        plain = tempfile.mkdtemp(prefix="plain-")
        self.addCleanup(xf.force_rmtree, plain)
        r = subprocess.run(
            [sys.executable, URS_PY, "--root", plain,
             "--run-id", self.RUN_ID, "advance", "base"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2)

    def test_tracked_runtime_state_refused(self):
        os.makedirs(os.path.join(self.root, ".solo", "run-state"),
                    exist_ok=True)
        p = os.path.join(self.root, ".solo", "run-state", "old.json")
        with open(p, "w") as f:
            f.write("{}")
        git(self.root, "add", "-f", p)
        git(self.root, "commit", "-qm", "track runtime state (unsupported)")
        r = self.urs("advance", "base")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("TRACKED", r.stdout)

    def test_show_prints_validated_state(self):
        self.assertEqual(self.urs("advance", "base").returncode, 0)
        r = self.urs("show")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["base_sha"], self.head)

    def test_concurrent_initializers_are_serialized(self):
        argv = [sys.executable, URS_PY, "--root", self.root,
                "--run-id", self.RUN_ID, "init"]
        procs = [subprocess.Popen(argv, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
                 for _ in range(4)]
        results = [p.communicate(timeout=60) + (p.returncode,) for p in procs]
        self.assertTrue(all(x[2] == 0 for x in results), results)
        self.assertEqual(self.state(), {"schema": "run-state-v1",
                                        "run_id": self.RUN_ID})
        self.assertTrue(os.path.isfile(self.state_path() + ".lock"))

    def test_transient_lock_bootstrap_permission_errors_are_retried(self):
        lock_path = self.state_path() + ".lock"
        parent = os.path.dirname(lock_path)
        real_open = os.open
        real_makedirs = os.makedirs
        open_attempts = []
        directory_attempts = []

        def directory_briefly_denied(path, *args, **kwargs):
            if path == parent and not directory_attempts:
                directory_attempts.append(path)
                raise PermissionError(13, "simulated Windows sharing violation")
            return real_makedirs(path, *args, **kwargs)

        def briefly_denied(path, flags, mode=0o777, **kwargs):
            if path == lock_path and not open_attempts:
                open_attempts.append(path)
                raise PermissionError(13, "simulated Windows sharing violation")
            return real_open(path, flags, mode, **kwargs)

        with mock.patch.object(urs_module.os, "makedirs",
                               side_effect=directory_briefly_denied), \
                mock.patch.object(urs_module.os, "open",
                               side_effect=briefly_denied), \
                mock.patch.object(urs_module.time, "sleep") as sleep:
            with urs_module.state_lock(lock_path, timeout=1):
                self.assertTrue(os.path.isfile(lock_path))
        self.assertEqual(directory_attempts, [parent])
        self.assertEqual(open_attempts, [lock_path])
        self.assertEqual(sleep.call_args_list,
                         [mock.call(0.05), mock.call(0.05)])

    def test_persistent_lock_bootstrap_permission_error_times_out(self):
        lock_path = self.state_path() + ".lock"
        denied = PermissionError(13, "persistent permission denial")
        with mock.patch.object(urs_module.os, "makedirs",
                               side_effect=denied), \
                mock.patch.object(urs_module.time, "monotonic",
                                  side_effect=[10.0, 11.0]), \
                mock.patch.object(urs_module.time, "sleep") as sleep:
            with self.assertRaisesRegex(
                    TimeoutError, "run-state lock directory"):
                with urs_module.state_lock(lock_path, timeout=0.5):
                    self.fail("persistent permission denial must fail closed")
        sleep.assert_not_called()

    def test_lock_bootstrap_uses_descriptor_stat_and_retries(self):
        lock_path = self.state_path() + ".lock"
        real_fstat = os.fstat
        attempts = []

        def fstat_briefly_denied(fd):
            if not attempts:
                attempts.append(fd)
                raise PermissionError(13, "simulated descriptor sharing violation")
            return real_fstat(fd)

        with mock.patch.object(urs_module.os, "fstat",
                               side_effect=fstat_briefly_denied), \
                mock.patch.object(
                    urs_module.os.path, "getsize",
                    side_effect=AssertionError(
                        "lock bootstrap must not stat the pathname")), \
                mock.patch.object(urs_module.time, "sleep") as sleep:
            with urs_module.state_lock(lock_path, timeout=1):
                self.assertTrue(os.path.isfile(lock_path))
        self.assertEqual(len(attempts), 1)
        sleep.assert_called_once_with(0.05)

    def test_persistent_lock_descriptor_permission_error_times_out(self):
        lock_path = self.state_path() + ".lock"
        denied = PermissionError(13, "persistent descriptor denial")
        with mock.patch.object(urs_module.os, "fstat",
                               side_effect=denied), \
                mock.patch.object(urs_module.time, "monotonic",
                                  side_effect=[20.0, 21.0]), \
                mock.patch.object(urs_module.time, "sleep") as sleep:
            with self.assertRaisesRegex(
                    TimeoutError, "initializing run-state lock"):
                with urs_module.state_lock(lock_path, timeout=0.5):
                    self.fail("persistent descriptor denial must fail closed")
        sleep.assert_not_called()
        with open(lock_path, "ab") as lock_file:
            lock_file.write(b"")

    def test_revision_compare_and_swap_refuses_stale_writer(self):
        self.assertEqual(self.urs("init").returncode, 0)
        with open(SCHEMA, encoding="utf-8") as f:
            schema = json.load(f)
        state, revision, err = urs_module.read_state(
            self.state_path(), self.RUN_ID, schema)
        self.assertIsNone(err)
        externally_changed = dict(state, base_sha=self.head)
        with open(self.state_path(), "w", encoding="utf-8") as f:
            json.dump(externally_changed, f)
        attempted = dict(state, final_sha=self.head)
        self.assertEqual(urs_module.write_state(
            self.state_path(), attempted, schema, revision), 2)
        self.assertEqual(self.state(), externally_changed)

    def test_run_state_directory_symlink_escape_refused(self):
        if not hasattr(os, "symlink"):
            self.skipTest("platform has no symlink support")
        outside = tempfile.mkdtemp(prefix="run-state-outside-")
        self.addCleanup(xf.force_rmtree, outside)
        os.makedirs(os.path.join(self.root, ".solo"), exist_ok=True)
        link = os.path.join(self.root, ".solo", "run-state")
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError:
            self.skipTest("environment refuses directory symlinks")
        r = self.urs("advance", "base")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(os.listdir(outside), [])

    def test_same_directory_state_file_symlink_is_refused(self):
        if not hasattr(os, "symlink"):
            self.skipTest("platform has no symlink support")
        state_dir = os.path.dirname(self.state_path())
        os.makedirs(state_dir, exist_ok=True)
        target = os.path.join(state_dir, "real-state.json")
        expected = {"schema": "run-state-v1", "run_id": self.RUN_ID}
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            json.dump(expected, f)
            f.write("\n")
        try:
            os.symlink(target, self.state_path())
        except OSError:
            self.skipTest("environment refuses file symlinks")
        r = self.urs("init")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("symlink/junction", r.stdout)
        with open(target, encoding="utf-8") as f:
            self.assertEqual(json.load(f), expected)

    def test_same_directory_lock_file_symlink_is_refused(self):
        if not hasattr(os, "symlink"):
            self.skipTest("platform has no symlink support")
        state_dir = os.path.dirname(self.state_path())
        os.makedirs(state_dir, exist_ok=True)
        target = os.path.join(state_dir, "real.lock")
        with open(target, "wb") as f:
            f.write(b"0")
        try:
            os.symlink(target, self.state_path() + ".lock")
        except OSError:
            self.skipTest("environment refuses file symlinks")
        r = self.urs("init")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("symlink/junction", r.stdout)
        self.assertFalse(os.path.exists(self.state_path()))
        with open(target, "rb") as f:
            self.assertEqual(f.read(), b"0")


if __name__ == "__main__":
    unittest.main()
