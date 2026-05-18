from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

old = '''    df["search_text"] = (
        df["item_name"].fillna("").apply(normalize_text)
        + " "
        + df["restaurant_name"].fillna("").apply(normalize_text)
        + " "
        + df["platform"].fillna("").apply(normalize_text)
        + " "
        + df["city"].fillna("").apply(normalize_text)
    )

    return df
'''

new = '''    # Scrape sırasında sayfadan ürün yerine yanlışlıkla yakalanan UI metinlerini temizle
    bad_item_patterns = [
        "şu anda temsili restoranları görüntülemekte",
        "su anda temsili restoranlari goruntulemekte",
        "aradığınız sayfa bulunamadı",
        "anasayfaya dön",
        "cookie",
        "çerez",
    ]

    def is_bad_item_name(value):
        raw = str(value or "").lower()
        normalized = normalize_text(raw)
        return any(pattern in raw or pattern in normalized for pattern in bad_item_patterns)

    df = df[~df["item_name"].apply(is_bad_item_name)].copy()

    df["search_text"] = (
        df["item_name"].fillna("").apply(normalize_text)
        + " "
        + df["restaurant_name"].fillna("").apply(normalize_text)
        + " "
        + df["platform"].fillna("").apply(normalize_text)
        + " "
        + df["city"].fillna("").apply(normalize_text)
    )

    return df
'''

if old not in text:
    raise RuntimeError("load_data içindeki search_text bloğu bulunamadı.")

text = text.replace(old, new)

old = '''def tokenize(value):
    normalized = normalize_text(value)
    return [token for token in normalized.split() if token]


def smart_match(value, query):
    """
    Kısa aramalarda tam kelime eşleşmesi yapar.
    Örn: 'su' sadece 'su', 'su 50 cl', 'erikli su' gibi ürünleri getirir.
    'sultan', 'suadiye', 'sucuk' gibi kelimeleri getirmez.
    """
    q = normalize_text(query)
    text = normalize_text(value)

    if not q:
        return True

    query_tokens = tokenize(q)
    text_tokens = tokenize(text)

    if not query_tokens:
        return True

    # Tek ve kısa kelimelerde exact token match
    if len(query_tokens) == 1 and len(query_tokens[0]) <= 3:
        return query_tokens[0] in text_tokens

    # Çok kelimeli aramada tüm tokenlar geçsin
    if len(query_tokens) > 1:
        return all(token in text_tokens for token in query_tokens)

    # Uzun tek kelimelerde contains serbest
    return q in text
'''

new = '''def tokenize(value):
    normalized = normalize_text(value)
    return [token for token in normalized.split() if token]


def raw_tokenize(value):
    import re
    raw = str(value or "").lower()
    return re.findall(r"[a-zçğıöşü0-9]+", raw)


def smart_match(value, query):
    """
    Kısa aramalarda tam kelime eşleşmesi yapar.
    'su' aramasında 'şu', 'sultan', 'suadiye', 'sucuk' gelmez.
    Ayrıca demo için 'su böreği' gibi yemekleri içme suyu aramasından ayırır.
    """
    raw_query = str(query or "").lower().strip()
    raw_value = str(value or "").lower().strip()

    q = normalize_text(query)
    text = normalize_text(value)

    if not q:
        return True

    query_tokens = tokenize(q)
    text_tokens = tokenize(text)
    raw_query_tokens = raw_tokenize(raw_query)
    raw_value_tokens = raw_tokenize(raw_value)

    if not query_tokens:
        return True

    # Özel demo durumu: "su" araması içme suyu ürünlerini getirsin
    if raw_query == "su":
        if "su" not in raw_value_tokens:
            return False

        excluded_food_words = [
            "böreği",
            "börek",
            "boregi",
            "borek",
            "sucuk",
            "sulu",
        ]

        if any(word in raw_value or word in text for word in excluded_food_words):
            return False

        return True

    # Tek ve kısa kelimelerde önce ham token eşleşmesi kullan.
    # Böylece 'su' ile 'şu' eşleşmez.
    if len(raw_query_tokens) == 1 and len(raw_query_tokens[0]) <= 3:
        return raw_query_tokens[0] in raw_value_tokens

    # Çok kelimeli aramada tüm tokenlar geçsin
    if len(query_tokens) > 1:
        return all(token in text_tokens for token in query_tokens)

    # Uzun tek kelimelerde contains serbest
    return q in text
'''

if old not in text:
    raise RuntimeError("smart_match bloğu bulunamadı.")

text = text.replace(old, new)

path.write_text(text, encoding="utf-8")
print("Streamlit arama ve hatalı ürün filtresi güncellendi.")
