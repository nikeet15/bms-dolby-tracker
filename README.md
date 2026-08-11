# BMSTracker

A Telegram bot that watches BookMyShow for when showtimes open at **Allu Cinemas, Kokapet (Hyderabad)** and alerts you when your preferred dates and showtimes are bookable.

The bot is named **BMSTracker** on Telegram.

## Setup

1. Clone this repo and create a Python 3.9+ virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

2. Create a `.env` file in the project root:

   ```bash
   cp .env.example .env   # or create it manually
   ```

   Fill in your values (see [Configuration](#configuration)).

3. Start the bot:

   ```bash
   bms-tracker
   ```

   or

   ```bash
   venv/bin/python -m bms_tracker.cli
   ```

## Configuration

Create a `.env` file with these values:

| Variable                | Required | Default                                                   | Description                          |
| ----------------------- | -------- | --------------------------------------------------------- | ------------------------------------ |
| `TELEGRAM_BOT_TOKEN`    | Yes      | —                                                         | Bot token from @BotFather            |
| `BMS_INTERVAL_SECONDS`  | No       | `900`                                                     | How often the tracker checks (seconds) |
| `BMS_DATA_FILE`         | No       | `bms_data.json`                                           | Where per-chat settings are stored   |
| `BMS_VENUE_URL`         | No       | Allu Cinemas Kokapet buy-tickets URL                      | Venue base URL to watch              |

> `.env` and `bms_data.json` are gitignored — never commit them.

### Getting your bot token

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot`, choose a name (e.g. `BMSTracker`) and a username (e.g. `@bms_track_bot`).
3. Copy the token BotFather gives you into `TELEGRAM_BOT_TOKEN`.

## Usage in Telegram

Open a chat with **BMSTracker** (@bms_track_bot) and use these commands:

| Command                        | What it does                                            |
| ------------------------------ | ------------------------------------------------------- |
| `/start` or `/help`            | Show the welcome message and all commands               |
| `/setdate 15-08-2026, 16-08-2026` | Set the date(s) to watch (supports `15-08-2026`, `2026-08-15`, `15/08/2026`) |
| `/settime`                     | Pick preferred showtimes from the live list             |
| `/notify once`                 | Alert only once when bookings open (default)            |
| `/notify every`                | Alert on every check cycle while bookings are open      |
| `/notify every 5`              | Alert every 5 minutes while bookings are open           |
| `/status`                      | Show your current dates, timings, and notify setting    |
| `/clear`                       | Show the command list again                             |
| `/reset`                       | Remove all your dates and timings                       |

### How it works

- Set dates with `/setdate`. You can set several at once.
- Optionally pick exact showtimes with `/settime` (tap options, then **Done**, or reply with numbers like `1,3`).
- The tracker checks the venue every `BMS_INTERVAL_SECONDS` (default 15 minutes).
- When a booked showtime matches your preferences, the bot sends you an alert with the date, timings, and a direct booking link.
- Changing your dates or timings resets the "already alerted" state, so you'll get a fresh alert if the new settings match.

> Note: BookMyShow redirects dates that aren't open yet to a default show date. The bot detects this and treats the date as "not open".
