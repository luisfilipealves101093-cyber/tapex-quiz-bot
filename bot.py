import json
import os
import csv
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update, BotCommand, BotCommandScopeChatAdministrators
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
SHEET_URL = os.getenv("SHEET_URL")

SCORES_FILE = "scores.json"
TIMEZONE = ZoneInfo("America/Sao_Paulo")


# ===============================
# UTIL
# ===============================
def now_local():
    return datetime.now(TIMEZONE)


def load_scores():
    if not os.path.exists(SCORES_FILE):
        return {}
    with open(SCORES_FILE, "r") as f:
        return json.load(f)


def save_scores(data):
    with open(SCORES_FILE, "w") as f:
        json.dump(data, f)


# ===============================
# LER PLANILHA CSV
# ===============================
def load_sheet():
    response = requests.get(SHEET_URL)
    response.raise_for_status()
    decoded = response.content.decode("utf-8")
    reader = csv.DictReader(decoded.splitlines())
    return list(reader)


# ===============================
# ENVIAR PERGUNTAS AUTOMÁTICAS
# ===============================
async def check_scheduled_questions(context: ContextTypes.DEFAULT_TYPE):
    rows = load_sheet()
    current = now_local()

    for row in rows:
        if row["Enviado"]:
            continue

        if not row["Data"] or not row["Hora"]:
            continue

        data_str = row["Data"]
        hora_str = row["Hora"]

        question_datetime = datetime.strptime(
            f"{data_str} {hora_str}", "%d/%m/%Y %H:%M"
        ).replace(tzinfo=TIMEZONE)

        if current >= question_datetime:
            correct_index = ["A", "B", "C", "D"].index(row["Correta"].strip())

            poll = await context.bot.send_poll(
                chat_id=GROUP_ID,
                question=row["Pergunta"],
                options=[row["A"], row["B"], row["C"], row["D"]],
                type="quiz",
                correct_option_id=correct_index,
                is_anonymous=False,
                open_period=int(row["Tempo_segundos"]),
            )

            context.bot_data[poll.poll.id] = {
                "correta": correct_index,
                "peso": int(row["Peso"]) if row["Peso"] else 1,
            }

            row["Enviado"] = "SIM"


# ===============================
# CAPTURA ACERTOS
# ===============================
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer

    poll_info = context.bot_data.get(answer.poll_id)
    if not poll_info:
        return

    selected_option = answer.option_ids[0]
    correct_option = poll_info["correta"]
    peso = poll_info["peso"]

    if selected_option != correct_option:
        return

    scores = load_scores()
    user_id = str(answer.user.id)

    scores[user_id] = scores.get(user_id, 0) + peso
    save_scores(scores)


# ===============================
# RANKING GERAL
# ===============================
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scores = load_scores()

    if not scores:
        await update.message.reply_text("Sem pontuação ainda.")
        return

    sorted_scores = sorted(
        scores.items(), key=lambda x: x[1], reverse=True
    )

    text = "🏆 Ranking Geral\n\n"

    for user_id, points in sorted_scores[:10]:
        try:
            member = await context.bot.get_chat_member(
                GROUP_ID, int(user_id)
            )
            name = member.user.first_name
        except:
            name = "Usuário"

        text += f"{name}: {points} pontos\n"

    await update.message.reply_text(text)


# ===============================
# MAIN
# ===============================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    app.job_queue.run_repeating(
        check_scheduled_questions,
        interval=60,
        first=10,
    )

    app.run_polling()


if __name__ == "__main__":
    main()
