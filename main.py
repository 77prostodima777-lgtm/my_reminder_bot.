import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Бот працює онлайн!\n\nКоманди:\n/start\n/help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Це бот для нагадувань.\nСкоро додамо /remind"
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN не заданий")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    print("🤖 Бот запущений")
    app.run_polling()


if __name__ == "__main__":
    main()
