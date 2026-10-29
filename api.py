"""HTTP API and Telegram Mini App authentication for ECHOCHAIN."""
import hashlib
import hmac
import json
import os
import secrets
import string
import time
from urllib.parse import parse_qsl

from aiohttp import web

from database.database import (
    add_event, create_artifact, create_colony, get_artifact, get_colony,
    is_colony_member, list_artifacts, list_colonies, list_colony_artifacts,
    list_user_artifacts, mutate_artifact, recent_events, remember_user,
    settle_artifact, stats,
)
from engine.world_engine import Genome, evolve


def verify_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> dict:
    """Validate Telegram WebApp initData and return its signed user object."""
    if not init_data or not bot_token:
        raise ValueError("Telegram authentication is missing")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    values = dict(pairs)
    received_hash = values.pop("hash", "")
    if not received_hash:
        raise ValueError("Telegram signature is missing")

    check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Telegram signature is invalid")

    try:
        auth_date = int(values["auth_date"])
        user = json.loads(values["user"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Telegram authentication data is incomplete") from exc

    now = int(time.time())
    if auth_date > now + 60 or now - auth_date > max_age:
        raise ValueError("Telegram session has expired")
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise ValueError("Telegram user data is invalid")
    return user


def _artifact_json(row) -> dict:
    return {
        "code": row["code"],
        "name": row["name"],
        "generation": row["generation"],
        "genome": json.loads(row["genome_json"]),
        "parent_code": row["parent_code"],
        "creator_id": row["creator_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _event_json(row) -> dict:
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return {
        "id": row["id"],
        "type": row["event_type"],
        "artifact_code": row["artifact_code"],
        "payload": payload,
        "created_at": row["created_at"],
    }


def create_app(bot_token: str) -> web.Application:
    app = web.Application(client_max_size=64 * 1024)

    @web.middleware
    async def errors(request, handler):
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception:
            return web.json_response({"error": "Внутренняя ошибка сервера."}, status=500)

    app.middlewares.append(errors)

    def current_user(request):
        raw = request.headers.get("X-Telegram-Init-Data", "")
        try:
            user = verify_init_data(raw, bot_token)
        except ValueError as exc:
            raise web.HTTPUnauthorized(text=json.dumps({"error": str(exc)}, ensure_ascii=False),
                                       content_type="application/json")
        remember_user(user["id"], user.get("username"))
        return user

    async def health(_request):
        return web.json_response({"service": "ECHOCHAIN", "status": "ok"})

    async def me(request):
        user = current_user(request)
        return web.json_response({
            "id": user["id"],
            "first_name": user.get("first_name", ""),
            "username": user.get("username"),
        })

    async def universe(request):
        current_user(request)
        s = stats()
        return web.json_response({
            "stats": s,
            "recent_artifacts": [
                {"code": row["code"], "name": row["name"], "generation": row["generation"]}
                for row in list_artifacts(5)
            ],
        })

    async def artifacts(request):
        user = current_user(request)
        return web.json_response({
            "items": [_artifact_json(row) for row in list_user_artifacts(user["id"])]
        })

    async def create_artifact_route(request):
        user = current_user(request)
        data = await request.json()
        name = " ".join(str(data.get("name", "")).split())[:48] or "Безымянное Эхо"
        code = "EC-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        genome = Genome()
        create_artifact(code, user["id"], name, genome.to_dict())
        return web.json_response({"artifact": _artifact_json(get_artifact(code))}, status=201)

    async def mutate_artifact_route(request):
        user = current_user(request)
        code = request.match_info["code"].upper()
        row = get_artifact(code)
        if row is None:
            raise web.HTTPNotFound(text='{"error":"Артефакт не найден."}', content_type="application/json")
        if int(row["creator_id"]) != user["id"]:
            raise web.HTTPForbidden(text='{"error":"Развивать можно только свой артефакт."}',
                                    content_type="application/json")
        parent = Genome.from_json(row["genome_json"])
        generation = int(row["generation"]) + 1
        next_genome = evolve(parent, code, generation)
        result = mutate_artifact(code, next_genome.to_dict(), user["id"])
        if result is None:
            raise web.HTTPConflict(text='{"error":"Артефакт изменился. Обнови страницу."}',
                                   content_type="application/json")
        return web.json_response({"artifact": _artifact_json(get_artifact(code))})

    async def colonies(request):
        current_user(request)
        return web.json_response({
            "items": [
                {"name": row["name"], "members": row["members"], "artifacts": row["artifacts"]}
                for row in list_colonies(100)
            ]
        })

    async def create_colony_route(request):
        user = current_user(request)
        data = await request.json()
        name = " ".join(str(data.get("name", "")).split())[:40]
        if not name:
            raise web.HTTPBadRequest(text='{"error":"Укажи название колонии."}',
                                      content_type="application/json")
        _colony_id, created = create_colony(name, user["id"])
        if not created:
            raise web.HTTPConflict(text='{"error":"Колония с таким названием уже существует."}',
                                   content_type="application/json")
        return web.json_response({"name": name}, status=201)

    async def colony_artifacts(request):
        current_user(request)
        name = request.match_info["name"]
        colony = get_colony(name)
        if colony is None:
            raise web.HTTPNotFound(text='{"error":"Колония не найдена."}', content_type="application/json")
        items = [
            {"code": row["code"], "name": row["name"], "generation": row["generation"]}
            for row in list_colony_artifacts(name)
        ]
        return web.json_response({"colony": dict(colony), "items": items})

    async def settle_route(request):
        user = current_user(request)
        name = request.match_info["name"]
        data = await request.json()
        code = str(data.get("artifact_code", "")).strip().upper()
        status, colony_name = settle_artifact(code, name, user["id"])
        messages = {
            "artifact_not_found": "Артефакт не найден.",
            "colony_not_found": "Колония не найдена.",
            "not_owner": "Поселить можно только свой артефакт.",
            "not_member": "Сначала нужно стать участником колонии.",
            "already_settled": "Артефакт уже находится в колонии.",
        }
        if status != "settled":
            raise web.HTTPConflict(text=json.dumps({"error": messages.get(status, "Не удалось поселить артефакт.")},
                                                   ensure_ascii=False), content_type="application/json")
        return web.json_response({"status": status, "colony": colony_name})

    async def events(request):
        current_user(request)
        return web.json_response({"items": [_event_json(row) for row in recent_events(40)]})

    app.router.add_get("/health", health)
    app.router.add_get("/api/me", me)
    app.router.add_get("/api/universe", universe)
    app.router.add_get("/api/artifacts", artifacts)
    app.router.add_post("/api/artifacts", create_artifact_route)
    app.router.add_post("/api/artifacts/{code}/mutate", mutate_artifact_route)
    app.router.add_get("/api/colonies", colonies)
    app.router.add_post("/api/colonies", create_colony_route)
    app.router.add_get("/api/colonies/{name}/artifacts", colony_artifacts)
    app.router.add_post("/api/colonies/{name}/settle", settle_route)
    app.router.add_get("/api/events", events)

    web_dir = os.path.join(os.path.dirname(__file__), "webapp")
    app.router.add_get("/", lambda _request: web.FileResponse(os.path.join(web_dir, "index.html")))
    app.router.add_static("/assets/", os.path.join(web_dir, "assets"), show_index=False)
    return app
