"""Smoke-import for marrow_classify_meal DAG module (no Airflow runtime required).

Parses VisionResult + prompt constants; optionally parses the DAG if airflow is installed.
"""

from __future__ import annotations

import ast
import email.message
import importlib.machinery
import importlib.util
import io
import logging
import sys
import types
import urllib.error
from pathlib import Path

import pytest

DAG_PATH = Path(__file__).resolve().parents[2] / "dags" / "classify_meal.py"
SCHEMA_PATH = DAG_PATH.with_name("_vision_schema.py")


def _ensure_module(name: str) -> types.ModuleType:
    existing = sys.modules.get(name)
    if existing is not None and getattr(existing, "__spec__", None) is not None:
        return existing
    module = existing if existing is not None else types.ModuleType(name)
    module.__path__ = []  # type: ignore[attr-defined]
    module.__package__ = name
    # find_spec() raises if a sys.modules entry has __spec__ is None.
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
    sys.modules[name] = module
    return module


def _install_airflow_stubs() -> type[Exception]:
    """Enough of Airflow for classify_meal to import without the runtime."""
    airflow = _ensure_module("airflow")
    exceptions = _ensure_module("airflow.exceptions")

    class AirflowSkipException(Exception):
        pass

    exceptions.AirflowSkipException = AirflowSkipException  # type: ignore[attr-defined]
    airflow.exceptions = exceptions  # type: ignore[attr-defined]

    sdk = _ensure_module("airflow.sdk")

    def dag(**_kwargs):
        def deco(fn):
            return fn

        return deco

    class _Arrow:
        def __rshift__(self, other):
            return other

        def __rrshift__(self, other):
            return self

    def task(fn):
        def _call(*_args, **_kwargs):
            return _Arrow()

        return _call

    sdk.dag = dag  # type: ignore[attr-defined]
    sdk.task = task  # type: ignore[attr-defined]

    for name in (
        "airflow.providers",
        "airflow.providers.common",
        "airflow.providers.common.ai",
        "airflow.providers.common.ai.operators",
    ):
        _ensure_module(name)
    operators = _ensure_module("airflow.providers.common.ai.operators.llm_file_analysis")

    class LLMFileAnalysisOperator:
        def __init__(self, **kwargs):
            self.output = object()
            self.task_id = kwargs.get("task_id")

        def __rshift__(self, other):
            return other

        def __rrshift__(self, other):
            return self

    operators.LLMFileAnalysisOperator = LLMFileAnalysisOperator  # type: ignore[attr-defined]
    return AirflowSkipException


def _load_classify_meal():
    if importlib.util.find_spec("airflow") is None:
        _install_airflow_stubs()
    dag_dir = str(DAG_PATH.parent)
    if dag_dir not in sys.path:
        sys.path.insert(0, dag_dir)
    spec = importlib.util.spec_from_file_location("classify_meal_under_test", DAG_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "http://marrow.test/meal-analysis",
        code,
        "error",
        email.message.Message(),
        io.BytesIO(b'{"detail":"superseded"}'),
    )


@pytest.mark.parametrize("status_code", [410, 404])
def test_classify_callback_superseded_status_skips(monkeypatch, caplog, status_code: int):
    """complete/fail 410 (and legacy 404) skip the task instead of failing the DAG."""
    module = _load_classify_meal()
    monkeypatch.setenv("MARROW_DEV_API_BASE_URL", "http://marrow.test")
    monkeypatch.setenv("MARROW_DEV_AIRFLOW_SERVICE_TOKEN", "token")

    def _raise(*_args, **_kwargs):
        raise _http_error(status_code)

    monkeypatch.setattr(module.urllib.request, "urlopen", _raise)
    from airflow.exceptions import AirflowSkipException

    path = "/api/v1/internal/airflow/meal-analysis/7/complete"
    with caplog.at_level(logging.INFO, logger="_superseded"):
        with pytest.raises(AirflowSkipException, match="superseded"):
            module._marrow_request("POST", path, body={"user_id": "abc"})
    assert f"returned {status_code}" in caplog.text
    assert "skipping superseded meal analysis" in caplog.text


def test_classify_callback_other_http_errors_still_fail(monkeypatch):
    module = _load_classify_meal()
    monkeypatch.setenv("MARROW_DEV_API_BASE_URL", "http://marrow.test")
    monkeypatch.setenv("MARROW_DEV_AIRFLOW_SERVICE_TOKEN", "token")

    def _raise(*_args, **_kwargs):
        raise _http_error(500)

    monkeypatch.setattr(module.urllib.request, "urlopen", _raise)
    with pytest.raises(RuntimeError, match="-> 500"):
        module._marrow_request(
            "POST",
            "/api/v1/internal/airflow/meal-analysis/7/fail",
            body={"error_message": "boom"},
        )


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
    assert '"max_tokens": 8192' in source
    assert 'model_id="openai:google/gemini-3.1-flash-lite"' in source
    assert "pydanticai_openrouter" in source


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
