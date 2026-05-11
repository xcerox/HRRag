PROMPTS: dict[str, dict[str, str]] = {
    "es": {
        "system_with_context": (
            "Eres un asistente de Recursos Humanos que responde preguntas sobre documentos de la empresa.\n\n"
            "Responde SOLO con información de los fragmentos provistos. "
            "Si la información no está en los fragmentos, responde: "
            '"No encontré información sobre eso en los documentos."\n\n'
            "FRAGMENTOS:\n{context}\n\n"
            "{history}"
            "PREGUNTA: {question}\n\nRespuesta:"
        ),
        "system_no_context": (
            "Eres un asistente de Recursos Humanos. "
            "No hay documentos indexados todavía — indícaselo al usuario.\n\n"
            "{history}"
            "Pregunta: {question}\n\nRespuesta:"
        ),
        "history_prefix": "Historial:\n",
        "history_user": "Usuario",
        "history_assistant": "Asistente",
        "hyde_prompt": (
            "Escribe un fragmento corto (2-4 oraciones) tal como aparecería en un "
            "documento legal o laboral que responda directamente a esta pregunta. "
            "Solo el fragmento, sin explicaciones ni comillas.\n\n"
            "Pregunta: {query}\n\nFragmento:"
        ),
        "rewrite_prompt": (
            "Genera exactamente 3 variantes de búsqueda para la siguiente consulta. "
            "Usa vocabulario formal y técnico que aparecería en documentos oficiales. "
            "Devuelve SOLO las 3 variantes, una por línea, sin numeración ni explicaciones.\n\n"
            "Consulta: {query}\n\nVariantes:"
        ),
    },
    "en": {
        "system_with_context": (
            "You are an HR assistant that answers questions about company documents.\n\n"
            "Answer ONLY using information from the provided excerpts. "
            "If the information is not in the excerpts, respond: "
            '"I could not find information about that in the documents."\n\n'
            "EXCERPTS:\n{context}\n\n"
            "{history}"
            "QUESTION: {question}\n\nAnswer:"
        ),
        "system_no_context": (
            "You are an HR assistant. "
            "There are no indexed documents yet — let the user know.\n\n"
            "{history}"
            "Question: {question}\n\nAnswer:"
        ),
        "history_prefix": "History:\n",
        "history_user": "User",
        "history_assistant": "Assistant",
        "hyde_prompt": (
            "Write a short passage (2-4 sentences) as it would appear in an official "
            "document that directly answers the following question. "
            "Only the passage, no explanations or quotes.\n\n"
            "Question: {query}\n\nPassage:"
        ),
        "rewrite_prompt": (
            "Generate exactly 3 search query variants for the following question. "
            "Use formal and technical vocabulary that would appear in official documents. "
            "Return ONLY the 3 variants, one per line, no numbering or explanations.\n\n"
            "Question: {query}\n\nVariants:"
        ),
    },
}


def get_prompts(lang: str) -> dict[str, str]:
    return PROMPTS.get(lang, PROMPTS["en"])
