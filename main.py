"""Точка входа Telegram-бота ECHOCHAIN."""
import asyncio
import os
import secrets
import string
import json
from html import escape

from dotenv import load_dotenv

# Загружаем настройки из .env, если файл существует.
# Переменные окружения хостинга имеют приоритет.
load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo
from aiohttp import web

from api import create_app

from database.database import (
    add_event, create_artifact, create_colony, get_artifact, init_db,
    list_artifacts, list_colonies, list_colony_artifacts, mutate_artifact,
    remember_user, settle_artifact, stats,
)
from engine.world_engine import Genome, evolve
from channel_publisher import router as channel_router

dp = Dispatcher()
dp.include_router(channel_router)


def code_for_artifact() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "EC-" + "".join(secrets.choice(alphabet) for _ in range(6))


def format_genome(genome: dict[str, int]) -> str:
    labels = {
        "stability": "Устойчивость",
        "energy": "Энергия",
        "resonance": "Резонанс",
        "adaptation": "Адаптация",
        "complexity": "Сложность",
    }
    return "\n".join(f"• {labels[key]}: {value}/100" for key, value in genome.items())


@dp.message(CommandStart())
async def start(message: Message) -> None:
    user = message.from_user
    if user:
        remember_user(user.id, user.username)
        add_event("user_entered", user.id)
    webapp_url = os.getenv("WEBAPP_URL", "").strip()
    keyboard = None
    if webapp_url:
        if not webapp_url.startswith("https://"):
            raise RuntimeError("WEBAPP_URL должен начинаться с https://")
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Открыть ECHOCHAIN", web_app=WebAppInfo(url=webapp_url))]],
            resize_keyboard=True,
        )
    await message.answer(
        "🜂 <b>ECHOCHAIN</b>\n"
        "Общая цифровая цивилизация, которая развивается вместе со своими участниками.\n\n"
        "Вселенная активна. Первое Эхо ждёт своего создателя.\n\n"
        "Используй /help, чтобы узнать доступные команды.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@dp.message(Command("myid"))
async def my_id(message: Message) -> None:
    if message.from_user:
        await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@dp.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "<b>Команды ECHOCHAIN</b>\n"
        "/universe — состояние вселенной\n"
        "/create [название] — создать артефакт\n"
        "/artifact КОД — посмотреть артефакт\n"
        "/mutate КОД — развить артефакт\n"
        "/colony — список колоний\n"
        "/colony create НАЗВАНИЕ — основать колонию\n"
        "/colony settle КОД НАЗВАНИЕ — поселить свой артефакт\n"
        "/colony artifacts НАЗВАНИЕ — список артефактов колонии\n"
        "/myid — узнать свой Telegram ID\n"
        "/channel_status — настройки канала (владелец)\n"
        "/release ТЕКСТ — опубликовать обычную новость (владелец)\n"
        "/announce ТЕКСТ — отправить важную публикацию на подтверждение (владелец)",
        parse_mode="HTML",
    )


@dp.message(Command("universe"))
async def universe(message: Message) -> None:
    s = stats()
    recent = list_artifacts(3)
    lines = [
        "🌌 <b>ВСЕЛЕННАЯ ECHOCHAIN</b>",
        "Состояние: <b>АКТИВНА</b>",
        f"Известные участники: {s['users']}",
        f"Артефакты: {s['artifacts']}",
        f"Колонии: {s['colonies']}",
        f"Записанные события: {s['events']}",
    ]
    if recent:
        lines.append("\nНедавно созданные артефакты:")
        lines.extend(
            f"• <code>{escape(str(row['code']))}</code> — {escape(str(row['name']))} (поколение {row['generation']})"
            for row in recent
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("create"))
async def create(message: Message) -> None:
    user = message.from_user
    if not user:
        return
    remember_user(user.id, user.username)
    name = (message.text or "").partition(" ")[2].strip() or "Безымянное Эхо"
    name = " ".join(name.split())[:48]
    code = code_for_artifact()
    genome = Genome()
    create_artifact(code, user.id, name, genome.to_dict())
    await message.answer(
        "✧ <b>АРТЕФАКТ СОЗДАН</b>\n"
        f"Название: {escape(name)}\nКод: <code>{escape(code)}</code>\nПоколение: 0\n\n"
        f"{format_genome(genome.to_dict())}\n\n"
        f"Посмотреть артефакт: /artifact {code}",
        parse_mode="HTML",
    )


@dp.message(Command("artifact"))
async def artifact(message: Message) -> None:
    code = (message.text or "").partition(" ")[2].strip().upper()
    if not code:
        await message.answer("Использование: /artifact EC-ABC123")
        return
    row = get_artifact(code)
    if not row:
        await message.answer("Артефакт с таким кодом не найден.")
        return
    genome = json.loads(row["genome_json"])
    parent = row["parent_code"] or "ИСТОК"
    await message.answer(
        "✧ <b>ЗАПИСЬ ОБ АРТЕФАКТЕ</b>\n"
        f"Название: {escape(str(row['name']))}\nКод: <code>{escape(str(row['code']))}</code>\n"
        f"Поколение: {row['generation']}\nРодитель: <code>{escape(str(parent))}</code>\n\n"
        f"{format_genome(genome)}",
        parse_mode="HTML",
    )


@dp.message(Command("mutate"))
async def mutate(message: Message) -> None:
    user = message.from_user
    code = (message.text or "").partition(" ")[2].strip().upper()
    if not user:
        return
    if not code:
        await message.answer("Использование: /mutate EC-ABC123")
        return
    row = get_artifact(code)
    if not row:
        await message.answer("Артефакт с таким кодом не найден.")
        return
    parent_genome = Genome.from_json(row["genome_json"])
    next_generation = int(row["generation"]) + 1
    next_genome = evolve(parent_genome, code, next_generation)
    result = mutate_artifact(code, next_genome.to_dict(), user.id)
    if result is None:
        await message.answer("Артефакт изменился до сохранения мутации. Попробуй ещё раз.")
        return
    generation, name = result
    await message.answer(
        "⟁ <b>МУТАЦИЯ ЗАПИСАНА</b>\n"
        f"Артефакт: {escape(name)} (<code>{escape(code)}</code>)\n"
        f"Поколение: {generation}\n\n"
        f"{format_genome(next_genome.to_dict())}\n\n"
        "Результат определяет система, а не голосование.",
        parse_mode="HTML",
    )


@dp.message(Command("colony"))
async def colony(message: Message) -> None:
    user = message.from_user
    args = (message.text or "").partition(" ")[2].strip()
    if args.lower().startswith("settle "):
        if not user:
            return
        parts = args[7:].strip().split(maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            await message.answer(
                "Использование: /colony settle EC-ABC123 НАЗВАНИЕ",
            )
            return
        remember_user(user.id, user.username)
        status, colony_name = settle_artifact(parts[0], parts[1], user.id)
        if status == "settled":
            await message.answer(
                f"🪐 Артефакт <code>{escape(parts[0].upper())}</code> поселён в колонии "
                f"<b>{escape(colony_name or parts[1])}</b>.",
                parse_mode="HTML",
            )
        elif status == "artifact_not_found":
            await message.answer("Артефакт с таким кодом не найден.")
        elif status == "colony_not_found":
            await message.answer("Колония с таким названием не найдена.")
        elif status == "not_owner":
            await message.answer("Поселить можно только артефакт, созданный тобой.")
        elif status == "not_member":
            await message.answer("Сначала нужно стать участником этой колонии.")
        else:
            await message.answer("Этот артефакт уже поселён в одной из колоний.")
        return

    if args.lower().startswith("artifacts "):
        colony_name = args[9:].strip()
        if not colony_name:
            await message.answer("Использование: /colony artifacts НАЗВАНИЕ")
            return
        artifacts = list_colony_artifacts(colony_name)
        if not artifacts:
            await message.answer(
                "В этой колонии пока нет поселённых артефактов или колония не найдена."
            )
            return
        lines = [f"🪐 <b>АРТЕФАКТЫ КОЛОНИИ: {escape(colony_name[:40])}</b>"]
        lines.extend(
            f"• <b>{escape(str(row['name']))}</b> — <code>{escape(str(row['code']))}</code> "
            f"(поколение {row['generation']})"
            for row in artifacts
        )
        await message.answer("\n".join(lines), parse_mode="HTML")
        return

    if args.lower().startswith("create "):
        if not user:
            return
        name = args[7:].strip()
        if not name:
            await message.answer("Использование: /colony create НАЗВАНИЕ")
            return
        remember_user(user.id, user.username)
        _, created = create_colony(name, user.id)
        if created:
            await message.answer(f"🪐 Колония основана: <b>{escape(name[:40])}</b>", parse_mode="HTML")
        else:
            await message.answer("Колония с таким названием уже существует.")
        return
    colonies = list_colonies()
    if not colonies:
        await message.answer("Колоний пока нет. Основать первую можно командой /colony create НАЗВАНИЕ")
        return
    lines = ["🪐 <b>ИЗВЕСТНЫЕ КОЛОНИИ</b>"]
    lines.extend(
        f"• {escape(str(row['name']))} — участников: {row['members']}, "
        f"артефактов: {row['artifacts']}"
        for row in colonies
    )
    lines.append("\nОсновать колонию: /colony create НАЗВАНИЕ")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def main() -> None:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "put_your_telegram_bot_token_here":
        raise RuntimeError("Не задан BOT_TOKEN. Добавь его в переменные хостинга или в файл .env.")
    init_db()
    bot = Bot(token=token)
    app = create_app(token)
    runner = web.AppRunner(app)
    await runner.setup()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"ECHOCHAIN HTTP server listening on {host}:{port}")
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
