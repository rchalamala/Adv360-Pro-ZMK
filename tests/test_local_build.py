import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class LocalBuildTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="adv360 build test ")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        source = Path(__file__).resolve().parents[1]
        shutil.copytree(source / "bin", self.root / "bin")
        for name in ("Makefile", "Dockerfile"):
            shutil.copyfile(source / name, self.root / name)
        (self.root / "config").mkdir()
        self.version = self.root / "config/version.dtsi"
        self.version.write_text("committed version\n")
        subprocess.run(["git", "init", "-q", "-b", "main", self.root], check=True)
        self.git("add", ".")
        self.git(
            "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
            "commit", "-qm", "fixture",
        )
        self.version.write_text("owner's uncommitted version\n")
        (self.root / "firmware").mkdir()
        (self.root / "firmware/existing.uf2").write_text("keep existing firmware\n")
        self.engine = self.root / "engine"
        self.engine.write_text("""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

root = Path(os.environ['TEST_ROOT'])
with (root / 'engine.log').open('a') as log:
    log.write(sys.argv[1] + '\\n')
if os.environ.get('FAIL_PHASE') == 'build' and sys.argv[1] == 'build':
    sys.exit(23)
if sys.argv[1] == 'build':
    Path(sys.argv[sys.argv.index('--iidfile') + 1]).write_text('sha256:built-image')
if sys.argv[1] == 'run':
    assert sys.argv[-1] == 'sha256:built-image', 'must run the image built by this invocation'
    mounts = {}
    values = {}
    for index, value in enumerate(sys.argv):
        if value == '-v':
            source, destination, _ = sys.argv[index + 1].split(':', 2)
            mounts[destination] = Path(source)
        if value == '-e':
            name, value = sys.argv[index + 1].split('=', 1)
            values[name] = value
    version = (mounts['/app/config'] / 'version.dtsi').read_text()
    (root / 'invocation.json').write_text(json.dumps({'values': values, 'version': version}))
    (mounts['/app/firmware'] / 'built.uf2').write_text('built firmware\\n')
    if os.environ.get('FAIL_PHASE') == 'run':
        sys.exit(23)
""")
        self.engine.chmod(0o755)

    def git(self, *args):
        return subprocess.run(["git", "-C", self.root, *args], check=True, capture_output=True)

    def build(self, phase="", target="all"):
        return subprocess.run(
            ["make", f"DOCKER={self.engine}", target], cwd=self.root,
            env=os.environ | {"TEST_ROOT": str(self.root), "FAIL_PHASE": phase,
                              "SOURCE_DATE_EPOCH": "1735689600", "BUILD_SOURCE_LABEL": "test"},
            capture_output=True, text=True,
        )

    def assert_source_preserved(self):
        self.assertEqual(self.version.read_text(), "owner's uncommitted version\n")
        self.assertEqual((self.root / "firmware/existing.uf2").read_text(), "keep existing firmware\n")

    def test_success_preserves_owner_edits_and_builds_from_generated_copy(self):
        self.git("config", "core.abbrev", "12")
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_source_preserved()
        self.assertEqual((self.root / "firmware/built.uf2").read_text(), "built firmware\n")
        invocation = json.loads((self.root / "invocation.json").read_text())
        self.assertIn("macro_ver", invocation["version"])
        self.assertIn(
            "bindings = <&kp N2>, <&kp N0>, <&kp N2>, <&kp N5>, "
            "<&kp N0>, <&kp N1>, <&kp N0>, <&kp N1>,",
            invocation["version"],
        )
        self.assertNotIn("owner's", invocation["version"])
        self.assertEqual(invocation["values"]["TIMESTAMP"], "202501010000")
        self.assertEqual(invocation["values"]["COMMIT"], self.git("rev-parse", "HEAD").stdout.decode()[:7])
        self.assertEqual(invocation["values"]["BUILD_SOURCE_LABEL"], "test")
        self.assertEqual(invocation["values"]["BUILD_RIGHT"], "true")

    def test_build_failure_preserves_owner_edits_and_existing_output(self):
        result = self.build("build")
        self.assertNotEqual(result.returncode, 0)
        self.assert_source_preserved()
        self.assertFalse((self.root / "firmware/built.uf2").exists())
        self.assertEqual((self.root / "engine.log").read_text(), "build\n")

    def test_generator_failure_stops_before_build(self):
        (self.root / "bin/get_version.sh").write_text("#!/usr/bin/env bash\nexit 17\n")
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assert_source_preserved()
        self.assertFalse((self.root / "engine.log").exists())

    def test_failed_container_does_not_publish_partial_output(self):
        result = self.build("run")
        self.assertNotEqual(result.returncode, 0)
        self.assert_source_preserved()
        self.assertFalse((self.root / "firmware/built.uf2").exists())

    def test_left_only_build_keeps_existing_contract(self):
        result = self.build(target="left")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_source_preserved()
        invocation = json.loads((self.root / "invocation.json").read_text())
        self.assertEqual(invocation["values"]["BUILD_RIGHT"], "false")


if __name__ == "__main__":
    unittest.main()
