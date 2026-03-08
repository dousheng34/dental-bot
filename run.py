import asyncio, threading, uvicorn, logging, os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def run_fastapi():
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)

async def run_bot():
    from bot import bot, start_polling
    from scheduler import setup_scheduler
    setup_scheduler(bot)
    await start_polling()

if __name__ == "__main__":
    t = threading.Thread(target=run_fastapi, daemon=True)
    t.start()
    print("🌐 FastAPI запущен на порту 8000")
    print("🤖 Запускаем Telegram бота...")
    print("⏰ Планировщик напоминаний активен")
    asyncio.run(run_bot())
