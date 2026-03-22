from app.core.enums import SocialStatus


def parse_german_price(raw: str) -> float | None:
    text = raw.replace("€", "").replace("EUR", "").strip()
    if not text:
        return None

    price_part = text.split()[0]
    clean_price = price_part.replace(".", "").replace(",", ".")
    filtered = "".join(c for c in clean_price if c.isdigit() or c == ".")

    try:
        return float(filtered) if filtered else None
    except ValueError:
        return None


def parse_german_sqm(raw: str) -> float | None:
    text = raw.replace("m²", " m²").replace("qm", " qm").strip()
    parts = text.split()

    for i, part in enumerate(parts):
        if any(marker in part.lower() for marker in ["m²", "qm", "meter"]) and i > 0:
            num_part = parts[i - 1].replace(",", ".")
            filtered = "".join(c for c in num_part if c.isdigit() or c == ".")
            try:
                return float(filtered)
            except ValueError:
                continue
    return None


def parse_german_room_count(raw: str) -> int | None:
    text = raw.lower().replace("zi.", "zimmer").replace("zi", "zimmer").strip()
    parts = text.split()

    for i, part in enumerate(parts):
        if "zimmer" in part:
            num_str = part.replace("zimmer", "")
            if not num_str and i > 0:
                num_str = parts[i - 1]

            num_str = num_str.replace(",", ".")
            filtered = "".join(c for c in num_str if c.isdigit() or c == ".")
            try:
                return int(float(filtered))
            except ValueError:
                continue

    filtered_all = "".join(c if c.isdigit() or c == "." else " " for c in raw).split()
    if filtered_all:
        try:
            return int(float(filtered_all[0]))
        except ValueError:
            pass

    return None


def detect_social_housing_status(text: str) -> SocialStatus:
    low = text.lower()
    wbs_keywords = [
        "wbs",
        "wohnberechtigungsschein",
        "sozialwohnung",
        "sozialer wohnungsbau",
        "geförder",
        "öffentlich gefördert",
    ]
    if any(kw in low for kw in wbs_keywords):
        return SocialStatus.WBS
    return SocialStatus.MARKET
