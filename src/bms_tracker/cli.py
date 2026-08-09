"""Entry point: runs the Telegram bot and the booking tracker together."""

import logging
import signal
import threading

from bms_tracker import config
from bms_tracker.bot import TelegramBot
from bms_tracker.notifier import Notifier
from bms_tracker.scraper import BMSScraper
from bms_tracker.store import Store
from bms_tracker.tracker import Tracker


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("bms-tracker")

    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Check the .env file.")
        return

    store = Store(config.DATA_FILE)
    scraper = BMSScraper()
    notifier = Notifier(config.TELEGRAM_BOT_TOKEN)

    tracker = Tracker(store, notifier, scraper, config.INTERVAL_SECONDS)

    bot = TelegramBot(
        config.TELEGRAM_BOT_TOKEN,
        store,
        scraper,
        notifier,
        on_change=tracker.on_config_changed,
        interval_seconds=config.INTERVAL_SECONDS,
    )

    bot_thread = threading.Thread(target=bot.run, daemon=True)
    bot_thread.start()

    def shutdown(_signum, _frame) -> None:
        logger.info("Shutting down...")
        tracker.stop()
        bot.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        tracker.run()
    except KeyboardInterrupt:
        tracker.stop()
        bot.stop()
    finally:
        logger.info("Exiting.")


if __name__ == "__main__":
    main()
