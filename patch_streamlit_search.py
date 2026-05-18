from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

old_safe_block = '''def safe(value):
    if value is None or pd.isna(value):
        return "-"
    return html.escape(str(value))


def filter_data(df, query, platforms, restaurants, sort_mode):
    filtered = df.copy()

    if query:
        q = normalize_text(query)
        filtered = filtered[filtered["search_text"].str.contains(q, na=False)]

    if platforms:
        filtered = filtered[filtered["platform"].isin(platforms)]

    if restaurants:
        filtered = filtered[filtered["restaurant_name"].isin(restaurants)]

    if sort_mode == "En düşük fiyat":
        filtered = filtered.sort_values("price", ascending=True)
    elif sort_mode == "En yüksek indirim":
        filtered = filtered.sort_values("discount_rate", ascending=False)
    elif sort_mode == "Platform":
        filtered = filtered.sort_values(["platform", "price"], ascending=[True, True])
    else:
        filtered = filtered.sort_values("restaurant_name", ascending=True)

    return filtered
'''

new_safe_block = '''def safe(value):
    if value is None or pd.isna(value):
        return "-"
    return html.escape(str(value))


def tokenize(value):
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


def filter_data(df, query, platforms, restaurants, sort_mode, search_scope):
    filtered = df.copy()

    if query:
        if search_scope == "Sadece ürün adı":
            filtered = filtered[
                filtered["item_name"].fillna("").apply(lambda value: smart_match(value, query))
            ]
        elif search_scope == "Sadece restoran adı":
            filtered = filtered[
                filtered["restaurant_name"].fillna("").apply(lambda value: smart_match(value, query))
            ]
        else:
            filtered = filtered[
                filtered["item_name"].fillna("").apply(lambda value: smart_match(value, query))
                | filtered["restaurant_name"].fillna("").apply(lambda value: smart_match(value, query))
                | filtered["platform"].fillna("").apply(lambda value: smart_match(value, query))
                | filtered["city"].fillna("").apply(lambda value: smart_match(value, query))
            ]

    if platforms:
        filtered = filtered[filtered["platform"].isin(platforms)]

    if restaurants:
        filtered = filtered[filtered["restaurant_name"].isin(restaurants)]

    if sort_mode == "En düşük fiyat":
        filtered = filtered.sort_values("price", ascending=True)
    elif sort_mode == "En yüksek indirim":
        filtered = filtered.sort_values("discount_rate", ascending=False)
    elif sort_mode == "Platform":
        filtered = filtered.sort_values(["platform", "price"], ascending=[True, True])
    else:
        filtered = filtered.sort_values("restaurant_name", ascending=True)

    return filtered
'''

if old_safe_block not in text:
    raise RuntimeError("Beklenen filter_data bloğu bulunamadı. streamlit_app.py değişmiş olabilir.")

text = text.replace(old_safe_block, new_safe_block)

old_sidebar_block = '''    query = st.text_input(
        "Ürün / restoran ara",
        value=default_query,
        placeholder="Örn: waffle, su, burger, bubble",
    )

    all_platforms = sorted(df["platform"].dropna().unique().tolist())
'''

new_sidebar_block = '''    query = st.text_input(
        "Ürün / restoran ara",
        value=default_query,
        placeholder="Örn: waffle, su, burger, bubble",
    )

    search_scope = st.radio(
        "Arama alanı",
        ["Sadece ürün adı", "Sadece restoran adı", "Tüm alanlar"],
        index=0,
    )

    all_platforms = sorted(df["platform"].dropna().unique().tolist())
'''

if old_sidebar_block not in text:
    raise RuntimeError("Beklenen sidebar query bloğu bulunamadı.")

text = text.replace(old_sidebar_block, new_sidebar_block)

old_call = '''filtered_df = filter_data(
    df=df,
    query=query,
    platforms=selected_platforms,
    restaurants=selected_restaurants,
    sort_mode=sort_mode,
)
'''

new_call = '''filtered_df = filter_data(
    df=df,
    query=query,
    platforms=selected_platforms,
    restaurants=selected_restaurants,
    sort_mode=sort_mode,
    search_scope=search_scope,
)
'''

if old_call not in text:
    raise RuntimeError("Beklenen filter_data çağrısı bulunamadı.")

text = text.replace(old_call, new_call)

path.write_text(text, encoding="utf-8")

print("Streamlit arama mantığı güncellendi.")
