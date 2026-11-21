"""The route catalogue and its in-process runner, without a database."""

from __future__ import annotations

import ast
import asyncio
import uuid
from pathlib import Path

import jsonschema
import pytest
from fastapi import APIRouter, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, ValidationError

from app.dependencies.auth import _require, require_catalogue_mutate, require_transfer
from app.main import app
from app.schemas.transfer import TransferCreate
from app.middleware.auth import get_current_user_id
from app.permissions import CATALOGUE_MUTATE
from app.services import mcp_route_runner
from app.services.mcp_action_types import Action, Arguments, RouteCall
from app.services.mcp_actions import ACTIONS, actions_index, search_actions
from app.services.mcp_route_runner import (
    MAX_RESULT_BYTES,
    READ_FAILED,
    UNAVAILABLE,
    UNKNOWN_OUTCOME,
    receipt_fields,
    run_route,
)
from app.services.mcp_routes import (
    EXCLUDED_PATHS,
    EXCLUDED_TAGS,
    TABS,
    UNCLASSIFIED,
    api_routes,
    exclusion,
    route_actions,
)

pytestmark = pytest.mark.no_db

ROUTE_ACTIONS = {name: action for name, action in ACTIONS.items() if action.route is not None}
EVERY_PERMISSION = {key for action in ACTIONS.values() for key in action.permissions}


def _guards(dependant):
    for child in dependant.dependencies:
        if hasattr(child.call, "permissions"):
            yield child.call.permissions
        yield from _guards(child)


def test_every_api_operation_is_offered_or_excluded_with_a_reason():
    routes = list(api_routes(app))
    reasons = {(next(iter(route.methods)), route.path): exclusion(route) for route in routes}
    assert (
        len(reasons)
        == len(routes)
        == len(app.openapi()["paths"])
        + sum(len(methods) - 1 for methods in app.openapi()["paths"].values())
    )
    # A new router must be added to TABS or to an exclusion table before it ships.
    assert [key for key, reason in reasons.items() if reason == UNCLASSIFIED] == []
    assert set(reasons.values()) == {None, "identity", "files", "non-staff"}
    offered = {key for key, reason in reasons.items() if reason is None}
    assert offered == {
        (action.route.method, action.route.path) for action in ROUTE_ACTIONS.values()
    }
    # The tables name only tags and paths that exist, so a stale entry cannot hide a decision.
    tags = {tag for route in routes for tag in route.tags}
    assert set(TABS) | set(EXCLUDED_TAGS) == tags and not set(TABS) & set(EXCLUDED_TAGS)
    assert all(any(route.path.startswith(prefix) for route in routes) for prefix in EXCLUDED_PATHS)


def test_expected_actions_exist_and_identity_file_and_non_staff_routes_do_not():
    for name in (
        "create_sku",
        "complete_stocktake",
        "create_payment",
        "create_till_sale",
        "post_journal",
        "lock_period",
        "cancel_transfer",
        "profit_loss",
        # The endpoint name `home_summary` belongs to a hand-written action.
        "home_home_summary",
    ):
        assert name in ROUTE_ACTIONS, name
    assert ACTIONS["home_summary"].route is None
    for name in (
        "create_token",
        "rotate_token",
        "create_user",
        "update_role",
        "invite",
        "update_profile",
        "execute_records",
        "create_customer_portal_user",
        "revoke_customer_portal_access",
        "upload_sku_photo",
        "commit_catalogue_import",
        "get_invoice_pdf",
        "sales_by_sku_csv",
        "portal_place_order",
        "accept_paid_order",
        "request_storefront_refund",
        "clerk_webhook",
        "health",
    ):
        assert name not in ACTIONS, name
    assert all(
        (action.effect == "read") == (action.route.method == "GET")
        for action in ROUTE_ACTIONS.values()
    )


def test_route_action_permissions_are_the_route_dependency_keys():
    by_route = {
        (action.route.method, action.route.path): action for action in ROUTE_ACTIONS.values()
    }
    guarded = 0
    for route in api_routes(app):
        action = by_route.get((next(iter(route.methods)), route.path))
        if action is None:
            continue
        guards = list(_guards(route.dependant))
        assert len(guards) <= 1
        assert action.permissions == (guards[0] if guards else ()), action.name
        guarded += bool(guards)
    assert guarded > 80
    assert ROUTE_ACTIONS["create_sku"].permissions == (CATALOGUE_MUTATE,)
    assert ROUTE_ACTIONS["receive_transfer"].permissions == ("stock.transfer", "till.sell")
    # The API lets any staff member preview, so the write guard must not block this route.
    assert ROUTE_ACTIONS["preview_auto_match"].permissions == ()
    with pytest.raises(ValueError, match="must name a permission"):
        Action("x", "Home", "x", Arguments, (), ROUTE_ACTIONS["get_sku"].handler, "write")


def _objects(schema):
    if isinstance(schema, dict):
        if schema.get("type") == "object" and "properties" in schema:
            yield schema
        for value in schema.values():
            yield from _objects(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _objects(value)


def test_every_offered_input_schema_is_closed_at_every_depth():
    nested = 0
    for action in ACTIONS.values():
        objects = list(_objects(action.arguments.model_json_schema()))
        assert objects and all(item["additionalProperties"] is False for item in objects), (
            action.name
        )
        nested += len(objects) > 1
    assert nested > 70


def test_unknown_body_keys_are_refused_at_any_depth_not_dropped():
    transfer = ROUTE_ACTIONS["create_transfer"].arguments
    line = {"sku_id": str(uuid.uuid4()), "qty": 1}
    body = {"from_location_id": str(uuid.uuid4()), "to_location_id": str(uuid.uuid4())}
    body["lines"] = [line]
    transfer.model_validate({"body": body})
    for bad, loc in (
        ({**body, "invoice_id": "x"}, ("body", "invoice_id")),
        ({**body, "lines": [{**line, "bin": "A"}]}, ("body", "lines", 0, "bin")),
    ):
        with pytest.raises(ValidationError) as refused:
            transfer.model_validate({"body": bad})
        assert [(issue["loc"], issue["type"]) for issue in refused.value.errors()] == [
            (loc, "extra_forbidden")
        ]
        # The API's own model, and so the HTTP route, still ignores the unknown key.
        TransferCreate.model_validate(bad)


def test_route_inputs_are_strict_self_contained_schemas_of_the_route_parameters():
    for action in ROUTE_ACTIONS.values():
        schema = action.arguments.model_json_schema()
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False and len(action.name) <= 80
        assert "\n" not in action.description
    create = ROUTE_ACTIONS["create_supplier"].arguments
    assert create.model_json_schema()["required"] == ["body"]
    for bad in ({}, {"body": {}}, {"body": {"name": "A"}, "path": "/api/v1/users"}):
        with pytest.raises(ValidationError):
            create.model_validate(bad)
    update = ROUTE_ACTIONS["update_sku"].arguments
    with pytest.raises(ValidationError):
        update.model_validate({"sku_id": "../users", "body": {}})
    # Query parameters keep the API's own names, types and limits.
    report = ROUTE_ACTIONS["profit_loss"].arguments.model_validate(
        {"from": "2026-01-01", "to": "2026-01-31"}
    )
    assert report.model_dump(mode="json") == {"from_date": "2026-01-01", "to_date": "2026-01-31"}
    with pytest.raises(ValidationError):
        ROUTE_ACTIONS["list_journals"].arguments.model_validate({"limit": 101})


def _derive(build, tag="skus"):
    api = FastAPI()
    router = APIRouter(prefix="/api/v1/things", tags=[tag])
    build(router)
    api.include_router(router)
    return api


class _Thing(BaseModel):
    name: str


def test_underivable_or_unclassified_routes_fail_closed():
    staff = Depends(get_current_user_id)

    def offered(router):
        @router.get("", response_model=_Thing)
        async def home_summary(_=staff): ...

        @router.post("", response_model=_Thing)
        async def make_thing(body: _Thing, _=Depends(require_transfer)): ...

        @router.post("/upload", response_model=_Thing)
        async def upload_thing(file: UploadFile = File(...), _=staff): ...

        @router.get("/{thing_id}/pdf")
        async def thing_pdf(thing_id: uuid.UUID, _=staff) -> Response: ...

        @router.get("/public", response_model=_Thing)
        async def public_thing(): ...

    api = _derive(offered)
    reasons = {route.name: exclusion(route) for route in api_routes(api)}
    assert reasons == {
        "home_summary": None,
        "make_thing": None,
        "upload_thing": "files",
        "thing_pdf": "files",
        "public_thing": "non-staff",
    }
    actions = {action.name: action for action in route_actions(api, frozenset({"home_summary"}))}
    assert set(actions) == {"skus_home_summary", "make_thing"}
    assert actions["make_thing"].permissions == ("stock.transfer",)
    assert actions["make_thing"].effect == "write"

    unknown = _derive(offered, tag="brand-new")
    assert {exclusion(route) for route in api_routes(unknown)} == {UNCLASSIFIED}
    assert route_actions(unknown, frozenset()) == ()

    def two_guards(router):
        @router.post("", response_model=_Thing)
        async def guarded(_=Depends(require_transfer), __=Depends(require_catalogue_mutate)): ...

    def empty_guard(router):
        @router.post("", response_model=_Thing)
        async def guarded(_=Depends(_require())): ...

    def custom_header(router):
        @router.get("", response_model=_Thing)
        async def headed(x_company: str = Header(), _=staff): ...

    def body_name_taken(router):
        @router.post("", response_model=_Thing)
        async def named(body: uuid.UUID, data: _Thing, _=staff): ...

    def text_path(router):
        # `/things/{name}` with name `upload` would reach the sibling route.
        @router.get("/{name}", response_model=_Thing)
        async def by_name(name: str, _=staff): ...

    def number_path(router):
        @router.get("/{number}", response_model=_Thing)
        async def by_number(number: int, _=staff): ...

    assert [action.name for action in route_actions(_derive(number_path), frozenset())] == [
        "by_number"
    ]
    for build in (two_guards, empty_guard, custom_header, body_name_taken, text_path):
        with pytest.raises(TypeError, match="MCP cannot"):
            route_actions(_derive(build), frozenset())


ROUTE_ACTION_NAMES = Path(__file__).with_name("mcp_route_action_names.txt")


def test_route_action_names_are_pinned():
    assert sorted(ROUTE_ACTIONS) == ROUTE_ACTION_NAMES.read_text().split(), (
        "Route action names come from endpoint function names and are saved in MCP write "
        "receipts. Renaming, adding or removing an offered endpoint renames a persisted MCP "
        f"action: update {ROUTE_ACTION_NAMES.name} deliberately."
    )


@pytest.mark.parametrize(
    ("task", "action"),
    [
        ("create a product", "create_sku"),
        ("receive a purchase order", "receive_purchase_order"),
        ("complete a stocktake", "complete_stocktake"),
        ("record a customer payment", "create_payment"),
        ("post a journal", "post_journal"),
        ("create a layby", "create_layby"),
        ("raise a purchase order", "create_purchase_order"),
        ("cancel a delivery", "cancel_delivery"),
        ("aged stock", "aged_stock"),
        # `lock_period` locks a VAT201 period.
        ("close a books period", "lock_books_period"),
    ],
)
def test_staff_tasks_find_their_action_in_the_first_three(task, action):
    found = search_actions(task, "", EVERY_PERMISSION)["actions"]
    assert action in [item["name"] for item in found]


def test_search_finds_route_actions_and_ranks_hand_written_actions_first_on_a_tie():
    def found(query, tab=""):
        return [item["name"] for item in search_actions(query, tab, EVERY_PERMISSION)["actions"]]

    assert found("draft transfer", "Warehouse")[0] == "transfers_create_draft"
    assert found("cancel draft transfer")[0] == "transfers_cancel_draft"
    assert found("complete stocktake")[0] == "complete_stocktake"
    assert found("post journal")[0] == "post_journal"
    assert "create_sku" in found("create sku")
    # Equal scores: the hand-written read comes first, then route actions by name.
    assert found("payment") == ["payments_find", "create_payment", "list_open_payment_documents"]
    # A route's synthesised description repeats its name and earns nothing on top.
    assert found("create transfer")[:2] == ["transfers_create_draft", "create_transfer"]
    assert "create_sku" not in found("create sku", "Books")
    # Without the key only the routes open to all staff remain.
    assert found("create sku") != [
        item["name"] for item in search_actions("create sku", "", set())["actions"]
    ]
    assert all(
        ACTIONS[item["name"]].permissions == ()
        for item in search_actions("create sku", "", set())["actions"]
    )

    index = actions_index(EVERY_PERMISSION)
    assert "\n## Catalogue / Catalogue\n" in index and "inputSchema" not in index
    assert "\ncreate_sku (write): Create sku. POST /api/v1/skus\n" in index
    assert sum("): " in line for line in index.splitlines()) == len(ACTIONS)
    limited = actions_index({"stock.transfer"})
    assert "cancel_transfer (write)" in limited and "create_sku" not in limited
    assert "get_sku (read)" in limited


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qty: int


class _Args(Arguments):
    name: str = "x"
    q: str | None = None


def _runner_app(hits):
    api = FastAPI()

    @api.get("/api/v1/things/{name}")
    async def thing(name: str, q: str | None = None):
        hits.append(("thing", name, q))
        return {"name": name, "q": q}

    @api.get("/api/v1/things/{name}/secret")
    async def secret(name: str):
        hits.append(("secret", name))
        return {"secret": True}

    @api.get("/api/v1/other")
    async def other():
        hits.append(("other",))
        return {"other": True}

    @api.api_route("/api/v1/answer/{name}", methods=["GET", "POST"])
    async def answer(name: str):
        if name == "forbidden":
            raise HTTPException(403, "You lack till.discount")
        if name == "conflict":
            raise HTTPException(409, "Owner access required")
        if name == "payload":
            return JSONResponse({"detail": {"code": "kit", "skus": ["A"]}}, status_code=409)
        if name == "crash":
            raise RuntimeError("database password is hunter2")
        if name == "slow":
            await asyncio.sleep(5)
        if name == "big":
            return {"id": "42", "rows": ["x" * 1024] * (MAX_RESULT_BYTES // 1024 + 1)}
        if name == "list":
            return [1, 2]
        return Response(status_code=204)

    @api.post("/api/v1/strict")
    async def strict(body: _Strict):
        return body

    return api


def _call(api, path, method="GET", path_params=("name",), query=(("q", "q"),)):
    return RouteCall(api, method, path, path_params, query)


async def test_a_parameter_value_cannot_change_which_route_is_called():
    hits: list = []
    route = _call(_runner_app(hits), "/api/v1/things/{name}")
    for value in ("x/secret", "..", "../other", ".", "x?y=1", "x%2Fsecret", "x#f", "x\\secret", ""):
        outcome = await run_route(route, _Args(name=value), None)
        assert outcome.error == "Invalid arguments: name (unsafe_path_value)", value
    assert hits == []
    # A query value travels as data, whatever it contains.
    nasty = "a/../b?c=d&q=e%2F#f"
    outcome = await run_route(route, _Args(name="ok", q=nasty), None)
    assert outcome.result == {"name": "ok", "q": nasty}
    assert hits == [("thing", "ok", nasty)]


async def test_route_answers_map_to_denial_refusal_unknown_and_size_limit(monkeypatch):
    api = _runner_app([])

    async def answer(name, method="GET"):
        return await run_route(_call(api, "/api/v1/answer/{name}", method), _Args(name=name), None)

    denied = await answer("forbidden")
    assert (denied.audit, denied.status, denied.error) == ("denied", 403, UNAVAILABLE)
    conflict = await answer("conflict", "POST")
    assert (conflict.audit, conflict.status, conflict.error) == (
        "failed",
        409,
        "Owner access required",
    )
    assert (await answer("payload")).error == '{"code":"kit","skus":["A"]}'
    crash = await answer("crash", "POST")
    assert (crash.audit, crash.status, crash.error) == ("failed", None, UNKNOWN_OUTCOME)
    assert (await answer("crash")).error == READ_FAILED
    monkeypatch.setattr(mcp_route_runner, "ROUTE_TIMEOUT_SECONDS", 0.05)
    slow = await answer("slow", "POST")
    assert (slow.status, slow.error) == (None, UNKNOWN_OUTCOME)

    big = await answer("big")
    assert big.audit == "failed" and big.result is None
    assert "limit is 128 KB" in big.error and "filters" in big.error
    # A completed write is never failed by its response size. Its receipt stays small.
    written = await answer("big", "POST")
    assert (written.audit, written.result) == ("success", None)
    assert written.receipt == {"id": "42", "http_status": 200}
    assert (await answer("list")).result == {"items": [1, 2]}
    done = await answer("none", "POST")
    assert (done.result, done.receipt) == ({}, {"http_status": 204})

    invalid = await run_route(
        _call(api, "/api/v1/strict", "POST", (), ()), _Args(), {"qty": "private-value", "x": 1}
    )
    assert invalid.status == 422 and "private-value" not in invalid.error
    assert invalid.error == "Invalid arguments: body.qty (int_parsing), body.x (extra_forbidden)"


def test_receipt_keeps_top_level_identifiers_only():
    assert receipt_fields(
        201,
        {
            "id": "7",
            "number": "TR-1",
            "status": "draft",
            "customer_id": "c1",
            "invoice_number": "INV-1",
            "paid": False,
            "total": 12.5,
            "name": "A Person",
            "email": "a@example.com",
            "phone": "+27 11 000 0000",
            "state": "Gauteng",
            "vat_number": "4000000000",
            "cipc_number": "2020/000000/07",
            "notes": None,
            "lines": [{"id": 1}],
            "customer": {"email": "a@example.com"},
            "long_id": "x" * 201,
        },
    ) == {
        "id": "7",
        "number": "TR-1",
        "status": "draft",
        "customer_id": "c1",
        "invoice_number": "INV-1",
        "http_status": 201,
    }


def test_services_never_import_routers():
    """A service depends on nothing above it; marks reach the catalogue through the app."""
    imported = []
    for module in (Path(__file__).parents[1] / "app" / "services").rglob("*.py"):
        for node in ast.walk(ast.parse(module.read_text())):
            if isinstance(node, ast.Import):
                imported += [(module.name, alias.name) for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                # `from app import routers` and `from app.routers.x import y` both name app.routers.
                imported += [(module.name, f"{node.module}.{alias.name}") for alias in node.names]
    assert [item for item in imported if f"{item[1]}.".startswith("app.routers.")] == []
