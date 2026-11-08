"""Offline behavior checks for deployment selection; no provider calls."""

from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import plan_deploy


def manifest_fixture() -> dict:
    return {
        "components": {
            "marrow-backend": {
                "nx": "marrow-backend",
                "target": "railway",
                "branches": ["main"],
                "railway": {
                    "role": "api",
                    "health_url": {"main": "https://api.example/health"},
                },
                "also_deploys": [
                    {"role": "mcp", "health_url": {"main": "https://mcp.example/mcp"}}
                ],
            },
            "marrow-frontend": {
                "nx": "marrow-frontend",
                "target": "railway",
                "branches": ["main"],
                "railway": {
                    "role": "frontend",
                    "health_url": {"main": "https://web.example/"},
                },
            },
            "printer": {
                "nx": "printer",
                "target": "coolify",
                "branches": ["main"],
                "coolify": {
                    "app_uuid": "fixture-app",
                    "webhook_secret_env": "FIXTURE_WEBHOOK",
                },
                "health_url": "https://printer.example/health",
            },
        }
    }


class DeployPlanTests(unittest.TestCase):
    def run_plan(
        self,
        manifest: dict,
        affected: set[str],
        **environment: str,
    ) -> tuple[dict, object]:
        env = {
            "ENVIRONMENT": "main",
            "COMPONENT": "auto",
            "NX_BASE": "base",
            "NX_HEAD": "head",
            **environment,
        }
        output = io.StringIO()
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(plan_deploy.yaml, "safe_load", return_value=manifest),
            patch.object(plan_deploy, "_nx_affected", return_value=affected) as nx,
            redirect_stdout(output),
        ):
            plan_deploy.main()
        # Equal-base diagnostics precede the final JSON object.
        body = output.getvalue()
        return json.loads(body[body.index("{\n") :]), nx

    def test_selects_affected_railway_and_coolify_components(self) -> None:
        plan, nx = self.run_plan(manifest_fixture(), {"marrow-backend", "printer"})
        self.assertEqual(plan["deploy_api"], "true")
        self.assertEqual(plan["deploy_mcp"], "true")
        self.assertEqual(plan["deploy_frontend"], "false")
        self.assertEqual(plan["api_health_url"], "https://api.example/health")
        self.assertEqual(plan["mcp_health_url"], "https://mcp.example/mcp")
        self.assertEqual(
            json.loads(plan["coolify_matrix"]),
            [
                {
                    "name": "printer",
                    "app_uuid": "fixture-app",
                    "webhook_secret_env": "FIXTURE_WEBHOOK",
                    "health_url": "https://printer.example/health",
                    "host": "",
                }
            ],
        )
        nx.assert_called_once_with("base", "head")

    def test_no_affected_projects_emits_no_deployment(self) -> None:
        plan, _ = self.run_plan(manifest_fixture(), set())
        self.assertEqual(plan["deploy_api"], "false")
        self.assertEqual(plan["deploy_mcp"], "false")
        self.assertEqual(plan["deploy_frontend"], "false")
        self.assertEqual(json.loads(plan["coolify_matrix"]), [])

    def test_manual_selection_respects_manifest_branch(self) -> None:
        plan, nx = self.run_plan(
            manifest_fixture(), set(), COMPONENT="all", ENVIRONMENT="unlisted"
        )
        self.assertEqual(plan["deploy_api"], "false")
        self.assertEqual(plan["deploy_mcp"], "false")
        self.assertEqual(plan["deploy_frontend"], "false")
        self.assertEqual(json.loads(plan["coolify_matrix"]), [])
        nx.assert_not_called()

    def test_equal_base_checks_marrow_and_uses_parent_for_coolify(self) -> None:
        plan, nx = self.run_plan(
            manifest_fixture(), {"printer"}, NX_BASE="head", NX_PARENT="parent"
        )
        self.assertEqual(plan["deploy_api"], "true")
        self.assertEqual(plan["deploy_mcp"], "true")
        self.assertEqual(plan["deploy_frontend"], "true")
        self.assertEqual(plan["coolify_diff_base"], "parent")
        self.assertEqual(json.loads(plan["coolify_matrix"])[0]["name"], "printer")
        nx.assert_called_once_with("parent", "head")

    def test_unsupported_or_missing_target_fails_before_selection(self) -> None:
        for target in ("retired-provider", None):
            with self.subTest(target=target):
                manifest = manifest_fixture()
                manifest["components"]["printer"]["target"] = target
                with (
                    patch.dict(
                        os.environ,
                        {"ENVIRONMENT": "main", "COMPONENT": "all"},
                        clear=True,
                    ),
                    patch.object(plan_deploy.yaml, "safe_load", return_value=manifest),
                    patch.object(plan_deploy, "_nx_affected") as nx,
                    redirect_stdout(io.StringIO()) as output,
                    self.assertRaisesRegex(ValueError, "Unsupported deploy target"),
                ):
                    plan_deploy.main()
                self.assertEqual(output.getvalue(), "")
                nx.assert_not_called()

    def test_selected_target_requires_its_own_config(self) -> None:
        for missing in (None, "wrong-shape"):
            with self.subTest(config=missing):
                manifest = manifest_fixture()
                manifest["components"]["marrow-backend"]["railway"] = missing
                error = ValueError if missing is None else TypeError
                with self.assertRaisesRegex(
                    error, "(Missing|Invalid) railway configuration"
                ):
                    self.run_plan(manifest, {"marrow-backend"})


if __name__ == "__main__":
    unittest.main()
