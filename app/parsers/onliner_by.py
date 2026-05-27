import re
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from app.parsers.base import BaseParser
from app.config import settings
from app.utils.logger import logger

class OnlinerByParser(BaseParser):
    def __init__(self):
        super().__init__("onliner.by")
        self.ua = UserAgent()
        # Фильтр: до 10000 USD, сортировка по дате
        self.base_url = f"https://ab.onliner.by/?price[to]={settings.MAX_PRICE_USD}&price[currency]=USD#sort[]=created_at:desc"

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

        offers = soup.select(".vehicle-form__offers-unit")
        logger.debug(f"[onliner.by] Total offers found: {len(offers)}")

        for idx, offer in enumerate(offers[:10]):
            try:
                href = offer.get("href")
                if not href or (href.startswith("http") and "promote" in href):
                    continue
                full_url = f"https://ab.onliner.by{href}" if href.startswith("/") else href
                external_id = full_url.split("/")[-1]

                full_text = offer.get_text(separator=" ", strip=True)
                logger.debug(f"[onliner.by] Offer {idx} full text: {full_text[:400]}")

                # Марка и модель — между годом/городом и VIN
                car_title_match = re.search(r'(?:Минск|Брест|Гродно|Гомель|Могил[её]в|Витебск|Молодечно|Борисов|Барановичи|Пинск|Орша|Лида|Полоцк|Мозырь|Солигорск|Новополоцк|Жлобин|Светлогорск|Речица|Дзержинск|Слуцк)\s+(.+?)\s+VIN\b', full_text)
                if not car_title_match:
                    car_title_match = re.search(r'\b(20[0-9]{2})\s+(?:Минск|Брест|Гродно|Гомель|Могил[её]в|Витебск)?\s*(.+?)\s+VIN\b', full_text)

                if car_title_match:
                    car_name = car_title_match.group(1).strip()
                    car_name = re.sub(r'\s*Обмен\s*$', '', car_name).strip()
                    name_parts = car_name.split()
                    brand = name_parts[0] if len(name_parts) > 0 else "Unknown"
                    model = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Unknown"
                else:
                    pre_vin = re.split(r'\s+VIN\s+', full_text)[0]
                    words = pre_vin.split()
                    valid_words = [w for w in words if w not in ['Обмен', 'Возможен', 'торг', 'Один', 'владелец']]
                    if valid_words:
                        brand = valid_words[0]
                        model = " ".join(valid_words[1:])
                    else:
                        brand = "Unknown"
                        model = "Unknown"

                logger.debug(f"[onliner.by] Offer {idx} brand: '{brand}', model: '{model}'")

                # Цена в USD
                usd_match = re.search(r'(\d[\d\s]*)\s*\$$', full_text)
                if usd_match:
                    price = int(''.join(filter(str.isdigit, usd_match.group(1))))
                else:
                    byn_match = re.search(r'(\d[\d\s]*)\s*ƃ', full_text)
                    if byn_match:
                        price_byn = int(''.join(filter(str.isdigit, byn_match.group(1))))
                        price = price_byn // 3
                    else:
                        all_numbers = re.findall(r'(\d[\d\s]*)', full_text)
                        price = int(''.join(filter(str.isdigit, all_numbers[0]))) if all_numbers else 0

                if price > settings.MAX_PRICE_USD:
                    logger.debug(f"[onliner.by] Offer {idx}: price ${price} > MAX, skipping")
                    continue

                # Год
                year_match = re.search(r'\b(20[0-9]{2})\b', full_text)
                year = int(year_match.group(1)) if year_match else 0

                # Пробег
                mileage_match = re.search(r'(\d[\d\s]*)\s*км', full_text)
                mileage = int(''.join(filter(str.isdigit, mileage_match.group(1)))) if mileage_match else 0

                # Характеристики
                engine = "Unknown"
                gearbox = "Unknown"
                engine_types = ["бензин", "дизель", "электро", "гибрид", "газ"]
                for et in engine_types:
                    if et in full_text.lower():
                        engine = et
                        break
                gearbox_types = ["автомат", "механика", "вариатор", "робот"]
                for gt in gearbox_types:
                    if gt in full_text.lower():
                        gearbox = gt
                        break

                # Город
                cities = ["Минск", "Брест", "Гродно", "Гомель", "Могилёв", "Могилев", "Витебск", "Борисов",
                          "Барановичи", "Пинск", "Орша", "Новополоцк", "Лида", "Молодечно", "Полоцк",
                          "Жлобин", "Светлогорск", "Речица", "Солигорск", "Мозырь"]
                city = "Unknown"
                for c in cities:
                    if c in full_text:
                        city = c
                        break

                # Фото
                img_tag = offer.select_one("img")
                photo_url = img_tag.get("src") if img_tag else None

                logger.debug(f"[onliner.by] Parsed: {brand} {model} {year} ${price} {city} mileage={mileage}km")

                ads.append({
                    "external_id": f"onliner_{external_id}",
                    "source": "onliner.by",
                    "url": full_url,
                    "price": price,
                    "currency": "USD",
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
                await self.log_status("warning", f"Failed to parse individual ad on onliner.by: {e}")
                continue

        return ads