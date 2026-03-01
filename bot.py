async def send_quiz(row, context):

    pergunta_completa = row["Pergunta"].strip()
    alternativas = [row["A"], row["B"], row["C"], row["D"]]
    imagem_url = row.get("Imagem", "").strip()

    correct_index = ["A", "B", "C", "D"].index(row["Correta"].strip())

    try:
        tempo = int(row["Tempo_segundos"])
    except:
        tempo = None

    # ===============================
    # 🎯 Detectar tipo automaticamente
    # ===============================
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

    # ===============================
    # 📜 1️⃣ ENVIAR ENUNCIADO PRIMEIRO
    # ===============================
    if len(pergunta_completa) > 300:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=pergunta_completa
        )
        await asyncio.sleep(0.4)
        pergunta_enquete = pergunta_base
    else:
        pergunta_enquete = pergunta_completa

    # ===============================
    # 🖼 2️⃣ ENVIAR IMAGEM (SE EXISTIR)
    # ===============================
    if imagem_url:
        await context.bot.send_photo(
            chat_id=GROUP_ID,
            photo=imagem_url
        )
        await asyncio.sleep(0.4)

    # ===============================
    # 📏 3️⃣ VERIFICAR TAMANHO DAS ALTERNATIVAS
    # ===============================
    alternativas_longas = any(len(alt) > 100 for alt in alternativas)

    if alternativas_longas:
        texto_alternativas = "Alternativas:\n\n"
        letras = ["A", "B", "C", "D"]

        for i, alt in enumerate(alternativas):
            texto_alternativas += f"{letras[i]}) {alt}\n\n"

        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=texto_alternativas
        )
        await asyncio.sleep(0.4)

        opcoes_enquete = ["A", "B", "C", "D"]
    else:
        opcoes_enquete = alternativas

    # ===============================
    # 🗳 4️⃣ ENVIAR ENQUETE POR ÚLTIMO
    # ===============================
    poll = await context.bot.send_poll(
        chat_id=GROUP_ID,
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
        "chat_id": GROUP_ID
    }

    # ===============================
    # 💬 Comentário automático (mantido igual)
    # ===============================
    if tempo and comentario:
        context.job_queue.run_once(
            enviar_comentario_automatico,
            when=tempo,
            data={"poll_id": poll.poll.id}
        )
