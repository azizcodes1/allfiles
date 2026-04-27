from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from config import DB_PATH
import uvicorn

app = FastAPI()

# Allow your gallery to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your GitHub Pages URL
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/gallery/{user_id}")
async def get_gallery(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, prompt, image_url, is_public FROM generations WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/masterpieces")
async def get_masterpieces():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT g.id, g.prompt, g.image_url, u.full_name, u.username 
        FROM generations g
        JOIN users u ON g.user_id = u.user_id
        WHERE g.is_public = 1
        ORDER BY g.timestamp DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/make-public/{gen_id}")
async def make_public(gen_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE generations SET is_public = 1 WHERE id = ?", (gen_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/make-private/{gen_id}")
async def make_private(gen_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE generations SET is_public = 0 WHERE id = ?", (gen_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/delete-image/{gen_id}")
async def delete_image(gen_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM generations WHERE id = ?", (gen_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
