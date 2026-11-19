from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.models.account import Account
from app.models.customer import Customer
from app.models.inventory import LocationStock
from app.models.location import Location, LocationType
from app.models.mcp_token import McpToken
from app.models.sku import Sku
from app.models.team import Team
from app.models.transfer import Transfer, TransferLine, TransferStatus
from app.models.user import User
from app.permissions import TILL_SELL, USERS_MANAGE
from app.services.mcp_domains import READ_ACTIONS
from f0rge_core.exceptions import NotFoundError
from f0rge_db.organisation import current_tenant_id

ACTIONS = {action.name: action for action in READ_ACTIONS}


@pytest.mark.no_db
def test_discovery_catalogue_matches_sidebar_and_rejects_unexpected_filters():
    assert len(ACTIONS) == len(READ_ACTIONS)
    assert {action.tab.split(" / ")[0] for action in READ_ACTIONS} == {
        "Home",
        "Catalogue",
        "Stock",
        "Warehouse",
        "Till",
        "Sales",
        "Books",
        "Admin",
    }
    assert all(action.effect == "read" for action in READ_ACTIONS)
    assert ACTIONS["roles_find"].permissions == (USERS_MANAGE,)
    assert ACTIONS["till_price_preview"].permissions == (TILL_SELL,)
    for name, arguments in (
        ("catalogue_search", {"query": "   "}),
        ("transfers_find", {"status": "invalid"}),
        ("sales_orders_find", {"limit": 26}),
        ("customers_find", {"fields": ["email"]}),
        ("my_permissions", {"user_id": str(uuid4())}),
    ):
        with pytest.raises(ValidationError):
            ACTIONS[name].arguments.model_validate(arguments)


async def test_scoped_read_catalogue_and_safe_transfer_line_pagination(async_db):
    team_id = current_tenant_id()
    other_team = Team(name="Other MCP business", slug=f"other-{uuid4().hex}")
    async_db.add(other_team)
    await async_db.flush()
    user_id = await async_db.scalar(select(User.id).where(User.team_id == team_id))
    token = McpToken(
        team_id=team_id,
        user_id=user_id,
        name="Desk",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    async def call(name, **arguments):
        action = ACTIONS[name]
        return await action.handler(async_db, token, action.arguments.model_validate(arguments))

    stamp = uuid4().hex[:12]
    locations = [
        Location(name=f"Location {index} {stamp}", type=LocationType.WAREHOUSE)
        for index in range(2)
    ]
    sku = Sku(
        our_ref=f"MCP-{stamp}",
        our_barcode=f"BC-{stamp}",
        name="Test sofa",
        design=stamp,
        fabric=stamp,
        retail_ex_vat=Decimal("100"),
    )
    other_customer = Customer(
        team_id=other_team.id, name=f"Customer {stamp}", email="hidden@example.com"
    )
    customer = Customer(
        name=f"Customer {stamp}", email="private@example.com", billing_address="private address"
    )
    async_db.add_all([*locations, sku, other_customer, customer])
    await async_db.flush()
    source, destination = locations
    receipt = Transfer(
        transfer_number=stamp,
        from_location_id=source.id,
        to_location_id=destination.id,
        created_by_user_id=user_id,
        status=TransferStatus.DRAFT,
    )
    # A fixture with the same number in the second business should never be discoverable.
    other_locations = [
        Location(name=f"Other {index} {stamp}", team_id=other_team.id, type=LocationType.WAREHOUSE)
        for index in range(2)
    ]
    async_db.add_all([receipt, *other_locations])
    await async_db.flush()
    foreign_transfer = Transfer(
        team_id=other_team.id,
        transfer_number=stamp,
        from_location_id=other_locations[0].id,
        to_location_id=other_locations[1].id,
        created_by_user_id=user_id,
        status=TransferStatus.DRAFT,
    )
    async_db.add_all(
        [
            foreign_transfer,
            LocationStock(
                location_id=source.id,
                sku_id=sku.id,
                on_hand=Decimal("3.25"),
                unit_cost_zar=Decimal("1234"),
            ),
            TransferLine(
                transfer_id=receipt.id,
                sku_id=sku.id,
                qty_dispatched=Decimal("1.25"),
                unit_cost_zar=Decimal("1234"),
            ),
            TransferLine(
                transfer_id=receipt.id,
                sku_id=sku.id,
                qty_dispatched=Decimal("2"),
                unit_cost_zar=Decimal("1234"),
            ),
        ]
    )
    await async_db.flush()

    assert (await call("customers_find", query=stamp))["items"] == [
        {"id": str(customer.id), "name": customer.name}
    ]
    assert (await call("catalogue_search", query=sku.our_ref))["items"][0]["id"] == str(sku.id)
    stock = (await call("stock_on_hand", sku_id=sku.id, location_id=source.id))["items"][0]
    assert Decimal(stock["on_hand"]) == Decimal("3.25")
    assert "unit_cost_zar" not in stock
    transfers = (await call("transfers_find", query=stamp))["items"]
    assert [row["id"] for row in transfers] == [str(receipt.id)]
    with pytest.raises(NotFoundError):
        await call("transfers_get", transfer_id=foreign_transfer.id)
    first = await call("transfers_get", transfer_id=receipt.id, limit=1)
    second = await call(
        "transfers_get", transfer_id=receipt.id, limit=1, offset=first["next_offset"]
    )
    lines = first["lines"] + second["lines"]
    assert second["next_offset"] is None
    assert len({row["line_id"] for row in lines}) == 2
    assert {Decimal(row["qty_dispatched"]) for row in lines} == {Decimal("1.25"), Decimal("2")}
    assert all("unit_cost_zar" not in row for row in lines)

    # Issue a real query for each declared list action. Public projections must
    # serialize even when a tenant has not recorded any data for that tab yet.
    for action in READ_ACTIONS:
        if (
            set(action.arguments.model_fields) == {"limit", "offset", "query"}
            and action.name != "catalogue_search"
        ):
            page = await call(action.name, query=stamp, limit=1)
            assert len(page["items"]) <= 1

    for name in (
        "reorder_shortages",
        "bank_unmatched_counts",
        "vat201_periods_list",
        "books_periods_list",
        "document_number_formats",
    ):
        assert "items" in await call(name, limit=1)
    assert "items" in await call("sales_history_find", sku_id=sku.id)
    assert (await call("current_business"))["id"] == str(team_id)
    assert "settings" in await call("business_settings")
    assert (await call("current_token"))["name"] == "Desk"
    csv = await call(
        "inventory_import_check_csv", csv_text="SKU,Name,Category,Price\nitem,Sofa,Seating,100"
    )
    assert csv == {"rows_checked": 1, "error_count": 0, "first_errors": []}
    invalid = await call("inventory_import_check_csv", csv_text="SKU,Name\nitem,Sofa")
    assert invalid["error_count"] and invalid["first_errors"]
    bank_id = await async_db.scalar(
        select(Account.id).where(Account.team_id == team_id, Account.is_bank.is_(True)).limit(1)
    )
    cash = await call(
        "report_cash_summary", account_id=bank_id, from_date="2026-11-01", to_date="2026-11-15"
    )
    assert len(cash["accounts"]) == 1
    with pytest.raises(NotFoundError):
        await call(
            "report_cash_summary", account_id=uuid4(), from_date="2026-11-01", to_date="2026-11-15"
        )
    assert set(await call("home_summary")) == {"on_hand_qty", "on_order_qty"}
    assert "permissions" in await call("my_permissions")
    assert "items" in await call("location_bins_list", location_id=source.id)
    assert "items" in await call("stock_by_bin", sku_id=sku.id)
    preview = await call("till_price_preview", sku_id=sku.id, customer_id=customer.id)
    assert Decimal(preview["total_inc_vat"]) == Decimal("115.00")
    with pytest.raises(NotFoundError):
        await call("till_price_preview", sku_id=sku.id, customer_id=other_customer.id)


@pytest.mark.no_db
def test_compact_discovery_reaches_each_sidebar_destination_and_filters_capabilities():
    from app.permissions import PERMISSION_CATALOG, STOCK_TRANSFER
    from app.services.mcp_actions import search_actions

    sidebar = {
        "Home": [""],
        "Catalogue": ["Catalogue", "Suppliers", "Price lists", "Proformas", "Locations"],
        "Stock": ["Stocktakes", "Adjustments", "Import", "Reorder", "Stock by bin"],
        "Warehouse": ["Purchase orders", "Transit", "Receive", "Warehouse", "Transfers", "Picks"],
        "Till": [""],
        "Sales": ["Quotes", "Orders", "Laybys", "Customers", "Returns", "Deliveries", "History"],
        "Books": [
            "Chart of accounts",
            "Journals",
            "Invoices",
            "Repeating invoices",
            "Credit notes",
            "Bills",
            "Payments",
            "Bank reconciliation",
            "Reports",
            "VAT201",
            "Books periods",
        ],
        "Admin": [
            "Organisation",
            "Team members",
            "Roles & permissions",
            "Audit log",
            "My profile",
            "Settings directory",
            "Integrations",
            "MCP tokens",
            "Company",
            "Documents",
            "Locations",
            "Operations",
            "Labels",
        ],
    }
    declared = {tab for action in READ_ACTIONS for tab in (action.tab, *action.related_tabs)}
    granted = set(PERMISSION_CATALOG)
    expected = {
        f"{group} / {tab}" if tab else group for group, tabs in sidebar.items() for tab in tabs
    }
    assert expected <= declared
    assert set(search_actions("", "", granted)["domains"]) == set(sidebar)
    for tab in expected:
        actions = search_actions("", tab, granted)["actions"]
        assert 0 < len(actions) <= 3
        assert all("inputSchema" in action for action in actions)

    def names(tab, permissions):
        result = []
        offset = 0
        while True:
            page = search_actions("", tab, permissions, offset)
            result.extend(action["name"] for action in page["actions"])
            if page["next_offset"] is None:
                return result
            offset = page["next_offset"]

    assert "transfers_dispatch" not in names("Warehouse / Transfers", {TILL_SELL})
    assert "transfers_receive" in names("Warehouse / Transfers", {TILL_SELL})
    assert "transfers_dispatch" in names("Warehouse / Transfers", {STOCK_TRANSFER})
    assert not names("Stock / Import", set())
    assert not names("Admin / Roles & permissions", set())
    assert not names("Admin / Organisation", set())
    assert "current_token" in names("Admin / Integrations", set())
    assert "business_settings" in names("Admin / Labels", set())
