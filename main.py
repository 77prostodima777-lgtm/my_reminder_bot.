import os
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ======================
# НАЛАШТУВАННЯ
# ======================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не знайдено в змінних середовища")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Тимчасове сховище (пізніше замінимо на БД)
REMINDERS = {}


# ======================
# ДОПОМІЖНІ ФУНКЦІЇ
# ======================

def parse_time(time_str: str) -> datetime | None:
    """
    Формат: HH:MM
    """
    try:
        now = datetime.now()
        hour, minute = map(int, time_str.split(":"))
        reminder_time = now.replace(hour=hour, minute=minute, second=0)

        if reminder_time < now:
            reminder_time += timedelta(days=1)

        return reminder_time
    except Exception:
        return None


async def reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    text = job.data

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ НАГАДУВАННЯ:\n{text}"
    )


# ======================
# КОМАНДИ
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт!\n\n"
        "Я бот-нагадувач.\n\n"
        "📌 Команди:\n"
        "/add HH:MM текст — додати нагадування\n"
        "/list — список нагадувань\n"
        "/delete ID — видалити нагадування\n"
        "/help — допомога"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 ДОВІДКА\n\n"
        "➕ Додати нагадування:\n"
        "/add 18:30 Купити воду\n\n"
        "📋 Переглянути список:\n"
        "/list\n\n"
        "❌ Видалити:\n"
        "/delete 1"
    )


async def add_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Неправильний формат\n"
            "Приклад:\n/add 18:30 Купити воду"
        )
        return

    time_str = context.args[0]
    text = " ".join(context.args[1:])

    reminder_time = parse_time(time_str)

    if not reminder_time:
        await update.message.reply_text("❌ Час має бути у форматі HH:MM")
        return

    chat_id = update.effective_chat.id

    job = context.job_queue.run_once(
        reminder_callback,
        when=(reminder_time - datetime.now()).total_seconds(),
        chat_id=chat_id,
        data=text,
    )

    REMINDERS.setdefault(chat_id, []).append({
        "id": job.id,
        "time": reminder_time.strftime("%H:%M"),
        "text": text,
    })

    await update.message.reply_text(
        f"✅ Нагадування додано!\n"
        f"🕒 {time_str}\n"
        f"📌 {text}"
    )


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    reminders = REMINDERS.get(chat_id, [])

    if not reminders:
        await update.message.reply_text("📭 У тебе немає нагадувань")
        return

    message = "📋 ТВОЇ НАГАДУВАННЯ:\n\n"
    for i, r in enumerate(reminders, start=1):
        message += f"{i}. ⏰ {r['time']} — {r['text']}\n"

    await update.message.reply_text(message)


async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Вкажи ID\n/delete 1")
        return

    chat_id = update.effective_chat.id
    reminders = REMINDERS.get(chat_id, [])

    try:
        index = int(context.args[0]) - 1
        reminder = reminders.pop(index)
        await update.message.reply_text("🗑 Нагадування видалено")
    except Exception:
        await update.message.reply_text("❌ Невірний ID")


# ======================
# ЗАПУСК БОТА
# ======================

def main():
    app = ApplicationBuilder().
