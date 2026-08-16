from app.ai.models import AIRequest, CoverageContext


class PromptBuilder:
    def build_editorial_instructions(self, context: CoverageContext) -> str:
        rules = [
            "Escribir en español.",
            "Usar tono objetivo, estilo de agencia, tercera persona y tiempo presente.",
            "Máximo 60 palabras.",
            "Describir únicamente la acción principal visible o contextual.",
            "Usar solo el contexto suministrado.",
            "No inventar identidades, cargos, hechos, lugares ni eventos.",
            "No emitir opiniones ni lenguaje promocional.",
            "Devolver únicamente la narración editable.",
            "No incluir fecha, ciudad, país, ubicación estructurada, fotógrafo, agencia, iniciales ni caption completo.",
        ]
        if context.is_drone:
            rules.append(
                "La fotografía está marcada como tomada con dron: no comenzar la narración con 'vista aérea', 'una vista aérea' ni 'vista aérea tomada con un dron'; describir directamente el sujeto o contenido visible."
            )
        context_bits = [
            f"Título de cobertura: {context.coverage_title}",
            f"Descripción: {context.description or 'No especificada'}",
            f"Personas conocidas explícitamente: {', '.join(context.known_people) if context.known_people else 'No especificadas'}",
            f"Organizaciones: {', '.join(context.organizations) if context.organizations else 'No especificadas'}",
            f"Palabras clave: {', '.join(context.keywords) if context.keywords else 'No especificadas'}",
            f"Notas editoriales: {context.notes or 'No especificadas'}",
        ]
        return "\n".join([*rules, "", "Contexto permitido:", *context_bits])

    def build_request(self, request: AIRequest) -> str:
        return "\n".join([
            self.build_editorial_instructions(request.coverage_context),
            "",
            f"Archivo de referencia: {request.image.filename}",
            f"Idioma: {request.language}",
            f"Límite de palabras: {request.max_words}",
        ])
