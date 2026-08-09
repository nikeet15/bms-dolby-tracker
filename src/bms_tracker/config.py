"""Configuration loaded from the environment / .env file."""

import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
INTERVAL_SECONDS = int(os.getenv("BMS_INTERVAL_SECONDS", "900"))
DATA_FILE = os.getenv("BMS_DATA_FILE", "bms_data.json")
VENUE_URL = os.getenv(
    "BMS_VENUE_URL",
    "https://in.bookmyshow.com/cinemas/HYD/allu-cinemas-kokapet/buytickets/ALUC/",
)
