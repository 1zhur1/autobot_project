from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.core import AsyncSessionLocal
from app.database.models import ParsedAd, PublishedAd
from app.utils.logger import logger

bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def format_message(ad: ParsedAd, brand: str, model: str, year: int, engine: str, gearbox: str, mileage: int) -> str:
    return (
        f"🔥 <b>{brand} {model}</b>\n"
        f"💰 BYN{ad.price:,}\n"
        f"📍 {ad.city}\n"
        f"⚙️ {gearbox}\n"
        f"⛽ {engine}\n"
        f"📏 {mileage:,} км\n"
        f"📆 {year}\n\n"
        f"🔗 <a href='{ad.url}'>Ссылка</a>"
    )

async def publish_ad(ad_id: int):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(ParsedAd)
                .options(selectinload(ParsedAd.car))
                .where(ParsedAd.id == ad_id)
            )
            ad = result.scalar_one_or_none()
            if not ad:
                logger.warning(f"Ad {ad_id} not found in database, skipping publish")
                return
                
            car = ad.car
            
            # Проверка на дубликат публикации
            pub_exists = await session.execute(select(PublishedAd).where(PublishedAd.ad_id == ad.id))
            if pub_exists.scalar_one_or_none():
                logger.info(f"Ad {ad.external_id} already published, skipping")
                return

            text = await format_message(
                ad, car.brand, car.model, car.year, car.engine, car.gearbox, car.mileage
            )

            logger.info(f"Attempting to publish ad {ad.external_id} to channel {settings.CHANNEL_ID}")
            
            if ad.photo_url:
                msg = await bot.send_photo(chat_id=settings.CHANNEL_ID, photo=ad.photo_url, caption=text)
            else:
                msg = await bot.send_message(chat_id=settings.CHANNEL_ID, text=text, disable_web_page_preview=False)
                
            published = PublishedAd(ad_id=ad.id, message_id=msg.message_id)
            session.add(published)
            await session.commit()
            logger.info(f"Successfully published {ad.external_id} to channel (message_id={msg.message_id}).")
            
        except Exception as e:
            logger.error(f"Failed to publish ad {ad_id} (external_id={getattr(ad, 'external_id', 'unknown') if 'ad' in dir() else 'unknown'}): {e}")
            await session.rollback()