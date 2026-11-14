import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() == 0,
                     "cross-user artifact readback runs in the root-owned compiler container")
class BuildArtifactTests(unittest.TestCase):
    def test_private_source_manifest_produces_readable_artifacts(self):
        with tempfile.TemporaryDirectory(prefix="adv360 artifact test ") as temporary:
            workspace = Path(temporary)
            workspace.chmod(0o755)
            for name in ("config", "firmware", "bin"):
                (workspace / name).mkdir(mode=0o755)
            manifest = workspace / "config/west.yml"
            manifest.write_text("manifest: {projects: []}\n")
            manifest.chmod(0o600)
            west = workspace / "bin/west"
            west.write_text(
                "#!" + sys.executable + "\n"
                "import pathlib, sys\n"
                "if sys.argv[1] == 'build':\n"
                "    output = pathlib.Path(sys.argv[sys.argv.index('-d') + 1]) / 'zephyr'\n"
                "    output.mkdir(parents=True)\n"
                "    (output / 'zmk.uf2').write_bytes(b'firmware fixture')\n"
                "    (output / '.config').write_text('CONFIG_TEST=y\\n')\n"
                "elif sys.argv[1:] == ['manifest', '--freeze', '--active-only']:\n"
                "    print('manifest: {projects: []}')\n"
                "else:\n"
                "    raise RuntimeError(sys.argv)\n"
            )
            git = workspace / "bin/git"
            git.write_text("#!/bin/sh\nprintf '%s\\n' dacab4875df72109b96cc8977547a0dc04875bcd\n")
            west.chmod(0o755)
            git.chmod(0o755)
            environment = dict(os.environ, PATH=str(workspace / "bin") + os.pathsep + os.environ["PATH"])
            environment.update(
                TIMESTAMP="202501010000", COMMIT="abc1234", BUILD_RIGHT="true",
                BUILD_SOURCE_REVISION="a" * 40, BUILD_SOURCE_DIRTY="false",
                BUILD_SOURCE_LABEL="test", SOURCE_DATE_EPOCH="1735689600",
                BUILD_IMAGE_REF="compiler@sha256:" + "b" * 64,
            )
            script = Path(__file__).resolve().parents[1] / "bin/build.sh"
            built = subprocess.run(["bash", script], cwd=workspace, env=environment,
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)

            def unprivileged_reader():
                os.setgid(65534)
                os.setuid(65534)

            readback = subprocess.run(
                [sys.executable, "-c",
                 "from pathlib import Path; import sys; "
                 "files = list(Path(sys.argv[1]).iterdir()); "
                 "assert files; [path.read_bytes() for path in files]",
                 str(workspace / "firmware")],
                preexec_fn=unprivileged_reader, capture_output=True, text=True,
            )
            self.assertEqual(readback.returncode, 0, readback.stderr)
            self.assertEqual((workspace / "firmware/west-manifest.yml").read_bytes(), manifest.read_bytes())
            self.assertEqual(manifest.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
