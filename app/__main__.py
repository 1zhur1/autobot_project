import asyncio
from app.utils.logger import logger
from app.database.core import init_db
from app.scheduler.worker import run_scheduler
from app.services.publisher import bot

async def main():
    logger.info("Initializing database...")
    await init_db()
    
    logger.info("Bot starting up...")
    
    # Запускаем шедулер как таску в event loop
    scheduler_task = asyncio.create_task(run_scheduler())
    
    try:
        await scheduler_task
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())