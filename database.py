import sqlite3
from config import DB_PATH

def init_db(db_path=DB_PATH):
    """Initialize the SQLite database with necessary tables."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_premium BOOLEAN DEFAULT FALSE,
            language TEXT,
            full_name TEXT,
            username TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pending_transactions (
            user_id INTEGER,
            comment_id TEXT PRIMARY KEY,
            amount INTEGER,
            status TEXT DEFAULT 'pending'
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prompt TEXT,
            enhanced_prompt TEXT,
            image_url TEXT,
            is_public BOOLEAN DEFAULT FALSE,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Migration: Add columns if they don't exist
    try:
        cur.execute("ALTER TABLE users ADD COLUMN language TEXT")
    except sqlite3.OperationalError: pass
    try:
        cur.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
    except sqlite3.OperationalError: pass
    try:
        cur.execute("ALTER TABLE users ADD COLUMN username TEXT")
    except sqlite3.OperationalError: pass
    try:
        cur.execute("ALTER TABLE generations ADD COLUMN is_public BOOLEAN DEFAULT FALSE")
    except sqlite3.OperationalError: pass
    conn.commit()

    conn.close()

def add_user(user_id, full_name=None, username=None, db_path=DB_PATH):
    """Add or update a user in the database."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO users (user_id, full_name, username) VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET 
            full_name = COALESCE(excluded.full_name, users.full_name),
            username = COALESCE(excluded.username, users.username)
    ''', (user_id, full_name, username))
    conn.commit()
    conn.close()

def set_user_language(user_id, lang, db_path=DB_PATH):
    """Set user's language preference."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def get_user_language(user_id, db_path=DB_PATH):
    """Get user's language preference."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else None

def set_premium(user_id, status=True, db_path=DB_PATH):
    """Set the premium status for a user."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_premium = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

def is_premium(user_id, db_path=DB_PATH):
    """Check if a user has premium status."""
    # Admin Overrides
    if user_id == 6437879950: # Replace with your real ID
        return True
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT is_premium FROM users WHERE user_id = ?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return bool(res[0]) if res else False

def create_transaction(user_id, comment_id, amount, db_path=DB_PATH):
    """Store a pending payment."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO pending_transactions (user_id, comment_id, amount) VALUES (?, ?, ?)", 
                (user_id, comment_id, amount))
    conn.commit()
    conn.close()

def get_transaction_by_comment(comment_id, db_path=DB_PATH):
    """Retrieve transaction details by comment ID."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT user_id, amount, status FROM pending_transactions WHERE comment_id = ?", (comment_id,))
    res = cur.fetchone()
    conn.close()
    return res # (user_id, amount, status)

def mark_transaction_paid(comment_id, db_path=DB_PATH):
    """Update transaction status and grant premium."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # 1. Get user_id
    cur.execute("SELECT user_id FROM pending_transactions WHERE comment_id = ?", (comment_id,))
    res = cur.fetchone()
    if res:
        user_id = res[0]
        # 2. Set Status Paid
        cur.execute("UPDATE pending_transactions SET status = 'paid' WHERE comment_id = ?", (comment_id,))
        # 3. Grant Premium
        cur.execute("UPDATE users SET is_premium = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return user_id
    conn.close()
    return None
def save_generation(user_id, prompt, enhanced_prompt, image_url, db_path=DB_PATH):
    """Save a generated image to the database."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO generations (user_id, prompt, enhanced_prompt, image_url) VALUES (?, ?, ?, ?)",
                (user_id, prompt, enhanced_prompt, image_url))
    conn.commit()
    conn.close()

def get_user_generations(user_id, db_path=DB_PATH):
    """Retrieve all images generated by a specific user."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT prompt, image_url, timestamp, is_public, id FROM generations WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    res = cur.fetchall()
    conn.close()
    return res

def set_generation_public(gen_id, is_public=True, db_path=DB_PATH):
    """Toggle the public visibility of a generation."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE generations SET is_public = ? WHERE id = ?", (is_public, gen_id))
    conn.commit()
    conn.close()

def get_public_generations(db_path=DB_PATH):
    """Retrieve all public images from all users."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        SELECT g.prompt, g.image_url, g.timestamp, u.full_name, u.username 
        FROM generations g
        JOIN users u ON g.user_id = u.user_id
        WHERE g.is_public = 1
        ORDER BY g.timestamp DESC
    ''')
    res = cur.fetchall()
    conn.close()
    return res
