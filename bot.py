import json
import os
import csv
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
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
SENT_FILE = "sent_questions.json"

TIMEZONE = ZoneInfo("America/Sao_Paulo")


# ===============================
# UTIL
# ===============================
def now_local():
    return datetime.now(TIMEZONE)


# ---------- SCORES ----------
def load_scores():
    if not os.path.exists(SCORES_FILE):
        return {}
    with open(SCORES_FILE, "r") as f:
        return json.load(f)


def save_scores(data):
    with open(SCORES_FILE, "w") as f:
        json.dump(data, f)


# ---------- SENT QUESTIONS ----------
def load_sent_questions():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r") as f:
        return set(json.load(f))


def save_sent_questions(data):
    with open(SENT_FILE, "w") as f:
        json.dump(list(data), f)


SENT_QUESTIONS = load_sent_questions()


# ---------- SHEET ----------
def load_sheet():
    response = requests.get(SHEET_URL)
    response.raise_for_status()
    decoded = response.content.decode("utf-8")
    reader = csv.DictReader(decoded.splitlines())
    return list(reader)


def find_question_by_id(question_id):
    rows = load_sheet()
    for row in rows:
        if row["ID"].strip() == question_id.strip():
            return row
    return None


# ===============================
# ENVIAR QUIZ
# ===============================
async def send_quiz(row, context):
    correct_index = ["A", "B", "C", "D"].index(row["Correta"].strip())

    poll = await context.bot.send_poll(
        chat_id=GROUP_ID,
        question=row["Pergunta"],
        options=[row["A"], row["B"], row["C"], row["D"]],
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False,
        open_period=int(row["Tempo_segundos"]) if row["Tempo_segundos"] else 60,
    )

    context.bot_data[poll.poll.id] = {
        "correta": correct_index,
        "peso": int(row["Peso"]) if row["Peso"] else 1,
    }


# ===============================
# COMANDO MANUAL /quiz ID
# ===============================
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return

    if not context.args:
        await update.message.reply_text("Use: /quiz ID_DA_QUESTAO")
        return

    question_id = context.args[0]
    row = find_question_by_id(question_id)

    if not row:
        await update.message.reply_text("ID não encontrado.")
        return

    await send_quiz(row, context)


# ===============================
# AUTOMÁTICO POR DATA/HORA (CORRIGIDO)
# ===============================
async def check_scheduled_questions(context: ContextTypes.DEFAULT_TYPE):
    rows = load_sheet()
    current = now_local()

    for row in rows:
        question_id = row["ID"].strip()

        if question_id in SENT_QUESTIONS:
            continue

        if not row["Data"] or not row["Hora"]:
            continue

        data_str = row["Data"]
        hora_str = row["Hora"]

        try:
            question_datetime = datetime.strptime(
                f"{data_str} {hora_str}", "%d/%m/%Y %H:%M:%S"
            )
        except ValueError:
            question_datetime = datetime.strptime(
                f"{data_str} {hora_str}", "%d/%m/%Y %H:%M"
            )

        question_datetime = question_datetime.replace(tzinfo=TIMEZONE)

        # 🔥 NOVA LÓGICA: janela de 60 segundos
        time_difference = (current - question_datetime).total_seconds()

        if 0 <= time_difference < 60:
            await send_quiz(row, context)

            SENT_QUESTIONS.add(question_id)
            save_sent_questions(SENT_QUESTIONS)


# ===============================
# CAPTURA ACERTOS
# ===============================
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer

    poll_info = context.bot_data.get(answer.poll_id)
    if not poll_info:
        return

    selected = answer.option_ids[0]
    correct = poll_info["correta"]
    peso = poll_info["peso"]

    if selected != correct:
        return

    scores = load_scores()
    user_id = str(answer.user.id)

    scores[user_id] = scores.get(user_id, 0) + peso
    save_scores(scores)


# ===============================
# RANKING
# ===============================
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scores = load_scores()

    if not scores:
        await update.message.reply_text("Sem pontuação ainda.")
        return

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

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

    app.add_handler(CommandHandler("quiz", quiz))
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
