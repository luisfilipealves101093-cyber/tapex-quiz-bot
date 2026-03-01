async def send_quiz(row, context):

    correct_index = ["A", "B", "C", "D"].index(row["Correta"].strip())

    try:
        tempo = int(row["Tempo_segundos"])
    except:
        tempo = None

    pergunta_completa = row["Pergunta"].strip()

    # ✅ Se pergunta for maior que 300 caracteres
    if len(pergunta_completa) > 300:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=pergunta_completa
        )
        pergunta_enquete = "Qual a alternativa correta?"
    else:
        pergunta_enquete = pergunta_completa

    # 🔥 VERIFICA TAMANHO DAS ALTERNATIVAS (limite 100 do Telegram)
    alternativas = [
        row["A"].strip(),
        row["B"].strip(),
        row["C"].strip(),
        row["D"].strip()
    ]

    alternativa_longa = any(len(a) > 100 for a in alternativas)

    if alternativa_longa:
        # Envia alternativas completas como texto
        texto_alternativas = (
            f"A) {alternativas[0]}\n\n"
            f"B) {alternativas[1]}\n\n"
            f"C) {alternativas[2]}\n\n"
            f"D) {alternativas[3]}"
        )

        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=texto_alternativas
        )

        opcoes_enquete = ["A", "B", "C", "D"]
    else:
        opcoes_enquete = alternativas

    poll = await context.bot.send_poll(
        chat_id=GROUP_ID,
        question=pergunta_enquete,
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
        "chat_id": GROUP_ID
    }

    # Comentário automático continua igual
    if tempo and comentario:
        context.job_queue.run_once(
            enviar_comentario_automatico,
            when=tempo,
            data={"poll_id": poll.poll.id}
        )
