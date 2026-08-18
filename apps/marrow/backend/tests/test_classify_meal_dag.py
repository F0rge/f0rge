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
    assert 'dag_id="marrow_classify_meal"' in source or "dag_id='marrow_classify_meal'" in source
    assert "Never emit null/None in ingredients" in source
    assert "agent_params" in source


def test_dag_vision_result_drops_null_ingredients():
    """Gemini sometimes returns ingredients: [null, null, …]."""
    spec = importlib.util.spec_from_file_location("marrow_vision_schema", SCHEMA_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.VisionResult.model_validate(
        {
            "dish_name": "salad",
            "cuisine": None,
            "confidence": 0.8,
            "ingredients": [
                None,
                {"name": "lettuce", "visible": True, "confidence": 0.9},
                None,
                "tomato",
            ],
        }
    )
    assert [i.name for i in result.ingredients] == ["lettuce", "tomato"]
    empty = module.VisionResult.model_validate(
        {
            "dish_name": "unknown",
            "cuisine": None,
            "confidence": 0,
            "ingredients": [None] * 14,
        }
    )
    assert empty.ingredients == []


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
