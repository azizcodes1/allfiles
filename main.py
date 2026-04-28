import asyncio
import os
import uvicorn
import logging
import api
from api import app as fastapi_app
from bot import dp, bot, BOT_TOKEN
from database import init_db

# Inject bot and dp into API for Webhook support
api.dp_instance = dp
api.bot_instance = bot

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def run_api():
    """Runs the FastAPI server with restart logic."""
    while True:
        try:
            logging.info("Starting API server...")
            # Render automatically sets the PORT environment variable
            port = int(os.environ.get("PORT", 8000))
            
            # Setup Webhook if on Render
            if os.environ.get("RENDER"):
                webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook/{BOT_TOKEN}"
                logging.info(f"Setting webhook to: {webhook_url}")
                await bot.set_webhook(webhook_url)
            
            config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="info")
            server = uvicorn.Server(config)
            await server.serve()
        except Exception as e:
            logging.error(f"API server crashed: {e}. Restarting in 5 seconds...")
            await asyncio.sleep(5)

async def run_bot():
    """Runs the Telegram Bot (Polling or Webhook mode)."""
    if os.environ.get("RENDER"):
        logging.info("Bot running in Webhook mode via API.")
        return # Polling not needed on Render

    while True:
        try:
            logging.info("Starting Telegram Bot (Polling)...")
            await bot.delete_webhook() # Ensure we can poll
            await dp.start_polling(bot)
        except Exception as e:
            logging.error(f"Bot crashed: {e}. Restarting in 5 seconds...")
            await asyncio.sleep(5)

async def run_listener():
    """Runs the CardXabar payment listener with non-interactive start."""
    while True:
        try:
            from listener import client
            logging.info("Connecting Payment Listener...")
            await client.connect()
            if not await client.is_user_authorized():
                logging.warning("Userbot not authorized! CardXabar monitoring will be disabled. Run listener.py locally to login.")
                return 
            
            logging.info("Payment Listener connected and monitoring.")
            await client.run_until_disconnected()
        except Exception as e:
            logging.error(f"Payment Listener crashed: {e}. Restarting in 10 seconds...")
            await asyncio.sleep(10)

async def main():
    # Initialize the permanent database
    try:
        init_db()
    except Exception as e:
        logging.error(f"Database initialization failed: {e}")
        return

    # Run everything at the same time
    await asyncio.gather(
        run_api(),
        run_bot(),
        run_listener()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Process interrupted by user.")