from playwright.async_api import async_playwright
from app.parsers.base import BaseParser
from app.config import settings
from app.utils.logger import logger
import re

class OnlinerByParser(BaseParser):
    def __init__(self):
        super().__init__("onliner.by")
        # Фильтр: до 10000 USD, сортировка по дате
        self.base_url = f"https://ab.onliner.by/?price[to]={settings.MAX_PRICE_USD}&price[currency]=USD#sort[]=created_at:desc"

    async def fetch_ads(self):
        ads = []
        async with async_playwright() as p:
            browser = await self._launch_browser(p)
            page = await self.setup_page(browser)

            page.set_default_timeout(90000)
            await page.goto(self.base_url, wait_until="domcontentloaded", timeout=90000)
            await self.random_delay(3, 5)

            # Ждём элементы списка
            await page.wait_for_selector(".vehicle-form__offers-unit", timeout=90000)
            offers = await page.locator(".vehicle-form__offers-unit").all()
            logger.debug(f"[onliner.by] Total offers found: {len(offers)}")

            for idx, offer in enumerate(offers[:10]):
                try:
                    href = await offer.get_attribute("href")
                    if not href or href.startswith("http") and "promote" in href:
                        continue
                    full_url = f"https://ab.onliner.by{href}" if href.startswith("/") else href
                    external_id = full_url.split("/")[-1]

                    # Полный текст оффера (содержит название, цену, параметры)
                    full_text = await offer.inner_text()
                    full_text = full_text.replace("\u00a0", " ").strip()
                    logger.debug(f"[onliner.by] Offer {idx} full text: {full_text[:400]}")

                    # Название авто — ищем между городом/годом и "VIN"
                    # Пример: "2016 Минск Ford Focus (III) Рестайлинг VIN 25 764"
                    # Извлекаем: всё между <город> (или <год>) и "VIN"
                    car_title_match = re.search(r'(?:Минск|Брест|Гродно|Гомель|Могил[её]в|Витебск|Молодечно|Борисов|Барановичи|Пинск|Орша|Лида|Полоцк|Мозырь|Солигорск|Новополоцк|Жлобин|Светлогорск|Речица|Дзержинск|Слуцк)\s+(.+?)\s+VIN\b', full_text)
                    if not car_title_match:
                        # Fallback: после года ищем до VIN
                        car_title_match = re.search(r'\b(20[0-9]{2})\s+(?:Минск|Брест|Гродно|Гомель|Могил[её]в|Витебск)?\s*(.+?)\s+VIN\b', full_text)
                    if car_title_match:
                        car_name = car_title_match.group(1).strip()
                        # Убираем "Обмен" если есть в конце
                        car_name = re.sub(r'\s*Обмен\s*$', '', car_name).strip()
                        name_parts = car_name.split()
                        brand = name_parts[0] if len(name_parts) > 0 else "Unknown"
                        model = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Unknown"
                    else:
                        # Fallback 2: всё что перед "VIN" вообще
                        pre_vin = re.split(r'\s+VIN\s+', full_text)[0]
                        # Извлекаем последние 2-3 слова (марка модель)
                        words = pre_vin.split()
                        if len(words) >= 2:
                            # Пропускаем слова "Обмен", "Возможен торг" и т.д.
                            valid_words = [w for w in words if w not in ['Обмен', 'Возможен', 'торг', 'Один', 'владелец', 'Возможен']]
                            if valid_words:
                                brand = valid_words[0]
                                model = " ".join(valid_words[1:])
                            else:
                                brand = "Unknown"
                                model = "Unknown"
                        else:
                            brand = "Unknown"
                            model = "Unknown"
                    logger.debug(f"[onliner.by] Offer {idx} brand: '{brand}', model: '{model}'")

                    # Цена в USD — ищем "$" в тексте (после ƃ)
                    # Формат: "23 271 ƃ 8400 $ / 7215 €" или "8400 $"
                    usd_match = re.search(r'(\d[\d\s]*)\s*\$$', full_text)
                    if usd_match:
                        price_str = usd_match.group(1).strip()
                        price = int(''.join(filter(str.isdigit, price_str)))
                    else:
                        # Fallback: BYN
                        byn_match = re.search(r'(\d[\d\s]*)\s*ƃ', full_text)
                        if byn_match:
                            price_byn = int(''.join(filter(str.isdigit, byn_match.group(1))))
                            price = price_byn // 3
                        else:
                            all_numbers = re.findall(r'(\d[\d\s]*)', full_text)
                            price = int(''.join(filter(str.isdigit, all_numbers[0]))) if all_numbers else 0

                    # Проверка цены до 10k USD
                    if price > settings.MAX_PRICE_USD:
                        logger.debug(f"[onliner.by] Offer {idx}: price ${price} > MAX ${settings.MAX_PRICE_USD}, skipping")
                        continue

                    # Год — ищем 4-значное число от 2000 до 2030
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

                    # Город — ищем в тексте (после цены или в конце)
                    # Часто город выглядит как "Минск", "Гродно" и т.д.
                    cities = ["Минск", "Брест", "Гродно", "Гомель", "Могилёв", "Могилев", "Витебск", "Борисов",
                              "Барановичи", "Пинск", "Орша", "Новополоцк", "Лида", "Молодечно", "Полоцк",
                              "Жлобин", "Светлогорск", "Речица", "Солигорск", "Мозырь"]
                    city = "Unknown"
                    for c in cities:
                        if c in full_text:
                            city = c
                            break

                    # Фото
                    photo_img = offer.locator("img").first
                    photo_url = await photo_img.get_attribute("src", timeout=15000)

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
                        "photo_url": photo_url
                    })
                except Exception as e:
                    await self.log_status("warning", f"Failed to parse individual ad on onliner.by: {e}")
                    continue

            await browser.close()
        return ads