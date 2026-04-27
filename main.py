import asyncio
import uvicorn
from api import app as fastapi_app
from bot import dp, bot
import multiprocessing

async def run_api():
    # Runs the FastAPI server
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

async def run_bot():
    # Runs the Telegram Bot
    print("Bot is starting...")
    await dp.start_polling(bot)

async def main():
    # Run both at the same time
    await asyncio.gather(
        run_api(),
        run_bot()
    )

if __name__ == "__main__":
    asyncio.run(main())
