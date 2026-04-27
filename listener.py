from telethon import TelegramClient, events
import re
import logging
from config import API_ID, API_HASH, BOT_TOKEN
from database import mark_transaction_paid
from aiogram import Bot

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Userbot Client
client = TelegramClient('luxe_session', API_ID, API_HASH)

# Main Bot Client (for notifications)
bot = Bot(token=BOT_TOKEN)

# CardXabar official username
CARDXABAR_BOT = "CardXabarBot"

@client.on(events.NewMessage(from_users=CARDXABAR_BOT))
async def handle_card_xabar(event):
    """
    Parses standard @CardXabarBot notification text.
    Example text: 'Kirim: 50,000 UZS. Izoh: 123456'
    """
    text = event.message.text
    logging.info(f"Incoming notification: {text}")

    # 1. Extract Amount (numbers only)
    # Looking for something like "50,000" or "50000"
    amount_match = re.search(r"Kirim:\s*([\d\s,]+)\s*UZS", text)
    
    # 2. Extract Comment (6-digit unique ID)
    comment_match = re.search(r"Izoh:\s*(\d{6})", text)

    if amount_match and comment_match:
        # Clean amount string "50,000" -> 50000
        amount = int(amount_match.group(1).replace(",", "").replace(" ", "").strip())
        comment_id = comment_match.group(1)

        logging.info(f"Detected Transfer: {amount} UZS | Comment: {comment_id}")

        # 3. Check DB and activate
        user_id = mark_transaction_paid(comment_id)
        
        if user_id:
            logging.info(f"✅ Payment Verified! Gifting premium to {user_id}")
            
            # 4. Notify the user via the Main Bot
            try:
                success_msg = (
                    "💳 *Payment Verified Successfully!*\n\n"
                    "Your Uzcard/Humo transfer has been detected. Your account has "
                    "been upgraded to the *Modern Luxury Premium Tier* instantly."
                )
                await bot.send_message(user_id, success_msg, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Failed to notify user {user_id}: {e}")
        else:
            logging.warning("Unknown or already processed comment ID detected.")

async def start_listener():
    print("--- CardXabar Payment Listener Starting ---")
    await client.start()
    print("Userbot Logged In. Monitoring @CardXabarBot...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_listener())
