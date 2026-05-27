import asyncio
import random
from typing import List, Dict, Any, Optional
from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Browser, Page
from app.utils.logger import logger
from app.database.core import AsyncSessionLocal
from app.database.models import ParserLog

class BaseParser:
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.ua = UserAgent()

    async def log_status(self, status: str, message: str):
        async with AsyncSessionLocal() as session:
            log = ParserLog(source=self.source_name, status=status, message=message)
            session.add(log)
            await session.commit()
        if status == "error":
            logger.error(f"[{self.source_name}] {message}")
        else:
            logger.info(f"[{self.source_name}] {message}")

    async def random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def setup_page(self, browser: Browser) -> Page:
        context = await browser.new_context(
            user_agent=self.ua.random,
            viewport={'width': random.randint(1280, 1920), 'height': random.randint(720, 1080)},
            java_script_enabled=True
        )
        # Anti-detect evasion
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = await context.new_page()
        page.set_default_timeout(30000)
        return page

    async def fetch_ads(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("fetch_ads must be implemented in subclasses")

    async def run(self) -> List[Dict[str, Any]]:
        retries = 3
        for attempt in range(retries):
            try:
                results = await self.fetch_ads()
                await self.log_status("success", f"Parsed {len(results)} ads")
                return results
            except Exception as e:
                await self.log_status("error", f"Attempt {attempt + 1} failed: {str(e)}")
                await self.random_delay(5.0, 10.0)
        return []