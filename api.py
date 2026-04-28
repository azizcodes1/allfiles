from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL
from database import get_conn, release_conn
import uvicorn
from aiogram import types, Bot, Dispatcher
from aiogram.types import Update

app = FastAPI()
dp_instance: Dispatcher = None
bot_instance: Bot = None

# Allow your gallery to talk to this API
@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "LuxePrompt AI API"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/gallery/{user_id}")
async def get_gallery(user_id: int):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, prompt, image_url, is_public FROM generations WHERE user_id = %s ORDER BY timestamp DESC", (user_id,))
    rows = cur.fetchall()
    cur.close()
    release_conn(conn)
    return rows

@app.get("/api/masterpieces")
async def get_masterpieces():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT g.id, g.prompt, g.image_url, u.full_name, u.username 
        FROM generations g
        JOIN users u ON g.user_id = u.user_id
        WHERE g.is_public = true
        ORDER BY g.timestamp DESC
    ''')
    rows = cur.fetchall()
    cur.close()
    release_conn(conn)
    return rows

@app.post("/api/make-public/{gen_id}")
async def make_public(gen_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE generations SET is_public = true WHERE id = %s", (gen_id,))
    conn.commit()
    cur.close()
    release_conn(conn)
    return {"status": "success"}

@app.post("/api/make-private/{gen_id}")
async def make_private(gen_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE generations SET is_public = false WHERE id = %s", (gen_id,))
    conn.commit()
    cur.close()
    release_conn(conn)
    return {"status": "success"}

@app.delete("/api/delete-image/{gen_id}")
async def delete_image(gen_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM generations WHERE id = %s", (gen_id,))
    conn.commit()
    cur.close()
    release_conn(conn)
    return {"status": "success"}

@app.post("/webhook/{token}")
async def telegram_webhook(token: str, update: dict):
    """Handle incoming Telegram updates via Webhook."""
    if dp_instance and bot_instance:
        telegram_update = Update(**update)
        await dp_instance.feed_update(bot_instance, telegram_update)
        return {"status": "ok"}
    return {"status": "error", "message": "Bot not initialized"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
