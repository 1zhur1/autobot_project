import re
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from app.parsers.base import BaseParser
from app.config import settings
from app.utils.logger import logger

class KufarByParser(BaseParser):
    def __init__(self):
        super().__init__("kufar.by")
        self.ua = UserAgent()
        # Цена в BYN: фильтр до MAX_PRICE_USD * 3.2 (курс BYN/USD)
        max_byn = int(settings.MAX_PRICE_USD * 3.2)
        self.base_url = f"https://auto.kufar.by/l/cars?prc=r%3A0%2C{max_byn}&sort=lst.d"

    async def fetch_ads(self):
        ads = []
        headers = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(self.base_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                html = await response.text()

        soup = BeautifulSoup(html, "lxml")

        sections = soup.select("section")
        logger.debug(f"[kufar.by] Found {len(sections)} section elements")

        for idx, section in enumerate(sections[:10]):
            try:
                link_tag = section.select_one("a")
                if not link_tag:
                    continue
                url = link_tag.get("href")
                if not url or "/vi/cars/" not in url:
                    logger.debug(f"[kufar.by] Section {idx}: skipped, no valid url (url={url})")
                    continue

                external_id = url.split("/vi/cars/")[-1].split("?")[0]

                all_text = section.get_text(separator=" ", strip=True)

                # Ищем цену: "12 000 р." или "12,000 р."
                price_match = re.search(r'(\d[\d\s]*)\s*р\.', all_text)
                if not price_match:
                    logger.debug(f"[kufar.by] Section {idx}: no BYN price found")
                    continue
                price = int(''.join(filter(str.isdigit, price_match.group(1))))

                h3 = section.select_one("h3")
                if not h3:
                    continue
                title = h3.get_text(strip=True)
                parts = title.split(",")
                car_name = parts[0].strip()
                year = int(parts[1].replace('г.', '').strip()) if len(parts) > 1 else 0

                brand = car_name.split()[0]
                model = " ".join(car_name.split()[1:])

                p_tags = section.select("p")
                if len(p_tags) < 2:
                    continue
                details = p_tags[1].get_text(strip=True)
                det_parts = [d.strip() for d in details.split(',')]
                gearbox = det_parts[0] if len(det_parts) > 0 else "Unknown"
                engine = f"{det_parts[1]} {det_parts[2]}" if len(det_parts) > 2 else "Unknown"
                mileage_str = det_parts[3] if len(det_parts) > 3 else ""
                mileage_digits = ''.join(filter(str.isdigit, mileage_str))
                mileage = int(mileage_digits) if mileage_digits else 0

                city = p_tags[-1].get_text(strip=True) if p_tags else "Unknown"

                img_tag = section.select_one("img")
                photo_url = img_tag.get("src") if img_tag else None

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
                    "photo_url": photo_url,
                })
            except Exception as e:
                await self.log_status("warning", f"Failed to parse individual ad on kufar.by: {e}")
                continue

        return ads