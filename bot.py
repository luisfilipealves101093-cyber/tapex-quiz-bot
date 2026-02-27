import json
import os
from telegram import Update, BotCommand, BotCommandScopeChatAdministrators
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

RANKING_FILE = "ranking.json"

# ===============================
# CARREGAR PERGUNTAS
# ===============================
with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)


# ===============================
# RANKING
# ===============================
def load_ranking():
    if not os.path.exists(RANKING_FILE):
        return {}
    with open(RANKING_FILE, "r") as f:
        return json.load(f)


def save_ranking(data):
    with open(RANKING_FILE, "w") as f:
        json.dump(data, f)


# ===============================
# COMANDO /quiz (SÓ ADMIN)
# ===============================
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return

    user_id = update.effective_user.id
    member = await context.bot.get_chat_member(GROUP_ID, user_id)

    # Apenas admin ou criador pode usar
    if member.status not in ["administrator", "creator"]:
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

    poll_message = await context.bot.send_poll(
        chat_id=GROUP_ID,
        question=q["pergunta"],
        options=q["opcoes"],
        type="quiz",
        correct_option_id=q["correta"],
        is_anonymous=False,
        open_period=q.get("tempo"),
    )

    # Salva alternativa correta para ranking
    context.bot_data[poll_message.poll.id] = {
        "correta": q["correta"]
    }


# ===============================
# CAPTURAR RESPOSTAS (RANKING)
# ===============================
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    user = answer.user

    if answer.option_ids is None:
        return

    selected_option = answer.option_ids[0]

    poll_info = context.bot_data.get(answer.poll_id)
    if not poll_info:
        return

    correct_option = poll_info["correta"]

    if selected_option == correct_option:
        ranking = load_ranking()
        ranking[str(user.id)] = ranking.get(str(user.id), 0) + 1
        save_ranking(ranking)


# ===============================
# COMANDO /ranking
# ===============================
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ranking_data = load_ranking()

    if not ranking_data:
        await update.message.reply_text("Ainda não há pontuação.")
        return

    sorted_ranking = sorted(
        ranking_data.items(), key=lambda x: x[1], reverse=True
    )

    text = "🏆 Ranking:\n\n"

    for user_id, points in sorted_ranking[:10]:
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
# DEFINIR COMANDOS SÓ PARA ADMINS
# ===============================
async def set_commands(app):
    await app.bot.set_my_commands(
        [
            BotCommand("quiz", "Enviar pergunta"),
            BotCommand("ranking", "Ver ranking"),
        ],
        scope=BotCommandScopeChatAdministrators(GROUP_ID),
    )


# ===============================
# MAIN
# ===============================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    app.post_init = set_commands

    app.run_polling()


if __name__ == "__main__":
    main()
