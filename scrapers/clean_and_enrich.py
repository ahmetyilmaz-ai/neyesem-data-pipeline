"""
Merkezi veri temizleme + zenginleştirme katmanı.

combine_sources.py tüm platform çıktılarını birleştirirken bu katmandan geçirir.
Amaç: scrape sırasında sızan çöp kayıtları (UI etiketleri, promo kodları, anlamsız
isimler), uçuk fiyatları ve birebir tekrarları tek noktada elemek; her ürüne
tutarlı bir `category` alanı eklemek.

Böylece "garbage in -> garbage out" zinciri AI'ya ulaşmadan kaynakta kırılır.
"""

import re

from scrapers.utils import normalize_text


# Ürün adı OLMAYAN, scrape sırasında yanlışlıkla isim sanılan UI/etiket metinleri.
UI_LABEL_WORDS = [
    "detaylar",
    "detay",
    "sepete ekle",
    "sepete",
    "ekle",
    "adet",
    "sec",
    "secenek",
    "gor",
    "incele",
    "tumunu gor",
    "daha fazla",
    "devamini",
    "siparis",
    "minimum",
    "minimum sepet",
    "teslimat",
    "kampanya",
    "puan",
    "yorum",
    "dakika",
    "filtre",
    "sirala",
    "su anda",
    "temsili",
    "cookie",
    "cerez",
    "anasayfa",
    "restoran",
]

# Kategori çıkarımı. Değerler AI tarafındaki şema ile uyumlu tutulmuştur
# (build_index.infer_category ile aynı mantık), böylece diyet/alerjen filtreleri
# kategori bazlı çalışabilir.
CATEGORY_KEYWORDS = {
    "Pizza": ["pizza"],
    "Burger": ["burger", "hamburger"],
    "Döner": ["döner", "doner"],
    "Pide & Lahmacun": ["pide", "lahmacun"],
    "Kebap": ["kebap", "kebab", "adana", "urfa", "şiş", "sis", "iskender"],
    "Tavuk": ["tavuk", "chicken", "kanat", "piliç", "pilic", "nugget"],
    "Çiğ Köfte": ["çiğ köfte", "cig kofte", "çiğköfte", "cigkofte"],
    "Tatlı": [
        "tatlı", "tatli", "waffle", "pasta", "kek", "cake", "baklava", "dondurma",
        "sütlaç", "sutlac", "kazandibi", "magnolia", "künefe", "kunefe", "tiramisu",
        "profiterol", "muhallebi", "trileçe", "trilece", "brownie", "browni", "kurabiye",
    ],
    "İçecek": [
        "su", "kola", "cola", "ayran", "ice tea", "fanta", "sprite", "limonata", "pepsi",
        "soda", "gazoz", "şalgam", "salgam", "meşrubat", "mesrubat", "milkshake", "shake",
        "smoothie", "çay", "cay", "kahve", "latte", "espresso", "americano", "cappuccino",
        "mocha", "fuse tea", "fusetea", "meyve suyu", "churchill", "erikli", "sümeker", "sumeker",
    ],
    "Çorba": ["çorba", "corba", "soup"],
    "Sağlıklı": ["salata", "fit", "bowl", "ızgara", "izgara"],
    "Deniz Ürünleri": ["balık", "balik", "hamsi", "midye", "karides", "somon", "levrek", "kalamar"],
}


def _normalized_name(item):
    return normalize_text(item.get("item_name") or item.get("normalized_item_name") or "")


def is_promo_or_code(name):
    """ILKYEMEK200, GURME500 gibi promosyon/kupon kodlarını yakalar."""
    normalized = normalize_text(name)
    if not normalized:
        return False
    # harf bloğu + rakam (ilkyemek200, gurme500) ya da uzun harf+rakam karışımı kod.
    if re.fullmatch(r"[a-z]+\d+[a-z0-9]*", normalized):
        return True
    if re.fullmatch(r"[a-z0-9]{8,}", normalized) and any(ch.isdigit() for ch in normalized):
        return True
    return False


def is_garbage(item):
    """Ürün olarak kabul edilemeyecek kayıtları tespit eder."""
    raw_name = str(item.get("item_name") or "").strip()
    normalized = normalize_text(raw_name)

    if len(normalized) < 3:
        return True

    # UI etiketi / anlamsız metin (tam kelime ya da içerme).
    tokens = set(normalized.split())
    for word in UI_LABEL_WORDS:
        w = normalize_text(word)
        if not w:
            continue
        if " " in w:
            if w in normalized:
                return True
        elif len(w) <= 4:
            if w in tokens:
                return True
        elif w in normalized:
            return True

    if is_promo_or_code(raw_name):
        return True

    price = item.get("price")
    try:
        price = float(price)
    except (TypeError, ValueError):
        return True

    if price <= 5 or price > 2500:
        return True

    return False


def infer_category(item_name):
    text = normalize_text(item_name)
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            kw = normalize_text(keyword)
            if not kw:
                continue
            if len(kw) <= 3:
                if kw in text.split():
                    return category
            elif kw in text:
                return category
    return "Genel"


def clean_and_enrich(items):
    """Çöp kayıtları eler, kategori ekler ve birebir tekrarları kaldırır.

    İstatistikleri (girdi/çıktı/elenen) döndürür ki çağıran taraf raporlayabilsin.
    """
    cleaned = []
    seen = set()

    stats = {
        "input": len(items),
        "dropped_garbage": 0,
        "dropped_duplicate": 0,
    }

    for item in items:
        if is_garbage(item):
            stats["dropped_garbage"] += 1
            continue

        dedupe_key = (
            item.get("platform"),
            normalize_text(item.get("restaurant_name")),
            _normalized_name(item),
            round(float(item.get("price")), 2),
        )

        if dedupe_key in seen:
            stats["dropped_duplicate"] += 1
            continue

        seen.add(dedupe_key)

        enriched = dict(item)
        if not enriched.get("category"):
            enriched["category"] = infer_category(item.get("item_name"))

        cleaned.append(enriched)

    stats["output"] = len(cleaned)
    return cleaned, stats
