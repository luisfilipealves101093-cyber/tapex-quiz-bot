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
TIMEZONE = ZoneInfo("America/Sao_Paulo")

# 🔒 Controle de perguntas já enviadas
SENT_QUESTIONS = set()


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

    enunciado = row["Pergunta"].strip()
    correct_index = ["A", "B", "C", "D"].index(row["Correta"].strip())
    tempo = int(row["Tempo_segundos"]) if row["Tempo_segundos"] else 60
    peso = int(row["Peso"]) if row["Peso"] else 1

    # 🧠 Detecta automaticamente se é questão longa
    if len(enunciado) > 250:

        # 1️⃣ Envia enunciado completo
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=f"📘 *Questão*\n\n{enunciado}",
            parse_mode="Markdown"
        )

        # 2️⃣ Envia enquete curta
        poll = await context.bot.send_poll(
            chat_id=GROUP_ID,
            question="Qual a alternativa correta?",
            options=[row["A"], row["B"], row["C"], row["D"]],
            type="quiz",
            correct_option_id=correct_index,
            is_anonymous=False,
            open_period=tempo,
        )

    else:
        # 🟢 Questão curta → envia normal
        poll = await context.bot.send_poll(
            chat_id=GROUP_ID,
            question=enunciado,
            options=[row["A"], row["B"], row["C"], row["D"]],
            type="quiz",
            correct_option_id=correct_index,
            is_anonymous=False,
            open_period=tempo,
        )

    context.bot_data[poll.poll.id] = {
        "correta": correct_index,
        "peso": peso,
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
# AUTOMÁTICO POR DATA/HORA
# ===============================
async def check_scheduled_questions(context: ContextTypes.DEFAULT_TYPE):
    rows = load_sheet()
    current = now_local()

    for row in rows:

        question_id = row["ID"].strip()

        # 🔒 Se já foi enviada, ignora
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

        if current >= question_datetime:
            await send_quiz(row, context)

            # ✅ Marca como enviada
            SENT_QUESTIONS.add(question_id)


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
