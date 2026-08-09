"""Telegram message sending."""

import logging

import requests

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, bot_token: str) -> None:
        self.api = f"https://api.telegram.org/bot{bot_token}"

    def send(self, chat_id, text: str) -> bool:
        """Send a plain-text message to a chat. Returns True on success."""
        if not chat_id:
            logger.warning("No chat_id given; skipping message.")
            return False
        try:
            response = requests.post(
                f"{self.api}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error(
                "Telegram send failed (status=%s): %s",
                getattr(exc.response, "status_code", None),
                exc.__class__.__name__,
            )
            return False


__all__ = ["Notifier"]
