# NeYesem Data Pipeline

NeYesem Data Pipeline, yemek platformlarından restoran ve ürün verilerini toplayıp ortak bir JSON formatına çeviren ve fiyat karşılaştırması yapan akademik PoC projesidir.

Bu repo; Yemeksepeti, Trendyol Go ve Getir Yemek verilerini tek formatta birleştirip Streamlit demo ekranında göstermeyi hedefler.

## Demo

Canlı demo:

https://neyesem.streamlit.app

Demo ekranında ürün/restoran araması yapılabilir, platformlara göre fiyatlar karşılaştırılabilir ve en uygun seçenek görüntülenebilir.

## Özellikler

- Yemeksepeti scraper çıktısını normalize eder.
- Trendyol Go restoran linklerini sayfadan çıkarır.
- Trendyol Go restoran menülerini scrape eder.
- Getir Yemek restoran ve menü verisini çeker.
- Tüm platformları ortak JSON formatına çevirir.
- Platform verilerini `all_items.json` içinde birleştirir.
- Streamlit üzerinden müşteri/demo ekranı sunar.
- Terminal üzerinden hızlı fiyat karşılaştırması yapılabilir.

## Proje Yapısı

```txt
.
├── data/
│   ├── raw/
│   │   ├── yemeksepeti_raw.json
│   │   ├── trendyol_urls.txt
│   │   ├── trendyol_raw.json
│   │   └── getir_raw.json
│   │
│   └── normalized/
│       ├── yemeksepeti_items.json
│       ├── trendyol_items.json
│       ├── getir_items.json
│       └── all_items.json
│
├── scrapers/
│   ├── utils.py
│   ├── yemeksepeti_normalizer.py
│   ├── trendyol_scraper.py
│   └── getir_normalizer.py
│
├── extract_trendyol_links_from_page.py
├── scrape_trendyol.py
├── scrape_getir.py
├── normalize_existing.py
├── normalize_trendyol.py
├── normalize_getir.py
├── combine_sources.py
├── compare_items.py
├── streamlit_app.py
└── requirements.txt
```

## Kurulum

Bağımlılıkları kur:

```powershell
python -m pip install -r .\requirements.txt
```

Playwright Chromium kur:

```powershell
python -m playwright install chromium
```

## Veri Güncelleme Akışı

### 1. Trendyol restoran linklerini çıkar

```powershell
python .\extract_trendyol_links_from_page.py
```

Tarayıcı açılınca konum/cookie ekranı varsa geç. Restoran listesi görünür hale geldiğinde terminalde Enter'a bas.

### 2. Trendyol menülerini çek

```powershell
python .\scrape_trendyol.py
```

Bu işlem `data/raw/trendyol_raw.json` dosyasını üretir.

### 3. Getir Yemek verisini çek

```powershell
python .\scrape_getir.py
```

Bu işlem `data/raw/getir_raw.json` dosyasını üretir.

### 4. Platform verilerini normalize et

```powershell
python .\normalize_existing.py
python .\normalize_trendyol.py
python .\normalize_getir.py
```

### 5. Tüm kaynakları birleştir

```powershell
python .\combine_sources.py
```

Bu işlem birleşik veri setini üretir:

```txt
data/normalized/all_items.json
```

## Demo Ekranını Çalıştırma

```powershell
streamlit run .\streamlit_app.py
```

Örnek aramalar:

```txt
pizza
waffle
burger
döner
su
```

## Terminalden Karşılaştırma

Streamlit kullanmadan hızlı arama yapmak için:

```powershell
python .\compare_items.py "pizza"
python .\compare_items.py "waffle"
python .\compare_items.py "su"
```

## Ortak Veri Formatı

Her platformdan gelen ürünler aşağıdaki ortak formata dönüştürülür:

```json
{
  "platform": "trendyol",
  "restaurant_name": "Örnek Restoran",
  "restaurant_rating": "4.5",
  "item_name": "Örnek Ürün",
  "normalized_item_name": "ornek urun",
  "price": 120.0,
  "original_price": 150.0,
  "discount_rate": 20.0,
  "product_url": "https://...",
  "city": "bursa",
  "scraped_at": "2026-05-16T23:09:24"
}
```

## Veri Kontrolü

Veri setinde kaç ürün ve kaç platform olduğunu görmek için:

```powershell
python .\check_data.py
```

Örnek çıktı:

```txt
Toplam ürün: 2434
Platformlar: Counter({'getir_yemek': ..., 'trendyol': ..., 'yemeksepeti': ...})
```

## Veri Kalitesi Notları

Bu proje akademik PoC amaçlıdır. Platformların sayfa yapısı veya API cevapları değişirse scraper kodlarının güncellenmesi gerekebilir.

Bazı platformlarda ürün/fiyat eşleşmesi sayfa metninden çıkarıldığı için hatalı eşleşmeler oluşabilir. Demo ekranında bariz hatalı kayıtları filtreleyen basit kontroller eklenmiştir.

Fiyatlar ve restoran erişilebilirliği konuma göre değişebilir.


## Not

Bu proje sipariş, ödeme veya kullanıcı hesabı işlemi yapmaz. Sadece akademik demo amacıyla restoran/ürün/fiyat verilerini düşük hacimli olarak işler.