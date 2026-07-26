from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class AirflowClient:
    """Airflow 3 REST client (JWT via POST /auth/token)."""

    def __init__(self) -> None:
        self._token: Optional[str] = None

    def _base_url(self) -> str:
        return settings.airflow_api_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(settings.airflow_api_url.strip())

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        if self._token:
            return self._token
        response = await client.post(
            "/auth/token",
            json={
                "username": settings.airflow_username,
                "password": settings.airflow_password,
            },
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise RuntimeError(
                f"Airflow /auth/token response missing access_token: {response.text}"
            )
        self._token = token
        return token

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async with httpx.AsyncClient(
            base_url=self._base_url(),
            timeout=httpx.Timeout(60.0),
        ) as client:
            token = await self._get_token(client)
            headers = dict(kwargs.pop("headers", {}) or {})
            headers["Authorization"] = f"Bearer {token}"
            response = await client.request(method, path, headers=headers, **kwargs)
            if response.status_code == 401:
                self._token = None
                token = await self._get_token(client)
                headers["Authorization"] = f"Bearer {token}"
                response = await client.request(method, path, headers=headers, **kwargs)
            return response

    async def trigger_meal_analysis(
        self,
        *,
        photo_id: int,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        dag_id = settings.meal_analysis_dag_id
        payload = {
            "logical_date": None,
            "conf": {
                "photo_id": photo_id,
                "user_id": str(user_id),
            },
        }
        response = await self._request(
            "POST",
            f"/api/v2/dags/{dag_id}/dagRuns",
            json=payload,
        )
        if response.status_code >= 400:
            logger.error(
                {
                    "event": "airflow_trigger_failed",
                    "status_code": response.status_code,
                    "body": response.text[:500],
                    "photo_id": photo_id,
                }
            )
            return {
                "error": response.text,
                "status_code": response.status_code,
            }
        data = response.json()
        logger.info(
            {
                "event": "meal_analysis_dag_triggered",
                "dag_run_id": data.get("dag_run_id"),
                "photo_id": photo_id,
            }
        )
        return {
            "dag_run_id": data.get("dag_run_id"),
            "state": data.get("state"),
            "logical_date": data.get("logical_date"),
        }
