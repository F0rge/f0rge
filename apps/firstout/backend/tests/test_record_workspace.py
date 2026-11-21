"""Exercise the HTTP seam against disposable PostgreSQL and real domain services."""

from __future__ import annotations

import asyncio
import datetime
import uuid

import jwt
import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings, settings
from app.database import TenantSession
from app.exceptions import ForbiddenError
from app.models.customer import Customer
from app.models.price_list import PriceList
from app.models.proforma import Proforma
from app.models.record_workspace import RecordWorkspaceBatch
from app.models.team import Team
from app.models.tenant_onboarding import TenantInvitation
from app.models.user import User
from app.models.supplier import Supplier
from app.schemas.customer_crm import CustomerCrmCreate
from app.schemas.purchase_order import PurchaseOrderCreate
from app.schemas.record_workspace import WorkspaceExecute, WorkspacePreflight
from app.services.customers_crm import CustomersCrmService
from app.services.price_lists import PriceListService
from app.services.proformas import ProformaService
from app.services.purchase_orders import PurchaseOrderService
from app.services.record_workspace import RecordWorkspaceService
from app.services.record_workspace_execute import RecordWorkspaceExecuteService
from app.services.record_workspace_tokens import issue_token, read_token
from f0rge_db.crud import unit_of_work
from f0rge_db.organisation import tenant_id_ctx
from f0rge_core.exceptions import NotFoundError, ValidationError
from tests.conftest import authenticate_as, create_test_staff

PREFIX = "/api/v1/record-workspaces"


async def query(client, resource="customers", **body):
    response = await client.post(f"{PREFIX}/{resource}/query", json=body)
    assert response.status_code == 200, response.text
    return response.json()


async def customer(client, name, **fields):
    response = await client.post("/api/v1/customers", json={"name": name, **fields})
    assert response.status_code == 201, response.text
    return response.json()


async def prepare(client, resource="customers", **body):
    response = await client.post(f"{PREFIX}/{resource}/preflight", json=body)
    assert response.status_code == 200, response.text
    return response.json()


async def execute(client, prepared, resource="customers", request_id=None):
    response = await client.post(
        f"{PREFIX}/{resource}/execute",
        json={
            "preflight_token": prepared["preflight_token"],
            "request_id": str(request_id or uuid.uuid4()),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_query_filters_complete_dataset_before_pagination(owner_client, async_db):
    async_db.add_all(
        [Customer(name=f"Workspace page {i:03}", payment_terms_days=i) for i in range(63)]
    )
    await async_db.flush()
    result = await query(
        owner_client,
        q="Workspace page",
        limit=10,
        offset=50,
        sort={"field": "payment_terms_days", "direction": "asc"},
    )
    assert result["total"] == 63
    assert [row["payment_terms_days"] for row in result["items"]] == list(range(50, 60))
    assert len(result["revisions"]) == 10
    assert result["selection_count"] == 63 and result["selection_token"]
    assert len(result["selection_ids"]) == 63
    numeric = await query(
        owner_client,
        q="Workspace page",
        filters=[
            {"field": "payment_terms_days", "operator": "gte", "value": 60},
        ],
    )
    assert numeric["total"] == 3
    empty = await query(
        owner_client,
        q="Workspace page",
        filters=[
            {"field": "email", "operator": "empty"},
        ],
    )
    assert empty["total"] == 63
    zero = await query(
        owner_client,
        q="Workspace page",
        limit=1,
        sort={"field": "payment_terms_days", "direction": "asc"},
    )
    assert zero["items"][0]["payment_terms_days"] == 0


async def test_large_result_requires_refined_all_matching_selection(owner_client, async_db):
    async_db.add_all([Customer(name=f"Large workspace selection {i:03}") for i in range(501)])
    await async_db.flush()
    result = await query(owner_client, q="Large workspace selection", limit=10)
    assert result["total"] == result["selection_count"] == 501
    assert len(result["items"]) == 10
    assert result["selection_token"] is None and result["selection_ids"] == []


async def test_missing_signing_key_keeps_reads_available_and_rejects_bulk(
    owner_client, monkeypatch
):
    record = await customer(owner_client, "Workspace key missing")
    monkeypatch.setattr(settings, "jwt_secret", "")
    monkeypatch.setattr(settings, "record_workspace_signing_key", "")
    result = await query(owner_client)
    assert not result["bulk_available"]
    assert result["selection_token"] is None and result["selection_ids"] == []
    response = await owner_client.post(
        f"{PREFIX}/customers/preflight", json={"ids": [record["id"]], "action": "archive"}
    )
    assert response.status_code == 503
    assert "RECORD_WORKSPACE_SIGNING_KEY" in response.text


async def test_dedicated_signing_key_round_trip_without_legacy_secret(owner_client, monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "")
    monkeypatch.setattr(
        settings, "record_workspace_signing_key", "workspace-dedicated-test-key-32char"
    )
    actor = uuid.UUID((await owner_client.get("/api/v1/auth/me")).json()["id"])
    token = issue_token("selection", "customers", actor, {"ids": [], "revisions": {}})
    assert read_token(token, "selection", "customers", actor)["ids"] == []
    assert (await query(owner_client))["bulk_available"]


async def test_bulk_fifty_records_uses_reviewed_outcomes(owner_client, async_db):
    records = [Customer(name=f"Workspace bulk fifty {i:03}") for i in range(50)]
    async_db.add_all(records)
    await async_db.flush()
    selected = await query(owner_client, q="Workspace bulk fifty")
    prepared = await prepare(
        owner_client, selection_token=selected["selection_token"], action="archive"
    )
    result = await execute(owner_client, prepared)
    assert len(result["succeeded"]) == 50 and result["failed"] == []
    assert (await query(owner_client, q="Workspace bulk fifty", lifecycle="archived"))[
        "total"
    ] == 50


async def test_postcommit_response_failure_preserves_durable_success(owner_client, monkeypatch):
    import app.services.record_workspace_execute as executor_module

    record = await customer(owner_client, "Workspace committed response failure")
    prepared = await prepare(owner_client, ids=[record["id"]], action="archive")
    actual_action = executor_module.apply_action

    async def fail_after_actual_commit(*args, **kwargs):
        await actual_action(*args, **kwargs)
        raise NotFoundError("Response reload failed after commit")

    monkeypatch.setattr(executor_module, "apply_action", fail_after_actual_commit)
    request_id = uuid.uuid4()
    result = await execute(owner_client, prepared, request_id=request_id)
    assert result["succeeded"] == [record["id"]] and result["failed"] == []
    assert (await owner_client.get(f"/api/v1/customers/{record['id']}")).json()["is_archived"]
    replay = await execute(owner_client, prepared, request_id=request_id)
    assert replay["replayed"] and replay["succeeded"] == result["succeeded"]


def test_short_dedicated_signing_key_is_rejected():
    with pytest.raises(ValueError, match="at least 32"):
        Settings(_env_file=None, record_workspace_signing_key="too-short")


async def test_all_and_any_filter_conditions(owner_client):
    await customer(owner_client, "Workspace Alpha", payment_terms_days=10)
    await customer(owner_client, "Workspace Beta", payment_terms_days=20)
    conditions = [
        {"field": "name", "operator": "contains", "value": "Alpha"},
        {"field": "payment_terms_days", "operator": "gt", "value": 15},
    ]
    assert (await query(owner_client, q="Workspace", filters=conditions, match="all"))["total"] == 0
    assert (await query(owner_client, q="Workspace", filters=conditions, match="any"))["total"] == 2


@pytest.mark.parametrize(
    "body",
    [
        {"filters": [{"field": "password_hash", "operator": "contains", "value": "a"}]},
        {"filters": [{"field": "name", "operator": "gt", "value": 1}]},
        {"filters": [{"field": "payment_terms_days", "operator": "contains", "value": "1"}]},
        {"filters": [{"field": "payment_terms_days", "operator": "gt", "value": "not a number"}]},
        {"filters": [{"field": "on_hold", "operator": "eq", "value": "not a boolean"}]},
        {"sort": {"field": "team_id"}},
    ],
)
async def test_query_rejects_unapproved_fields_and_operators(owner_client, body):
    response = await owner_client.post(f"{PREFIX}/customers/query", json=body)
    assert response.status_code == 400


@pytest.mark.parametrize(
    "resource",
    [
        "customers",
        "suppliers",
        "price-lists",
        "locations",
        "users",
        "roles",
        "accounts",
        "repeating-invoices",
        "proformas",
        "quotes",
        "payments",
    ],
)
async def test_every_workspace_resource_has_a_scoped_query(owner_client, resource):
    result = await query(owner_client, resource, lifecycle="all")
    assert isinstance(result["items"], list)
    assert result["counts"]["active"] + result["counts"]["archived"] == result["total"]


async def test_frozen_selection_exclusions_archive_and_replay(owner_client, async_db):
    first = await customer(owner_client, "Frozen selection first")
    second = await customer(owner_client, "Frozen selection second")
    snapshot = await query(owner_client, q="Frozen selection")
    newer = await customer(owner_client, "Frozen selection newer")
    prepared = await prepare(
        owner_client,
        action="archive",
        selection_token=snapshot["selection_token"],
        excluded_ids=[second["id"]],
    )
    assert prepared["eligible_count"] == 1
    request_id = uuid.uuid4()
    result = await execute(owner_client, prepared, request_id=request_id)
    assert result["succeeded"] == [first["id"]] and not result["replayed"]
    again = await execute(owner_client, prepared, request_id=request_id)
    assert again["succeeded"] == [first["id"]] and again["replayed"]
    active = await query(owner_client, q="Frozen selection")
    assert {row["id"] for row in active["items"]} == {second["id"], newer["id"]}
    archived = await query(owner_client, q="Frozen selection", lifecycle="archived")
    assert [row["id"] for row in archived["items"]] == [first["id"]]
    audit = await async_db.scalar(
        select(RecordWorkspaceBatch).where(RecordWorkspaceBatch.request_id == request_id)
    )
    assert audit.selection == [{"id": first["id"], "revision": snapshot["revisions"][first["id"]]}]
    assert audit.result["succeeded"] == [first["id"]]
    restored = await prepare(owner_client, ids=[first["id"]], action="restore")
    assert (await execute(owner_client, restored))["succeeded"] == [first["id"]]


async def test_stale_selection_and_post_review_changes_are_reported(owner_client):
    record = await customer(owner_client, "Workspace stale")
    snapshot = await query(owner_client, q=record["name"])
    await owner_client.patch(f"/api/v1/customers/{record['id']}", json={"phone": "011 555 1111"})
    stale = await prepare(
        owner_client, ids=[record["id"]], action="archive", revisions=snapshot["revisions"]
    )
    assert stale["eligible_count"] == 0 and stale["blocked_count"] == 1
    prepared = await prepare(owner_client, ids=[record["id"]], action="archive")
    await owner_client.patch(f"/api/v1/customers/{record['id']}", json={"phone": "011 555 2222"})
    result = await execute(owner_client, prepared)
    assert not result["succeeded"] and "changed after review" in result["failed"][0]["reason"]
    assert not (await owner_client.get(f"/api/v1/customers/{record['id']}")).json()["is_archived"]


async def test_bulk_edit_clear_is_explicit_and_omitted_fields_survive(owner_client):
    record = await customer(
        owner_client,
        "Workspace field semantics",
        email="sample@example.com",
        phone="011 555 1000",
        payment_terms_days=10,
    )
    prepared = await prepare(
        owner_client,
        ids=[record["id"]],
        action="edit",
        patch={"email": None, "payment_terms_days": 45},
    )
    assert (await execute(owner_client, prepared))["succeeded"] == [record["id"]]
    current = (await owner_client.get(f"/api/v1/customers/{record['id']}")).json()
    assert current["email"] is None and current["phone"] == "011 555 1000"
    assert current["payment_terms_days"] == 45
    invalid = await owner_client.post(
        f"{PREFIX}/customers/preflight",
        json={
            "ids": [record["id"]],
            "action": "edit",
            "patch": {"price_classification": None},
        },
    )
    assert invalid.status_code == 400


async def test_role_delete_preflight_protects_presets_and_assigned_roles(owner_client):
    unused = (
        await owner_client.post(
            "/api/v1/roles", json={"name": "Workspace unused", "permissions": []}
        )
    ).json()
    assigned = (
        await owner_client.post(
            "/api/v1/roles", json={"name": "Workspace assigned", "permissions": []}
        )
    ).json()
    await create_test_staff(owner_client, email="workspace-role@example.com", role=assigned["slug"])
    roles = await query(owner_client, "roles", limit=100)
    prepared = await prepare(
        owner_client, "roles", ids=[row["id"] for row in roles["items"]], action="delete"
    )
    assert [row["id"] for row in prepared["eligible"]] == [unused["id"]]
    assert prepared["blocked_count"] >= 6
    outcome = await execute(owner_client, prepared, "roles")
    assert outcome["succeeded"] == [unused["id"]]
    assert assigned["id"] in {row["id"] for row in (await owner_client.get("/api/v1/roles")).json()}


async def test_pending_invite_blocks_direct_and_stale_bulk_delete(owner_client, async_db):
    actor = (await owner_client.get("/api/v1/auth/me")).json()
    role = (
        await owner_client.post("/api/v1/roles", json={"name": "Invited staff", "permissions": []})
    ).json()
    prepared = await prepare(owner_client, "roles", ids=[role["id"]], action="delete")
    assert prepared["eligible_count"] == 1

    invite = TenantInvitation(
        email="pending-staff@example.com",
        role=role["slug"],
        invited_by_user_id=uuid.UUID(actor["id"]),
        status="pending",
    )
    async_db.add(invite)
    async with unit_of_work(async_db):
        pass

    direct = await owner_client.delete(f"/api/v1/roles/{role['id']}")
    assert direct.status_code == 409
    assert "pending staff invitation" in direct.json()["detail"]
    blocked = await prepare(owner_client, "roles", ids=[role["id"]], action="delete")
    assert blocked["eligible_count"] == 0
    assert "pending staff invitation" in blocked["blocked"][0]["reason"]
    outcome = await execute(owner_client, prepared, "roles")
    assert outcome["succeeded"] == []
    assert "pending staff invitation" in outcome["failed"][0]["reason"]

    await async_db.refresh(invite)
    invite.status = "revoked"
    async with unit_of_work(async_db):
        pass
    assert (await owner_client.delete(f"/api/v1/roles/{role['id']}")).status_code == 204


async def test_token_actor_binding_and_mutation_permissions(owner_client):
    supplier = (
        await owner_client.post("/api/v1/suppliers", json={"name": "Workspace supplier"})
    ).json()
    snapshot = await query(owner_client, "suppliers", q="Workspace supplier")
    await create_test_staff(owner_client, email="workspace-buyer@example.com", role="buyer")
    await authenticate_as(owner_client, "workspace-buyer@example.com")
    wrong_actor = await owner_client.post(
        f"{PREFIX}/suppliers/preflight",
        json={
            "selection_token": snapshot["selection_token"],
            "action": "archive",
        },
    )
    assert wrong_actor.status_code == 403
    await create_test_staff(owner_client, email="workspace-warehouse@example.com", role="warehouse")
    await authenticate_as(owner_client, "workspace-warehouse@example.com")
    denied = await owner_client.post(
        f"{PREFIX}/suppliers/preflight", json={"ids": [supplier["id"]], "action": "archive"}
    )
    assert denied.status_code == 403
    assert (await owner_client.post(f"{PREFIX}/roles/query", json={})).status_code == 403
    assert (await owner_client.post(f"{PREFIX}/users/query", json={})).status_code == 403
    credit_filter = await owner_client.post(
        f"{PREFIX}/customers/query",
        json={
            "filters": [{"field": "on_hold", "operator": "eq", "value": True}],
        },
    )
    assert credit_filter.status_code == 403


async def test_supplier_edit_currency_validation_and_archived_edit_protection(owner_client):
    supplier = (
        await owner_client.post("/api/v1/suppliers", json={"name": "Workspace currency"})
    ).json()
    changed = await owner_client.patch(
        f"/api/v1/suppliers/{supplier['id']}", json={"default_currency": "zar"}
    )
    assert changed.status_code == 200 and changed.json()["default_currency"] == "ZAR"
    invalid = await owner_client.patch(
        f"/api/v1/suppliers/{supplier['id']}", json={"default_currency": "Z"}
    )
    assert invalid.status_code == 422
    await owner_client.patch(
        f"/api/v1/suppliers/{supplier['id']}/archive", json={"is_archived": True}
    )
    blocked = await prepare(
        owner_client,
        "suppliers",
        ids=[supplier["id"]],
        action="edit",
        patch={"default_currency": "USD"},
    )
    assert blocked["blocked_count"] == 1 and blocked["eligible_count"] == 0


async def test_foreign_tenant_ids_are_not_enumerated_or_mutated(owner_client, async_db):
    other = Team(name="Workspace other organisation", slug="workspace-other-org")
    async_db.add(other)
    await async_db.flush()
    foreign = Customer(team_id=other.id, name="Workspace foreign identity")
    async_db.add(foreign)
    await async_db.flush()
    assert (await query(owner_client, q="Workspace foreign"))["total"] == 0
    prepared = await prepare(owner_client, ids=[str(foreign.id)], action="archive")
    assert (
        prepared["blocked_count"] == 1 and prepared["blocked"][0]["label"] == "Unavailable record"
    )
    assert "foreign identity" not in str(prepared)
    snapshot = await query(owner_client)
    actor = (await owner_client.get("/api/v1/auth/me")).json()["id"]
    token = tenant_id_ctx.set(other.id)
    try:
        with pytest.raises(ForbiddenError):
            read_token(snapshot["selection_token"], "selection", "customers", uuid.UUID(actor))
    finally:
        tenant_id_ctx.reset(token)


async def test_tampered_token_and_reused_request_id_are_rejected(owner_client):
    record = await customer(owner_client, "Workspace replay identity")
    prepared = await prepare(owner_client, ids=[record["id"]], action="archive")
    token = prepared["preflight_token"]
    tampered = await owner_client.post(
        f"{PREFIX}/customers/execute",
        json={
            "preflight_token": token[:-3] + "xxx",
            "request_id": str(uuid.uuid4()),
        },
    )
    assert tampered.status_code == 409
    request_id = uuid.uuid4()
    await execute(owner_client, prepared, request_id=request_id)
    inverse = await prepare(owner_client, ids=[record["id"]], action="restore")
    reused = await owner_client.post(
        f"{PREFIX}/customers/execute",
        json={
            "preflight_token": inverse["preflight_token"],
            "request_id": str(request_id),
        },
    )
    assert reused.status_code == 409


async def test_expired_preflight_does_not_apply_changes(owner_client):
    record = await customer(owner_client, "Workspace expiry")
    prepared = await prepare(owner_client, ids=[record["id"]], action="archive")
    claims = jwt.decode(prepared["preflight_token"], options={"verify_signature": False})
    claims["exp"] = 1
    expired = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")
    response = await owner_client.post(
        f"{PREFIX}/customers/execute",
        json={
            "preflight_token": expired,
            "request_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 409
    assert not (await owner_client.get(f"/api/v1/customers/{record['id']}")).json()["is_archived"]


@pytest.mark.parametrize("same_request", [True, False])
async def test_parallel_execution_has_one_mutation_and_durable_outcomes(
    async_engine,
    same_request,
):
    """Actual separate PG connections, not concurrent calls sharing the SAVEPOINT fixture."""
    maker = async_sessionmaker(
        async_engine, expire_on_commit=False, sync_session_class=TenantSession
    )
    first_request = uuid.uuid4()
    second_request = first_request if same_request else uuid.uuid4()
    async with maker() as session:
        actor = await session.scalar(select(User.id).where(User.email == settings.seed_owner_email))
        record = await CustomersCrmService(session).create(
            CustomerCrmCreate(name="Workspace concurrent " + uuid.uuid4().hex)
        )
        record_id = record.id
        prepared = await RecordWorkspaceService(session).preflight(
            "customers", WorkspacePreflight(ids=[record_id], action="archive"), actor
        )

    async def run(request_id):
        async with maker() as session:
            return await RecordWorkspaceExecuteService(session).execute(
                "customers",
                WorkspaceExecute(preflight_token=prepared.preflight_token, request_id=request_id),
                actor,
            )

    try:
        first, second = await asyncio.wait_for(
            asyncio.gather(run(first_request), run(second_request)), 20
        )
        if same_request:
            assert first.succeeded == second.succeeded == [record_id]
            assert first.replayed != second.replayed
        else:
            assert sorted([len(first.succeeded), len(second.succeeded)]) == [0, 1]
            loser = first if first.failed else second
            assert "changed after review" in loser.failed[0].reason
        async with maker() as session:
            batches = (
                await session.scalars(
                    select(RecordWorkspaceBatch).where(
                        RecordWorkspaceBatch.request_id.in_([first_request, second_request])
                    )
                )
            ).all()
            assert len(batches) == (1 if same_request else 2)
            assert sum(len(batch.result["succeeded"]) for batch in batches) == 1
            assert (await session.get(Customer, record_id)).is_archived
    finally:
        async with maker() as session:
            async with unit_of_work(session):
                await session.execute(
                    delete(RecordWorkspaceBatch).where(
                        RecordWorkspaceBatch.request_id.in_([first_request, second_request])
                    )
                )
                await session.execute(delete(Customer).where(Customer.id == record_id))


@pytest.mark.parametrize("resource", ["price-lists", "proformas"])
async def test_archive_lock_serializes_new_references_and_refreshes_cached_records(
    async_engine, resource
):
    maker = async_sessionmaker(
        async_engine, expire_on_commit=False, sync_session_class=TenantSession
    )
    async with maker() as setup:
        actor = await setup.scalar(select(User.id).where(User.email == settings.seed_owner_email))
        supplier = Supplier(name="Workspace reference " + uuid.uuid4().hex, default_currency="ZAR")
        setup.add(supplier)
        await setup.flush()
        record = (
            PriceList(name="Workspace reference " + uuid.uuid4().hex)
            if resource == "price-lists"
            else Proforma(
                supplier_id=supplier.id,
                invoice_number=uuid.uuid4().hex,
                invoice_date=datetime.date.today(),
                currency="ZAR",
                pdf_storage_key="owned-test-reference.pdf",
            )
        )
        async with unit_of_work(setup):
            setup.add(record)
        record_id, supplier_id = record.id, supplier.id
    model = PriceList if resource == "price-lists" else Proforma
    service_type = PriceListService if resource == "price-lists" else ProformaService
    application_name = "workspace-reference-" + uuid.uuid4().hex
    try:
        async with maker() as archiver, maker() as linker:
            # This session has already seen an active record. A lock must refresh it.
            cached = await linker.get(model, record_id)
            assert not cached.is_archived
            row = await service_type(archiver).crud.get_by_id(record_id, for_update=True)
            row.is_archived = True
            await archiver.flush()

            async def link_record():
                await linker.execute(
                    select(func.set_config("application_name", application_name, True))
                )
                if resource == "price-lists":
                    return await CustomersCrmService(linker).create(
                        CustomerCrmCreate(name=uuid.uuid4().hex, price_list_id=record_id)
                    )
                return await PurchaseOrderService(linker).create(
                    PurchaseOrderCreate(
                        supplier_id=supplier_id,
                        proforma_id=record_id,
                        lines=[{"description": "Owned test", "qty": 1, "factory_unit_amount": "1"}],
                    ),
                    actor,
                )

            task = asyncio.create_task(link_record())

            async def await_database_lock():
                async with maker() as observer:
                    while not task.done():
                        waiting = await observer.scalar(
                            text(
                                "SELECT count(*) FROM pg_stat_activity WHERE application_name = :name AND wait_event_type = 'Lock'"
                            ),
                            {"name": application_name},
                        )
                        if waiting:
                            return
                        await asyncio.sleep(0.01)
                raise AssertionError("Reference validation did not wait for the archive lock")

            try:
                await asyncio.wait_for(await_database_lock(), timeout=3)
            finally:
                await archiver.commit()
            with pytest.raises(ValidationError, match="Restore"):
                await asyncio.wait_for(task, timeout=3)
            await linker.rollback()
            # The direct archive endpoint uses the same locking CRUD contract.
            restored = await service_type(archiver).set_archived(record_id, False)
            assert not restored.is_archived
    finally:
        async with maker() as cleanup:
            async with unit_of_work(cleanup):
                await cleanup.execute(delete(model).where(model.id == record_id))
                await cleanup.execute(delete(Supplier).where(Supplier.id == supplier_id))


async def test_owner_bulk_disable_is_blocked_and_regular_members_can_be_disabled(owner_client):
    member = await create_test_staff(
        owner_client, email="workspace-disable@example.com", role="buyer"
    )
    me = (await owner_client.get("/api/v1/auth/me")).json()
    prepared = await prepare(owner_client, "users", ids=[me["id"], member["id"]], action="disable")
    assert prepared["eligible_count"] == 1 and prepared["blocked_count"] == 1
    assert (await execute(owner_client, prepared, "users"))["succeeded"] == [member["id"]]
    inactive = await query(owner_client, "users", lifecycle="archived")
    assert member["id"] in {row["id"] for row in inactive["items"]}
    enabled = await prepare(owner_client, "users", ids=[member["id"]], action="enable")
    assert (await execute(owner_client, enabled, "users"))["succeeded"] == [member["id"]]
    assert member["id"] not in {
        row["id"] for row in (await query(owner_client, "users", lifecycle="archived"))["items"]
    }


async def test_global_identity_block_cannot_be_enabled_by_tenant_bulk(owner_client, async_db):
    member = await create_test_staff(
        owner_client, email="workspace-global-block@example.com", role="buyer"
    )
    identity = await async_db.get(User, uuid.UUID(member["id"]))
    identity.is_disabled = True
    await async_db.flush()
    prepared = await prepare(owner_client, "users", ids=[member["id"]], action="enable")
    assert prepared["eligible_count"] == 0 and prepared["blocked_count"] == 1
    assert "Global identity access" in prepared["blocked"][0]["reason"]


async def test_price_list_archive_preserves_assignment_and_blocks_new_assignment(owner_client):
    price = (
        await owner_client.post("/api/v1/price-lists", json={"name": "Workspace terms"})
    ).json()
    record = await customer(owner_client, "Workspace assigned price", price_list_id=price["id"])
    deletion = await prepare(owner_client, "price-lists", ids=[price["id"]], action="delete")
    assert deletion["blocked_count"] == 1
    prepared = await prepare(owner_client, "price-lists", ids=[price["id"]], action="archive")
    assert (await execute(owner_client, prepared, "price-lists"))["succeeded"] == [price["id"]]
    assert price["id"] not in {
        row["id"] for row in (await owner_client.get("/api/v1/price-lists")).json()
    }
    assert (await owner_client.get(f"/api/v1/price-lists/{price['id']}")).json()["is_archived"]
    assert (await owner_client.get(f"/api/v1/customers/{record['id']}")).json()[
        "price_list_id"
    ] == price["id"]
    denied = await owner_client.post(
        "/api/v1/customers", json={"name": "Workspace new price", "price_list_id": price["id"]}
    )
    assert denied.status_code == 400
    unchanged = await owner_client.patch(
        f"/api/v1/customers/{record['id']}",
        json={"price_list_id": price["id"], "phone": "011 123 4567"},
    )
    assert unchanged.status_code == 200


async def test_proforma_archive_keeps_document_and_prevents_new_po_link(owner_client):
    supplier = (
        await owner_client.post("/api/v1/suppliers", json={"name": "Workspace source"})
    ).json()
    created = await owner_client.post(
        "/api/v1/proformas",
        data={
            "supplier_id": supplier["id"],
            "invoice_number": "WS-001",
            "invoice_date": "2026-11-15",
        },
        files={"file": ("source.pdf", b"%PDF-1.4\nworkspace", "application/pdf")},
    )
    assert created.status_code == 201, created.text
    record = created.json()
    prepared = await prepare(owner_client, "proformas", ids=[record["id"]], action="archive")
    assert (await execute(owner_client, prepared, "proformas"))["succeeded"] == [record["id"]]
    assert (await owner_client.get(f"/api/v1/proformas/{record['id']}/file")).content.startswith(
        b"%PDF"
    )
    archived = await query(owner_client, "proformas", lifecycle="archived")
    assert archived["items"][0]["id"] == record["id"]
    denied = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier["id"],
            "proforma_id": record["id"],
            "lines": [{"sku_id": str(uuid.uuid4()), "qty": 1, "factory_unit_amount": "1"}],
        },
    )
    assert denied.status_code == 400 and "Restore the proforma" in denied.text


async def test_repeating_invoice_pause_resume_and_date_filter(owner_client):
    party = await customer(owner_client, "Workspace scheduled customer")
    created = await owner_client.post(
        "/api/v1/repeating-invoices",
        json={
            "customer_id": party["id"],
            "name": "Workspace monthly",
            "day_of_month": 15,
            "next_date": "2026-12-15",
            "lines": [{"description": "Monthly", "qty": 1, "unit_ex_vat": "100"}],
        },
    )
    assert created.status_code == 201, created.text
    schedule = created.json()
    result = await query(
        owner_client,
        "repeating-invoices",
        filters=[
            {"field": "next_date", "operator": "gt", "value": "2026-12-01"},
        ],
    )
    assert result["items"][0]["customer_name"] == party["name"]
    prepared = await prepare(
        owner_client, "repeating-invoices", ids=[schedule["id"]], action="pause"
    )
    outcome = await execute(owner_client, prepared, "repeating-invoices")
    assert outcome["succeeded"] == [schedule["id"]], outcome
    assert (await query(owner_client, "repeating-invoices"))["total"] == 0
    paused = await query(owner_client, "repeating-invoices", lifecycle="archived")
    assert paused["items"][0]["id"] == schedule["id"]
    resumed = await prepare(
        owner_client, "repeating-invoices", ids=[schedule["id"]], action="resume"
    )
    await execute(owner_client, resumed, "repeating-invoices")
    assert (await query(owner_client, "repeating-invoices"))["total"] == 1
