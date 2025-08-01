#main che va con db

import os
import re
import asyncio
import sqlite3
import requests
from dotenv import load_dotenv
from telethon import TelegramClient, events
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from openai import OpenAI

load_dotenv()

# Config
api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
channel_username = os.getenv("TELEGRAM_CHANNEL")
HORDE_API_KEY = os.getenv("HORDE_API_KEY")
HORDE_URL = "https://stablehorde.net/api/v2/generate/async"

client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client_telegram = TelegramClient("session_main", api_id, api_hash)
app = FastAPI()

DB_FILE = "news.db"


# ================== UTILS ==================
def remove_emoji(text: str) -> str:
    emoji_pattern = re.compile(
        "[" 
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002700-\U000027BF"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, news TEXT, prompt TEXT, image_url TEXT)"
    )
    conn.commit()
    conn.close()


def save_to_db(news, prompt, image_url):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO news (news, prompt, image_url) VALUES (?, ?, ?)", (news, prompt, image_url))
    conn.commit()
    conn.close()


def get_last_record():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT news, prompt, image_url, timestamp FROM news ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row


async def generate_prompt(news_text: str) -> str:
    prompt_text = (
        "Scrivi in inglese un prompt fotorealistico e serio (max 1000 caratteri) per creare un'immagine "
        "che rappresenti la crudeltà umana, con molte persone e dettagli, basato su questa notizia:\n"
        f"{news_text}"
    )

    response = client_openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt_text}],
    )
    return response.choices[0].message.content.strip()


async def generate_image_stable_horde(prompt: str) -> str:
    payload = {
        "prompt": prompt,
        "params": {"width": 512, "height": 512, "steps": 20},
        "nsfw": False,
        "censor_nsfw": True,
    }
    headers = {"apikey": HORDE_API_KEY, "Client-Agent": "TelegramNewsAI:1.0"}

    res = requests.post(HORDE_URL, json=payload, headers=headers)
    if res.status_code != 202:
        print("Errore Stable Horde:", res.text)
        return None

    job_id = res.json().get("id")
    print(f"✅ Job inviato a Stable Horde: {job_id}")

    while True:
        status = requests.get(f"{HORDE_URL.replace('/async', '')}/status/{job_id}")
        data = status.json()

        if data.get("done"):
            gens = data.get("generations", [])
            if gens:
                return gens[0]["img"]
            break

        await asyncio.sleep(5)

    return None


# ================== TELEGRAM ==================
async def process_news(news_text):
    print(f"📰 Nuova notizia: {news_text}")
    prompt = await generate_prompt(news_text)
    print(f"✏️ Prompt generato: {prompt}")
    image_url = await generate_image_stable_horde(prompt)
    print(f"🖼️ Immagine generata: {image_url}")

    if image_url:
        save_to_db(news_text, prompt, image_url)


@client_telegram.on(events.NewMessage(chats=channel_username))
async def handler(event):
    news_text = remove_emoji(event.message.message.strip())
    await process_news(news_text)


async def get_latest_news():
    await client_telegram.start()
    messages = await client_telegram.get_messages(channel_username, limit=1)
    if messages and messages[0].message:
        return remove_emoji(messages[0].message.strip())
    return None


# ================== FASTAPI ==================
@app.on_event("startup")
async def startup():
    init_db()
    await client_telegram.start()

    # Se DB è vuoto → salva l'ultima notizia
    if not get_last_record():
        news = await get_latest_news()
        if news:
            await process_news(news)

    asyncio.create_task(client_telegram.run_until_disconnected())
    print("✅ Client Telegram avviato e in ascolto...")


@app.get("/", response_class=HTMLResponse)
async def index():
    row = get_last_record()
    if not row:
        return HTMLResponse("<h1>Nessuna notizia disponibile</h1>")

    news, prompt, image_url, timestamp = row

    html = f"""
    <html>
    <head>
        <title>News & AI Art</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: black;
                color: white;
                text-align: center;
                padding: 20px;
            }}
            .card {{
                background: #000;
                padding: 20px;
                margin: 20px auto;
                border-radius: 10px;
                max-width: 50%;
            }}
            img {{
                max-width: 100%;
                border-radius: 0px;
                margin-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            {f"<img src='{image_url}' />" if image_url else "<p><b>Errore: immagine non generata</b></p>"}
        </div>
        
        <div class="card">
        <h2>News</h2>
            <p><b>{news}</b></p>
            <small><i>{timestamp}</i></small>
        </div>    
        <div class="card">
            <h2>Prompt</h2>
            <p>{prompt}</p>
        </div>

        
    </body>
    </html>
    """
    return HTMLResponse(html)

