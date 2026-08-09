import os
import subprocess
import requests


class Notifier:
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    def open_in_firefox(self, url: str):
        """Opens the given URL in Firefox."""
        try:
            subprocess.run(["open", "-a", "Firefox", url], check=True)
        except Exception as e:
            print(f"[!] Could not open Firefox: {e}")

    def send_telegram_alert(self, message: str):
        """Sends a push notification via Telegram Bot."""
        if not self.bot_token or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"[!] Telegram Notification Error: {e}")