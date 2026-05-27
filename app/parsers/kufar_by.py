from playwright.async_api import async_playwright
from app.parsers.base import BaseParser
from app.config import settings
from app.utils.logger import logger
import re

class KufarByParser(BaseParser):
    def __init__(self):
        super().__init__("kufar.by")
        # Цена в BYN: фильтр до MAX_PRICE_USD * 3.2 (курс BYN/USD)
        max_byn = int(settings.MAX_PRICE_USD * 3.2)
        self.base_url = f"https://auto.kufar.by/l/cars?prc=r%3A0%2C{max_byn}&sort=lst.d"

    async def fetch_ads(self):
        ads = []
        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            page = await self.setup_page(browser)
            
            await page.goto(self.base_url, wait_until="domcontentloaded")
            await self.random_delay(3, 5)
            
            sections = await page.locator("section").all()
            logger.debug(f"[kufar.by] Found {len(sections)} section elements")
            for idx, section in enumerate(sections[:10]):
                try:
                    link_locator = section.locator("a").first
                    url = await link_locator.get_attribute("href")
                    if not url or "/vi/cars/" not in url:
                        logger.debug(f"[kufar.by] Section {idx}: skipped, no valid url (url={url})")
                        continue
                    
                    external_id = url.split("/vi/cars/")[-1].split("?")[0]
                    
                    # Цена в BYN — получаем весь текст секции и ищем "р." 
                    all_text = await section.inner_text()
                    all_text = all_text.replace("\u00a0", " ").strip()
                    
                    # Ищем цену: "12 000 р." или "12,000 р."
                    price_match = re.search(r'(\d[\d\s]*)\s*р\.', all_text)
                    if price_match:
                        price = int(''.join(filter(str.isdigit, price_match.group(1))))
                    else:
                        logger.debug(f"[kufar.by] Section {idx}: no BYN price found in text: {all_text[:150]}")
                        continue

                    title_elements = section.locator("h3")
                    title_count = await title_elements.count()
                    if title_count == 0:
                        continue
                    title = await title_elements.first.inner_text()
                    parts = title.split(",")
                    car_name = parts[0].strip()
                    year = int(parts[1].replace('г.', '').strip()) if len(parts) > 1 else 0
                    
                    brand = car_name.split()[0]
                    model = " ".join(car_name.split()[1:])

                    p_elements = section.locator("p")
                    p_count = await p_elements.count()
                    if p_count < 2:
                        continue
                    details = await p_elements.nth(1).inner_text()
                    # Пример: "Автомат, 2.0 л, Бензин, 200 000 км"
                    det_parts = [d.strip() for d in details.split(',')]
                    gearbox = det_parts[0] if len(det_parts) > 0 else "Unknown"
                    engine = f"{det_parts[1]} {det_parts[2]}" if len(det_parts) > 2 else "Unknown"
                    mileage_str = det_parts[3] if len(det_parts) > 3 else ""
                    mileage_digits = ''.join(filter(str.isdigit, mileage_str))
                    mileage = int(mileage_digits) if mileage_digits else 0

                    city = await p_elements.last.inner_text()
                    
                    img_locator = section.locator("img").first
                    photo_url = await img_locator.get_attribute("src")
                    
                    logger.debug(f"[kufar.by] Section {idx}: parsed {brand} {model} {year} {price} BYN")

                    ads.append({
                        "external_id": f"kufar_{external_id}",
                        "source": "kufar.by",
                        "url": url.split("?")[0],
                        "price": price,
                        "currency": "BYN",
                        "brand": brand,
                        "model": model,
                        "year": year,
                        "engine": engine,
                        "gearbox": gearbox,
                        "mileage": mileage,
                        "city": city,
                        "photo_url": photo_url
                    })
                except Exception as e:
                    await self.log_status("warning", f"Failed to parse individual ad on kufar.by: {e}")
                    continue

            await browser.close()
        return ads