import os
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =========================
# НАЛАШТУВАННЯ
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if BOT_TOKEN is None:
    raise RuntimeError("BOT_TOKEN не заданий")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

REMINDERS = {}


# =========================
# ДОПОМІЖНІ ФУНКЦІЇ
# =========================

def parse_time(time_str):
    try:
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now()

        reminder_time = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )

        if reminder_time <= now:
            reminder_time += timedelta(days=1)

        return reminder_time
    except Exception:
        return None


async def reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"⏰ НАГАДУВАННЯ:\n{context.job.data}"
    )


# =========================
# КОМАНДИ
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт!\n\n"
        "Я бот-нагадувач.\n\n"
        "Команди:\n"
        "/add 18:30 Текст — додати\n"
        "/list — список\n"
        "/delete 1 — видалити"
    )


async def add_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /add 18:30 текст")
        return

    time_str = context.args[0]
    text = " ".join(context.args[1:])

    reminder_time = parse_time(time_str)
    if reminder_time is None:
        await update.message.reply_text("❌ Час у форматі HH:MM")
        return

    chat_id = update.effective_chat.id
    delay = (reminder_time - datetime.now()).total_seconds()

    job = context.job_queue.run_once(
        reminder_callback,
        delay,
        chat_id=chat_id,
        data=text
    )

    REMINDERS.setdefault(chat_id, []).append({
        "job_id": job.id,
        "time": time_str,
        "text": text
    })

    await update.message.reply_text(
        f"✅ Додано:\n⏰ {time_str}\n📌 {text}"
    )


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    items = REMINDERS.get(chat_id, [])

    if not items:
        await update.message.reply_text("📭 Нагадувань немає")
        return

    msg = "📋 Нагадування:\n"
    for i, r in enumerate(items, 1):
        msg += f"{i}. {r['time']} — {r['text']}\n"

    await update.message.reply_text(msg)


async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ /delete 1")
        return

    chat_id = update.effective_chat.id
    index = int(context.args[0]) - 1

    try:
        REMINDERS[chat_id].pop(index)
        await update.message.reply_text("🗑 Видалено")
    except Exception:
        await update.message.reply_text("❌ Невірний ID")


# =========================
# ЗАПУСК
# =========================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_reminder))
    app.add_handler(CommandHandler("list", list_reminders))
    app.add_handler(CommandHandler("delete", delete_reminder))

    logger.info("🤖 Бот запущений")
    app.run_polling()


if name == "__main__":
    main()
