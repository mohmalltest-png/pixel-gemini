# pixel-gemini

**Pixel 10 Pro Google One Gemini Offer Bot – Telegram Interface**

A Replit-hosted Telegram bot that simulates a Google Pixel 10 Pro (Android 16)
device, logs into a user-supplied Gmail account, and retrieves the
**12-month free Gemini Pro** activation link from Google One.

---

## Project Structure

```
pixel-gemini/
├── main.py               # Telegram bot entry point
├── device_simulator.py   # Android Pixel 10 Pro device simulation
├── google_automation.py  # Google One login and offer detection
├── config.py             # Configuration and constants
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

---

## Features

| Feature | Details |
|---|---|
| 📱 Device simulation | Pixel 10 Pro (Android 16) with unique IMEI, Android ID, and user-agent per session |
| 🤖 Telegram bot | `/start`, `/login`, `/check_offer`, `/get_link`, `/status` commands |
| 🔐 Gmail login | Selenium-based Google account authentication |
| 💳 Offer detection | Scans Google One for the 12-month Gemini Pro offer and extracts the activation link |
| 🔄 Session management | In-memory per-user sessions; passwords deleted from chat on capture |

---

## Setup Guide

### 1. Requirements

- **Python**: 3.10 or higher
- **Google Chrome**: Installed on your system
- **Telegram Bot Token**: Get one from [@BotFather](https://t.me/BotFather) on Telegram

---

### 2. Running on Any Local Computer (Windows, macOS, Linux)

1. **Clone or download** this folder to your machine.
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure your environment**:
   Create a `.env` file in the root directory:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
   # Optional: set HEADLESS=False to watch browser during testing
   HEADLESS=True
   ```
4. **Run the bot**:
   ```bash
   python main.py
   ```

---

### 3. Running on Replit

1. Import this repository into a new Repl on [Replit](https://replit.com).
2. Go to **Secrets** (🔒) in the sidebar and add:
   - Key: `TELEGRAM_BOT_TOKEN`
   - Value: `Your bot token from BotFather`
3. Click **Run** or execute `python main.py`.

---


## Usage

| Command | Description |
|---|---|
| `/start` | Show welcome message and command list |
| `/login` | Enter Gmail email and password (two-step conversation) |
| `/check_offer` | Simulate device, log in, and search for the Gemini Pro offer |
| `/get_link` | Retrieve the last captured offer link |
| `/status` | View current session info and device profile |

### Typical flow

```
You: /start
Bot: Welcome…

You: /login
Bot: Please enter your Gmail address:

You: user@gmail.com
Bot: Email received. Now enter your password:

You: ••••••••
Bot: ✅ Credentials saved. New Pixel 10 Pro device profile created…

You: /check_offer
Bot: ⏳ Launching device simulator…
Bot: 🎉 Gemini Pro Offer Found! 🔗 https://one.google.com/…
```

---

## Technical Notes

- **Headless Chrome** is used via Selenium with mobile emulation matching
  the Pixel 10 Pro screen dimensions (390 × 844, pixel ratio 3.0).
- A new **IMEI**, **Android ID**, and **Chrome version patch** are generated
  for every session using the `device_simulator.py` module.
- The **user agent** keeps the Pixel 10 Pro identity constant while varying
  the Chrome patch version and Android ID to reduce fingerprinting.
- Credentials are stored **in memory only** and never written to disk.
  The Telegram message containing the password is deleted immediately after
  being read.

---

## Requirements

- Python 3.10+
- Google Chrome / Chromium installed (Replit provides this)
- `chromedriver` on PATH (managed automatically by `webdriver-manager`)

---

## Disclaimer

This project is provided for educational and personal use only.
Automating Google account access may violate Google's Terms of Service.
Use responsibly and only with accounts you own.
