from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import settings
from f0rge_core.exceptions import ConflictError

logger = logging.getLogger(__name__)


class ShopifyAdminClient:
    """Thin GraphQL Admin API client. Env token wins over the stored channel token."""

    def __init__(self, shop_domain: str, token: str, api_version: Optional[str] = None) -> None:
        domain = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
        if domain.endswith(".myshopify.com"):
            self.shop_domain = domain
        elif "." not in domain:
            self.shop_domain = f"{domain}.myshopify.com"
        else:
            self.shop_domain = domain
        self.token = token
        self.api_version = api_version or settings.shopify_api_version

    @property
    def _url(self) -> str:
        return f"https://{self.shop_domain}/admin/api/{self.api_version}/graphql.json"

    async def graphql(
        self, query: str, variables: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                self._url,
                headers={
                    "Content-Type": "application/json",
                    "X-Shopify-Access-Token": self.token,
                },
                json={"query": query, "variables": variables or {}},
            )
            response.raise_for_status()
            body = response.json()
        if body.get("errors"):
            raise ConflictError(str(body["errors"]))
        return body.get("data") or {}

    async def set_available_quantities(
        self,
        quantities: list[dict[str, Any]],
        reference: str,
    ) -> None:
        if not quantities:
            return
        data = await self.graphql(
            """
            mutation inventorySetQuantities($input: InventorySetQuantitiesInput!) {
              inventorySetQuantities(input: $input) {
                userErrors { field message }
              }
            }
            """,
            {
                "input": {
                    "name": "available",
                    "reason": "correction",
                    "ignoreCompareQuantity": True,
                    "referenceDocumentUri": reference,
                    "quantities": quantities,
                }
            },
        )
        errors = (data.get("inventorySetQuantities") or {}).get("userErrors") or []
        if errors:
            raise ConflictError(str(errors))

    async def list_locations(self) -> list[dict[str, str]]:
        data = await self.graphql(
            """
            query {
              locations(first: 50) {
                nodes { id name }
              }
            }
            """
        )
        nodes = ((data.get("locations") or {}).get("nodes")) or []
        return [{"gid": node["id"], "name": node["name"]} for node in nodes]

    async def create_fulfillment(self, fulfillment_order_id: str) -> None:
        data = await self.graphql(
            """
            mutation fulfillmentCreate($fulfillment: FulfillmentInput!) {
              fulfillmentCreate(fulfillment: $fulfillment) {
                userErrors { field message }
              }
            }
            """,
            {
                "fulfillment": {
                    "lineItemsByFulfillmentOrder": [{"fulfillmentOrderId": fulfillment_order_id}],
                    "notifyCustomer": False,
                }
            },
        )
        errors = (data.get("fulfillmentCreate") or {}).get("userErrors") or []
        if errors:
            raise ConflictError(str(errors))

    async def fulfillment_order_id_for_order(self, shopify_order_id: str) -> Optional[str]:
        gid = shopify_order_id
        if not gid.startswith("gid://"):
            gid = f"gid://shopify/Order/{shopify_order_id}"
        data = await self.graphql(
            """
            query fulfillmentOrders($id: ID!) {
              order(id: $id) {
                fulfillmentOrders(first: 1) {
                  nodes { id }
                }
              }
            }
            """,
            {"id": gid},
        )
        nodes = (((data.get("order") or {}).get("fulfillmentOrders") or {}).get("nodes")) or []
        if not nodes:
            return None
        return str(nodes[0]["id"])
