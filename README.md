# NeYesem Data Pipeline

NeYesem projesinin veri toplama katmanı. Yemek platformlarının **resmi API'lerinden**
restoran ve ürün verisini çeker, ortak bir JSON formatına çevirir, temizler ve birleştirir.

İki platform desteklenir; ikisi de tarayıcı/Selenium/Playwright kullanmaz, doğrudan
API'ye `requests` ile gider:

| Platform | Scraper | Veri kaynağı |
|----------|---------|--------------|
| **Trendyol Go** | `scrape_trendyol_api.py` | `api.tgoapis.com` (resmi discovery + restaurant API) |
| **Getir Yemek** | `scrape_getir.py` | `food-client-api-gateway.getirapi.com` + sayfa `__NEXT_DATA__` |

> Not: Yemeksepeti, PerimeterX bot koruması nedeniyle kapsam dışıdır.

## Mimari

```
scrape_trendyol_api.py ─┐
scrape_getir.py ────────┤
                        ▼
            data/raw/*.json   (ham çıktı)
                        │
   normalize_trendyol.py / normalize_getir.py
                        ▼
        data/normalized/*_items.json  (ortak format)
                        │
              combine_sources.py
        (scrapers/clean_and_enrich: çöp filtresi + kategori + tekrar eleme)
                        ▼
        data/normalized/all_items.json   (AI'ın kullandığı birleşik veri)
```

## Proje Yapısı

```txt
.
├── scrape_trendyol_api.py        # Trendyol Go - resmi API (tarayıcısız)
├── scrape_getir.py               # Getir Yemek - resmi API (tarayıcısız)
├── normalize_trendyol.py
├── normalize_getir.py
├── combine_sources.py            # birleştir + temizle + kategori ekle
├── check_data.py                 # veri sayım/kontrol
├── refresh_data.py               # tüm pipeline'ı tek komutla çalıştırır
├── compare_items.py              # terminalden fiyat karşılaştırma
├── streamlit_app.py              # demo arayüzü
└── scrapers/
    ├── menu_parser.py            # ortak, toleranslı JSON menü parser
    ├── clean_and_enrich.py       # çöp filtresi + kategori + dedup
    ├── trendyol_normalizer.py
    └── utils.py
```

## Kurulum

```powershell
python -m pip install -r requirements.txt
```

## Kullanım

Tek komutla tüm pipeline (önerilen):

```powershell
python refresh_data.py
```

Adım adım:

```powershell
python scrape_trendyol_api.py --max 0   # 0 = tüm Bursa restoranları (~988)
python scrape_getir.py
python normalize_trendyol.py
python normalize_getir.py
python combine_sources.py               # -> data/normalized/all_items.json
python check_data.py
```

`--max` ile restoran sınırı verilebilir (hızlı test için `--max 20` gibi).

## Ortak Veri Formatı

```json
{
  "platform": "trendyol",
  "restaurant_name": "Örnek Restoran",
  "restaurant_rating": 4.5,
  "item_name": "Örnek Ürün",
  "category": "Pizza",
  "price": 120.0,
  "original_price": 150.0,
  "discount_rate": 20.0,
  "product_url": "https://...",
  "city": "bursa",
  "scraped_at": "2026-06-09T12:00:00"
}
```

## Veri Kalitesi

`combine_sources.py` tek noktada çöpü eler: UI etiketleri ("Detaylar" vb.),
promosyon kodları, anlamsız/kısa isimler, uçuk fiyatlar ve birebir tekrarlar.
Her ürüne kategori bilgisi eklenir.

## Not

Akademik PoC. Sipariş/ödeme/kullanıcı işlemi yapmaz; düşük hacimli, sadece-okuma
veri toplar. Platform API'leri değişirse scraper güncellenmesi gerekebilir.
