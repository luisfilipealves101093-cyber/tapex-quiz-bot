import json
import os
import csv
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

# ===============================
# CONFIG
# ===============================
TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
SHEET_URL = os.getenv("SHEET_URL")

SCORES_FILE = "scores.json"
TIMEZONE = ZoneInfo("America/Sao_Paulo")

SENT_QUESTIONS = set()

# ===============================
# UTIL
# ===============================
def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


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
async def send_quiz(row, context, chat_id, thread_id=None):

    pergunta_completa = row["Pergunta"].strip()
    alternativas = [row["A"], row["B"], row["C"], row["D"]]
    imagem_url = row.get("Imagem", "").strip()

    correct_index = ["A", "B", "C", "D"].index(row["Correta"].strip())

    try:
        tempo = int(row["Tempo_segundos"])
    except:
        tempo = None

    # Detectar tipo automaticamente
    texto_lower = pergunta_completa.lower()

    palavras_incorreta = [
        "incorreta", "incorreto",
        "falsa", "falso",
        "errada", "errado",
        "exceto", "não é correta",
        "não é correto"
    ]

    if any(p in texto_lower for p in palavras_incorreta):
        pergunta_base = "Qual a alternativa INCORRETA?"
    else:
        pergunta_base = "Qual a alternativa correta?"

    # 1️⃣ Enunciado
    if len(pergunta_completa) > 300:
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=pergunta_completa
        )
        await asyncio.sleep(0.4)
        pergunta_enquete = pergunta_base
    else:
        pergunta_enquete = pergunta_completa

    # 2️⃣ Imagem
    if imagem_url:
        await context.bot.send_photo(
            chat_id=chat_id,
            message_thread_id=thread_id,
            photo=imagem_url
        )
        await asyncio.sleep(0.4)

    # 3️⃣ Alternativas longas
    alternativas_longas = any(len(alt) > 100 for alt in alternativas)

    if alternativas_longas:
        texto_alternativas = "Alternativas:\n\n"
        letras = ["A", "B", "C", "D"]

        for i, alt in enumerate(alternativas):
            texto_alternativas += f"{letras[i]}) {alt}\n\n"

        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=texto_alternativas
        )
        await asyncio.sleep(0.4)

        opcoes_enquete = ["A", "B", "C", "D"]
    else:
        opcoes_enquete = alternativas

    # 4️⃣ Enquete
    poll = await context.bot.send_poll(
        chat_id=chat_id,
        message_thread_id=thread_id,
        question=pergunta_enquete[:300],
        options=opcoes_enquete,
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False,
        open_period=tempo,
    )

    comentario = row.get("Comentário", "").strip()

    context.bot_data[poll.poll.id] = {
        "correta": correct_index,
        "peso": int(row["Peso"]) if row["Peso"] else 1,
        "comentario": comentario,
        "chat_id": chat_id,
        "thread_id": thread_id
    }

    # Comentário automático
    if tempo and comentario:
        context.job_queue.run_once(
            enviar_comentario_automatico,
            when=tempo,
            data={"poll_id": poll.poll.id}
        )


# ===============================
# COMENTÁRIO AUTOMÁTICO
# ===============================
async def enviar_comentario_automatico(context: ContextTypes.DEFAULT_TYPE):

    poll_id = context.job.data["poll_id"]
    poll_info = context.bot_data.get(poll_id)

    if not poll_info:
        return

    comentario = poll_info.get("comentario")
    if not comentario:
        return

    comentario = escape_markdown(comentario)
    texto = f"🧠 Comentário:\n\n||{comentario}||"

    await context.bot.send_message(
        chat_id=poll_info["chat_id"],
        message_thread_id=poll_info["thread_id"],
        text=texto,
        parse_mode="MarkdownV2"
    )


# ===============================
# COMANDO /quiz
# ===============================
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_chat.id != GROUP_ID:
        return

    if not context.args:
        await update.message.reply_text("Use: /quiz Q001-Q010 ou /quiz Q001 Q002")
        return

    for arg in context.args:

        if "-" in arg:
            inicio, fim = arg.split("-")
            prefixo = inicio[:1]
            num_inicio = int(inicio[1:])
            num_fim = int(fim[1:])

            for numero in range(num_inicio, num_fim + 1):
                question_id = f"{prefixo}{numero:03d}"
                row = find_question_by_id(question_id)

                if row:
                    await send_quiz(
                        row,
                        context,
                        chat_id=update.effective_chat.id,
                        thread_id=update.message.message_thread_id
                    )
                    await asyncio.sleep(1)
                else:
                    await update.message.reply_text(f"{question_id} não encontrado.")

        else:
            row = find_question_by_id(arg)

            if row:
                await send_quiz(
                    row,
                    context,
                    chat_id=update.effective_chat.id,
                    thread_id=update.message.message_thread_id
                )
                await asyncio.sleep(1)
            else:
                await update.message.reply_text(f"{arg} não encontrado.")


# ===============================
# AGENDAMENTO
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

        try:
            question_datetime = datetime.strptime(
                f"{row['Data']} {row['Hora']}", "%d/%m/%Y %H:%M:%S"
            )
        except ValueError:
            question_datetime = datetime.strptime(
                f"{row['Data']} {row['Hora']}", "%d/%m/%Y %H:%M"
            )

        question_datetime = question_datetime.replace(tzinfo=TIMEZONE)

        if current >= question_datetime:
            await send_quiz(
                row,
                context,
                chat_id=GROUP_ID,
                thread_id=None
            )
            SENT_QUESTIONS.add(question_id)


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
            member = await context.bot.get_chat_member(GROUP_ID, int(user_id))
            name = member.user.first_name
        except:
            name = "Usuário"

        text += f"{name}: {points} pontos\n"

    await update.message.reply_text(text)


# ===============================
# CAPTURA ACERTOS
# ===============================
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):

    answer = update.poll_answer
    poll_info = context.bot_data.get(answer.poll_id)

    if not poll_info:
        return

    if answer.option_ids[0] != poll_info["correta"]:
        return

    scores = load_scores()
    user_id = str(answer.user.id)

    scores[user_id] = scores.get(user_id, 0) + poll_info["peso"]
    save_scores(scores)


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
