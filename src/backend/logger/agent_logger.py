"""Sistema de logging para guardar respuestas de agentes en archivos markdown."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class AgentLogger:
    """
    Logger que guarda las respuestas de cada agente en archivos markdown.
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        """
        Inicializa el logger.

        Args:
            base_dir: Directorio base para los logs. Por defecto 'logs' en la raíz.
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(__file__).parent.parent.parent.parent / "logs"

        self.session_dir: Optional[Path] = None
        self.agent_counter: int = 0
        self.session_timestamp: Optional[str] = None

    def start_session(self, user_id: str = "anonymous", user_message: str = "") -> str:
        """
        Inicia una nueva sesión creando un directorio con timestamp.

        Args:
            user_id: ID del usuario.
            user_message: Mensaje original del usuario.

        Returns:
            Path del directorio de la sesión.
        """
        self.session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_dir = self.base_dir / self.session_timestamp
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.agent_counter = 0

        started_at = datetime.now().isoformat()

        metadata_content = f"""# Sesión: {self.session_timestamp}

## Información de la Sesión

- **Usuario:** {user_id}
- **Inicio:** {started_at}

## Mensaje Original

```
{user_message}
```

---

## Agentes Ejecutados

Los archivos de respuesta de cada agente están en este directorio.
"""

        session_file = self.session_dir / "00_session_info.md"
        session_file.write_text(metadata_content, encoding="utf-8")

        return str(self.session_dir)

    def log_agent_response(
        self,
        agent_name: str,
        raw_response: str,
        parsed_response: Optional[dict[str, Any]] = None,
        input_text: Optional[str] = None,
        execution_time_ms: Optional[float] = None,
    ) -> str:
        """
        Guarda la respuesta de un agente en un archivo markdown.

        Args:
            agent_name: Nombre del agente (ej: "IntentAgent").
            raw_response: Respuesta cruda del agente.
            parsed_response: Respuesta parseada como diccionario.
            input_text: Texto de entrada que recibió el agente.
            execution_time_ms: Tiempo de ejecución en milisegundos.

        Returns:
            Path del archivo creado.

        Raises:
            RuntimeError: Si no se ha iniciado una sesión.
        """
        if not self.session_dir:
            raise RuntimeError(
                "Debe llamar a start_session() antes de log_agent_response()"
            )

        self.agent_counter += 1
        timestamp = datetime.now().isoformat()

        filename = f"{self.agent_counter:02d}_{agent_name}.md"
        filepath = self.session_dir / filename

        content_parts = [
            f"# {agent_name}",
            "",
            f"**Ejecutado:** {timestamp}",
        ]

        if execution_time_ms is not None:
            content_parts.append(f"**Tiempo de ejecución:** {execution_time_ms:.2f} ms")

        content_parts.extend(["", "---", ""])

        if input_text:
            content_parts.extend([
                "## Input",
                "",
                "```",
                input_text,
                "```",
                "",
            ])

        content_parts.extend([
            "## Respuesta Raw",
            "",
            "```",
            raw_response,
            "```",
            "",
        ])

        if parsed_response:
            content_parts.extend([
                "## Respuesta Parseada (JSON)",
                "",
                "```json",
                json.dumps(parsed_response, indent=2, ensure_ascii=False),
                "```",
                "",
            ])

        content = "\n".join(content_parts)
        filepath.write_text(content, encoding="utf-8")

        return str(filepath)

    def end_session(
        self,
        success: bool,
        final_message: str = "",
        errors: Optional[list] = None,
    ) -> None:
        """
        Finaliza la sesión agregando un resumen.

        Args:
            success: Si el workflow fue exitoso.
            final_message: Mensaje final del workflow.
            errors: Lista de errores si los hubo.
        """
        if not self.session_dir:
            return

        session_file = self.session_dir / "00_session_info.md"
        status = "Exitoso" if success else "Con errores"

        summary = f"""

---

## Resumen de Ejecución

- **Estado:** {status}
- **Agentes ejecutados:** {self.agent_counter}
- **Finalizado:** {datetime.now().isoformat()}

### Mensaje Final

```
{final_message}
```
"""

        if errors:
            summary += "\n### Errores\n\n"
            for error in errors:
                summary += f"- {error}\n"

        with open(session_file, "a", encoding="utf-8") as f:
            f.write(summary)
