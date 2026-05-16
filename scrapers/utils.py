import re
import unicodedata
from datetime import datetime


def parse_price(price_text):
    """
    '203,92 TL', '1.250,00 TL', '239.90 TL' gibi değerleri float'a çevirir.
    Geçersiz değerlerde None döner.
    """
    if not price_text:
        return None

    text = str(price_text)
    text = text.replace("TL", "")
    text = text.replace("₺", "")
    text = text.strip()

    # Sadece sayı, nokta ve virgül bırak
    text = re.sub(r"[^0-9,\.]", "", text)

    if not text:
        return None

    # Türkçe format: 1.250,50 -> 1250.50
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        # 239.90 gibi noktalı decimal olabilir
        parts = text.split(".")
        if len(parts) > 2:
            text = "".join(parts)

    try:
        return float(text)
    except ValueError:
        return None


def calculate_discount_rate(price, original_price):
    if not price or not original_price:
        return None

    if original_price <= price:
        return None

    return round(((original_price - price) / original_price) * 100, 2)


def normalize_text(value):
    """
    Ürün eşleştirme için metni sadeleştirir.
    Örn: 'Tavuk Döner Menü' -> 'tavuk doner menu'
    """
    if not value:
        return ""

    value = value.lower().strip()

    replacements = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
    }

    for src, target in replacements.items():
        value = value.replace(src, target)

    value = unicodedata.normalize("NFKD", value)
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")