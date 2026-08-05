"""Domain-specific enum mappings and text normalization constants for Real Estate MCP."""

from typing import Any

# Property Types
PROPERTY_TYPE_MAP: dict[str, str] = {
    "can_ho": "Căn hộ",
    "biet_thu_don_lap": "Biệt thự đơn lập",
    "biet_thu_song_lap": "Biệt thự song lập",
    "biet_thu_tu_lap": "Biệt thự tự lập",
    "lien_ke": "Liền kề",
    "nha_pho": "Nhà phố",
    "shophouse": "Shophouse",
    "thuong_mai_dich_vu": "Thương mại dịch vụ",
}

# Legal Status
LEGAL_STATUS_MAP: dict[str, str] = {
    "so_do": "Sổ đỏ",
    "dat_coc": "Hợp đồng đặt cọc",
    "hdmb": "Hợp đồng mua bán",
    "thoa_thuan": "Thoả thuận",
}

# Usage Status
USAGE_STATUS_MAP: dict[str, str] = {
    "trong": "Đang để trống",
    "cho_thue": "Đang cho thuê",
    "dang_o": "Đang ở",
}

# Furnishing / Interior
FURNISHING_MAP: dict[str, str] = {
    "cao_cap": "Cao cấp",
    "co_ban": "Cơ bản",
    "co_khong_ro": "Có",
    "day_du": "Đầy đủ",
    "khong": "Không",
    "tho": "Nhà thô",
}

# Master map combining the split domain dictionaries
MASTER_ENUM_MAP: dict[str, str] = {
    **PROPERTY_TYPE_MAP,
    **LEGAL_STATUS_MAP,
    **USAGE_STATUS_MAP,
    **FURNISHING_MAP,
}


def clean_sql_enum(value: Any, mapping: dict[str, str] | None = None) -> str | None:
    """Normalize raw SQL enum string into friendly Vietnamese label.

    Returns None if value is missing/NULL so UI renders default '-' cleanly.
    """
    if value is None:
        return None
    val_str = str(value).strip()
    if not val_str or val_str.lower() in ("null", "none", "k", "-"):
        return None

    val_lower = val_str.lower()
    target_map = mapping if mapping is not None else MASTER_ENUM_MAP

    if val_lower in target_map:
        return target_map[val_lower]

    if "_" in val_str and " " not in val_str:
        return val_str.replace("_", " ").capitalize()

    return val_str


def get_province_abbreviation(province: str | None) -> str:
    """Dynamically generate province abbreviation by taking the first letter of each space-separated word.

    Examples:
        'Hà Nội' -> 'HN'
        'Hồ Chí Minh' -> 'HCM'
        'Hải Phòng' -> 'HP'
        'Hưng Yên' -> 'HY'
        'Đà Nẵng' -> 'ĐN'
        'Bình Dương' -> 'BD'
        'Thành phố Cần Thơ' -> 'CT'
    """
    import re

    if not province:
        return ""

    text = str(province).strip()
    clean_text = re.sub(r"^(tỉnh|thành phố|tp\.)\s*", "", text, flags=re.IGNORECASE).strip()
    if not clean_text:
        clean_text = text

    # Special handling for common multi-letter abbreviations
    lower_text = clean_text.lower()
    if "hồ chí minh" in lower_text:
        return "HCM"
    if "hà nội" in lower_text:
        return "HN"
    if "hải phòng" in lower_text:
        return "HP"
    if "hưng yên" in lower_text:
        return "HY"

    # Take the first letter of each space/hyphen separated word
    words = [w for w in re.split(r"[\s\-]+", clean_text) if w]
    abbr = "".join(w[0].upper() for w in words if w[0].isalpha())

    return abbr if abbr else clean_text[:3].upper()
