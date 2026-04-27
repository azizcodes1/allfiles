import asyncio
import os
import uvicorn
from api import app as fastapi_app
from bot import dp, bot
import multiprocessing

async def run_api():
    # Runs the FastAPI server
    port = int(os.environ.get("PORT", 8000))
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

async def run_bot():
    # Runs the Telegram Bot
    print("Bot is starting...")
    await dp.start_polling(bot)

from database import init_db

async def main():
    # Initialize the permanent database
    init_db()
    
    # Run both at the same time
    await asyncio.gather(
        run_api(),
        run_bot()
    )

if __name__ == "__main__":
    asyncio.run(main())