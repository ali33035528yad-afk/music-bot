import os
import sqlite3
from contextlib import closing
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
DB_PATH = os.getenv("DB_PATH", "musicbot.sqlite")
SEARCH_API_URL = os.getenv("SEARCH_API_URL", "").strip()

app = FastAPI(title="Music Bot")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT DEFAULT '',
            audio_url TEXT NOT NULL,
            source_url TEXT DEFAULT '',
            added_by TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

async def tg(method: str, payload: dict):
    if not BOT_TOKEN:
        return {"ok": False, "description": "BOT_TOKEN is not configured"}
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.post(url, json=payload)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "description": r.text}

async def send(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await tg("sendMessage", payload)

async def send_audio(chat_id, audio_url, title=""):
    payload = {"chat_id": chat_id, "audio": audio_url}
    if title:
        payload["caption"] = title
    return await tg("sendAudio", payload)

def search_local(q):
    q = q.lower().strip()
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT id,title,artist,audio_url,source_url FROM songs "
            "WHERE lower(title) LIKE ? OR lower(artist) LIKE ? "
            "ORDER BY id DESC LIMIT 10",
            (f"%{q}%", f"%{q}%")
        ).fetchall()
    return rows

async def search_api(q):
    if not SEARCH_API_URL:
        return []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(SEARCH_API_URL, params={"q": q})
            r.raise_for_status()
            data = r.json()
        return data.get("results", [])[:10]
    except Exception:
        return []

async def handle_message(message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    user = message.get("from", {})
    username = user.get("username") or str(user.get("id", ""))

    if not chat_id:
        return

    if text.startswith("/start"):
        await send(chat_id,
            "🎵 ربات موسیقی فعال است.\n\n"
            "دستورات:\n"
            "/search نام آهنگ — جستجو\n"
            "/archive — آرشیو\n"
            "/add عنوان | خواننده | لینک مستقیم MP3 — افزودن\n"
            "/help — راهنما")
        return

    if text.startswith("/help"):
        await send(chat_id,
            "راهنما:\n"
            "• /search نام آهنگ\n"
            "• /archive\n"
            "• /add عنوان | خواننده | لینک مستقیم فایل صوتی\n\n"
            "برای ارسال آهنگ، لینک باید مستقیم و قابل دسترسی توسط Telegram باشد.")
        return

    if text.startswith("/archive"):
        with closing(db()) as conn:
            rows = conn.execute(
                "SELECT id,title,artist FROM songs ORDER BY id DESC LIMIT 20"
            ).fetchall()
        if not rows:
            await send(chat_id, "📂 آرشیو هنوز خالی است.")
            return
        out = ["📂 آرشیو آهنگ‌ها:"]
        for sid, title, artist in rows:
            out.append(f"{sid}. {title}" + (f" — {artist}" if artist else ""))
        await send(chat_id, "\n".join(out))
        return

    if text.startswith("/add "):
        raw = text[5:].strip()
        parts = [p.strip() for p in raw.split("|", 2)]
        if len(parts) != 3 or not all(parts):
            await send(chat_id, "فرمت صحیح:\n/add عنوان | خواننده | لینک مستقیم MP3")
            return
        title, artist, audio_url = parts
        with closing(db()) as conn:
            conn.execute(
                "INSERT INTO songs(title,artist,audio_url,added_by) VALUES(?,?,?,?)",
                (title, artist, audio_url, username)
            )
            conn.commit()
        await send(chat_id, "✅ آهنگ به آرشیو اضافه شد.")
        return

    if text.startswith("/search "):
        q = text[8:].strip()
        if not q:
            await send(chat_id, "مثال: /search محسن چاوشی")
            return

        rows = search_local(q)
        api_rows = await search_api(q)

        if not rows and not api_rows:
            await send(chat_id,
                "🔎 نتیجه‌ای پیدا نشد.\n"
                "برای جستجوی آنلاین، SEARCH_API_URL را در Environment Variables تنظیم کن.")
            return

        buttons = []
        for sid, title, artist, audio_url, source_url in rows:
            label = f"🎧 {title}" + (f" — {artist}" if artist else "")
            buttons.append([{
                "text": label[:60],
                "callback_data": f"song:{sid}"
            }])

        text_out = f"🔎 نتایج برای «{q}»:\n\n"
        if rows:
            for sid, title, artist, *_ in rows:
                text_out += f"{sid}. {title}" + (f" — {artist}" if artist else "") + "\n"
        if api_rows:
            text_out += "\n🌐 نتایج آنلاین:\n"
            for item in api_rows:
                text_out += f"• {item.get('title','بدون عنوان')}"
                if item.get("artist"):
                    text_out += f" — {item['artist']}"
                text_out += "\n"

        await send(chat_id, text_out, {"inline_keyboard": buttons} if buttons else None)
        return

    await send(chat_id, "دستور نامعتبر است. /help را بزن.")

async def handle_callback(callback):
    data = callback.get("data", "")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    callback_id = callback.get("id")

    await tg("answerCallbackQuery", {"callback_query_id": callback_id})

    if data.startswith("song:") and chat_id:
        try:
            sid = int(data.split(":", 1)[1])
        except ValueError:
            return
        with closing(db()) as conn:
            row = conn.execute(
                "SELECT title,artist,audio_url FROM songs WHERE id=?", (sid,)
            ).fetchone()
        if not row:
            await send(chat_id, "این آهنگ در آرشیو پیدا نشد.")
            return
        title, artist, audio_url = row
        await send_audio(chat_id, audio_url, f"{title} — {artist}".strip(" —"))

@app.get("/")
async def root():
    return {"ok": True, "service": "music-bot"}

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/set-webhook")
async def set_webhook(url: str = ""):
    target = url.strip() or WEBHOOK_URL
    if not target:
        return JSONResponse({"ok": False, "error": "WEBHOOK_URL is not configured"})
    return await tg("setWebhook", {"url": target})

@app.get("/webhook-info")
async def webhook_info():
    return await tg("getWebhookInfo", {})

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    if "message" in update:
        await handle_message(update["message"])
    elif "callback_query" in update:
        await handle_callback(update["callback_query"])
    return {"ok": True}

@app.on_event("startup")
async def startup():
    db().close()
    if WEBHOOK_URL and BOT_TOKEN:
        await tg("setWebhook", {"url": WEBHOOK_URL})
