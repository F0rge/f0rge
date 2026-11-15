"""Release artifact boundary regressions; no credentials or providers are used."""

from __future__ import annotations

import ast
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
        self.assertIn('"$RELEASE_TAG" =~ ^release/firstout-api/railway/', validate)
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
        self.assertIn("firstout-backend", tests)
        self.assertIn("--targets=lint,format-check,test", tests)

    def test_component_choice_is_closed_and_preserves_frontend_defaults(self) -> None:
        events = self.workflow.get("on", self.workflow.get(True))
        component = events["workflow_dispatch"]["inputs"]["component"]
        self.assertEqual(component["type"], "choice")
        self.assertEqual(component["options"], ["frontend", "api"])
        self.assertEqual(component["default"], "frontend")
        select = next(
            step["run"]
            for step in self.steps
            if step.get("name") == "Select the closed Firstout component"
        )
        for value in (
            "ghcr.io/f0rge/firstout-frontend",
            "ghcr.io/f0rge/firstout-api",
            "apps/firstout/frontend/Dockerfile",
            "apps/firstout/backend/Dockerfile",
            "firstout-release-evidence",
            "firstout-api-release-evidence",
            "firstout-release.json",
            "firstout-api-release.json",
            "10838be1-7a37-4dfc-810a-8805d040d5d7",
            "77a83033-b75e-4da1-88d0-b6db39bcedaf",
        ):
            self.assertIn(value, select)
        self.assertIn("*) echo 'Unknown Firstout component'", select)
        self.assertNotIn("${{ inputs.", select)

    def test_api_tools_and_checks_are_explicit(self) -> None:
        install = next(
            step
            for step in self.steps
            if step.get("name") == "Install API development dependencies"
        )
        self.assertEqual(install["if"], "env.RELEASE_COMPONENT == 'api'")
        self.assertIn(
            "uv sync --frozen --project apps/firstout/backend", install["run"]
        )
        smoke = next(
            step["run"]
            for step in self.steps
            if step.get("name")
            == "Test the exact production image without external access"
        )
        self.assertIn("firstout-api-container-smoke.py", smoke)
        self.assertIn('--source-commit "$SOURCE_COMMIT"', smoke)
        self.assertIn("firstout-container-smoke.mjs", smoke)

    def test_one_single_platform_image_is_smoked_before_publication(self) -> None:
        builds = [
            step
            for step in self.steps
            if step.get("uses", "").startswith("docker/build-push-action@")
        ]
        self.assertEqual(len(builds), 1)
        build = builds[0]["with"]
        self.assertEqual(build["platforms"], "linux/amd64")
        self.assertEqual(build["file"], "${{ env.IMAGE_DOCKERFILE }}")
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
        self.assertEqual(upload["with"]["name"], "${{ env.EVIDENCE_NAME }}")
        self.assertEqual(upload["with"]["path"], "${{ env.MANIFEST_FILE }}")
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
            "schema_revision",
            "component",
        ):
            self.assertIn(field, self.text)
        self.assertNotIn("approved: true", self.text)
        self.assertIn("smoke.source_commit !== env.SOURCE_COMMIT", self.text)
        self.assertIn("smoke.image_id !== env.IMAGE_ID", self.text)
        self.assertIn("format: true, migrations: true", self.text)

    def test_api_context_excludes_exports_and_frozen_runtime_cannot_sync(self) -> None:
        ignore = (
            (ROOT / "apps/firstout/backend/Dockerfile.dockerignore")
            .read_text()
            .splitlines()
        )
        rules = [line for line in ignore if line and not line.startswith("#")]
        self.assertEqual(rules[0], "*")
        for pattern in (
            "**/.env*",
            "**/.venv",
            "**/__pycache__",
            "**/exports",
            "**/prepared-data",
        ):
            self.assertIn(pattern, rules)
            self.assertGreater(
                rules.index(pattern), rules.index("!apps/firstout/backend/app/**")
            )
        for dependency in ("core", "db", "storage", "testing"):
            self.assertIn(f"!libs/backend/{dependency}/pyproject.toml", rules)
            self.assertIn(f"!libs/backend/{dependency}/src/**", rules)
        self.assertNotIn("!apps/firstout/backend/**", rules)
        dockerfile = (ROOT / "apps/firstout/backend/Dockerfile").read_text()
        self.assertIn("org.opencontainers.image.revision=$SOURCE_COMMIT", dockerfile)
        self.assertIn(
            'CMD ["/app/apps/firstout/backend/.venv/bin/python", "-m", "uvicorn"',
            dockerfile,
        )
        self.assertNotIn('CMD ["uv",', dockerfile)

    def test_api_smoke_has_real_startup_migrations_and_no_external_services(
        self,
    ) -> None:
        smoke = (ROOT / ".github/scripts/firstout-api-container-smoke.py").read_text()
        calls = [
            node
            for node in ast.walk(ast.parse(smoke))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "docker"
        ]
        arguments = [
            [
                argument.value
                for argument in call.args
                if isinstance(argument, ast.Constant)
            ]
            for call in calls
        ]
        self.assertIn('"network", "create", "--internal"', smoke)
        self.assertIn('"postgres:18"', smoke)
        self.assertTrue(
            any(
                all(part in args for part in ["-m", "alembic", "upgrade", "head"])
                for args in arguments
            )
        )
        self.assertIn("NOSUPERUSER NOBYPASSRLS", smoke)
        self.assertIn("TENANT_ISOLATION_MODE=enforced", smoke)
        self.assertIn("PAYMENT_REMINDER_TICKER=false", smoke)
        self.assertIn("SEED_PLAYGROUND=false", smoke)
        self.assertIn("SEED_BOOT_FIXTURES=false", smoke)
        self.assertIn("synthetic.clerk.accounts.dev", smoke)
        self.assertIn("import app.commands.replace_primavera", smoke)
        self.assertIn("assert error.code == 401", smoke)
        self.assertIn("assert 'no-store'", smoke)
        self.assertNotIn("--lifespan", smoke)
        self.assertNotIn('"railway"', smoke.lower())

    def test_api_activates_rls_before_normal_enforced_startup(self) -> None:
        smoke = (ROOT / ".github/scripts/firstout-api-container-smoke.py").read_text()
        calls = [
            node
            for node in ast.walk(ast.parse(smoke))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "docker"
        ]

        def strings(call: ast.Call) -> list[str]:
            return [arg.value for arg in call.args if isinstance(arg, ast.Constant)]

        migration = next(call for call in calls if "alembic" in strings(call))
        activation = next(
            call for call in calls if "app.commands.tenant_cutover" in strings(call)
        )
        startup = next(
            call
            for call in calls
            if "run" in strings(call)
            and "--detach" in strings(call)
            and any(isinstance(arg, ast.Name) and arg.id == "api" for arg in call.args)
        )
        self.assertIn("activate", strings(activation))
        self.assertIn("--rm", strings(activation))
        self.assertLess(migration.lineno, activation.lineno)
        self.assertLess(activation.lineno, startup.lineno)
        activation_source = ast.get_source_segment(smoke, activation)
        self.assertIn("DATABASE_URL={runtime_url}", activation_source)
        self.assertIn("MIGRATION_DATABASE_URL={owner_url}", activation_source)
        self.assertIn("*enforced_env", activation_source)
        self.assertIn("relrowsecurity AND c.relforcerowsecurity", smoke)
        self.assertNotIn("DISABLE ROW LEVEL SECURITY", smoke)

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
