"""Telegram news-channel publishing and owner approval workflow."""
import logging
import os
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from database.database import add_pending_channel_post
from database.channel_posts import (
    claim_pending_channel_post,
    finish_channel_post,
    reject_pending_channel_post,
    release_channel_post,
)

router = Router(name="channel_publisher")
logger = logging.getLogger(__name__)


def _owner_id() -> int | None:
    value = os.getenv("OWNER_ID", "").strip()
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _channel_id() -> str:
    return os.getenv("CHANNEL_CHAT_ID", "").strip()


def _approval_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Опубликовать", callback_data=f"chpost:approve:{post_id}"),
        InlineKeyboardButton(text="Отклонить", callback_data=f"chpost:reject:{post_id}"),
    ]])


async def publish_channel_event(bot, text: str, important: bool = False) -> bool:
    """Publish a routine update or queue an important post for owner approval."""
    channel_id = _channel_id()
    if not channel_id:
        logger.info("Channel publishing skipped: CHANNEL_CHAT_ID is not configured.")
        return False

    if not important:
        try:
            await bot.send_message(
                chat_id=channel_id, text=escape(text), parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return True
        except Exception:
            logger.exception("Could not publish routine channel update.")
            return False

    owner_id = _owner_id()
    if owner_id is None:
        logger.error("Important post was not queued: OWNER_ID is missing or invalid.")
        return False

    post_id = add_pending_channel_post(text[:3500], owner_id)
    try:
        await bot.send_message(
            chat_id=owner_id,
            text=("📝 <b>Публикация ожидает подтверждения</b>\n\n"
                  f"{escape(text[:3500])}\n\nНомер: <code>{post_id}</code>"),
            parse_mode="HTML", reply_markup=_approval_keyboard(post_id),
            disable_web_page_preview=True,
        )
        return True
    except Exception:
        logger.exception("Could not deliver approval request to OWNER_ID.")
        return False


@router.message(Command("channel_status"))
async def channel_status(message: Message) -> None:
    owner_id = _owner_id()
    if not message.from_user or owner_id is None or message.from_user.id != owner_id:
        await message.answer("Эта команда доступна только владельцу проекта.")
        return
    channel_ready = bool(_channel_id())
    await message.answer(
        "📡 <b>Настройки канала</b>\n"
        f"CHANNEL_CHAT_ID: {'задан' if channel_ready else 'не задан'}\n"
        f"OWNER_ID: {'задан' if owner_id else 'не задан'}\n"
        "Права администратора бота в канале проверяются при первой публикации.",
        parse_mode="HTML",
    )


@router.message(Command("announce"))
async def announce(message: Message) -> None:
    owner_id = _owner_id()
    if not message.from_user or owner_id is None or message.from_user.id != owner_id:
        await message.answer("Эта команда доступна только владельцу проекта.")
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /announce Текст важного объявления")
        return
    if not _channel_id():
        await message.answer("Сначала настрой CHANNEL_CHAT_ID на хостинге.")
        return

    post_id = add_pending_channel_post(text[:3500], owner_id)
    await message.answer(
        "📝 <b>Черновик важной публикации</b>\n\n"
        f"{escape(text[:3500])}\n\nНомер: <code>{post_id}</code>\n"
        "Публикация появится в канале только после подтверждения.",
        parse_mode="HTML", reply_markup=_approval_keyboard(post_id),
        disable_web_page_preview=True,
    )


@router.callback_query(lambda callback: bool(callback.data and callback.data.startswith("chpost:")))
async def handle_channel_approval(callback: CallbackQuery) -> None:
    owner_id = _owner_id()
    if not callback.from_user or owner_id is None or callback.from_user.id != owner_id:
        await callback.answer("Нет доступа.", show_alert=True)
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 3 or parts[1] not in {"approve", "reject"}:
        await callback.answer("Некорректная команда.")
        return
    try:
        post_id = int(parts[2])
    except ValueError:
        await callback.answer("Некорректный номер публикации.")
        return

    action = parts[1]
    if action == "reject":
        if not reject_pending_channel_post(post_id):
            await callback.answer("Публикация уже обрабатывается или обработана.")
            return
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Публикация отклонена.")
        return

    # Claim before sending: a second click cannot publish the same post again.
    post = claim_pending_channel_post(post_id)
    if post is None:
        await callback.answer("Публикация уже обрабатывается или обработана.")
        return

    channel_id = _channel_id()
    if not channel_id:
        release_channel_post(post_id)
        await callback.answer("Не настроен CHANNEL_CHAT_ID.", show_alert=True)
        return

    try:
        sent = await callback.bot.send_message(
            chat_id=channel_id, text=escape(str(post["text"])),
            parse_mode="HTML", disable_web_page_preview=True,
        )
    except Exception:
        logger.exception("Could not publish approved channel post.")
        release_channel_post(post_id)
        await callback.answer("Не удалось опубликовать. Можно попробовать ещё раз.", show_alert=True)
        return

    finish_channel_post(post_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Опубликовано.")
    await callback.message.answer(
        f"✅ Публикация отправлена в канал. Сообщение: <code>{sent.message_id}</code>",
        parse_mode="HTML",
    )


@router.message(Command("release"))
async def release(message: Message) -> None:
    owner_id = _owner_id()
    if not message.from_user or owner_id is None or message.from_user.id != owner_id:
        await message.answer("Эта команда доступна только владельцу проекта.")
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /release Текст обычной новости разработки")
        return
    if not _channel_id():
        await message.answer("Сначала настрой CHANNEL_CHAT_ID на хостинге.")
        return
    published = await publish_channel_event(
        message.bot, "🛠 НОВОСТИ РАЗРАБОТКИ\n\n" + text[:3500], important=False,
    )
    if published:
        await message.answer("✅ Обычная новость опубликована в канале.")
    else:
        await message.answer("Не удалось опубликовать новость. Проверь настройки канала и права бота.")
