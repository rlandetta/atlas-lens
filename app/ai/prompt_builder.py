from app.ai.models import AIRequest, CoverageContext


class PromptBuilder:
    def build_editorial_instructions(self, context: CoverageContext, template: str = "xinhua") -> str:
        rules = [
            "Escribir en español.",
            "Usar tono objetivo, estilo de agencia, tercera persona y tiempo presente.",
            "Máximo 60 palabras.",
            "Describir únicamente la acción principal visible o contextual.",
            "Usar solo el contexto suministrado.",
            "No inventar identidades, cargos, hechos, lugares ni eventos.",
            "No emitir opiniones ni lenguaje promocional.",
            "Devolver únicamente la narración editable.",
            "No incluir fecha, ciudad, país, fotógrafo, agencia, iniciales ni caption completo.",
        ]
        context_bits = [
            f"Título de cobertura: {context.title}",
            f"Contexto de evento: {context.event_context or 'No especificado'}",
            f"Personas conocidas explícitamente: {', '.join(context.known_people) if context.known_people else 'No especificadas'}",
        ]
        return "\n".join([*rules, "", "Contexto permitido:", *context_bits])

    def build_request(self, request: AIRequest) -> str:
        return "\n".join([
            self.build_editorial_instructions(request.coverage_context, request.template),
            "",
            f"Archivo de referencia: {request.image.filename}",
            f"Idioma: {request.language}",
            f"Límite de palabras: {request.max_words}",
        ])
