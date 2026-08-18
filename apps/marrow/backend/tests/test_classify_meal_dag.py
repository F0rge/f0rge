"""Smoke-import for marrow_classify_meal DAG module (no Airflow runtime required).

Parses VisionResult + prompt constants; optionally parses the DAG if airflow is installed.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

DAG_PATH = Path(__file__).resolve().parents[2] / "dags" / "classify_meal.py"
SCHEMA_PATH = DAG_PATH.with_name("_vision_schema.py")


def test_classify_meal_dag_file_parses():
    source = DAG_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "marrow_classify_meal"
        for node in tree.body
    ) or any(
        isinstance(node, ast.FunctionDef) and node.name == "marrow_classify_meal"
        for node in ast.walk(tree)
    )


def test_vision_result_in_dag_accepts_fixture():
    source = DAG_PATH.read_text(encoding="utf-8")
    from app.services.vision_prompt import VisionResult

    fixture = {
        "dish_name": "rice bowl",
        "cuisine": "japanese",
        "confidence": 0.77,
        "ingredients": [{"name": "rice", "visible": True, "confidence": 0.99}],
    }
    assert VisionResult.model_validate(fixture).dish_name == "rice bowl"
    assert "food identification assistant" in source
    assert "LLMFileAnalysisOperator" in source
    assert "dag_id=DAG_ID" in source
    assert "classify_dag_id" in source
    assert "photos_conn_id" in source
    assert "Never emit null/None in ingredient lists" in source
    assert "agent_params" in source


def test_dag_vision_result_drops_null_ingredients():
    """Gemini sometimes returns ingredient slots as null or nested objects."""
    spec = importlib.util.spec_from_file_location("marrow_vision_schema", SCHEMA_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.VisionResult.model_validate(
        {
            "dish_name": "salad",
            "cuisine": None,
            "confidence": 0.8,
            "visible_ingredients": [
                None,
                {"name": "lettuce"},
                None,
                "tomato",
            ],
            "inferred_ingredients": ["salt", None],
        }
    )
    assert result.visible_ingredients == ["lettuce", "tomato"]
    assert result.inferred_ingredients == ["salt"]
    ings = result.to_marrow_ingredients()
    assert [i["name"] for i in ings] == ["lettuce", "tomato", "salt"]
    assert ings[2]["visible"] is False

    empty = module.VisionResult.model_validate(
        {
            "dish_name": "unknown",
            "cuisine": None,
            "confidence": 0,
            "visible_ingredients": [None] * 14,
        }
    )
    assert empty.visible_ingredients == []
    assert empty.to_marrow_ingredients() == []


def test_dag_vision_result_rejects_identified_dish_without_ingredients():
    spec = importlib.util.spec_from_file_location("marrow_vision_schema", SCHEMA_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(Exception):
        module.VisionResult.model_validate(
            {
                "dish_name": "mixed green salad with orange juice",
                "cuisine": None,
                "confidence": 0.95,
                "visible_ingredients": [],
                "inferred_ingredients": [],
            }
        )


@pytest.mark.skipif(
    importlib.util.find_spec("airflow") is None,
    reason="airflow not installed in marrow test env",
)
def test_dag_import_when_airflow_present():
    spec = importlib.util.spec_from_file_location("classify_meal", DAG_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, "VisionResult")
    assert hasattr(module, "marrow_classify_meal")
    assert module.DAG_ID == "marrow_classify_meal_dev"
    assert module.FILE_CONN_ID == "aws_photos_dev"


BUNDLE_ENV_PATH = DAG_PATH.with_name("_bundle_env.py")
COMPOSE_PATH = Path(__file__).resolve().parents[3] / "airflow" / "docker-compose.yml"


def _load_bundle_env():
    spec = importlib.util.spec_from_file_location("marrow_bundle_env", BUNDLE_ENV_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle_env_from_clone_path():
    env = _load_bundle_env()
    dev = "/opt/airflow/dag_bundles/marrow_dev/versions/abc/apps/marrow/dags/classify_meal.py"
    prod = "/opt/airflow/dag_bundles/marrow_prod/versions/def/apps/marrow/dags/classify_meal.py"
    assert env.marrow_airflow_env(dev) == "dev"
    assert env.classify_dag_id(dag_file=dev) == "marrow_classify_meal_dev"
    assert env.photos_conn_id(dag_file=dev) == "aws_photos_dev"
    assert env.marrow_airflow_env(prod) == "prod"
    assert env.classify_dag_id(dag_file=prod) == "marrow_classify_meal_prod"
    assert env.photos_conn_id(dag_file=prod) == "aws_photos_prod"


def test_bundle_env_local_checkout_defaults_dev():
    env = _load_bundle_env()
    local = str(DAG_PATH)
    assert env.marrow_airflow_env(local) == "dev"
    assert env.classify_dag_id(dag_file=local) == "marrow_classify_meal_dev"


def test_bundle_env_reads_env_specific_url_and_token(monkeypatch):
    env = _load_bundle_env()
    prod = "/opt/airflow/dag_bundles/marrow_prod/versions/sha/apps/marrow/dags/x.py"
    monkeypatch.setenv("MARROW_PROD_API_BASE_URL", "https://api.marrow-health.com/")
    monkeypatch.setenv("MARROW_PROD_AIRFLOW_SERVICE_TOKEN", "prod-token")
    monkeypatch.setenv("MARROW_DEV_API_BASE_URL", "https://api-dev.marrow-health.com")
    monkeypatch.setenv("MARROW_DEV_AIRFLOW_SERVICE_TOKEN", "dev-token")
    assert env.marrow_api_base_url(dag_file=prod) == "https://api.marrow-health.com"
    assert env.marrow_service_token(dag_file=prod) == "prod-token"
    dev = "/opt/airflow/dag_bundles/marrow_dev/versions/sha/apps/marrow/dags/x.py"
    assert env.marrow_api_base_url(dag_file=dev) == "https://api-dev.marrow-health.com"
    assert env.marrow_service_token(dag_file=dev) == "dev-token"


def test_compose_splits_marrow_git_bundles():
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    assert '"name":"marrow_dev"' in text
    assert '"name":"marrow_prod"' in text
    assert '"name":"marrow"' not in text.replace('"name":"marrow_dev"', "").replace(
        '"name":"marrow_prod"', ""
    )
    assert '"tracking_ref":"main"' in text
    assert "MARROW_DEV_API_BASE_URL" in text
    assert "MARROW_PROD_API_BASE_URL" in text
    assert "MARROW_DEV_AIRFLOW_SERVICE_TOKEN" in text
    assert "MARROW_PROD_AIRFLOW_SERVICE_TOKEN" in text
