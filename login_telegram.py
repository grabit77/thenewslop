import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient('session_session', api_id, api_hash)

async def main():
    await client.start()  # Qui ti chiederà telefono e codice se non sei loggato
    print("Logged in!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

