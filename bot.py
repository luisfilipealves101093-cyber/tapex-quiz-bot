import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Use: /quiz numero_da_pergunta")
        return

    try:
        numero = int(context.args[0]) - 1
        q = questions[numero]
    except:
        await update.message.reply_text("Pergunta inválida.")
        return

    await context.bot.send_poll(
        chat_id=GROUP_ID,
        question=q["pergunta"],
        options=q["opcoes"],
        type="quiz",
        correct_option_id=q["correta"],
        is_anonymous=False,
        open_period=q.get("tempo", None)
    )

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("quiz", quiz))

app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 10000)),
    webhook_url=f"{RENDER_EXTERNAL_URL}/"
)
