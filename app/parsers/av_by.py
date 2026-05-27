import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from app.parsers.base import BaseParser
from app.config import settings

class AvByParser(BaseParser):
    def __init__(self):
        super().__init__("av.by")
        self.base_url = f"https://cars.av.by/filter?price_usd[max]={settings.MAX_PRICE_USD}&sort=4"
        self.ua = UserAgent()

    async def fetch_ads(self):
        ads = []
        headers = {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Referer": "https://cars.av.by/",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(self.base_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                html = await response.text()

        soup = BeautifulSoup(html, "lxml")

        listing_items = soup.select(".listing-item")
        if not listing_items:
            await self.log_status("warning", "No .listing-item elements found on av.by")
            return []

        for item in listing_items[:10]:
            try:
                # Ссылка
                link_tag = item.select_one("h3.listing-item__title a.listing-item__link")
                if not link_tag:
                    continue
                href = link_tag.get("href")
                if not href:
                    continue
                full_url = f"https://cars.av.by{href}" if href.startswith("/") else href
                external_id = href.split("/")[-1]

                # Заголовок
                title = link_tag.get_text(strip=True)
                if "·" in title:
                    brand_model = title.split("·")[0].strip()
                else:
                    brand_model = title
                brand_parts = brand_model.split()
                brand = brand_parts[0] if len(brand_parts) > 0 else "Unknown"
                model = " ".join(brand_parts[1:]) if len(brand_parts) > 1 else "Unknown"

                # Цена
                price_el = item.select_one(".listing-item__price-primary")
                price = 0
                if price_el:
                    price_digits = ''.join(filter(str.isdigit, price_el.get_text()))
                    price = int(price_digits) if price_digits else 0

                # Параметры
                params_divs = item.select(".listing-item__params > div")
                params_texts = [div.get_text(strip=True) for div in params_divs]

                year = 0
                gearbox = "Unknown"
                engine_text = "Unknown"
                mileage = 0

                if len(params_texts) >= 1:
                    year_str = params_texts[0].replace("г.", "").strip()
                    if year_str.isdigit():
                        year = int(year_str)

                if len(params_texts) >= 2:
                    parts = [p.strip() for p in params_texts[1].split(",")]
                    if len(parts) >= 1:
                        gearbox = parts[0]
                    if len(parts) >= 2:
                        engine_text = parts[1]
                    if len(parts) >= 3:
                        engine_text = f"{parts[1]}, {parts[2]}"

                if len(params_texts) >= 3:
                    mileage = int(''.join(filter(str.isdigit, params_texts[2])))

                # Локация
                city_el = item.select_one(".listing-item__location")
                city = city_el.get_text(strip=True) if city_el else "Unknown"

                # Фото
                photo_el = item.select_one(".listing-item__photo img")
                photo_url = None
                if photo_el:
                    photo_url = photo_el.get("data-src") or photo_el.get("src")

                ads.append({
                    "external_id": f"av_{external_id}",
                    "source": "av.by",
                    "url": full_url,
                    "price": price,
                    "currency": "BYN",
                    "brand": brand,
                    "model": model,
                    "year": year,
                    "engine": engine_text,
                    "gearbox": gearbox,
                    "mileage": mileage,
                    "city": city,
                    "photo_url": photo_url,
                })
            except Exception as e:
                await self.log_status("warning", f"Failed to parse individual ad on av.by: {e}")
                continue

        return ads