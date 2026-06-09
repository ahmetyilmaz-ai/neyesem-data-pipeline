"""
Platformdan bağımsız, toleranslı menü ürünü çıkarıcı.

Getir'in çalışan __NEXT_DATA__ parser mantığı genelleştirilmiştir. Trendyol'un
XHR/JSON cevapları, Getir'in __NEXT_DATA__'sı ve benzer SPA yapıları aynı
fonksiyondan geçer. Amaç: her platform için ayrı, kırılgan parser yazmak yerine
tek bir "JSON içinden ürünleri bul" motoru kullanmak.

Tasarım ilkeleri:
- İç içe JSON'u gez (walk), kategori->ürünler yapısını öncele.
- Alan adlarında toleranslı ol (name/title, price/sellingPrice/..., originalPrice/...).
- Restoran kartı / UI etiketi / promo kodu gibi ürün-olmayan objeleri reddet.
- Fiyatı normalize et (kuruş, "TL" stringi, dict sarmalı).
"""

from scrapers.utils import parse_price, normalize_text
from scrapers.clean_and_enrich import UI_LABEL_WORDS, is_promo_or_code


NAME_KEYS = ["name", "title", "productName", "displayName", "itemName"]

PRICE_KEYS = [
    "price", "priceText", "displayPrice", "finalPrice", "sellingPrice",
    "discountedPrice", "discountPrice", "salePrice",
]

ORIGINAL_PRICE_KEYS = [
    "originalPrice", "oldPrice", "strikeThroughPrice", "listPrice",
    "basePrice", "marketPrice",
]

DISCOUNT_KEYS = ["discountPercentage", "discount_percentage", "discountRate", "discountRatio"]

IMAGE_KEYS = ["imageURL", "imageUrl", "fullScreenImageURL", "image", "picURL", "thumbnailURL"]

DESC_KEYS = ["description", "desc", "summary", "shortDescription"]

PRODUCT_LIST_KEYS = ["products", "items", "productList", "menuItems", "lineItems"]

# Bir obje bu alanları taşıyıp fiyat alanı taşımıyorsa, bu bir RESTORAN kartıdır,
# ürün değil. (minBasketPrice'ı ürün fiyatı sanma hatasını engeller.)
RESTAURANT_ONLY_KEYS = {
    "minbasketprice", "deliveryfee", "averagedeliveryinterval", "kitchen",
    "kitchennameids", "ratingtext", "restaurantid", "vendorid",
}


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def _get_by_keys(obj, keys):
    lower_map = {str(k).lower(): v for k, v in obj.items()}
    for key in keys:
        value = lower_map.get(key.lower())
        if value is not None:
            return value
    return None


def _parse_any_price(value):
    if value is None:
        return None
    if isinstance(value, dict):
        for key in PRICE_KEYS + ORIGINAL_PRICE_KEYS + ["value", "amount", "text"]:
            if key in value:
                parsed = _parse_any_price(value.get(key))
                if parsed is not None:
                    return parsed
        return None
    if isinstance(value, (int, float)):
        price = float(value)
        # Bazı API'ler kuruş gönderir: 24990 -> 249.90
        if price > 5000:
            price = price / 100
        return price
    return parse_price(value)


def _is_bad_name(name):
    raw = str(name or "").strip()
    normalized = normalize_text(raw)
    if len(normalized) < 3 or len(raw) > 120:
        return True
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
    if is_promo_or_code(raw):
        return True
    return False


def _is_restaurant_card(obj):
    lowered = {str(k).lower() for k in obj.keys()}
    has_restaurant_signal = bool(lowered.intersection(RESTAURANT_ONLY_KEYS))
    has_product_price = bool(lowered.intersection(
        {k.lower() for k in PRICE_KEYS}
    ))
    return has_restaurant_signal and not has_product_price


def parse_product(obj, category_name=None):
    """Tek bir dict'i ürüne çevirmeye çalışır; ürün değilse None döner."""
    if not isinstance(obj, dict):
        return None

    name = _get_by_keys(obj, NAME_KEYS)
    if _is_bad_name(name):
        return None

    if _is_restaurant_card(obj):
        return None

    price_field = _get_by_keys(obj, PRICE_KEYS)
    price = _parse_any_price(price_field)
    if price is None or price <= 0 or price > 5000:
        return None

    # Orijinal/indirimsiz fiyat: önce ürünün üst seviyesinde ara.
    original_price = _parse_any_price(_get_by_keys(obj, ORIGINAL_PRICE_KEYS))
    # Trendyol gibi API'lerde fiyat iç içe gelir: price={salePrice, marketPrice}.
    # marketPrice o dict'in İÇİNDE olduğu için üst seviyede bulunamaz; dict ise oradan al.
    if (original_price is None or original_price <= price) and isinstance(price_field, dict):
        nested_original = _parse_any_price(_get_by_keys(price_field, ORIGINAL_PRICE_KEYS))
        if nested_original is not None and nested_original > price:
            original_price = nested_original
    if original_price is None or original_price < price:
        original_price = price

    return {
        "name": str(name).strip(),
        "price": round(price, 2),
        "original_price": round(original_price, 2),
        "discount_percentage": _get_by_keys(obj, DISCOUNT_KEYS),
        "category": category_name or _get_by_keys(obj, ["category", "categoryName", "groupName"]),
        "image_url": _get_by_keys(obj, IMAGE_KEYS),
        "description": _get_by_keys(obj, DESC_KEYS),
    }


def extract_menu_items(payload):
    """Bir JSON payload'ı (ya da payload listesi) içinden ürünleri çıkarır.

    Önce kategori->ürünler yapısını dener (en güvenilir), bulamazsa generic
    ürün taraması yapar. Birebir (isim+fiyat) tekrarları eler.
    """
    payloads = payload if isinstance(payload, list) else [payload]

    items = []
    seen = set()

    def add(item):
        if not item:
            return
        key = (normalize_text(item["name"]), item["price"])
        if key in seen:
            return
        seen.add(key)
        items.append(item)

    # 1) Kategori -> ürün listesi yapısı (en temiz sinyal).
    for root in payloads:
        for obj in walk(root):
            if not isinstance(obj, dict):
                continue
            product_list = _get_by_keys(obj, PRODUCT_LIST_KEYS)
            if not isinstance(product_list, list):
                continue
            category_name = _get_by_keys(obj, ["name", "title", "categoryName"])
            for product in product_list:
                add(parse_product(product, category_name=category_name))

    # 2) Kategori yapısı bulunamadıysa generic ürün taraması.
    if not items:
        for root in payloads:
            for obj in walk(root):
                add(parse_product(obj))

    return items
