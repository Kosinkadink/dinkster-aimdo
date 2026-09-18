from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_release_manifest.py"
SPEC = importlib.util.spec_from_file_location("build_release_manifest", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
manifest_builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = manifest_builder
SPEC.loader.exec_module(manifest_builder)

VERSION = "0.5.5.post2"
COMMIT = "1" * 40
PLATFORMS = (
    "manylinux2014_aarch64.manylinux_2_17_aarch64",
    "manylinux_2_17_x86_64.manylinux2014_x86_64",
    "win_amd64",
    "win_arm64",
)


class ReleaseManifestTests(unittest.TestCase):
    def make_wheels(self, root: Path, platforms: tuple[str, ...] = PLATFORMS) -> list[Path]:
        wheels = []
        for index, platform_tag in enumerate(platforms):
            wheel = root / f"dinkster_aimdo-{VERSION}-cp39-abi3-{platform_tag}.whl"
            wheel.write_bytes(f"wheel-{index}".encode())
            wheels.append(wheel)
        return wheels

    def test_complete_native_matrix_is_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wheels = self.make_wheels(Path(directory))
            expected_hashes = {
                wheel.name: hashlib.sha256(wheel.read_bytes()).hexdigest() for wheel in wheels
            }
            manifest = manifest_builder.build_manifest(
                wheels,
                repository="Kosinkadink/dinkster-aimdo",
                release_tag=f"v{VERSION}",
                version=VERSION,
                source_commit=COMMIT,
            )
        self.assertEqual(manifest["package"], "dinkster-aimdo")
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["source_commit"], COMMIT)
        entries = manifest["wheels"]
        self.assertEqual(len(entries), 4)
        self.assertEqual({entry["size"] for entry in entries}, {7})
        self.assertEqual(
            {entry["filename"]: entry["sha256"] for entry in entries},
            expected_hashes,
        )
        self.assertIn(
            ["manylinux_2_17_x86_64", "manylinux2014_x86_64"],
            [entry["platform_tags"] for entry in entries],
        )

    def test_missing_platform_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wheels = self.make_wheels(Path(directory), PLATFORMS[:-1])
            with self.assertRaisesRegex(ValueError, "matrix is incomplete"):
                manifest_builder.build_manifest(
                    wheels,
                    repository="Kosinkadink/dinkster-aimdo",
                    release_tag=f"v{VERSION}",
                    version=VERSION,
                    source_commit=COMMIT,
                )

    def test_wrong_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheels = self.make_wheels(root)
            wheels[0] = wheels[0].rename(wheels[0].with_name(wheels[0].name.replace(VERSION, "9.9")))
            with self.assertRaisesRegex(ValueError, "version does not match"):
                manifest_builder.build_manifest(
                    wheels,
                    repository="Kosinkadink/dinkster-aimdo",
                    release_tag=f"v{VERSION}",
                    version=VERSION,
                    source_commit=COMMIT,
                )

    def test_stub_wheel_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheels = self.make_wheels(root)
            stub = root / f"dinkster_aimdo-{VERSION}-py3-none-any.whl"
            stub.write_bytes(b"stub")
            with self.assertRaisesRegex(ValueError, "stable ABI"):
                manifest_builder.build_manifest(
                    wheels + [stub],
                    repository="Kosinkadink/dinkster-aimdo",
                    release_tag=f"v{VERSION}",
                    version=VERSION,
                    source_commit=COMMIT,
                )


if __name__ == "__main__":
    unittest.main()
