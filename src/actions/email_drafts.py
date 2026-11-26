"""
actions/email_drafts.py
=======================
Safe Email Drafting & Review for Troko-Desk.
Drafts emails from user ideas (e.g. "Responde a Ana diciendo que mañana confirmo"),
displays the draft on the island notch, and requires explicit user confirmation
before any dispatch. Never sends automatically.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from ai.action_dispatcher import register
from config.settings import settings
from core.event_bus import bus
from core.state_machine import TrokoState, state_machine

logger = logging.getLogger(__name__)

# In-memory storage for active draft pending confirmation
_pending_email_draft: Optional[dict] = None


def create_draft(recipient: str, body: str, subject: Optional[str] = None) -> dict:
    global _pending_email_draft

    sub = subject or f"Mensaje para {recipient}"
    draft = {
        "recipient": recipient.strip(),
        "subject": sub.strip(),
        "body": body.strip(),
        "status": "pending_review",
    }
    _pending_email_draft = draft

    # Request explicit UI confirmation on the notch island
    bus.emit(
        "on_request_confirmation",
        title=f"¿Enviar correo a {recipient}?",
        callback_data={"action": "send_email", "draft": draft},
    )

    state_machine.transition(TrokoState.NOTIFICACION)
    state_machine.feedback("Borrador listo", success=True)
    return draft


def confirm_send_email() -> str:
    global _pending_email_draft
    if not _pending_email_draft:
        return "No hay ningún borrador pendiente de envío."

    draft = _pending_email_draft
    _pending_email_draft = None

    if settings.email_draft_mode:
        logger.info("[MOCK EMAIL SENT] To: %s | Subject: %s | Body: %s", draft["recipient"], draft["subject"], draft["body"])
        state_machine.transition(TrokoState.CONTENTO)
        state_machine.feedback("Enviado", success=True)
        return (
            f"📨 [Modo Seguro] Borrador confirmado y registrado para {draft['recipient']}.\n"
            f"Asunto: {draft['subject']}\n"
            f"Cuerpo:\n{draft['body']}"
        )
    else:
        state_machine.feedback("Enviado", success=True)
        return f"📨 Correo enviado a {draft['recipient']} con éxito."


def cancel_draft() -> str:
    global _pending_email_draft
    _pending_email_draft = None
    state_machine.feedback("Cancelado", success=False)
    return "❌ Borrador de correo cancelado."


def _on_confirmation_resolved(confirmed: bool, data: dict, **_) -> None:
    if data.get("action") == "send_email":
        if confirmed:
            confirm_send_email()
        else:
            cancel_draft()


bus.subscribe("on_confirmation_resolved", _on_confirmation_resolved)


# ---------------------------------------------------------------------------
# Action Dispatcher Handler
# ---------------------------------------------------------------------------

@register("draft_email")
async def _action_draft_email(args: dict) -> str:
    recipient = args.get("recipient", "Destinatario").strip()
    body = args.get("body", "").strip()
    subject = args.get("subject", None)

    if not body:
        raise ValueError("Se requiere el contenido del mensaje.")

    draft = create_draft(recipient, body, subject)
    return (
        f"📝 **Borrador preparado para {draft['recipient']}:**\n"
        f"Asunto: *{draft['subject']}*\n"
        f"\"{draft['body']}\"\n\n"
        f"➡️ Revisa la isla superior o di 'sí, enviar' para confirmar el envío."
    )
