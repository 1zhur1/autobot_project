import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.utils.logger import logger
from app.database.core import AsyncSessionLocal
from app.database.models import Car, ParsedAd
from app.parsers.av_by import AvByParser
from app.parsers.kufar_by import KufarByParser
from app.parsers.onliner_by import OnlinerByParser
from app.services.publisher import publish_ad

parsers = [
    AvByParser(),
    KufarByParser(),
    OnlinerByParser()
]

async def process_parsed_data(ads_data: list[dict]):
    async with AsyncSessionLocal() as session:
        for data in ads_data:
            # Anti-duplicate check
            exists = await session.execute(select(ParsedAd).where(ParsedAd.external_id == data["external_id"]))
            if exists.scalar_one_or_none():
                continue
                
            url_exists = await session.execute(select(ParsedAd).where(ParsedAd.url == data["url"]))
            if url_exists.scalar_one_or_none():
                continue

            car = Car(
                brand=data["brand"],
                model=data["model"],
                year=data["year"],
                engine=data["engine"],
                gearbox=data["gearbox"],
                mileage=data["mileage"]
            )
            session.add(car)
            await session.flush() # Получаем car.id

            parsed_ad = ParsedAd(
                external_id=data["external_id"],
                source=data["source"],
                url=data["url"],
                price=data["price"],
                currency=data["currency"],
                city=data["city"],
                photo_url=data["photo_url"],
                car_id=car.id
            )
            session.add(parsed_ad)
            await session.commit()
            
            # Публикуем объявление с задержкой между сообщениями (3-7 секунд)
            try:
                await publish_ad(parsed_ad.id)
                await asyncio.sleep(5)  # Задержка между сообщениями в канале
            except Exception as e:
                logger.error(f"Failed to publish ad {parsed_ad.id} ({data['external_id']}): {e}")
                await asyncio.sleep(2)

async def run_scheduler():
    logger.info("Starting scheduler background worker...")
    while True:
        for parser in parsers:
            logger.info(f"Running parser: {parser.source_name}")
            try:
                ads = await parser.run()
                if ads:
                    await process_parsed_data(ads)
            except Exception as e:
                logger.error(f"Error in scheduler for {parser.source_name}: {e}")
            
            # Задержка между парсерами
            await asyncio.sleep(5)
            
        logger.info(f"Sleeping for {settings.CHECK_INTERVAL_SECONDS} seconds...")
        await asyncio.sleep(settings.CHECK_INTERVAL_SECONDS)