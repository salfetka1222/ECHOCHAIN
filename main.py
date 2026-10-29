"""ECHOCHAIN Telegram bot entry point."""
import asyncio
import os
import secrets
import string
import json
from html import escape

from dotenv import load_dotenv

# Load private server configuration from .env when present.
# Environment variables supplied by the hosting panel take precedence.
load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from database.database import (
    add_event, create_artifact, create_colony, get_artifact, init_db,
    list_artifacts, list_colonies, mutate_artifact, remember_user, stats,
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
        "stability": "Stability",
        "energy": "Energy",
        "resonance": "Resonance",
        "adaptation": "Adaptation",
        "complexity": "Complexity",
    }
    return "\n".join(f"• {labels[key]}: {value}/100" for key, value in genome.items())


@dp.message(CommandStart())
async def start(message: Message) -> None:
    user = message.from_user
    if user:
        remember_user(user.id, user.username)
        add_event("user_entered", user.id)
    await message.answer(
        "🜂 <b>ECHOCHAIN</b>\n"
        "A shared evolving digital civilization.\n\n"
        "Universe online. The first Echo is waiting.\n\n"
        "Use /help to explore the commands.",
        parse_mode="HTML",
    )


@dp.message(Command("myid"))
async def my_id(message: Message) -> None:
    if message.from_user:
        await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@dp.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "<b>ECHOCHAIN commands</b>\n"
        "/universe — universe status\n"
        "/create [name] — create an artifact\n"
        "/artifact CODE — inspect an artifact\n"
        "/mutate CODE — evolve an artifact\n"
        "/colony — list colonies\n"
        "/colony create NAME — found a colony\n"
        "/myid — show your Telegram ID\n"
        "/channel_status — channel configuration (owner)\n"
        "/release TEXT — publish a routine development update (owner)\n"
        "/announce TEXT — submit an important post for approval (owner)",
        parse_mode="HTML",
    )


@dp.message(Command("universe"))
async def universe(message: Message) -> None:
    s = stats()
    recent = list_artifacts(3)
    lines = [
        "🌌 <b>ECHOCHAIN UNIVERSE</b>",
        "State: <b>ONLINE</b>",
        f"Known users: {s['users']}",
        f"Artifacts: {s['artifacts']}",
        f"Colonies: {s['colonies']}",
        f"Recorded echoes: {s['events']}",
    ]
    if recent:
        lines.append("\nRecent artifacts:")
        lines.extend(f"• <code>{escape(str(row['code']))}</code> — {escape(str(row['name']))} (Gen {row['generation']})" for row in recent)
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("create"))
async def create(message: Message) -> None:
    user = message.from_user
    if not user:
        return
    remember_user(user.id, user.username)
    name = (message.text or "").partition(" ")[2].strip() or "Unnamed Echo"
    name = " ".join(name.split())[:48]
    code = code_for_artifact()
    genome = Genome()
    create_artifact(code, user.id, name, genome.to_dict())
    await message.answer(
        "✧ <b>ARTIFACT CREATED</b>\n"
        f"Name: {escape(name)}\nCode: <code>{escape(code)}</code>\nGeneration: 0\n\n"
        f"{format_genome(genome.to_dict())}\n\n"
        f"Inspect it with /artifact {code}",
        parse_mode="HTML",
    )


@dp.message(Command("artifact"))
async def artifact(message: Message) -> None:
    code = (message.text or "").partition(" ")[2].strip().upper()
    if not code:
        await message.answer("Usage: /artifact EC-ABC123")
        return
    row = get_artifact(code)
    if not row:
        await message.answer("No artifact found with that code.")
        return
    genome = json.loads(row["genome_json"])
    parent = row["parent_code"] or "ORIGIN"
    await message.answer(
        "✧ <b>ARTIFACT RECORD</b>\n"
        f"Name: {escape(str(row['name']))}\nCode: <code>{escape(str(row['code']))}</code>\n"
        f"Generation: {row['generation']}\nParent: <code>{escape(str(parent))}</code>\n\n"
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
        await message.answer("Usage: /mutate EC-ABC123")
        return
    row = get_artifact(code)
    if not row:
        await message.answer("No artifact found with that code.")
        return
    parent_genome = Genome.from_json(row["genome_json"])
    next_generation = int(row["generation"]) + 1
    next_genome = evolve(parent_genome, code, next_generation)
    result = mutate_artifact(code, next_genome.to_dict(), user.id)
    if result is None:
        await message.answer("The artifact changed before mutation could be saved. Try again.")
        return
    generation, name = result
    await message.answer(
        "⟁ <b>MUTATION RECORDED</b>\n"
        f"Artifact: {escape(name)} (<code>{escape(code)}</code>)\n"
        f"Generation: {generation}\n\n"
        f"{format_genome(next_genome.to_dict())}\n\n"
        "The outcome is determined by the system, not a vote.",
        parse_mode="HTML",
    )


@dp.message(Command("colony"))
async def colony(message: Message) -> None:
    user = message.from_user
    args = (message.text or "").partition(" ")[2].strip()
    if args.lower().startswith("create "):
        if not user:
            return
        name = args[7:].strip()
        if not name:
            await message.answer("Usage: /colony create NAME")
            return
        remember_user(user.id, user.username)
        _, created = create_colony(name, user.id)
        if created:
            await message.answer(f"🪐 Colony founded: <b>{escape(name[:40])}</b>", parse_mode="HTML")
        else:
            await message.answer("A colony with that name already exists.")
        return
    colonies = list_colonies()
    if not colonies:
        await message.answer("No colonies yet. Found the first one with /colony create NAME")
        return
    lines = ["🪐 <b>KNOWN COLONIES</b>"]
    lines.extend(f"• {escape(str(row['name']))} — {row['members']} member(s)" for row in colonies)
    lines.append("\nCreate one with /colony create NAME")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def main() -> None:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "put_your_telegram_bot_token_here":
        raise RuntimeError("BOT_TOKEN is missing. Set it as an environment variable in your host or .env file.")
    init_db()
    bot = Bot(token=token)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
