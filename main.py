import os
import json
import uuid
from datetime import datetime, timedelta

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import gspread
from google.oauth2.service_account import Credentials


HELP_TEXT = (
    "🤖 <b>Reminder Bot</b>\n\n"
    "Команди:\n"
    "⏰ <b>/remind 20:30 текст</b> — нагадування сьогодні\n"
    "📅 <b>/remind 2026-01-15 12:00 текст</b> — нагадування на дату\n"
    "⏳ <b>/in 15 текст</b> — через 15 хв\n"
    "📋 <b>/list</b> — список\n"
    "❌ <b>/cancel ID</b> — скасувати\n"
    "ℹ️ <b>/help</b>\n"
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SHEET_ID = os.environ.get("SHEET_ID", "")
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON", "")

SHEET_NAME = "reminders"
POLL_SECONDS = 20  # як часто перевіряємо таблицю


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_datetime(parts: list[str]) -> datetime:
    """
    /remind 20:30 text
    /remind 2026-01-15 12:00 text
    """
    if len(parts) < 2:
        raise ValueError("No time")
    if len(parts[1]) == 5 and ":" in parts[1]:
        # HH:MM today
        t = datetime.strptime(parts[1], "%H:%M").time()
        dt = datetime.combine(datetime.now().date(), t)
        return dt
    # YYYY-MM-DD HH:MM
    if len(parts) < 3:
        raise ValueError("No date-time")
    return datetime.strptime(f"{parts[1]} {parts[2]}", "%Y-%m-%d %H:%M")


def get_ws():
    if not GOOGLE_CREDS_JSON:
        raise RuntimeError("GOOGLE_CREDS_JSON is empty")
    creds_dict = json.loads(GOOGLE_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    return sh.worksheet(SHEET_NAME)


def ensure_header(ws):
    # якщо лист пустий — ставимо шапку
    values = ws.get_all_values()
    if not values:
        ws.append_row(["id", "chat_id", "remind_at", "text", "status", "created_at"])
        return
    # якщо перший рядок не схожий на шапку — теж додамо (на всяк)
    if values[0][:6] != ["id", "chat_id", "remind_at", "text", "status", "created_at"]:
        ws.insert_row(["id", "chat_id", "remind_at", "text", "status", "created_at"], 1)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def remind_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split()
        chat_id = str(update.message.chat_id)

        dt = _parse_datetime(parts)
        # текст
        if len(parts[1]) == 5 and ":" in parts[1]:
            text = " ".join(parts[2:])
        else:
            text = " ".join(parts[3:])

        if not text.strip():
            await update.message.reply_text("❌ Додай текст: /remind 20:30 купити воду")
            return

        delay = (dt - datetime.now()).total_seconds()
        if delay <= 0:
            await update.message.reply_text("❌ Час вже минув")
            return

        ws = get_ws()
        ensure_header(ws)

        rid = str(uuid.uuid4())[:8]  # короткий ID
        ws.append_row([rid, chat_id, dt.strftime("%Y-%m-%d %H:%M:%S"), text, "PENDING", _now_str()])

        await update.message.reply_text(f"✅ Створено #{rid}\n⏰ {dt.strftime('%d.%m %H:%M')}")

    except Exception:
        await update.message.reply_text("❌ Формат:\n/remind 20:30 текст\n/remind 2026-01-15 12:00 текст")


async def in_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = str(update.message.chat_id)
        minutes = int(context.args[0])
        text = " ".join(context.args[1:]).strip()
        if not text:
            await update.message.reply_text("❌ Формат: /in 15 текст")
            return

        dt = datetime.now() + timedelta(minutes=minutes)

        ws = get_ws()
        ensure_header(ws)

        rid = str(uuid.uuid4())[:8]
        ws.append_row([rid, chat_id, dt.strftime("%Y-%m-%d %H:%M:%S"), text, "PENDING", _now_str()])
        await update.message.reply_text(f"✅ Створено #{rid}\n⏳ Через {minutes} хв")

    except Exception:
        await update.message.reply_text("❌ Формат: /in 15 текст")


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    ws = get_ws()
    ensure_header(ws)

    rows = ws.get_all_records()
    pending = [r for r in rows if str(r.get("chat_id")) == chat_id and r.get("status") == "PENDING"]

    if not pending:
        await update.message.reply_text("📭 Нема активних нагадувань")
        return

    msg = "📋 <b>Ваші нагадування:</b>\n\n"
    for r in pending[:50]:
        msg += f"#{r['id']} ⏰ {r['remind_at']} — {r['text']}\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    if not context.args:
        await update.message.reply_text("❌ Формат: /cancel ID")
        return

    rid = context.args[0].strip()
    ws = get_ws()
    ensure_header(ws)

    # шукаємо рядок з таким id і chat_id
    values = ws.get_all_values()
    # header in row 1
    found_row = None
    for i in range(2, len(values) + 1):
        row = values[i - 1]
        if len(row) >= 2 and row[0] == rid and row[1] == chat_id:
            found_row = i
            break

    if not found_row:
        await update.message.reply_text("❌ Не знайшов такий ID")
        return

    # status column = 5th (E)
    ws.update_cell(found_row, 5, "CANCELLED")
    await update.message.reply_text(f"✅ Скасовано #{rid}")


async def poll_due(context: ContextTypes.DEFAULT_TYPE):
    """
    Кожні POLL_SECONDS:
    - беремо всі PENDING
    - якщо час <= зараз → відправляємо → ставимо SENT
    """
    try:
        ws = get_ws()
        ensure_header(ws)

        values = ws.get_all_values()
        if len(values) < 2:
            return

        now = datetime.now()

        # map columns: A id, B chat_id, C remind_at, D text, E status
        for row_idx in range(2, len(values) + 1):
            row = values[row_idx - 1]
            if len(row) < 5:
                continue
            rid, chat_id, remind_at_str, text, status = row[0], row[1], row[2], row[3], row[4]

            if status != "PENDING":
                continue

            try:
                dt = datetime.strptime(remind_at_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue

            if dt <= now:
                # відправляємо
                await context.bot.send_message(chat_id=int(chat_id), text=f"⏰ Нагадування #{rid}\n\n{text}")
                # ставимо SENT
                ws.update_cell(row_idx, 5, "SENT")

    except Exception:
        # щоб бот не падав від разової помилки
        return


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty")
    if not SHEET_ID:
        raise RuntimeError("SHEET_ID is empty")
    if not GOOGLE_CREDS_JSON:
        raise RuntimeError("GOOGLE_CREDS_JSON is empty")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("remind", remind_cmd))
    app.add_handler(CommandHandler("in", in_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    # Перевірка таблиці по таймеру
    app.job_queue.run_repeating(poll_due, interval=POLL_SECONDS, first=5)

    print("✅ Bot started")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
