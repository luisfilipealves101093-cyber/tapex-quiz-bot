import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

current_question = 0

async def pergunta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_question
    
    if current_question >= len(questions):
        await context.bot.send_message(chat_id=GROUP_ID, text="Todas as perguntas já foram enviadas.")
        return

    q = questions[current_question]

    await context.bot.send_poll(
        chat_id=GROUP_ID,
        question=q["pergunta"],
        options=q["opcoes"],
        type="quiz",
        correct_option_id=q["correta"],
        is_anonymous=False,
        open_period=q.get("tempo", None)
    )

    current_question += 1

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("pergunta", pergunta))

app.run_polling()
