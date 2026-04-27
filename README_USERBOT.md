# 🏦 LuxePrompt Payment Listener Setup

This system automates Uzcard/Humo payments by monitoring notifications from the official **@CardXabarBot** on your personal Telegram account.

## 1. Get Your Telegram API Credentials
To allow the `listener.py` script to log into your account, you need an **API_ID** and **API_HASH**:

1. Log in to your [Telegram Core](https://my.telegram.org) account.
2. Go to **"API development tools"**.
3. Create a new application (you can use any name/title).
4. Copy your **App api_id** and **App api_hash**.
5. Paste them into `config.py` under `API_ID` and `API_HASH`.

## 2. Setting up @CardXabarBot
1. Open [@CardXabarBot](https://t.me/CardXabarBot) on Telegram.
2. Connect your Bank Card (Uzcard/Humo) to the bot so it sends you a message every time you receive money.
3. Ensure your bank sends the **CardXabar** notification to the same Telegram account you are using for the userbot.

## 3. Configure Your Card for Users
In `config.py`:
- Set `MY_CARD_NUMBER` to the card where you want to receive payments.
- Set `SUBSCRIPTION_PRICE_UZS` to your desired price (default 50,000 UZS).

## 4. How to Run
You must run both scripts at the same time:

**Terminal 1 (The Bot):**
```bash
python bot.py
```

**Terminal 2 (The Payment Listener):**
```bash
python listener.py
```

*Note: The first time you run `listener.py`, it will ask you to enter your phone number and the SMS code sent to your Telegram app to authenticate the session.*
