from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime, timedelta
import asyncio
import random
import os

TOKEN = os.environ.get("BOT_TOKEN")

HELP_TEXT = (
    "🤖 <b>My Reminder Bot</b>\n\n"
    "⏰ <b>/remind 20:30 текст</b> — сьогодні\n"
    "📅 <b>/remind 2026-01-20 12:00 текст</b>\n"
    "⏳ <b>/in 15 текст</b> — через 15 хв\n"
    "📋 <b>/list</b> — всі нагадування\n"
    "❌ <b>/cancel ID</b>\n"
    "👑 <b>/boss Імʼя</b>\n"
    "ℹ️ <b>/help</b>"
)

reminders = {}
reminder_id = 1
boss_names = {}

def get_boss(chat_id):
    return boss_names.get(chat_id, "Бос")

def get_phrase(chat_id):
    boss = get_boss(chat_id)
    return f"⏰ <b>{boss}</b>, нагадую:"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот онлайн!", parse_mode="HTML")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML")

async def set_boss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    boss_names[update.message.chat_id] = " ".join(context.args)
    await update.message.reply_text("👑 Гаразд!")

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global reminder_id
    chat_id = update.message.chat_id
    parts = update.message.text.split()

    if len(parts[1]) == 5:
        remind_at = datetime.combine(
            datetime.now().date(),
            datetime.strptime(parts[1], "%H:%M").time()
        )
        text = " ".join(parts[2:])
    else:
        remind_at = datetime.strptime(parts[1] + " " + parts[2], "%Y-%m-%d %H:%M")
        text = " ".join(parts[3:])

    delay = (remind_at - datetime.now()).total_seconds()
    if delay <= 0:
        await update.message.reply_text("❌ Час минув")
        return

    current_id = reminder_id
    reminder_id += 1

    reminders.setdefault(chat_id, []).append({
        "id": current_id,
        "time": remind_at,
        "text": text
    })

    await update.message.reply_text(f"✅ Нагадування #{current_id}")

    await asyncio.sleep(delay)
    await update.message.reply_text(f"{get_phrase(chat_id)}\n\n{text}", parse_mode="HTML")

async def remind_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    minutes = int(context.args[0])
    text = " ".join(context.args[1:])
    await asyncio.sleep(minutes * 60)
    await update.message.reply_text(f"⏰ Нагадування:\n{text}")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in reminders:
        await update.message.reply_text("📭 Порожньо")
        return

    msg = ""
    for r in reminders[chat_id]:
        msg += f"#{r['id']} ⏰ {r['time']} — {r['text']}\n"
    await update.message.reply_text(msg)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    rid = int(context.args[0])
    reminders[chat_id] = [r for r in reminders.get(chat_id, []) if r["id"] != rid]
    await update.message.reply_text("❌ Скасовано")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("boss", set_boss))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("in", remind_in))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.run_polling()

if __name__ == "__main__":
    main()
