import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 6437879950)) # Add your Telegram ID here or in .env

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
MY_CARD_NUMBER = os.getenv("MY_CARD_NUMBER", "5614682116833312")
MY_VISA_CARD_NUMBER = os.getenv("MY_VISA_CARD_NUMBER", "4916990351367708")
SUBSCRIPTION_PRICE_UZS = int(os.getenv("SUBSCRIPTION_PRICE_UZS", 100000))
SUBSCRIPTION_PRICE_USD = int(os.getenv("SUBSCRIPTION_PRICE_USD", 10))

# Database URL (Neon PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_vm8jKa6yiOIA@ep-odd-unit-amskj1tf.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require")
