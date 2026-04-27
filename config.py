import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Payment Provider Tokens
STRIPE_TOKEN = os.getenv("STRIPE_TOKEN")
PAYME_TOKEN = os.getenv("PAYME_TOKEN")
CLICK_TOKEN = os.getenv("CLICK_TOKEN")

# Userbot Credentials (for listener)
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")

# Uzcard / Humo Details
MY_CARD_NUMBER = os.getenv("MY_CARD_NUMBER", "8600000000000000")
SUBSCRIPTION_PRICE_UZS = int(os.getenv("SUBSCRIPTION_PRICE_UZS", 50000))

# Database Path
DB_PATH = "bot.sqlite3"
