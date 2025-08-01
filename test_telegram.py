import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
channel_username = os.getenv("TELEGRAM_CHANNEL")

async def main():
    client = TelegramClient('session_session', api_id, api_hash)
    await client.start()
    print("Client Telegram avviato")

    messages = await client.get_messages(channel_username, limit=1)
    if messages and messages[0].message:
        print("Ultima notizia:")
        print(messages[0].message)
    else:
        print("Nessuna notizia disponibile")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

