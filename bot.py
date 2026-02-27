import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Só permite comando dentro do grupo correto
    if update.effective_chat.id != GROUP_ID:
        return

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
        open_period=q.get("tempo")
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("quiz", quiz))
    app.run_polling()

if __name__ == "__main__":
    main()
