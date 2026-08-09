import time
from bms_tracker.scraper import BMSScraper
from bms_tracker.notifier import Notifier


def main():
    scraper = BMSScraper()
    notifier = Notifier()
    interval = 180  # 3 minutes

    print("==================================================")
    print("  Allu Cinemas (Kokapet) - Booking Tracker         ")
    print("==================================================")
    print(f"[*] Monitoring URL: {scraper.venue_url}")
    print(f"[*] Check Interval: Every {interval} seconds\n")

    notified = False

    while True:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Checking BookMyShow...")

        is_open = scraper.check_showtimes()

        if is_open and not notified:
            alert_msg = (
                "🎟️ **BOOKING OPEN!** 🎟️\n\n"
                "Allu Cinemas (Kokapet) bookings are now open on BookMyShow!\n\n"
                f"URL: {scraper.venue_url}"
            )
            print("\n🎉 MATCH FOUND! Sending notifications...")

            notifier.open_in_firefox(scraper.venue_url)
            notifier.send_telegram_alert(alert_msg)
            notified = True

        elif not is_open:
            print("  └─ Not available yet. Waiting for next cycle...")
            notified = False

        time.sleep(interval)


if __name__ == "__main__":
    main()