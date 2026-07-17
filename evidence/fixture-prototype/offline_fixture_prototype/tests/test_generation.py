import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from generate import generate
import verify_generated
from verify_generated import verify


class GeneratedArtifactTests(unittest.TestCase):
    def _rehash_all_generated_manifests(self, output: Path):
        manifests = output / "manifests"
        for manifest in sorted(manifests.glob("*.sha256")):
            if manifest.name == "manifest-root.sha256":
                continue
            rewritten = []
            for line in manifest.read_text().splitlines():
                _, relative = line.split("  ", 1)
                target = verify_generated.REPO_ROOT / relative if manifest.name == "prototype-source-manifest.sha256" else output / relative
                rewritten.append(f"{hashlib.sha256(target.read_bytes()).hexdigest()}  {relative}")
            manifest.write_text("\n".join(rewritten) + "\n")
        root = manifests / "manifest-root.json"
        root_payload = json.loads(root.read_text())
        for filename, key in verify_generated.CHILD_MANIFEST_ROOT_KEYS.items():
            root_payload[key] = "sha256-" + hashlib.sha256((manifests / filename).read_bytes()).hexdigest()
        root.write_text(json.dumps(root_payload, sort_keys=True, separators=(",", ":")) + "\n")
        (manifests / "manifest-root.sha256").write_text(
            hashlib.sha256(root.read_bytes()).hexdigest() + "  manifests/manifest-root.json\n"
        )

    def test_verifier_rederives_semantics_after_full_attacker_rehash(self):
        mutations = {
            "forged_advisory": ("reports/digest-verification-report.json", lambda data: data.__setitem__("advisory_output_digest", "advisory-sha256-" + "f" * 64)),
            "forged_replay": ("reports/fixture-certification-report.json", lambda data: data.__setitem__("replay_identifier", "replay-" + "e" * 64)),
            "contradictory_evidence": ("reports/reproducibility-report.json", lambda data: data.__setitem__("verdict", "NOT_REPRODUCIBLE")),
            "invalid_fixture": ("fixtures/raw/009-observe_indeterminate.json", lambda data: data.clear()),
        }
        for name, (relative, mutate) in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                output = self._generated_copy(directory)
                target = output / relative
                payload = json.loads(target.read_text())
                mutate(payload)
                target.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
                self._rehash_all_generated_manifests(output)
                result = verify(output)
                self.assertEqual(result["verdict"], "NEEDS_REVISION")
                self.assertFalse(result["semantic_derivation_pass"])

    def _tree_hashes(self, root: Path):
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }

    def _generated_copy(self, directory: str) -> Path:
        output = Path(directory) / "artifact"
        generate(output)
        return output

    def _assert_fails_closed(self, output: Path):
        result = verify(output)
        self.assertEqual(result["verdict"], "NEEDS_REVISION")
        self.assertFalse(result["all_manifests_pass"])

    def test_generation_is_byte_deterministic_and_manifests_verify(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir) / "artifact"
            second = Path(second_dir) / "artifact"
            first_result = generate(first)
            second_result = generate(second)
            self.assertEqual(first_result["verdict"], "FIXTURE_PROTOTYPE_READY")
            self.assertEqual(first_result["replay_identifier"], second_result["replay_identifier"])
            self.assertEqual(self._tree_hashes(first), self._tree_hashes(second))
            result = verify(first)
            self.assertEqual(result["verdict"], "FIXTURE_PROTOTYPE_READY")
            digest_report = json.loads((first / "reports" / "digest-verification-report.json").read_text())
            self.assertTrue(digest_report["checks"]["advisory_output_digest_integrity"])
            self.assertTrue(digest_report["advisory_output_digest"].startswith("advisory-sha256-"))

    def test_generated_scope_contains_no_runtime_or_exporter_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            paths = set(self._tree_hashes(output))
            self.assertFalse(any(path.startswith(("runtime/", "exporter/", "policies/", "contracts/")) for path in paths))
            self.assertIn("reports/fixture-certification-report.json", paths)
            self.assertIn("reports/final-validation-report.json", paths)
            self.assertIn("reports/reproducibility-report.json", paths)
            self.assertIn("fixtures/normalized-ledger.jsonl", paths)

    def test_verifier_fails_closed_when_all_manifests_are_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            shutil.rmtree(output / "manifests")
            (output / "manifests").mkdir()
            self._assert_fails_closed(output)

    def test_verifier_fails_closed_when_one_manifest_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            (output / "manifests" / "fixture-manifest.sha256").unlink()
            self._assert_fails_closed(output)

    def test_verifier_fails_closed_for_stale_hash_and_altered_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            target = next((output / "fixtures" / "raw").glob("*.json"))
            target.write_bytes(target.read_bytes() + b" ")
            self._assert_fails_closed(output)

    def test_verifier_fails_closed_for_extra_unmanifested_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            (output / "fixtures" / "unexpected.json").write_text("{}\n")
            self._assert_fails_closed(output)

    def test_verifier_fails_closed_for_unexpected_empty_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            (output / "unexpected-empty-dir").mkdir()
            result = verify(output)
            self.assertEqual(result["verdict"], "NEEDS_REVISION")
            self.assertFalse(result["all_manifests_pass"])

    def test_verifier_fails_closed_for_malformed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            manifest = output / "manifests" / "fixture-manifest.sha256"
            manifest.write_text("not-a-manifest-line\n")
            self._assert_fails_closed(output)

    def test_verifier_fails_closed_for_duplicate_manifest_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            manifest = output / "manifests" / "fixture-manifest.sha256"
            first = manifest.read_text().splitlines()[0]
            manifest.write_text(manifest.read_text() + first + "\n")
            self._assert_fails_closed(output)

    def test_verifier_fails_closed_for_wrong_root(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            root = output / "manifests" / "manifest-root.json"
            payload = json.loads(root.read_text())
            payload["fixture-manifest.sha256"] = "sha256-" + "0" * 64
            root.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
            root_hash = output / "manifests" / "manifest-root.sha256"
            root_hash.write_text(hashlib.sha256(root.read_bytes()).hexdigest() + "  manifests/manifest-root.json\n")
            self._assert_fails_closed(output)

    def test_verifier_fails_closed_for_unreadable_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            manifest = (output / "manifests" / "fixture-manifest.sha256").resolve()
            original_read_bytes = Path.read_bytes

            def guarded_read_bytes(path):
                if path.resolve() == manifest:
                    raise OSError("synthetic unreadable manifest")
                return original_read_bytes(path)

            with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                self._assert_fails_closed(output)

    def test_verifier_fails_closed_for_unexpected_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            (output / "manifests" / "unexpected.sha256").write_text("0" * 64 + "  fixtures/corpus-index.json\n")
            self._assert_fails_closed(output)

    def test_verifier_fails_closed_for_nested_manifest_content(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            nested = output / "manifests" / "unexpected.d"
            nested.mkdir()
            (nested / "payload.sha256").write_text("0" * 64 + "  fixtures/corpus-index.json\n")
            self._assert_fails_closed(output)

    def test_verifier_fails_closed_for_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            (output / "unexpected-link").symlink_to(output / "fixtures", target_is_directory=True)
            self._assert_fails_closed(output)

    def test_verifier_cli_fails_closed_for_symlinked_output_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output = self._generated_copy(directory)
            output_link = base / "artifact-link"
            output_link.symlink_to(output, target_is_directory=True)
            completed = subprocess.run(
                [sys.executable, str(Path(verify_generated.__file__)), "--output", str(output_link)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 1)
            result = json.loads(completed.stdout)
            self.assertEqual(result["verdict"], "NEEDS_REVISION")
            self.assertEqual(result["certification_error"], "output path is a symlink")

    def test_replace_rejects_symlink_output_without_deleting_target(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "sentinel-target"
            target.mkdir()
            sentinel = target / "survives.txt"
            sentinel.write_text("survive\n")
            output_link = base / "artifact"
            output_link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(SystemExit, "symlink"):
                generate(output_link, replace=True)
            self.assertEqual(sentinel.read_text(), "survive\n")

    def test_replace_rejects_existing_non_generated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "artifact"
            output.mkdir()
            sentinel = output / "survives.txt"
            sentinel.write_text("survive\n")
            with self.assertRaisesRegex(SystemExit, "generated-artifact markers"):
                generate(output, replace=True)
            self.assertEqual(sentinel.read_text(), "survive\n")

    def test_replace_rejects_forged_markers_without_deleting_sentinel(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "artifact"
            (output / "manifests").mkdir(parents=True)
            (output / "reports").mkdir()
            (output / "manifests" / "manifest-root.json").write_text("{}\n")
            (output / "reports" / "fixture-certification-report.json").write_text("{}\n")
            sentinel = output / "DO_NOT_DELETE"
            sentinel.write_text("survive\n")
            with self.assertRaisesRegex(SystemExit, "verified generated-artifact tree"):
                generate(output, replace=True)
            self.assertEqual(sentinel.read_text(), "survive\n")

    def test_replace_accepts_verified_generated_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            before = self._tree_hashes(output)
            result = generate(output, replace=True)
            self.assertEqual(result["verdict"], "FIXTURE_PROTOTYPE_READY")
            self.assertEqual(self._tree_hashes(output), before)

    def test_certification_requires_explicit_denied_authority_even_with_rehashed_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self._generated_copy(directory)
            certification = output / "reports" / "fixture-certification-report.json"
            payload = json.loads(certification.read_text())
            payload["production_authority"] = "ALLOWED"
            certification.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")

            for name in ("certification.sha256", "combined-artifact-manifest.sha256"):
                manifest = output / "manifests" / name
                rewritten = []
                for line in manifest.read_text().splitlines():
                    _, relative = line.split("  ", 1)
                    digest = hashlib.sha256((output / relative).read_bytes()).hexdigest()
                    rewritten.append(f"{digest}  {relative}")
                manifest.write_text("\n".join(rewritten) + "\n")

            root = output / "manifests" / "manifest-root.json"
            root_payload = json.loads(root.read_text())
            root_payload["certification_manifest_sha256"] = "sha256-" + hashlib.sha256(
                (output / "manifests" / "certification.sha256").read_bytes()
            ).hexdigest()
            root_payload["combined_artifact_manifest_sha256"] = "sha256-" + hashlib.sha256(
                (output / "manifests" / "combined-artifact-manifest.sha256").read_bytes()
            ).hexdigest()
            root.write_text(json.dumps(root_payload, sort_keys=True, separators=(",", ":")) + "\n")
            (output / "manifests" / "manifest-root.sha256").write_text(
                hashlib.sha256(root.read_bytes()).hexdigest() + "  manifests/manifest-root.json\n"
            )

            result = verify(output)
            self.assertTrue(result["all_manifests_pass"])
            self.assertEqual(result["verdict"], "NEEDS_REVISION")
            self.assertIn("production authority", str(result["certification_error"]))

    def test_verifier_fails_closed_when_source_changes_after_generation(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as source_directory:
            output = self._generated_copy(directory)
            source_root = Path(source_directory)
            source_manifest = output / "manifests" / "prototype-source-manifest.sha256"
            for line in source_manifest.read_text().splitlines():
                _, relative = line.split("  ", 1)
                source = verify_generated.REPO_ROOT / relative
                destination = source_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            first_relative = source_manifest.read_text().splitlines()[0].split("  ", 1)[1]
            changed = source_root / first_relative
            changed.write_bytes(changed.read_bytes() + b"\nchanged-after-generation\n")
            with mock.patch.object(verify_generated, "REPO_ROOT", source_root):
                self._assert_fails_closed(output)


if __name__ == "__main__":
    unittest.main()
