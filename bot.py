import json
import os
from datetime import datetime, timedelta
from telegram import Update, BotCommand, BotCommandScopeChatAdministrators
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

SCORES_FILE = "scores.json"

# Armazena dados do poll ativo
ACTIVE_POLLS = {}

# ===============================
# UTIL
# ===============================
def today_str():
    return datetime.utcnow().strftime("%Y-%m-%d")


def load_scores():
    if not os.path.exists(SCORES_FILE):
        return {}
    with open(SCORES_FILE, "r") as f:
        return json.load(f)


def save_scores(data):
    with open(SCORES_FILE, "w") as f:
        json.dump(data, f)


# ===============================
# CARREGAR PERGUNTAS
# ===============================
with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)


# ===============================
# /quiz (SÓ ADMIN)
# ===============================
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_chat.id != GROUP_ID:
        return

    member = await context.bot.get_chat_member(
        GROUP_ID, update.effective_user.id
    )

    if member.status not in ["administrator", "creator"]:
        return

    if not context.args:
        await update.message.reply_text("Use: /quiz numero")
        return

    try:
        numero = int(context.args[0]) - 1
        q = questions[numero]
    except:
        await update.message.reply_text("Pergunta inválida.")
        return

    poll_message = await context.bot.send_poll(
        chat_id=GROUP_ID,
        question=q["pergunta"],
        options=q["opcoes"],
        type="quiz",
        correct_option_id=q["correta"],
        is_anonymous=False,
        open_period=q.get("tempo"),
    )

    # Salva qual alternativa é correta e o peso
    ACTIVE_POLLS[poll_message.poll.id] = {
        "correta": q["correta"],
        "peso": q.get("peso", 1)
    }


# ===============================
# CAPTURA RESPOSTA
# ===============================
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id

    if poll_id not in ACTIVE_POLLS:
        return

    if not answer.option_ids:
        return

    selected = answer.option_ids[0]
    correct = ACTIVE_POLLS[poll_id]["correta"]
    peso = ACTIVE_POLLS[poll_id]["peso"]

    if selected == correct:
        scores = load_scores()
        user_id = str(answer.user.id)

        entry = {
            "date": today_str(),
            "points": peso
        }

        scores.setdefault(user_id, []).append(entry)
        save_scores(scores)


# ===============================
# RANKING POR PERÍODO
# ===============================
def calculate_ranking(period):
    scores = load_scores()
    ranking = {}
    now = datetime.utcnow()

    for user_id, entries in scores.items():
        total = 0
        for e in entries:
            entry_date = datetime.strptime(e["date"], "%Y-%m-%d")

            if period == "daily":
                if entry_date.date() == now.date():
                    total += e["points"]

            elif period == "weekly":
                if entry_date >= now - timedelta(days=7):
                    total += e["points"]

            elif period == "monthly":
                if entry_date.month == now.month and entry_date.year == now.year:
                    total += e["points"]

        if total > 0:
            ranking[user_id] = total

    return dict(sorted(ranking.items(), key=lambda x: x[1], reverse=True))


async def send_ranking(update, context, period, title):
    ranking = calculate_ranking(period)

    if not ranking:
        await update.message.reply_text("Sem pontuação ainda.")
        return

    text = f"🏆 {title}\n\n"

    for user_id, points in list(ranking.items())[:10]:
        try:
            member = await context.bot.get_chat_member(
                GROUP_ID, int(user_id)
            )
            name = member.user.first_name
        except:
            name = "Usuário"

        text += f"{name}: {points} pontos\n"

    await update.message.reply_text(text)


async def ranking_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_ranking(update, context, "daily", "Ranking Diário")


async def ranking_semanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_ranking(update, context, "weekly", "Ranking Semanal")


async def ranking_mensal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_ranking(update, context, "monthly", "Ranking Mensal")


# ===============================
# DEFINIR COMANDOS SÓ ADMINS
# ===============================
async def set_commands(app):
    await app.bot.set_my_commands(
        [
            BotCommand("quiz", "Enviar pergunta"),
            BotCommand("ranking_dia", "Ranking diário"),
            BotCommand("ranking_semana", "Ranking semanal"),
            BotCommand("ranking_mes", "Ranking mensal"),
        ],
        scope=BotCommandScopeChatAdministrators(GROUP_ID),
    )


# ===============================
# MAIN
# ===============================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("ranking_dia", ranking_diario))
    app.add_handler(CommandHandler("ranking_semana", ranking_semanal))
    app.add_handler(CommandHandler("ranking_mes", ranking_mensal))
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    app.post_init = set_commands

    app.run_polling()


if __name__ == "__main__":
    main()
