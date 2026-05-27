from playwright.async_api import async_playwright
from app.parsers.base import BaseParser
from app.config import settings

class AvByParser(BaseParser):
    def __init__(self):
        super().__init__("av.by")
        self.base_url = f"https://cars.av.by/filter?price_usd[max]={settings.MAX_PRICE_USD}&sort=4"

    async def fetch_ads(self):
        ads = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
            page = await self.setup_page(browser)

            page.set_default_timeout(60000)

            await page.goto(self.base_url, wait_until="networkidle", timeout=60000)
            await self.random_delay(3, 5)

            # Ждём появления элементов списка
            await page.wait_for_selector(".listing-item", timeout=60000)

            listings = await page.locator(".listing-item").all()
            for listing in listings[:10]:
                try:
                    # Ссылка и external_id
                    link_locator = listing.locator("h3.listing-item__title a.listing-item__link")
                    href = await link_locator.get_attribute("href", timeout=15000)
                    if not href:
                        continue
                    full_url = f"https://cars.av.by{href}" if href.startswith("/") else href
                    external_id = href.split("/")[-1]

                    # Заголовок (Renault Sandero II · Рестайлинг)
                    title = await link_locator.inner_text(timeout=15000)
                    title = title.replace("\u00a0", " ").strip()
                    # Убираем "· Рестайлинг" из названия модели, если есть
                    if "·" in title:
                        parts = title.split("·")
                        brand_model = parts[0].strip()
                    else:
                        brand_model = title
                    brand_parts = brand_model.split()
                    brand = brand_parts[0] if len(brand_parts) > 0 else "Unknown"
                    model = " ".join(brand_parts[1:]) if len(brand_parts) > 1 else "Unknown"

                    # Цена в BYN (на списке av.by показывает только BYN)
                    price_primary = await listing.locator(".listing-item__price-primary").inner_text(timeout=15000)
                    price = int(''.join(filter(str.isdigit, price_primary)))

                    # Параметры: <div>2019 г.</div><div>механика, 1,6 л, бензин, хэтчбек 5 дв.</div><div><span>313 519 км</span></div>
                    params_divs = await listing.locator(".listing-item__params > div").all()
                    params_texts = []
                    for div in params_divs:
                        txt = await div.inner_text(timeout=10000)
                        params_texts.append(txt.replace("\u00a0", " ").strip())

                    year = 0
                    gearbox = "Unknown"
                    engine_text = "Unknown"
                    mileage = 0

                    if len(params_texts) >= 1:
                        # Год: "2019 г."
                        year_str = params_texts[0].replace("г.", "").strip()
                        if year_str.isdigit():
                            year = int(year_str)

                    if len(params_texts) >= 2:
                        # "механика, 1,6 л, бензин, хэтчбек 5 дв."
                        parts = [p.strip() for p in params_texts[1].split(",")]
                        if len(parts) >= 1:
                            gearbox = parts[0]
                        if len(parts) >= 2:
                            engine_text = parts[1]
                            if len(parts) >= 3:
                                engine_text = f"{parts[1]}, {parts[2]}"

                    if len(params_texts) >= 3:
                        # "313 519 км"
                        mileage = int(''.join(filter(str.isdigit, params_texts[2])))

                    # Локация
                    city = await listing.locator(".listing-item__location").inner_text(timeout=15000)
                    city = city.replace("\u00a0", " ").strip()

                    # Фото — первое изображение в карусели
                    photo_img = listing.locator(".listing-item__photo img").first
                    photo_url = await photo_img.get_attribute("data-src", timeout=10000) or await photo_img.get_attribute("src", timeout=10000)

                    ads.append({
                        "external_id": f"av_{external_id}",
                        "source": "av.by",
                        "url": full_url,
                        "price": price,
                        "currency": "BYN",  # av.by теперь показывает BYN на списке
                        "brand": brand,
                        "model": model,
                        "year": year,
                        "engine": engine_text,
                        "gearbox": gearbox,
                        "mileage": mileage,
                        "city": city,
                        "photo_url": photo_url
                    })
                except Exception as e:
                    await self.log_status("warning", f"Failed to parse individual ad on av.by: {e}")
                    continue

            await browser.close()
        return ads