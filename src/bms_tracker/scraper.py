from datetime import date

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


class BMSScraper:
    VENUE_PATH = "https://in.bookmyshow.com/cinemas/HYD/allu-cinemas-kokapet/buytickets/ALUC/"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, venue_url: str = None):
        if venue_url:
            self.venue_url = venue_url
        else:
            self.venue_url = self.VENUE_PATH + date.today().strftime("%Y%m%d")

    def fetch_page(self) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=self.USER_AGENT,
                locale="en-US",
                viewport={"width": 1440, "height": 900},
                timezone_id="Asia/Kolkata",
            )
            page = context.new_page()
            page.goto(self.venue_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            html = page.content()
            browser.close()
        return html

    def check_showtimes(self) -> bool:
        """Fetches BMS venue page via a real browser and returns True if showtimes exist."""
        try:
            html = self.fetch_page()
            soup = BeautifulSoup(html, "html.parser")

            showtime_buttons = soup.select('[role="button"][aria-label^="Book "]')
            if showtime_buttons:
                return True

            return False

        except Exception as e:
            print(f"[!] Scraping error: {e}")
            return False
