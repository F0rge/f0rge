"""Release artifact boundary regressions; no credentials or providers are used."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class FirstoutPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (ROOT / ".github/workflows/release-firstout.yml").read_text()
        self.workflow = yaml.safe_load(self.text)
        self.job = self.workflow["jobs"]["tested-image"]
        self.steps = self.job["steps"]

    def test_publication_is_manual_main_only_and_has_no_provider_credentials(
        self,
    ) -> None:
        events = self.workflow.get("on", self.workflow.get(True))
        self.assertEqual(set(events), {"workflow_dispatch"})
        self.assertIn("github.ref == 'refs/heads/main'", self.job["if"])
        self.assertIn("github.repository == 'F0rge/f0rge'", self.job["if"])
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(
            self.job["permissions"], {"contents": "read", "packages": "write"}
        )
        self.assertNotIn("environment", self.job)
        self.assertEqual(
            re.findall(r"secrets\.([A-Za-z_]+)", self.text), ["GITHUB_TOKEN"]
        )
        self.assertNotRegex(
            self.text, r"(?im)^\s*(railway|curl .*graphql|gh workflow run)\b"
        )

    def test_source_is_bound_to_an_existing_release_tag_on_main(self) -> None:
        validate = next(
            step["run"]
            for step in self.steps
            if step.get("name") == "Validate immutable release inputs"
        )
        self.assertIn('"$SOURCE_COMMIT" =~ ^[0-9a-f]{40}$', validate)
        self.assertIn('"$RELEASE_TAG" =~ ^release/firstout-frontend/railway/', validate)
        self.assertIn("refs/tags/$RELEASE_TAG^{commit}", validate)
        self.assertIn(
            'git merge-base --is-ancestor "$SOURCE_COMMIT" origin/main', validate
        )
        self.assertNotIn("${{ inputs.", validate)
        checkouts = [
            step for step in self.steps if step.get("uses") == "actions/checkout@v4"
        ]
        self.assertEqual(len(checkouts), 2)
        self.assertTrue(
            all(step["with"]["persist-credentials"] is False for step in checkouts)
        )

    def test_checks_install_declared_development_tools(self) -> None:
        setup = next(
            step
            for step in self.steps
            if step.get("uses") == "./.github/actions/setup-node-workspace"
        )
        self.assertEqual(setup["env"]["NODE_ENV"], "development")
        tests = next(
            step["run"]
            for step in self.steps
            if step.get("name") == "Test the selected application"
        )
        self.assertIn("firstout-frontend", tests)
        for target in ("lint", "typecheck", "test"):
            self.assertIn(target, tests)
        self.assertIn("--skip-nx-cache", tests)

    def test_one_single_platform_image_is_smoked_before_publication(self) -> None:
        builds = [
            step
            for step in self.steps
            if step.get("uses", "").startswith("docker/build-push-action@")
        ]
        self.assertEqual(len(builds), 1)
        build = builds[0]["with"]
        self.assertEqual(build["platforms"], "linux/amd64")
        self.assertIs(build["load"], True)
        self.assertIs(build["push"], False)
        self.assertIs(build["provenance"], False)
        self.assertIs(build["sbom"], False)
        names = [step.get("name") for step in self.steps]
        self.assertLess(
            names.index("Test the exact production image without external access"),
            names.index("Authenticate publication only"),
        )
        self.assertLess(
            names.index("Test the exact production image without external access"),
            names.index("Publish and verify the tested image"),
        )
        publish = next(
            step["run"]
            for step in self.steps
            if step.get("name") == "Publish and verify the tested image"
        )
        self.assertNotIn("docker build", publish)
        self.assertIn('docker pull --platform linux/amd64 "$PINNED_IMAGE"', publish)
        self.assertIn('"$IMAGE_ID"', publish)

    def test_artifact_identity_and_attempt_are_retained_after_smoke(self) -> None:
        upload = self.steps[-1]
        self.assertEqual(upload["uses"], "actions/upload-artifact@v4")
        self.assertEqual(upload["with"]["name"], "firstout-release-evidence")
        self.assertEqual(upload["with"]["path"], "firstout-release.json")
        self.assertIs(upload["with"]["overwrite"], True)
        for field in (
            "schema_version",
            "source_commit",
            "release_tag",
            "workflow_run_id",
            "workflow_run_attempt",
            "workflow_commit",
            "digest",
            "platform",
            "container_smoke",
        ):
            self.assertIn(field, self.text)
        self.assertNotIn("approved: true", self.text)

    def test_local_build_context_excludes_environment_and_generated_artifacts(
        self,
    ) -> None:
        ignore = (
            (ROOT / "apps/firstout/frontend/Dockerfile.dockerignore")
            .read_text()
            .splitlines()
        )
        rules = [line for line in ignore if line and not line.startswith("#")]
        self.assertEqual(rules[0], "*")
        for pattern in ("**/.env*", "**/.next", "**/node_modules", "**/.superdesign"):
            self.assertIn(pattern, rules)
        allow_index = rules.index("!apps/firstout/frontend/**")
        self.assertGreater(rules.index("**/.env*"), allow_index)
        dockerfile = (ROOT / "apps/firstout/frontend/Dockerfile").read_text()
        for workspace in (
            "marrow/frontend",
            "dk/tag-printer/frontend",
            "firstout/frontend",
            "storefront/commerce",
            "storefront/web",
        ):
            self.assertIn(f"COPY apps/{workspace}/package.json", dockerfile)


if __name__ == "__main__":
    unittest.main()
