"""
Trendyol Go (tgoyemek) için tarayıcısız, tam otomatik scraper.

Trendyol'un kendi public API'sini doğrudan kullanır:
  1. Restoran listesi:
     GET web-discovery-apidiscovery-santral/restaurants/filters?latitude=..&longitude=..&page=..
  2. Restoran menüsü:
     GET web-restaurant-apirestaurant-santral/restaurants/{id}?latitude=..&longitude=..
     -> data.restaurant.sections[].products[]  (name, price.salePrice, ...)

Menü ayrıştırma ortak scrapers/menu_parser üzerinden yapılır.

Anti-ban:
  - User-Agent havuzundan rastgele seçim + session rotasyonu
  - İstekler arası rastgele gecikme + periyodik "burst" molası
  - 429/5xx/timeout'ta exponential backoff ile yeniden deneme
  - Opsiyonel proxy

Kullanım:
    python scrape_trendyol_api.py --max 0                 # tüm restoranlar (~988)
    python scrape_trendyol_api.py --max 50
    python scrape_trendyol_api.py --max 0 --min-delay 2 --max-delay 5   # ekstra güvenli (yavaş)
    python scrape_trendyol_api.py --max 0 --proxy socks5://127.0.0.1:9050
"""

import argparse
import json
import random
import time
from datetime import datetime
from pathlib import Path

import requests

from scrapers.menu_parser import extract_menu_items


OUTPUT_PATH = Path("data/raw/trendyol_raw.json")

DISCOVERY_BASE = "https://api.tgoapis.com/web-discovery-apidiscovery-santral"
RESTAURANT_BASE = "https://api.tgoapis.com/web-restaurant-apirestaurant-santral"

# Bursa merkez koordinatları (proje tek şehir: Bursa).
CITY = "bursa"
LAT = 40.195
LON = 29.060

PAGE_SIZE = 20

# --- Anti-ban ayarları ---
REQUEST_TIMEOUT = 20
BURST_EVERY = 15           # bu kadar istekten sonra daha uzun mola
BURST_DELAY = 8.0          # mola süresi (sn)
MAX_RETRIES = 4
BACKOFF_BASE = 2.0         # exponential backoff tabanı
BACKOFF_MAX = 60.0         # tek bekleme üst sınırı
SESSION_ROTATE_EVERY = 50  # bu kadar istekte bir yeni session + yeni UA

# Gerçekçi tarayıcı User-Agent havuzu (rastgele seçilir).
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

BASE_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Origin": "https://tgoyemek.com",
    "Referer": "https://tgoyemek.com/",
}


class PoliteFetcher:
    """Anti-ban'lı HTTP istemcisi: UA rotasyonu, gecikme, burst molası, backoff, proxy."""

    def __init__(self, min_delay=1.0, max_delay=2.5, proxy=None):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.proxy = proxy
        self.request_count = 0
        self._new_session()

    def _new_session(self):
        self.session = requests.Session()
        if self.proxy:
            self.session.proxies = {"http": self.proxy, "https": self.proxy}
        self.user_agent = random.choice(USER_AGENTS)

    def _headers(self):
        return {**BASE_HEADERS, "User-Agent": self.user_agent}

    def _polite_sleep(self):
        self.request_count += 1
        if self.request_count % SESSION_ROTATE_EVERY == 0:
            self._new_session()  # yeni kimlik
        if self.request_count % BURST_EVERY == 0:
            time.sleep(BURST_DELAY)
        else:
            time.sleep(random.uniform(self.min_delay, self.max_delay))

    def get_json(self, url, params=None):
        self._polite_sleep()
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(
                    url, params=params, headers=self._headers(), timeout=REQUEST_TIMEOUT
                )
                # 429 (rate limit) ve 5xx -> yeniden dene
                if response.status_code == 429 or response.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {response.status_code}")
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_exc = exc
                wait = min(BACKOFF_MAX, BACKOFF_BASE ** attempt)
                print(f"    (deneme {attempt + 1}/{MAX_RETRIES} başarısız: {exc} -> {wait:.0f}s bekle)")
                time.sleep(wait)
                if attempt == 0:
                    self._new_session()  # ihtimale karşı kimlik tazele
        raise last_exc


def list_restaurants(fetcher, max_restaurants):
    """restaurants/filters üzerinden sayfa sayfa restoranları toplar."""
    restaurants = []
    page = 1

    while True:
        try:
            payload = fetcher.get_json(
                f"{DISCOVERY_BASE}/restaurants/filters",
                params={"latitude": LAT, "longitude": LON, "page": page, "pageSize": PAGE_SIZE},
            )
        except Exception as exc:
            print(f"  Restoran listesi sayfa {page} alınamadı: {exc}")
            break

        data = payload.get("data", payload)
        page_restaurants = data.get("restaurants", []) or []
        if not page_restaurants:
            break

        for raw in page_restaurants:
            restaurants.append(
                {
                    "id": raw.get("id"),
                    "name": raw.get("name"),
                    "rating": raw.get("rating") or raw.get("ratingText"),
                    "kitchen": raw.get("kitchen"),
                }
            )

        total = data.get("restaurantCount")
        print(f"  Sayfa {page}: +{len(page_restaurants)} restoran "
              f"(toplam toplanan: {len(restaurants)} / {total})")

        if max_restaurants and len(restaurants) >= max_restaurants:
            restaurants = restaurants[:max_restaurants]
            break
        if total is not None and len(restaurants) >= total:
            break
        page += 1

    return restaurants


def fetch_menu(fetcher, restaurant_id):
    """Tek restoranın menü cevabını alır ve ortak parser ile ürünleri çıkarır."""
    payload = fetcher.get_json(
        f"{RESTAURANT_BASE}/restaurants/{restaurant_id}",
        params={"latitude": LAT, "longitude": LON},
    )

    products = extract_menu_items(payload)

    info = (
        payload.get("data", payload).get("restaurant", {}).get("info", {})
        if isinstance(payload, dict) else {}
    )
    score = info.get("score") or {}
    rating = None
    if isinstance(score, dict):
        rating = score.get("averageScore") or score.get("score") or score.get("value")

    items = []
    for product in products:
        items.append(
            {
                "name": product["name"],
                "price": f"{product['price']:.2f} TL",
                "original_price": f"{product['original_price']:.2f} TL",
                "category": product.get("category"),
                "image_url": product.get("image_url"),
                "source": "api",
            }
        )

    return items, info.get("name"), rating


def save(results):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=40, help="Çekilecek maksimum restoran (0 = tümü)")
    parser.add_argument("--min-delay", type=float, default=1.0, help="İstekler arası min gecikme (sn)")
    parser.add_argument("--max-delay", type=float, default=2.5, help="İstekler arası max gecikme (sn)")
    parser.add_argument("--proxy", type=str, default=None, help="Opsiyonel proxy (ör. socks5://127.0.0.1:9050)")
    args = parser.parse_args()

    fetcher = PoliteFetcher(min_delay=args.min_delay, max_delay=args.max_delay, proxy=args.proxy)

    print("Trendyol restoran listesi alınıyor...")
    restaurants = list_restaurants(fetcher, max_restaurants=args.max)
    print(f"\n{len(restaurants)} restoran bulundu. Menüler çekiliyor...\n")

    results = []
    for index, restaurant in enumerate(restaurants, start=1):
        rid = restaurant.get("id")
        if not rid:
            continue

        try:
            items, menu_name, rating = fetch_menu(fetcher, rid)
        except Exception as exc:
            print(f"[{index}/{len(restaurants)}] {restaurant.get('name')}: HATA {exc}")
            continue

        results.append(
            {
                "restaurant_name": menu_name or restaurant.get("name"),
                "restaurant_rating": rating if rating is not None else restaurant.get("rating"),
                "restaurant_url": f"https://tgoyemek.com/restoranlar/{rid}",
                "city": CITY,
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
                "extraction_source": "api",
                "items": items,
            }
        )

        print(f"[{index}/{len(restaurants)}] {restaurant.get('name')}: {len(items)} ürün")

        if index % 10 == 0:
            save(results)

    save(results)

    total_items = sum(len(r["items"]) for r in results)
    print()
    print(f"Kaydedildi: {OUTPUT_PATH}")
    print(f"Restoran: {len(results)} | Toplam ürün: {total_items}")


if __name__ == "__main__":
    main()
