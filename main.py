import os
import re
import requests
import asyncio
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI


# 🔹 Carica variabili ambiente
load_dotenv()
api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
channel_username = os.getenv("TELEGRAM_CHANNEL")
print("Username del canale:", channel_username)
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
HORDE_API_KEY = os.getenv("HORDE_API_KEY", "0000000000")
HORDE_URL = "https://stablehorde.net/api/v2/generate/async"

client = TelegramClient("session_session", api_id, api_hash)

# 🔹 FastAPI
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

DB_FILE = "news.db"
IMAGES_DIR = "static/images"
os.makedirs(IMAGES_DIR, exist_ok=True)

# -------------------- DB --------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news TEXT,
                    prompt TEXT,
                    image_name TEXT,
                    timestamp TEXT)""")
    conn.commit()
    conn.close()

def save_to_db(news, prompt, image_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO news (news, prompt, image_name, timestamp) VALUES (?, ?, ?, ?)",
              (news, prompt, image_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_all_news():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, news, prompt, image_name, timestamp FROM news ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# -------------------- Utility --------------------
def remove_emoji(text: str) -> str:
    emoji_pattern = re.compile("["
                               "\U0001F600-\U0001F64F"
                               "\U0001F300-\U0001F5FF"
                               "\U0001F680-\U0001F6FF"
                               "\U0001F1E0-\U0001F1FF"
                               "\U00002700-\U000027BF"
                               "\U000024C2-\U0001F251" "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

async def generate_prompt(news_text: str) -> str:
    prompt_text = f"""
    Scrivi un prompt in inglese (max 1000 caratteri) per generare un'immagine fotorealistica seria e drammatica, che rifletta sulla crudeltà umana
    basata su questa notizia: {news_text}.
    """
    response = client_openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt_text}],
    )
    return response.choices[0].message.content.strip()

async def generate_image_stable_horde(prompt: str) -> str:
    payload = {"prompt": prompt, "params": {"width": 512, "height": 512, "steps": 20},
               "nsfw": False, "censor_nsfw": True}
    headers = {"apikey": HORDE_API_KEY, "Client-Agent": "TelegramNewsAI:1.0"}

    res = requests.post(HORDE_URL, json=payload, headers=headers)
    if res.status_code != 202:
        print("Errore Stable Horde:", res.text)
        return None

    job_id = res.json().get("id")
    print(f"✅ Job inviato a Stable Horde: {job_id}")

    while True:
        status = requests.get(f"{HORDE_URL.replace('/async', '/status')}/{job_id}")
        data = status.json()
        if data.get("done"):
            gens = data.get("generations", [])
            if gens:
                return gens[0]["img"]
            break
        await asyncio.sleep(5)

    return None

def download_image(url, filename):
    path = os.path.join(IMAGES_DIR, filename)
    r = requests.get(url)
    if r.status_code == 200:
        with open(path, "wb") as f:
            f.write(r.content)
        print(f"💾 Immagine salvata in {path}")
        return filename
    return None

# -------------------- Gestione Telegram --------------------
def get_last_news_text():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT news FROM news ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else None
    
async def process_new_message(news_text: str):
    news_text = remove_emoji(news_text).strip()
    print(f"📰 Nuova notizia: {news_text}")

    prompt = await generate_prompt(news_text)
    print(f"✏️ Prompt generato: {prompt}")

    image_url = await generate_image_stable_horde(prompt)
    if not image_url:
        print("⚠️ Errore nella generazione immagine")
        return

    # Nome immagine = id progressivo
    next_id = len(get_all_news()) + 1
    image_name = f"{next_id}.png"
    download_image(image_url, image_name)

    save_to_db(news_text, prompt, image_name)

@client.on(events.NewMessage(chats=channel_username))
async def handler(event):
    print("🔥 RICEVUTO NUOVO MESSAGGIO:", event.message.message)
    if event.message.message:
        await process_new_message(event.message.message)

@app.on_event("startup")
async def startup():
    init_db()
    await client.start()

    last_saved = get_last_news_text()

    msgs = await client.get_messages(channel_username, limit=1)
    if msgs and msgs[0].message:
        last_message = remove_emoji(msgs[0].message).strip()

        # 🔹 Se il messaggio è diverso dall'ultimo salvato → generiamo prompt e immagine
        if last_message != last_saved:
            print("🆕 Nuova notizia trovata all'avvio, genero prompt...")
            await process_new_message(last_message)
        else:
            print("ℹ️ Nessuna nuova notizia, già salvata.")
    else:
        print("⚠️ Nessun messaggio trovato nel canale.")

    asyncio.create_task(client.run_until_disconnected())
    print("✅ Client Telegram avviato e in ascolto...")

# -------------------- Pagina Web --------------------
def generate_html(record, index, total):
    news_id, news_text, prompt, image_name, timestamp = record
    image_path = f"/static/images/{image_name}"

    prev_btn = f"<a href='/news/{index+1}'><button>prev</button></a>" if index+1 < total else ""

    if index == 0:
        next_btn = ""  # Niente pulsante sulla homepage
    elif index - 1 == 0:  # Se la prossima è l'ultima, manda alla home
        next_btn = "<a href='/'><button>next</button></a>"
    else:
        next_btn = f"<a href='/news/{index-1}'><button>next</button></a>"




    return f"""
   <html>
  <head>
    <title>THE NEWSLOP</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-black text-white relative overflow-x-hidden">
    <!-- Titolo cliccabile -->
    <div class="p-6 text-4xl font-bold cursor-pointer" onclick="toggleMenu()">
      THE NEWSLOP
    </div>

    <!-- Sidebar nascosta -->
    <div id="sidebar"
         class="fixed top-0 left-0 h-full w-64 bg-white text-black p-6 transform -translate-x-full transition-transform duration-300 z-50">
      <h2 class="text-2xl font-bold mb-4">About</h2>
      <p class="mb-4">THE NEWSLOP vuole riflettere su bias e censura dell'AI generativa partendo da notizie vere 
      Prendendo informazioni in tempo reale e e tramutandole in prompt per creare un immagine con l'AI. 
      </p>
      <p class="mb-4">Credits: <br> 
      <b>Coding:</b> gab, ChatGpt 
      <br> <b>News:</b> Chronocol <br> 
      <b>Prompt di partenza:</b> Scrivi un prompt in inglese (max 1000 caratteri) per generare un'immagine fotorealistica seria e drammatica, che rifletta sulla crudeltà umana
    basata su questa notizia: <br>
      <b>Prompting per immagine:</b> ChatGpt <br>
      <b>Immage Generation:</b> stablehorde <br>
      <b>Idea:</b> gab <br>
      <b>Special thanks:</b> Lau <br></p>
      <button class="mt-4 bg-black text-white px-4 py-2 rounded" onclick="toggleMenu()">Chiudi</button>
    </div>

    <!-- Contenitore centrale -->
    <div class="flex flex-col items-center justify-center mt-10">
      <!-- Pulsanti -->
    <div class="flex justify-center mt-6 space-x-4">
    
      {prev_btn} {next_btn}
    </div>

      <!-- Immagine -->
      <img 
        id="newsImage"
        style="width:800px;"
        src="{image_path}" 
        class="cursor-pointer m-5 transition-transform duration-300 hover:scale-105 hover:shadow-2xl"
        onclick="togglePanel()" 
      />

      <!-- Pannello nascosto -->
      <div 
        id="infoPanel" 
        style="width:800px"
        class="hidden bg-white text-black p-6 mt-6 cursor-pointer transition-transform duration-300 hover:scale-105 hover:shadow-2xl"
        onclick="togglePanel()"
      >
        <p class="text-lg font-bold">{timestamp}</p>
        <p class="mt-2"><b>News:</b> {news_text}</p>
        <p class="mt-2"><b>Prompt:</b> {prompt}</p>
      </div>
    </div>

    
    <script>
      function togglePanel() {{
        const img = document.getElementById("newsImage");
        const panel = document.getElementById("infoPanel");

        if (img.classList.contains("hidden")) {{
          img.classList.remove("hidden");
          panel.classList.add("hidden");
        }} else {{
          img.classList.add("hidden");
          panel.classList.remove("hidden");
        }}
      }}

      function toggleMenu() {{
        const sidebar = document.getElementById("sidebar");
        sidebar.classList.toggle("-translate-x-full");
      }}
    </script>
  </body>
</html>
    """

@app.get("/", response_class=HTMLResponse)
async def index():
    news_list = get_all_news()
    if not news_list:
        return HTMLResponse("<h1>Nessuna notizia disponibile</h1>")
    return generate_html(news_list[0], 0, len(news_list))

@app.get("/news/{index}", response_class=HTMLResponse)
async def show_news(index: int):
    news_list = get_all_news()
    if not news_list or index < 0 or index >= len(news_list):
        return HTMLResponse("<h1>Notizia non trovata</h1>")
    return generate_html(news_list[index], index, len(news_list))

