import os
import re
import math
import difflib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple, TypedDict, Mapping
import chromadb
from chromadb.api.types import Metadata

from app.core.config import settings, BASE_DIR
from app.core.database import get_db_connection

logger = logging.getLogger(__name__)


# ==============================================================================
# DOMAIN DICTIONARY & OUT-OF-DOMAIN INTENT PATTERNS
# ==============================================================================

CATEGORY_KEYWORDS = {
    "Âm thanh & Tai nghe": [
        "tai nghe", "headphone", "earphone", "earbuds", "loa", "speaker", "sound", "micro", "mic",
        "âm thanh", "bluetooth", "retrosound", "chống ồn", "anc", "studio", "thu âm", "hifi", "tws"
    ],
    "Chuột & Bàn phím": [
        "chuột", "mouse", "bàn phím", "keyboard", "phím cơ", "typewriter", "lót chuột", "pad", "bàn di",
        "công thái học", "silent", "không dây", "slim", "quang"
    ],
    "Gia dụng thông minh": [
        "đèn", "lamp", "chống cận", "edison", "khuếch tán", "tinh dầu", "đồng hồ", "nixie", "clock",
        "cân", "scale", "quạt", "fan", "turbine"
    ],
    "Phụ kiện & Dây cáp": [
        "sạc", "charger", "cáp", "cable", "hub", "type-c", "hdmi", "pin", "dự phòng", "powerbank",
        "giá đỡ", "stand", "cyberpunk"
    ],
    "Gaming Gear": [
        "gaming", "game", "chơi game", "7.1", "bass", "siêu nhẹ", "tay cầm", "controller",
        "hall effect", "tản nhiệt", "cooler"
    ]
}

OUT_OF_DOMAIN_PATTERNS = [
    # Food & Beverage
    r"\b(phở|bún|cơm|bánh|pizza|trái cây|hoa quả|thức ăn|đồ ăn|nước uống|cafe|cà phê|trà sữa|trà|thịt|gà)\b",
    # Travel & Hospitality
    r"\b(vé máy bay|hãng hàng không|chuyến bay|khách sạn|du lịch|tour du lịch|resort)\b",
    # Weather & General Life
    r"\b(thời tiết|dự báo thời tiết|trời mưa|nhiệt độ hôm nay|bão)\b",
    # Non-catalog heavy appliances / vehicles / fashion
    r"\b(tivi|tv|máy giặt|tủ lạnh|máy sấy|máy lạnh|điều hòa|xe máy|ô tô|xe đạp|quần áo|giày dép|áo phông|áo thun|quần jean|váy|đầm)\b",
]

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous\s+)?instructions",
    r"forget\s+(all\s+)?(previous\s+)?instructions",
    r"bỏ\s+qua\s+(hướng\s+dẫn|câu\s+lệnh|chỉ\s+dẫn)",
    r"quên\s+(hết\s+)?(chỉ\s+dẫn|hướng\s+dẫn)",
    r"(reveal|show|tiết\s+lộ)\s+(system\s+prompt|prompt)",
    r"system\s+prompt",
    r"api\s*key",
    r"gemini_api_key",
    r"secret\s*key",
    r"act\s+as\s+(admin|superadmin)",
    r"you\s+are\s+now\s+(admin|superadmin)",
    r"cost_price",
    r"giá\s+vốn",
    r"lợi\s+nhuận"
]


# ==============================================================================
# QUERY UNDERSTANDING, BUDGET EXTRACTION & ELIGIBILITY VERIFIERS
# ==============================================================================

def extract_budget_from_query(query: str) -> Optional[float]:
    """
    Extracts explicit maximum budget constraint from natural language query in VND.
    Supports formats like:
      - dưới 700.000đ, dưới 700k, < 700k, <= 700000
      - tầm 700k đổ lại, tối đa 1.5 triệu, không quá 1tr5
      - giá dưới 500.000 VNĐ
    """
    q = query.lower()

    # Pattern 0a: Textual spoken numbers (e.g. hai triệu rưỡi, hai trăm nghìn, tầm ba trăm)
    vn_text_num = {
        "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5,
        "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "mười": 10
    }
    for word, digit in vn_text_num.items():
        if f"{word} trăm nghìn" in q or f"{word} trăm ngàn" in q or f"{word} trăm k" in q:
            return float(digit * 100_000)
        if f"{word} triệu rưỡi" in q:
            return float(digit * 1_000_000 + 500_000)
        if f"{word} triệu" in q:
            return float(digit * 1_000_000)
        # Colloquial spoken Vietnamese without 'nghìn' (e.g. tầm ba trăm, giá hai trăm, dưới năm trăm)
        if re.search(rf"(?:tầm|khoảng|giá|dưới|không quá|tối đa|cỡ)\s+{word}\s+trăm(?!\s+(?:nghìn|ngàn|k|đồng|đ))", q):
            return float(digit * 100_000)

    # Pattern 0b: Standalone fractional / Spoken natural Vietnamese numbers (e.g. nửa triệu, triệu rưỡi, nửa củ)
    if re.search(r"\b(nửa triệu|nửa tr|nửa củ)\b", q):
        return 500000.0
    if re.search(r"\b(triệu rưỡi|1 triệu rưỡi|1tr5|1 tr 5)\b", q):
        return 1500000.0

    # Pattern 0c: Vietnamese slang currency units (củ = triệu, cành = nghìn, lốp/xị = trăm nghìn)
    m_cu_minor = re.search(r"(?:dưới|<|<=|tối đa|không quá|tầm|khoảng|giá|còn)?\s*(\d+)\s*củ\s*(\d+)", q)
    if m_cu_minor:
        major = int(m_cu_minor.group(1))
        minor = int(m_cu_minor.group(2))
        minor_val = minor * 100_000 if minor < 10 else minor * 10_000
        return float(major * 1_000_000 + minor_val)

    m_cu_ruoi = re.search(r"(?:dưới|<|<=|tối đa|không quá|tầm|khoảng|giá|còn)?\s*(\d+)\s*(?:củ|lốp)\s*rưỡi", q)
    if m_cu_ruoi:
        return float(int(m_cu_ruoi.group(1)) * 1_000_000 + 500_000)
    m_cu = re.search(r"(?:dưới|<|<=|tối đa|không quá|tầm|khoảng|giá|còn)?\s*(\d+)\s*củ", q)
    if m_cu:
        return float(int(m_cu.group(1)) * 1_000_000)
    m_xi = re.search(r"(?:dưới|<|<=|tối đa|không quá|tầm|khoảng|giá|còn)?\s*(\d+)\s*xị", q)
    if m_xi:
        return float(int(m_xi.group(1)) * 100_000)
    m_canh = re.search(r"(?:dưới|<|<=|tối đa|không quá|tầm|khoảng|giá|còn)?\s*(\d+)\s*cành", q)
    if m_canh:
        return float(int(m_canh.group(1)) * 1_000)

    # Pattern 1: X tr Y (e.g. 1tr5, 2tr2)
    m = re.search(r"(?:dưới|<|<=|tối đa|không quá|tầm|khoảng|giá)?\s*(\d+)\s*(?:tr|triệu)\s*(\d+)", q)
    if m:
        major = int(m.group(1))
        minor = int(m.group(2))
        if minor < 10:
            val = major * 1_000_000 + minor * 100_000
        else:
            val = major * 1_000_000 + minor * 10_000
        return float(val)

    # Pattern 2: (indicators) number (unit) or number (unit) (range indicators)
    budget_pattern = re.compile(
        r"(?:dưới|nhỏ hơn|<=|<|tối đa|không quá|tầm|khoảng|mức giá|ngân sách|giá)\s*"
        r"(\d+(?:[.,]\d+)*)\s*"
        r"(k|tr|triệu|nghìn|ngàn|đ|vnđ|vnd|đồng)?"
        r"|(?:^|\s)(\d+(?:[.,]\d+)*)\s*"
        r"(k|tr|triệu|nghìn|ngàn|đ|vnđ|vnd|đồng)\s*"
        r"(?:đổ lại|trở xuống|quay đầu|trở lại)?"
        r"|(?:^|\s)(\d+(?:[.,]\d+)*)\s*"
        r"(?:đổ lại|trở xuống|quay đầu|trở lại)",
        re.IGNORECASE
    )

    for match in budget_pattern.finditer(q):
        raw_num = match.group(1) or match.group(3) or match.group(5)
        raw_unit = (match.group(2) or match.group(4) or "").lower()

        if not raw_num:
            continue

        # If formatted with thousands separators (e.g. 6.000.000 or 700.000)
        if re.search(r"\d{1,3}(?:[.,]\d{3})+", raw_num):
            clean_digits = re.sub(r"[^\d]", "", raw_num)
            num = float(clean_digits)
        else:
            raw_num_clean = raw_num.replace(",", ".").strip()
            try:
                num = float(raw_num_clean)
            except ValueError:
                continue

        orig_match = match.group(0)

        if raw_unit in ("k", "nghìn", "ngàn"):
            return num * 1_000
        elif raw_unit in ("tr", "triệu"):
            return num * 1_000_000
        elif raw_unit in ("đ", "vnđ", "vnd", "đồng"):
            if re.search(r"\d{1,3}[.,]\d{3}(?:[.,]\d{3})?", orig_match):
                clean_int = re.sub(r"[^\d]", "", orig_match)
                if clean_int:
                    return float(clean_int)
            if num < 1000 and "k" not in orig_match:
                return num * 1_000
            return num
        else:
            if re.search(r"\d{1,3}[.,]\d{3}(?:[.,]\d{3})?", orig_match):
                clean_int = re.sub(r"[^\d]", "", orig_match)
                if clean_int:
                    return float(clean_int)
            if num >= 10_000:
                return num
            elif num >= 10 and num < 10_000:
                return num * 1_000

    return None


def resolve_effective_budget(query: str, budget_input: Optional[float]) -> Optional[float]:
    """
    Combines budget from query and budget from input field strictly.
    When both are present, takes the minimum constraint to avoid accidental budget inflation.
    """
    q_budget = extract_budget_from_query(query)
    in_budget = budget_input if budget_input is not None and budget_input > 0 else None

    if q_budget is not None and in_budget is not None:
        return min(q_budget, in_budget)
    elif q_budget is not None:
        return q_budget
    elif in_budget is not None:
        return in_budget
    return None


# ==============================================================================
# BRAND RECOGNITION & ALIAS MAPPING
# ==============================================================================

class BrandInfo(TypedDict):
    canonical_name: str
    aliases: List[str]


BRAND_DICTIONARY: Dict[str, BrandInfo] = {
    "apple": {
        "canonical_name": "Apple",
        "aliases": [
            "sản phẩm hãng táo", "sản phẩm táo", "sản phẩm của táo",
            "sản phẩm apple", "sản phẩm của apple", "hàng apple", "đồ apple", "đồ của apple",
            "hãng táo", "nhà táo", "táo khuyết", "đồ táo", "hàng táo",
            "apple", "iphone", "ipad", "macbook", "airpods"
        ]
    },
    "sony": {
        "canonical_name": "Sony",
        "aliases": [
            "sản phẩm sony", "sản phẩm của sony", "hàng sony", "đồ sony", "đồ của sony",
            "hãng sony", "nhà sony", "sony", "playstation", "wh-1000x"
        ]
    },
    "logitech": {
        "canonical_name": "Logitech",
        "aliases": [
            "sản phẩm logitech", "sản phẩm của logitech", "hàng logitech", "đồ logitech", "đồ của logitech",
            "hãng logitech", "nhà logitech", "logitech", "logi"
        ]
    },
    "samsung": {
        "canonical_name": "Samsung",
        "aliases": ["samsung", "sam sung", "hãng samsung", "galaxy"]
    },
    "razer": {
        "canonical_name": "Razer",
        "aliases": ["razer", "hãng razer", "đồ razer"]
    },
    "corsair": {
        "canonical_name": "Corsair",
        "aliases": ["corsair", "hãng corsair"]
    },
    "keychron": {
        "canonical_name": "Keychron",
        "aliases": ["keychron", "hãng keychron"]
    },
    "moondrop": {
        "canonical_name": "Moondrop",
        "aliases": ["moondrop", "hãng moondrop"]
    },
    "retrosound": {
        "canonical_name": "RetroSound",
        "aliases": ["retrosound", "retro sound", "hãng retrosound"]
    },
    "asus": {
        "canonical_name": "Asus",
        "aliases": ["asus", "hãng asus", "rog"]
    },
    "xiaomi": {
        "canonical_name": "Xiaomi",
        "aliases": ["xiaomi", "hãng xiaomi"]
    },
    "anker": {
        "canonical_name": "Anker",
        "aliases": ["anker", "hãng anker", "soundcore"]
    },
    "steelseries": {
        "canonical_name": "SteelSeries",
        "aliases": ["steelseries", "steel series"]
    },
    "edifier": {
        "canonical_name": "Edifier",
        "aliases": ["edifier", "hãng edifier"]
    },
    "akko": {
        "canonical_name": "Akko",
        "aliases": ["akko", "hãng akko"]
    }
}


def extract_brand_from_query(query: str) -> Optional[Dict[str, Any]]:
    """
    Extracts brand intent from natural language query.
    Supports brand aliases (e.g. 'hãng táo', 'táo khuyết' -> Apple).
    Also detects any explicit brand patterns (e.g. 'hãng X', 'thương hiệu Y', 'nhãn hiệu Z')
    even if the brand is not currently in the catalog.
    """
    q_lower = query.lower()
    for brand_key, info in BRAND_DICTIONARY.items():
        sorted_aliases: List[str] = sorted(info["aliases"], key=len, reverse=True)
        for alias in sorted_aliases:
            if not isinstance(alias, str):
                continue
            pattern = rf"(?:^|\W){re.escape(alias)}(?:$|\W)"
            if re.search(pattern, q_lower):
                return {
                    "brand_key": brand_key,
                    "canonical_name": info["canonical_name"]
                }

    # Explicit brand mention: 'hãng X', 'thương hiệu X', 'nhãn hiệu X', 'nhà X'
    explicit_match = re.search(r"\b(?:hãng|thương hiệu|nhãn hiệu|nhà)\s+([A-Za-z0-9\-]+)\b", query, re.IGNORECASE)
    if explicit_match:
        extracted = explicit_match.group(1).strip()
        skip_words = {"này", "đó", "nào", "sản", "phẩm", "tai", "chuột", "bàn", "phím", "loa", "đồ", "gì", "tốt"}
        if extracted.lower() not in skip_words:
            return {
                "brand_key": extracted.lower(),
                "canonical_name": extracted.title()
            }

    # Brand preceding 'chính hãng' (e.g. 'Sennheiser chính hãng')
    chinh_hang_match = re.search(r"\b([A-Z][a-zA-Z0-9\-]+)\s+chính hãng\b", query)
    if chinh_hang_match:
        extracted = chinh_hang_match.group(1).strip()
        skip_words = {"đồ", "hàng", "sản", "phẩm", "tai", "chuột", "bàn", "phím", "loa", "loại", "mua", "bán"}
        if extracted.lower() not in skip_words:
            return {
                "brand_key": extracted.lower(),
                "canonical_name": extracted.title()
            }

    return None


def match_product_brand(product: Dict[str, Any], brand_info: Dict[str, Any]) -> bool:
    """
    Verifies if a catalog product actually belongs to the given brand.
    Prioritizes brand name appearing in product name or explicit brand declaration in description.
    """
    brand_key = brand_info["brand_key"]
    canonical = brand_info["canonical_name"].lower()

    name_str = (product.get("name") or "").lower()
    desc_str = (product.get("description") or "").lower()

    # 1. Primary check: Brand name appears as distinct word in product name
    for b in [canonical, brand_key]:
        if re.search(r"\b" + re.escape(b) + r"\b", name_str):
            return True

    # 2. Explicit brand declaration in description
    for b in [canonical, brand_key]:
        brand_decl_patterns = [
            rf"\b(?:thương hiệu|hãng)\s*[:\-]?\s*{re.escape(b)}\b",
            rf"\bdo\s+{re.escape(b)}\s+(?:phát triển|sản xuất|chế tạo)\b",
            rf"\bchính hãng\s+{re.escape(b)}\b",
        ]
        if any(re.search(p, desc_str) for p in brand_decl_patterns):
            return True

    return False


def is_approximate_budget_query(query: str) -> bool:
    """Detects if query specifies an approximate/soft budget target (e.g. 'khoảng', 'tầm') rather than strict upper bound."""
    q = query.lower()
    has_approx = bool(re.search(r"\b(khoảng|tầm|xung quanh|cỡ|độ chừng)\b", q))
    has_strict_max = bool(re.search(r"\b(dưới|đừng quá|không quá|tối đa|nhỏ hơn|<=|<|đổ lại|quay đầu)\b", q))
    return has_approx and not has_strict_max


def parse_query_requirements(query: str) -> Dict[str, Any]:
    """
    Extracts structured query requirements: brand, target product type,
    desired functional capabilities, device compatibility, user host device, and mandatory attributes.
    """
    brand = extract_brand_from_query(query)
    q_lower = query.lower()

    target_type = None
    if any(k in q_lower for k in ["lót chuột", "tấm lót chuột", "bàn di chuột", "pad chuột", "mouse pad", "lót bàn phím"]):
        target_type = "mousepad"
    elif any(k in q_lower for k in ["hub", "chuyển đổi", "đầu chuyển", "cáp chuyển", "adapter", "dock"]):
        target_type = "hub_adapter"
    elif any(k in q_lower for k in ["dây sạc", "cáp sạc", "dây cáp"]):
        target_type = "cable"
    elif any(k in q_lower for k in ["củ sạc", "cốc sạc"]):
        target_type = "charger"
    elif any(k in q_lower for k in ["tản nhiệt", "đế tản nhiệt", "quạt tản nhiệt", "cooler"]):
        target_type = "cooler"
    elif any(k in q_lower for k in ["pin dự phòng", "sạc dự phòng", "powerbank"]):
        target_type = "powerbank"
    elif any(k in q_lower for k in ["giá đỡ", "chân đế", "kê laptop"]):
        target_type = "stand"
    elif any(k in q_lower for k in ["chuột", "mouse"]) and not any(k in q_lower for k in ["lót chuột", "bàn di chuột", "pad chuột", "cắm chuột", "hình chuột", "dây cáp", "cáp sạc", "hub", "chuyển đổi"]):
        target_type = "mouse"
    elif any(k in q_lower for k in ["bàn phím", "keyboard", "phím cơ", "bàn phím cơ", "gõ văn bản", "đánh máy", "gõ máy tính", "gõ code", "soạn thảo", "đồ để gõ"]) and not any(k in q_lower for k in ["lót bàn phím", "cắm phím", "pad chuột", "lót chuột", "bàn di"]):
        target_type = "keyboard"
    elif any(k in q_lower for k in ["tai nghe", "headphone", "earphone", "earbuds", "tws"]):
        target_type = "headphone"
    elif any(k in q_lower for k in ["loa", "speaker", "soundbar"]):
        target_type = "speaker"
    elif any(k in q_lower for k in ["tay cầm", "gamepad", "controller"]):
        target_type = "gamepad"
    elif any(k in q_lower for k in ["đèn", "đồng hồ", "quạt", "cân", "tinh dầu"]) and not any(k in q_lower for k in ["quạt tản nhiệt"]):
        target_type = "smarthome"

    # Desired Capabilities Extraction
    desired_capabilities = []
    if any(k in q_lower for k in ["xuất hình", "ra màn", "chiếu màn", "màn hdmi", "màn hình phụ", "cổng hdmi"]):
        desired_capabilities.append("xuất hình HDMI")
    if any(k in q_lower for k in ["sạc nhanh", "pd", "gan", "công suất lớn"]):
        desired_capabilities.append("sạc nhanh")
    if any(k in q_lower for k in ["pin dự phòng", "sạc dự phòng", "powerbank"]):
        desired_capabilities.append("pin sạc dự phòng")
    if any(k in q_lower for k in ["giá đỡ", "chân đế", "kê laptop", "nâng máy"]):
        desired_capabilities.append("giá đỡ laptop")
    if any(k in q_lower for k in ["tản nhiệt", "làm mát", "hạ nhiệt", "nóng ran máy", "nóng máy"]):
        desired_capabilities.append("tản nhiệt làm mát")
    if any(k in q_lower for k in ["nghe nhạc", "âm thanh", "thu âm", "hifi"]):
        desired_capabilities.append("nghe nhạc âm thanh")
    if any(k in q_lower for k in ["cắm mạng", "mạng dây", "lan", "ethernet"]):
        desired_capabilities.append("cắm mạng LAN")

    # Dynamic integrated / special capability extraction (e.g. tích hợp máy đo huyết áp, có màn hình led)
    m_integrated = re.search(r"\b(?:tích hợp|kèm theo|tích hợp thêm|có kèm|có chức năng|tính năng)\s+([^,.;!?]+)", q_lower)
    if m_integrated:
        cap_val = m_integrated.group(1).strip()
        common_traits = {"bluetooth", "pin sạc", "led", "rgb", "không dây", "có dây"}
        if cap_val and len(cap_val) >= 3 and cap_val not in common_traits:
            desired_capabilities.append(cap_val)

    # Device Compatibility Extraction
    device_compatibility = []
    if "hdmi" in q_lower:
        device_compatibility.append("HDMI")
    if re.search(r"\b(type-c|type c|usb-c)\b", q_lower):
        device_compatibility.append("Type-C")
    if re.search(r"\b(bluetooth)\b", q_lower):
        device_compatibility.append("Bluetooth")
    if re.search(r"\b(usb-a|usb 3|cổng usb|chuột usb)\b", q_lower):
        device_compatibility.append("USB-A")
    if re.search(r"\b(lan|rj45|ethernet|mạng dây)\b", q_lower):
        device_compatibility.append("LAN")

    # Host Device Owned by User
    user_device = None
    if re.search(r"\b(macbook|macbook air|macbook pro)\b", q_lower):
        user_device = "macbook"
    elif re.search(r"\b(laptop|máy tính xách tay)\b", q_lower):
        user_device = "laptop"
    elif re.search(r"\b(ipad|tablet|máy tính bảng)\b", q_lower):
        user_device = "ipad"
    elif re.search(r"\b(iphone|điện thoại|smartphone)\b", q_lower):
        user_device = "phone"
    elif re.search(r"\b(pc|máy bàn|máy tính để bàn)\b", q_lower):
        user_device = "PC"

    # Decouple owned host device brand from accessory search
    if user_device and brand:
        b_name = brand["canonical_name"].lower()
        host_device_pattern = rf"\b(?:điện thoại|laptop|máy tính|máy bàn|pc|ipad|tablet)\s+(?:[A-Za-z0-9\-]+\s+)*{re.escape(b_name)}\b"
        if re.search(host_device_pattern, q_lower):
            accessory_brand_pattern = rf"\b(?:sạc|tai nghe|phím|chuột|hub|cáp|củ sạc|đồ|hàng|hãng|thương hiệu)\s+(?:của\s+)?{re.escape(b_name)}\b"
            if not re.search(accessory_brand_pattern, q_lower):
                brand = None

    is_gaming = bool(re.search(r"\b(gaming|game|chơi game|esport)\b", q_lower))

    # Robust Negation Handling for Wired vs Wireless
    has_wireless_neg = bool(re.search(r"\b(không (?:dùng|cần|muốn|thích)?\s*(?:bluetooth|không dây|wireless))\b", q_lower)) or bool(re.search(r"\b(không\s*dây\s*lằng\s*nhằng)\b", q_lower))
    has_wired_neg = bool(re.search(r"\b(không (?:dùng|cần|muốn|thích)?\s*(?:loại\s*)?(?:có dây|dây cáp|dây lằng nhằng))\b", q_lower)) or bool(re.search(r"\b(không cần dây|không dùng dây|không có dây)\b", q_lower))

    if has_wireless_neg:
        is_wireless = False
        is_wired = True
    elif has_wired_neg:
        is_wireless = True
        is_wired = False
    else:
        is_wireless = bool(re.search(r"\b(không cần dây|không dùng dây|không có dây|không dây|wireless|bluetooth|tws|pin sạc)\b", q_lower))
        is_wired = bool(re.search(r"\b(có dây|cắm dây|wired|dây cắm usb)\b", q_lower)) and not is_wireless

    is_mechanical = bool(re.search(r"\b(phím cơ|bàn phím cơ|switch cơ|cơ)\b", q_lower)) if target_type == "keyboard" else False
    is_silent = bool(re.search(r"\b(silent|êm|yên tĩnh|chống ồn click|không tiếng click|không tiếng|không kêu|không ồn|không ồn ào|không lách cách|bấm êm)\b", q_lower))
    is_anc = bool(re.search(r"\b(chống ồn|anc|noise cancel|khử ồn)\b", q_lower)) and not bool(re.search(r"\b(chống ồn click)\b", q_lower))
    is_ergonomic = bool(re.search(r"\b(công thái học|ergonomic|chống mỏi)\b", q_lower))
    neg_constraints = []
    if has_wired_neg:
        neg_constraints.append("wired")
    if has_wireless_neg:
        neg_constraints.append("wireless")

    return {
        "brand": brand,
        "target_type": target_type,
        "desired_capabilities": desired_capabilities,
        "device_compatibility": device_compatibility,
        "user_device": user_device,
        "query": query,
        "is_gaming": is_gaming,
        "is_wireless": is_wireless,
        "is_wired": is_wired,
        "is_mechanical": is_mechanical,
        "is_silent": is_silent,
        "is_anc": is_anc,
        "is_ergonomic": is_ergonomic,
        "negative_constraints": neg_constraints,
    }


def classify_product_type(p: Dict[str, Any]) -> str:
    """Classifies catalog product into device types to prevent accessories from masquerading as devices."""
    name_lower = (p.get("name") or "").lower()
    cat_lower = (p.get("category_name") or "").lower()

    if any(k in name_lower for k in ["lót chuột", "tấm lót chuột", "bàn di chuột", "pad chuột"]):
        return "mousepad"
    if any(k in name_lower for k in ["chuột", "mouse"]) and not any(k in name_lower for k in ["lót chuột", "bàn di chuột", "pad chuột"]):
        return "mouse"
    if any(k in name_lower for k in ["bàn phím", "keyboard", "phím cơ"]):
        return "keyboard"
    if any(k in name_lower for k in ["tai nghe", "headphone", "earphone", "earbuds", "tws"]):
        return "headphone"
    if any(k in name_lower for k in ["loa", "speaker"]):
        return "speaker"
    if any(k in name_lower for k in ["tay cầm", "gamepad", "controller"]):
        return "gamepad"
    if any(k in name_lower for k in ["tản nhiệt", "đế tản nhiệt", "cooler"]):
        return "cooler"
    if any(k in name_lower for k in ["hub", "chuyển đổi", "adapter", "dock"]):
        return "hub_adapter"
    if any(k in name_lower for k in ["củ sạc", "cốc sạc"]):
        return "charger"
    if any(k in name_lower for k in ["dây cáp", "cáp sạc", "cáp"]):
        return "cable"
    if any(k in name_lower for k in ["pin sạc dự phòng", "pin dự phòng", "powerbank"]):
        return "powerbank"
    if any(k in name_lower for k in ["giá đỡ", "stand", "chân đế"]):
        return "stand"
    if any(k in name_lower for k in ["đèn", "đồng hồ", "cân", "quạt"]):
        return "smarthome"

    if "chuột" in cat_lower and "phím" not in name_lower:
        return "mouse"
    if "bàn phím" in cat_lower and "chuột" not in name_lower:
        return "keyboard"
    if "âm thanh" in cat_lower or "tai nghe" in cat_lower:
        return "headphone"
    if "phụ kiện" in cat_lower:
        return "charger_cable"
    return "other"


def check_product_eligibility(
    product: Dict[str, Any],
    reqs: Dict[str, Any],
    budget_max: Optional[float]
) -> Tuple[bool, Optional[str]]:
    """
    Validates if a candidate product is fully eligible for recommendation based on:
    1. Active status & stock > 0 in SQLite.
    2. Budget constraint (price <= budget_max).
    3. Brand match (if brand requested).
    4. Target product type match (if user explicitly requested a specific product type).
    5. Functional capability & compatibility evidence verified in SQLite record.
    6. Feature attributes (gaming, wireless, wired, mechanical, silent, anc, ergonomic).
    Returns (is_eligible, ineligibility_reason).
    """
    if product.get("status") != "active":
        return False, "Sản phẩm đã ngừng kinh doanh"
    if product.get("stock_quantity", 0) <= 0:
        return False, "Sản phẩm tạm thời hết hàng (tồn kho: 0)"

    # Brand filter: product must belong to requested brand if specified
    brand_req = reqs.get("brand")
    if brand_req:
        if not match_product_brand(product, brand_req):
            return False, f"Khác thương hiệu yêu cầu ({brand_req['canonical_name'].title()})"

    # Target product type filter: ONLY enforced if user explicitly named a product type
    target_type = reqs.get("target_type")
    prod_type = classify_product_type(product)
    if target_type and target_type not in ("other", "accessory"):
        primary_devices = {"mouse", "keyboard", "headphone", "speaker", "gamepad", "cooler", "mousepad"}
        if target_type in primary_devices:
            if prod_type != target_type:
                return False, f"Không đúng loại sản phẩm yêu cầu ({prod_type} khác {target_type})"
        elif target_type in ("hub_adapter", "charger", "cable", "powerbank", "stand"):
            if target_type == "hub_adapter" and prod_type not in ("hub_adapter", "charger_cable"):
                return False, f"Không phải hub chuyển đổi ({prod_type})"
            elif target_type == "powerbank" and prod_type not in ("powerbank", "charger_cable"):
                return False, f"Không phải pin sạc dự phòng ({prod_type})"
            elif target_type == "stand" and prod_type not in ("stand", "charger_cable"):
                return False, f"Không phải giá đỡ ({prod_type})"
            elif target_type == "charger" and prod_type != "charger":
                return False, f"Không phải củ sạc ({prod_type})"
            elif target_type == "cable" and prod_type != "cable":
                return False, f"Không phải dây cáp ({prod_type})"

    name_str = (product.get("name") or "").lower()
    cat_str = (product.get("category_name") or "").lower()
    desc_str = (product.get("description") or "").lower()
    full_info = f"{name_str} {cat_str} {desc_str}"
    query_str = (reqs.get("query") or "").lower()

    # When target_type is not explicitly defined, guard against completely mismatched categories
    if not target_type:
        if any(k in query_str for k in ["gõ văn bản", "đánh máy", "gõ máy tính", "gõ code", "soạn thảo", "đồ để gõ"]):
            if prod_type != "keyboard":
                return False, f"Không phải thiết bị phục vụ gõ văn bản/đánh máy ({prod_type})"
        elif any(k in query_str for k in ["nghe nhạc", "âm thanh", "tai nghe", "loa"]) and not any(k in query_str for k in ["chuột", "phím", "hub", "sạc"]):
            if prod_type not in ("headphone", "speaker"):
                return False, f"Không phải thiết bị phục vụ nghe nhìn/âm thanh ({prod_type})"

    # Battery constraint verification (e.g. pin tiểu AA / AAA vs pin sạc)
    forbids_aa_battery = bool(re.search(r"\b(không (?:dùng|cần|chơi|xài|muốn)?\s*(?:loại\s*)?(?:pin tiểu|pin aa|pin aaa|pin rời)|tuyệt đối không (?:dùng|chơi|xài)?\s*pin tiểu)\b", query_str))
    needs_aa_battery = bool(re.search(r"\b(pin tiểu|pin aa|pin aaa)\b", query_str)) and not forbids_aa_battery

    if forbids_aa_battery and any(k in full_info for k in ["pin tiểu", "pin aa", "pin aaa", "1x aa", "2x aa"]):
        return False, "Sử dụng pin tiểu AA/AAA, vi phạm điều kiện loại trừ của khách hàng"
    if needs_aa_battery and not any(k in full_info for k in ["pin tiểu", "pin aa", "pin aaa", "1x aa", "2x aa"]):
        return False, "Không dùng pin tiểu AA/AAA theo yêu cầu"

    # Functional Capability & Compatibility Evidence Checks
    compat_list = reqs.get("device_compatibility") or []
    # If HDMI connection is explicitly required:
    needs_hdmi = any("hdmi" in c.lower() for c in compat_list) or ("hdmi" in query_str and any(k in query_str for k in ["xuất hình", "ra màn", "cổng hdmi", "màn hình", "màn"]))
    if needs_hdmi:
        if "hdmi" not in full_info:
            return False, "Không hỗ trợ cổng xuất hình HDMI"

    # If Type-C connection is explicitly required:
    needs_type_c = any("type-c" in c.lower() or "usb-c" in c.lower() for c in compat_list)
    if needs_type_c and any(k in query_str for k in ["cổng type-c", "cổng usb-c", "toàn cổng type-c", "chân type-c", "đầu type-c"]):
        if not re.search(r"\b(type-c|type c|usb-c)\b", full_info):
            return False, "Không hỗ trợ kết nối qua cổng Type-C"

    # Desired Capabilities verification:
    caps = reqs.get("desired_capabilities") or []
    needs_video_out = any(k in c.lower() for c in caps for k in ["xuất hình", "ra màn", "chiếu màn", "màn hình"]) or any(k in query_str for k in ["xuất hình", "ra màn", "chiếu màn hình", "nối ra màn"])
    if needs_video_out:
        if not any(k in full_info for k in ["hdmi", "xuất hình", "màn hình", "4k", "displayport", "vga"]):
            return False, "Không hỗ trợ chức năng xuất hình ra màn hình ngoài"

    needs_fast_charge = any(k in c.lower() for c in caps for k in ["sạc nhanh", "công suất cao", "pd"]) or any(k in query_str for k in ["sạc nhanh", "công suất lớn", "sạc 65w", "sạc 100w"])
    if needs_fast_charge:
        if not any(k in full_info for k in ["sạc nhanh", "pd", "gan", "65w", "100w", "22.5w", "công suất"]):
            return False, "Không hỗ trợ tính năng sạc nhanh"

    needs_stand = any(k in c.lower() for c in caps for k in ["giá đỡ", "kê laptop", "nâng máy"]) or any(k in query_str for k in ["giá đỡ", "kê laptop", "đỡ laptop", "chân đế"])
    if needs_stand:
        if not any(k in full_info for k in ["giá đỡ", "chân đế", "nâng", "hợp kim nhôm xoay"]):
            return False, "Không phải sản phẩm giá đỡ nâng hạ"

    needs_cooler = any(k in c.lower() for c in caps for k in ["tản nhiệt", "làm mát", "hạ nhiệt"]) or any(k in query_str for k in ["tản nhiệt", "làm mát", "nóng máy", "quạt tản nhiệt"])
    if needs_cooler:
        if not any(k in full_info for k in ["tản nhiệt", "làm mát", "quạt", "cooler"]):
            return False, "Không hỗ trợ tính năng làm mát tản nhiệt"

    # General required capabilities check (purges ungrounded candidate matches)
    stop_cap_words = {"tính", "năng", "chức", "thêm", "kèm", "theo", "cho", "của", "máy", "thiết", "bị", "loại"}
    for c in caps:
        c_l = c.lower().strip()
        sig_words = [w for w in re.findall(r"\w+", c_l) if len(w) >= 3 and w not in stop_cap_words]
        if sig_words and not any(k in c_l for k in ["xuất hình", "sạc nhanh", "giá đỡ", "tản nhiệt", "nghe nhạc", "cắm mạng"]):
            if not any(w in full_info for w in sig_words):
                return False, f"Không có tính năng/bộ phận '{c}' theo yêu cầu"

    # Boolean Feature Attributes Checks
    if reqs.get("is_gaming"):
        is_prod_gaming = bool(re.search(r"\b(gaming|game|chơi game)\b", full_info)) or (cat_str == "gaming gear")
        if not is_prod_gaming:
            return False, "Không phải sản phẩm dòng Gaming"

    if reqs.get("is_wireless"):
        is_prod_wireless = bool(re.search(r"\b(không dây|wireless|bluetooth|tws|2\.4ghz|pin sạc)\b", full_info))
        if not is_prod_wireless:
            return False, "Không hỗ trợ kết nối không dây"

    if reqs.get("is_wired"):
        is_prod_wired = bool(re.search(r"\b(có dây|cắm dây|usb-a|dây cáp)\b", full_info)) and not ("không dây" in full_info)
        if not is_prod_wired:
            return False, "Không phải sản phẩm có dây"

    if reqs.get("is_mechanical"):
        is_prod_mech = bool(re.search(r"\b(cơ|phím cơ|switch|cherry|blue switch|red switch|brown switch)\b", full_info))
        if not is_prod_mech:
            return False, "Không phải bàn phím cơ"

    if reqs.get("is_silent"):
        is_prod_silent = bool(re.search(r"\b(silent|êm|yên tĩnh|chống ồn click|không gây ồn|không kêu|không tiếng|không lách cách|bấm êm)\b", full_info))
        if not is_prod_silent:
            return False, "Không có tính năng silent bấm êm không gây ồn"

    if reqs.get("is_anc"):
        is_prod_anc = bool(re.search(r"\b(chống ồn|anc|khử ồn)\b", full_info))
        if not is_prod_anc:
            return False, "Không có tính năng chống ồn chủ động ANC"

    if reqs.get("is_ergonomic"):
        is_prod_ergo = bool(re.search(r"\b(công thái học|ergonomic|chống mỏi)\b", full_info))
        if not is_prod_ergo:
            return False, "Không có thiết kế công thái học"

    # Enforce Negative Constraints (Item 5)
    neg_constraints = reqs.get("negative_constraints") or []
    for neg in neg_constraints:
        neg_clean = str(neg).lower().strip()
        if neg_clean in ("wired", "có dây", "dây"):
            is_wired_only = bool(re.search(r"\b(có dây|cắm dây|usb-a|dây cáp)\b", full_info)) and not ("không dây" in full_info or "wireless" in full_info or "bluetooth" in full_info)
            if is_wired_only:
                return False, "Vi phạm điều kiện phủ định: Sản phẩm có dây (người dùng yêu cầu không dây)"
        elif neg_clean in ("wireless", "không dây", "bluetooth"):
            is_wireless_prod = bool(re.search(r"\b(không dây|wireless|bluetooth|tws|2\.4ghz|pin sạc)\b", full_info))
            if is_wireless_prod:
                return False, "Vi phạm điều kiện phủ định: Sản phẩm không dây (người dùng yêu cầu có dây)"
        elif neg_clean in ("rgb", "led rgb", "đèn led"):
            if "rgb" in full_info:
                return False, "Vi phạm điều kiện phủ định: Có đèn LED RGB"
        elif neg_clean in ("clicky", "ồn", "tiếng ồn"):
            if any(k in full_info for k in ["blue switch", "clicky", "phát ra tiếng gõ lớn"]):
                return False, "Vi phạm điều kiện phủ định: Switch phát ra tiếng gõ lớn/clicky"

    # Hard Constraint: Price within budget
    price = float(product.get("selling_price", 0))
    if budget_max is not None and budget_max > 0:
        if price > budget_max:
            diff = price - budget_max
            return False, f"Vượt ngân sách {int(diff):,} đ ({int(price):,} đ so với mức {int(budget_max):,} đ)"

    return True, None


# ==============================================================================
# SPARSE RETRIEVAL (BM25), STRUCTURED SQL RETRIEVAL & HYBRID FUSION (RRF)
# ==============================================================================

class BM25Retriever:
    """
    In-memory BM25 lexical ranker for StoreFlow SQLite active products catalog.
    Provides Sparse Retrieval score and ranked candidate list.
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def _tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        return [w for w in re.findall(r"\w+", text.lower()) if len(w) >= 2]

    def search(self, query: str, top_k: int = 20) -> List[Tuple[int, float]]:
        try:
            q_tokens = self._tokenize(query)
            if not q_tokens:
                return []

            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT p.id, p.sku, p.name, c.name as category_name, p.description
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    WHERE p.status = 'active'
                """)
                rows = [dict(r) for r in c.fetchall()]

            if not rows:
                return []

            N = len(rows)
            doc_tokens_map = {}
            df: Dict[str, int] = {}
            total_dl = 0

            for r in rows:
                pid = r["id"]
                doc_text = f"{r.get('sku', '')} {r.get('name', '')} {r.get('category_name', '')} {r.get('description', '')}"
                tokens = self._tokenize(doc_text)
                doc_tokens_map[pid] = tokens
                total_dl += len(tokens)
                for t in set(tokens):
                    df[t] = df.get(t, 0) + 1

            avgdl = total_dl / max(1, N)
            scores: List[Tuple[int, float]] = []

            for pid, tokens in doc_tokens_map.items():
                dl = len(tokens)
                doc_score = 0.0
                tf: Dict[str, int] = {}
                for t in tokens:
                    tf[t] = tf.get(t, 0) + 1

                for qt in q_tokens:
                    if qt in tf:
                        n_q = df.get(qt, 0)
                        idf = math.log((N - n_q + 0.5) / (n_q + 0.5) + 1.0)
                        freq = tf[qt]
                        num = freq * (self.k1 + 1)
                        denom = freq + self.k1 * (1 - self.b + self.b * (dl / avgdl))
                        doc_score += idf * (num / denom)

                if doc_score > 0.0:
                    scores.append((pid, doc_score))

            scores.sort(key=lambda x: x[1], reverse=True)
            return scores[:top_k]
        except Exception as e:
            logger.warning(f"BM25 search error: {e}")
            return []


bm25_retriever = BM25Retriever()


def structured_sql_search(
    query: str,
    brand_req: Optional[Dict[str, Any]] = None,
    target_type: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    effective_budget: Optional[float] = None,
    top_k: int = 20
) -> List[Tuple[int, float]]:
    """
    Structured SQL Retrieval directly filtering catalog by brand, device type, budget, and features.
    Guarantees parameterized safety and ensures specific catalog items are never lost.
    """
    try:
        attrs = attributes or {}
        with get_db_connection() as conn:
            c = conn.cursor()
            query_sql = """
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.status, p.description
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.status = 'active'
            """
            params: List[Any] = []
            if effective_budget is not None and effective_budget > 0:
                query_sql += " AND p.selling_price <= ? "
                params.append(effective_budget)

            c.execute(query_sql, params)
            rows = [dict(r) for r in c.fetchall()]

        if not rows:
            return []

        scored: List[Tuple[int, float]] = []
        for r in rows:
            score = 1.0

            # Brand evaluation
            if brand_req:
                if match_product_brand(r, brand_req):
                    score += 10.0  # Dominant boost for target brand
                else:
                    score -= 5.0

            # Target type evaluation
            prod_type = classify_product_type(r)
            if target_type:
                if prod_type == target_type:
                    score += 5.0
                elif prod_type in ("mousepad", "cooler", "charger_cable") and target_type == "mouse":
                    score -= 8.0  # Heavily demote accessories
                else:
                    score -= 2.0

            # Attribute evaluation
            name_desc = f"{r.get('name', '')} {r.get('category_name', '')} {r.get('description', '')}".lower()
            if attrs.get("is_gaming") or attrs.get("gaming"):
                if re.search(r"\b(gaming|game|chơi game)\b", name_desc) or r.get("category_name") == "Gaming Gear":
                    score += 3.0
            if attrs.get("is_wireless") or attrs.get("wireless"):
                if re.search(r"\b(không dây|wireless|bluetooth|tws|2\.4ghz)\b", name_desc):
                    score += 3.0
            if attrs.get("is_wired") or attrs.get("wired"):
                if re.search(r"\b(có dây|cắm dây|usb-a)\b", name_desc):
                    score += 2.0
            if attrs.get("is_mechanical") or attrs.get("mechanical"):
                if re.search(r"\b(cơ|phím cơ|switch)\b", name_desc):
                    score += 3.0
            if attrs.get("is_anc") or attrs.get("anc"):
                if re.search(r"\b(chống ồn|anc|khử ồn)\b", name_desc):
                    score += 3.0
            if attrs.get("is_silent") or attrs.get("silent"):
                if re.search(r"\b(silent|êm|yên tĩnh)\b", name_desc):
                    score += 3.0

            # Capability & compatibility evaluation
            caps = attrs.get("desired_capabilities") or []
            compats = attrs.get("device_compatibility") or []
            q_lower = query.lower()

            if any("hdmi" in c.lower() for c in compats) or "hdmi" in q_lower or any("xuất hình" in c.lower() for c in caps):
                if "hdmi" in name_desc:
                    score += 8.0
                elif any(k in name_desc for k in ["hub", "chuyển đổi", "xuất hình"]):
                    score += 4.0

            if any("type-c" in c.lower() or "usb-c" in c.lower() for c in compats) or "type-c" in q_lower:
                if re.search(r"\b(type-c|type c|usb-c)\b", name_desc):
                    score += 3.0

            if any("sạc nhanh" in c.lower() for c in caps) or "sạc nhanh" in q_lower:
                if any(k in name_desc for k in ["sạc nhanh", "pd", "gan", "65w", "100w"]):
                    score += 4.0

            if any("tản nhiệt" in c.lower() for c in caps) or "tản nhiệt" in q_lower:
                if any(k in name_desc for k in ["tản nhiệt", "làm mát", "quạt"]):
                    score += 5.0

            if any("giá đỡ" in c.lower() for c in caps) or "giá đỡ" in q_lower:
                if any(k in name_desc for k in ["giá đỡ", "chân đế", "nâng"]):
                    score += 5.0

            if any("pin sạc dự phòng" in c.lower() for c in caps) or "pin dự phòng" in q_lower:
                if any(k in name_desc for k in ["pin sạc dự phòng", "pin dự phòng", "powerbank"]):
                    score += 5.0

            # In-stock bonus
            if r.get("stock_quantity", 0) > 0:
                score += 1.0

            if score > 0:
                scored.append((r["id"], score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
    except Exception as e:
        logger.warning(f"Structured SQL search error: {e}")
        return []


def reciprocal_rank_fusion(
    dense_candidates: List[Dict[str, Any]],     # [{"product_id": pid, "distance": dist}, ...]
    sparse_candidates: List[Tuple[int, float]], # [(pid, bm25_score), ...]
    sql_candidates: List[Tuple[int, float]],    # [(pid, sql_score), ...]
    weights: Optional[Dict[str, float]] = None,
    k: int = 60
) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) combining Dense, Sparse (BM25), and Structured SQL candidate rankings.
    Formula: RRF_score(d) = sum_{source} (w_source / (k + rank_source(d)))
    """
    w = weights or {"dense": 1.0, "sparse": 1.0, "sql": 1.0}
    rrf_scores: Dict[int, float] = {}
    details: Dict[int, Dict[str, Any]] = {}

    # 1. Dense ranking (sorted by distance ascending)
    sorted_dense = sorted(dense_candidates, key=lambda x: x.get("distance", 1.0))
    for rank, cand in enumerate(sorted_dense, start=1):
        pid = cand["product_id"]
        contrib = w.get("dense", 1.0) / (k + rank)
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + contrib
        details.setdefault(pid, {})["dense_rank"] = rank

    # 2. Sparse ranking (sorted by score descending)
    for rank, (pid, score) in enumerate(sparse_candidates, start=1):
        contrib = w.get("sparse", 1.0) / (k + rank)
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + contrib
        details.setdefault(pid, {})["sparse_rank"] = rank

    # 3. SQL ranking (sorted by score descending)
    for rank, (pid, score) in enumerate(sql_candidates, start=1):
        contrib = w.get("sql", 1.0) / (k + rank)
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + contrib
        details.setdefault(pid, {})["sql_rank"] = rank

    fused = []
    for pid, total_rrf in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
        fused.append({
            "product_id": pid,
            "rrf_score": total_rrf,
            "ranks": details.get(pid, {})
        })
    return fused


class ScoredCandidate(TypedDict):
    product_id: int
    row: Dict[str, Any]
    distance: float
    dense_score: float
    lexical_score: float
    rrf_score: float
    hybrid_score: float


class RAGService:
    """
    StoreFlow AI Retrieval & Grounding Service.
    Architecture: Dense Vector Retrieval (ChromaDB) + Lexical/Category Re-ranking + Strict SQLite Truth Guard.
    Features:
      1. Out-of-Domain Guard: blocks irrelevant queries with 0 hallucinated products.
      2. Dense Vector Retrieval (ChromaDB) with empirical cosine cutoff (0.55).
      3. Sparse / Lexical Re-ranking with category affinity boosting.
      4. Strict SQLite Post-Retrieval Verification Guard (status='active', stock_quantity > 0).
      5. Explicit Out-of-Stock Detection: alerts users when specific requested products are exhausted.
      6. Prompt Injection Neutralizer: cleans catalog text before sending to LLM.
      7. Synchronization & Reconciliation: detects and self-heals missing, orphan, and outdated vectors.
    """

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir:
            self.persist_dir = Path(persist_dir)
        else:
            p = Path(settings.CHROMA_PERSIST_DIRECTORY)
            if not p.is_absolute():
                self.persist_dir = BASE_DIR / p
            else:
                self.persist_dir = p

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name="storeflow_products",
            metadata={"hnsw:space": "cosine"}
        )
        self._sync_needed = False

    def mark_sync_needed(self) -> None:
        """Flags that an index desynchronization occurred and requires self-healing."""
        self._sync_needed = True

    def auto_heal_if_needed(self, force: bool = False) -> Dict[str, Any]:
        """
        Automatically performs self-healing reconciliation between SQLite and ChromaDB
        if flagged as out of sync or if force=True.
        """
        if not getattr(self, "_sync_needed", False) and not force:
            return {"healed": False, "reason": "in_sync"}
        try:
            status = self.check_sync_status()
            if not status.get("is_synced", True):
                heal_res = self.reconcile_sync()
                self._sync_needed = False
                return {"healed": True, "details": heal_res}
            self._sync_needed = False
            return {"healed": False, "reason": "already_synced"}
        except Exception as e:
            return {"healed": False, "error": str(e)}

    def _sanitize_text(self, text: str) -> str:
        """Neutralizes prompt injection attempts within catalog descriptions."""
        if not text:
            return ""
        clean = text
        for pattern in INJECTION_PATTERNS:
            clean = re.sub(pattern, "[REDACTED_TERM]", clean, flags=re.IGNORECASE)
        # Strip potential markdown formatting overrides
        clean = clean.replace("```", "").replace("<script>", "").replace("</script>", "")
        return clean.strip()

    def _build_product_document(self, p: Dict[str, Any]) -> str:
        """Constructs a descriptive semantic text chunk for product indexing."""
        price_str = f"{int(p.get('selling_price', 0)):,} VNĐ"
        desc_clean = self._sanitize_text(p.get("description", ""))
        return (
            f"Mã: {p.get('sku', '')} | Tên sản phẩm: {p.get('name', '')} | "
            f"Danh mục: {p.get('category_name', '')} | Giá bán: {price_str} | "
            f"Đơn vị: {p.get('unit', 'cái')} | Mô tả & Đặc tính: {desc_clean}"
        )

    # --------------------------------------------------------------------------
    # SYNCHRONIZATION & RECONCILIATION
    # --------------------------------------------------------------------------

    def sync_all_products(self) -> int:
        """
        Loads all products joined with categories from SQLite and indexes them into ChromaDB.
        Returns the number of products indexed.
        """
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
            """)
            rows = [dict(r) for r in c.fetchall()]

        if not rows:
            return 0

        documents: List[str] = []
        ids: List[str] = []
        metadatas: List[Metadata] = []

        for p in rows:
            doc = self._build_product_document(p)
            documents.append(doc)
            ids.append(str(p["id"]))
            meta_item: Metadata = {
                "product_id": int(p["id"]),
                "sku": str(p.get("sku") or ""),
                "category_id": int(p.get("category_id") or 0),
                "category_name": str(p.get("category_name") or ""),
                "selling_price": float(p.get("selling_price") or 0.0),
                "status": str(p.get("status") or "active"),
            }
            metadatas.append(meta_item)

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        return len(rows)

    def upsert_single_product(self, product_id: int) -> bool:
        """Upserts a single product into ChromaDB when added or updated in SQLite."""
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.id = ?
            """, (product_id,))
            row = c.fetchone()

        if not row:
            return False

        p = dict(row)
        doc = self._build_product_document(p)
        self.collection.upsert(
            ids=[str(p["id"])],
            documents=[doc],
            metadatas=[{
                "product_id": int(p["id"]),
                "sku": str(p.get("sku") or ""),
                "category_id": int(p.get("category_id") or 0),
                "category_name": str(p.get("category_name") or ""),
                "selling_price": float(p.get("selling_price") or 0.0),
                "status": str(p.get("status") or "active"),
            }]
        )
        return True

    def delete_single_product(self, product_id: int) -> None:
        """Deletes a product vector from ChromaDB."""
        try:
            self.collection.delete(ids=[str(product_id)])
        except Exception:
            pass

    def check_sync_status(self) -> Dict[str, Any]:
        """
        Audits synchronization health between SQLite products and ChromaDB vectors.
        Identifies:
          - missing_in_chroma: Products in SQLite without a ChromaDB vector.
          - orphan_in_chroma: ChromaDB vectors whose products were deleted from SQLite.
          - outdated_in_chroma: Vectors whose document content or status is stale compared to SQLite.
        """
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
            """)
            sqlite_rows = {str(r["id"]): dict(r) for r in c.fetchall()}

        sqlite_ids = set(sqlite_rows.keys())

        # Include documents and metadatas to check content freshness
        chroma_res = self.collection.get(include=["documents", "metadatas"])
        chroma_ids = set(chroma_res.get("ids", []))

        missing_in_chroma = sorted([int(i) for i in (sqlite_ids - chroma_ids)])
        orphan_in_chroma = sorted([int(i) for i in (chroma_ids - sqlite_ids)])

        # Verify content freshness for products existing in both
        outdated_in_chroma = []
        chroma_docs_map = {}
        chroma_meta_map = {}
        if "documents" in chroma_res and chroma_res["documents"]:
            for idx, cid in enumerate(chroma_res.get("ids", [])):
                chroma_docs_map[cid] = chroma_res["documents"][idx] if idx < len(chroma_res["documents"]) else ""
                chroma_meta_map[cid] = chroma_res["metadatas"][idx] if (chroma_res.get("metadatas") and idx < len(chroma_res["metadatas"])) else {}

        for cid, row in sqlite_rows.items():
            if cid in chroma_docs_map:
                expected_doc = self._build_product_document(row)
                existing_doc = chroma_docs_map[cid]
                existing_meta = chroma_meta_map.get(cid, {})
                if existing_doc != expected_doc or existing_meta.get("status") != str(row.get("status") or "active"):
                    outdated_in_chroma.append(int(cid))

        outdated_in_chroma.sort()
        is_synced = len(missing_in_chroma) == 0 and len(orphan_in_chroma) == 0 and len(outdated_in_chroma) == 0

        return {
            "is_synced": is_synced,
            "sqlite_count": len(sqlite_ids),
            "chroma_count": len(chroma_ids),
            "missing_in_chroma": missing_in_chroma,
            "orphan_in_chroma": orphan_in_chroma,
            "outdated_in_chroma": outdated_in_chroma
        }

    def reconcile_sync(self) -> Dict[str, Any]:
        """
        Self-healing routine: resolves all desync anomalies between SQLite and ChromaDB.
        Upserts missing products, refreshes outdated vector documents, and purges orphan records.
        """
        status = self.check_sync_status()
        upserted_count = 0
        updated_count = 0
        deleted_count = 0

        for mid in status["missing_in_chroma"]:
            if self.upsert_single_product(mid):
                upserted_count += 1

        for oid in status.get("outdated_in_chroma", []):
            if self.upsert_single_product(oid):
                updated_count += 1

        for orph_id in status["orphan_in_chroma"]:
            self.delete_single_product(orph_id)
            deleted_count += 1

        # Double check after healing
        final_status = self.check_sync_status()
        return {
            "repaired": True,
            "upserted_count": upserted_count,
            "updated_count": updated_count,
            "deleted_count": deleted_count,
            "final_sync_status": final_status
        }

    # --------------------------------------------------------------------------
    # INTENT ANALYSIS & LEXICAL SCORING
    # --------------------------------------------------------------------------

    def is_out_of_domain(self, query: str) -> bool:
        """Detects whether a query falls outside the StoreFlow technology product domain."""
        q_clean = query.lower().strip()
        # Decouple display appliances from connectivity accessories:
        # If user mentions TV/tivi alongside connector terms, they are seeking a cable/hub/adapter, not a TV appliance.
        has_display_host = bool(re.search(r"\b(tivi|tv)\b", q_clean))
        has_connectivity = bool(re.search(r"\b(cáp|dây|hub|chuyển đổi|adapter|đầu chuyển|cắm|nối|kết nối|hdmi|type-c|usb-c)\b", q_clean))
        is_tv_accessory_query = has_display_host and has_connectivity

        for pattern in OUT_OF_DOMAIN_PATTERNS:
            if is_tv_accessory_query and ("tivi" in pattern or "tv" in pattern):
                # Check other non-TV appliances in the same pattern
                sub_pattern = r"\b(máy giặt|tủ lạnh|máy sấy|máy lạnh|điều hòa|xe máy|ô tô|xe đạp|quần áo|giày dép|áo phông|áo thun|quần jean|váy|đầm)\b"
                if re.search(sub_pattern, q_clean):
                    return True
                continue
            if re.search(pattern, q_clean):
                return True
        return False

    def detect_target_categories(self, query: str) -> Set[str]:
        """Identifies specific product categories explicitly implied in the query."""
        q_lower = query.lower()
        matched = set()
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if kw in q_lower:
                    matched.add(cat)
                    break
        return matched

    def compute_lexical_similarity(self, query: str, product_name: str, description: str) -> float:
        """Computes lexical token overlap and fuzzy word similarity."""
        name_str = product_name or ""
        desc_str = description or ""
        q_words = set(re.findall(r"\w+", (query or "").lower()))
        doc_text = f"{name_str} {desc_str}".lower()
        doc_words = set(re.findall(r"\w+", doc_text))

        if not q_words:
            return 0.0

        intersection = q_words.intersection(doc_words)
        token_score = len(intersection) / len(q_words)

        fuzzy_hits = 0
        for qw in q_words:
            if len(qw) >= 4:
                for dw in doc_words:
                    if difflib.SequenceMatcher(None, qw, dw).ratio() > 0.8:
                        fuzzy_hits += 1
                        break
        fuzzy_score = min(fuzzy_hits / len(q_words), 1.0)
        return max(token_score, fuzzy_score)

    # --------------------------------------------------------------------------
    # RETRIEVAL & GROUNDING PIPELINE
    # --------------------------------------------------------------------------

    def search_candidates(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Executes semantic search over ChromaDB index and returns Top-K candidate products.
        Automatically heals index if desynchronization was flagged, or if collection is empty.
        """
        if getattr(self, "_sync_needed", False):
            self.auto_heal_if_needed()

        total_indexed = self.collection.count()
        if total_indexed == 0:
            self.sync_all_products()
            total_indexed = self.collection.count()

        if total_indexed == 0:
            return []

        n_results = min(top_k, total_indexed)
        res = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )

        candidates = []
        ids_list = res.get("ids")
        if ids_list and len(ids_list) > 0:
            metadatas_list = res.get("metadatas")
            documents_list = res.get("documents")
            distances_list = res.get("distances")

            for idx, pid_str in enumerate(ids_list[0]):
                meta = metadatas_list[0][idx] if (metadatas_list and len(metadatas_list) > 0) else {}
                doc = documents_list[0][idx] if (documents_list and len(documents_list) > 0) else ""
                dist = distances_list[0][idx] if (distances_list and len(distances_list) > 0) else None
                candidates.append({
                    "product_id": int(pid_str),
                    "metadata": meta,
                    "document": doc,
                    "distance": dist,
                })
        return candidates

    def get_grounded_recommendation_context(
        self,
        query: str,
        top_k: int = 5,
        budget_max: Optional[float] = None,
        distance_cutoff: float = 0.55,
        intent: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Crucial Hybrid RAG Pipeline with Strict SQLite Guardrail & Eligibility Filtering:
        1. Query Understanding & Budget Extraction: parses natural language budget & features.
        2. Out-of-Domain Guard & Clarification Handler: rejects queries unrelated to store catalog with 0 hallucinated products.
        3. Three-Way Hybrid Retrieval:
           - Source 1: Dense Retrieval (ChromaDB vectors)
           - Source 2: Sparse Retrieval (BM25 lexical index across active catalog)
           - Source 3: Structured SQL Retrieval (parameterized catalog search)
        4. Candidate Fusion: Reciprocal Rank Fusion (RRF) with brand/type priority weights.
        5. Strict SQLite Post-Retrieval Verification Guard & Eligibility Filtering (Lần 1).
        6. Explicit Out-of-Stock Detection: identifies specifically requested items that are zero stock.
        7. Clear separation between Eligible Recommendations and Alternative Suggestions.
        """
        # Step 0: Budget & Query Understanding
        effective_budget = resolve_effective_budget(query, budget_max)
        reqs = parse_query_requirements(query)

        # Incorporate structured intent if provided
        if intent is not None:
            if getattr(intent, "max_price", None) is not None:
                if effective_budget is not None:
                    effective_budget = min(effective_budget, intent.max_price)
                else:
                    effective_budget = intent.max_price
            if getattr(intent, "brand", None):
                b_info = extract_brand_from_query(intent.brand) or {
                    "brand_key": intent.brand.lower(),
                    "canonical_name": intent.brand
                }
                reqs["brand"] = b_info
            if getattr(intent, "product_type", None):
                reqs["target_type"] = intent.product_type
            if getattr(intent, "desired_capabilities", None):
                reqs["desired_capabilities"] = intent.desired_capabilities
            if getattr(intent, "device_compatibility", None):
                reqs["device_compatibility"] = intent.device_compatibility
            if getattr(intent, "user_device", None):
                reqs["user_device"] = intent.user_device
            if getattr(intent, "negative_constraints", None):
                reqs["negative_constraints"] = intent.negative_constraints
            if getattr(intent, "attributes", None) and isinstance(intent.attributes, dict):
                for k, v in intent.attributes.items():
                    reqs[f"is_{k}"] = v

            # Check if intent signals need for clarification
            if getattr(intent, "needs_clarification", False):
                return {
                    "products": [],
                    "alternative_products": [],
                    "effective_budget": effective_budget,
                    "context_text": getattr(intent, "clarification_question", None) or "Quý khách vui lòng làm rõ yêu cầu để cửa hàng có thể hỗ trợ chính xác nhất.",
                    "out_of_stock_detected": None,
                    "out_of_stock_excluded": [],
                    "total_verified": 0,
                    "status": "needs_clarification",
                    "clarification_question": getattr(intent, "clarification_question", None),
                    "brand_name": None,
                    "intent": intent,
                }

        # Step 1: Out-of-Domain Guard
        if self.is_out_of_domain(query) or (intent and getattr(intent, "is_out_of_domain", False)):
            return {
                "products": [],
                "alternative_products": [],
                "effective_budget": effective_budget,
                "context_text": "Cửa hàng StoreFlow AI hiện không kinh doanh các mặt hàng hoặc dịch vụ này. Chúng tôi chuyên cung cấp thiết bị công nghệ, phụ kiện văn phòng, âm thanh và gaming gear.",
                "out_of_stock_detected": None,
                "out_of_stock_excluded": [],
                "total_verified": 0,
                "status": "out_of_domain",
                "intent": intent,
            }

        # Step 2: Three-Way Hybrid Retrieval (Dense + Sparse BM25 + Structured SQL)
        # Source 1: Dense Retrieval from ChromaDB
        dense_candidates = self.search_candidates(query, top_k=max(top_k * 4, 20))

        # Source 2: Sparse Lexical Retrieval from BM25
        sparse_candidates = bm25_retriever.search(query, top_k=max(top_k * 4, 20))

        # Source 3: Structured SQL Retrieval
        brand_req = reqs.get("brand")
        sql_candidates = structured_sql_search(
            query=query,
            brand_req=brand_req,
            target_type=reqs.get("target_type"),
            attributes=reqs,
            effective_budget=effective_budget,
            top_k=max(top_k * 4, 20)
        )

        # Candidate Fusion via Reciprocal Rank Fusion (RRF)
        fusion_weights = {"sql": 2.5, "sparse": 1.0, "dense": 0.8} if brand_req else {"dense": 1.0, "sparse": 1.0, "sql": 1.0}
        fused_candidates = reciprocal_rank_fusion(
            dense_candidates=dense_candidates,
            sparse_candidates=sparse_candidates,
            sql_candidates=sql_candidates,
            weights=fusion_weights
        )

        if not fused_candidates and not dense_candidates:
            return self._fallback_sqlite_search(query, top_k, effective_budget, reqs)

        # Step 3: Fetch candidate details from SQLite
        candidate_pids: List[int] = [
            int(c["product_id"]) for c in fused_candidates if c.get("product_id") is not None
        ]
        # Also ensure dense candidates are fetched in case of fusion anomalies
        for dc in dense_candidates:
            dc_pid = dc.get("product_id")
            if dc_pid is not None:
                dc_pid_int = int(dc_pid)
                if dc_pid_int not in candidate_pids:
                    candidate_pids.append(dc_pid_int)

        brand_matched_pids: Set[int] = set()
        if brand_req:
            with get_db_connection() as conn:
                bc = conn.cursor()
                bc.execute("""
                    SELECT p.id, p.name, p.description
                    FROM products p
                    WHERE p.status = 'active'
                """)
                for r in bc.fetchall():
                    if match_product_brand(dict(r), brand_req):
                        b_pid = r["id"]
                        if b_pid is not None:
                            b_pid_int = int(b_pid)
                            brand_matched_pids.add(b_pid_int)
                            if b_pid_int not in candidate_pids:
                                candidate_pids.append(b_pid_int)

        if not candidate_pids:
            return self._fallback_sqlite_search(query, top_k, effective_budget, reqs)

        placeholders = ",".join("?" for _ in candidate_pids)
        with get_db_connection() as conn:
            c = conn.cursor()
            # Explicitly NEVER select cost_price
            c.execute(f"""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description, p.image_url
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.id IN ({placeholders})
            """, candidate_pids)
            all_candidate_rows: Dict[int, Dict[str, Any]] = {
                int(r["id"]): dict(r) for r in c.fetchall() if r["id"] is not None
            }

        # Step 4: Detect Target Category
        target_cats = self.detect_target_categories(query)

        # Step 5: Check if top candidate is an explicit Out-Of-Stock item requested by name
        oos_detected = None
        top1_dist: float = 1.0
        top1_cand = dense_candidates[0] if dense_candidates else (fused_candidates[0] if fused_candidates else None)
        if top1_cand and top1_cand.get("product_id") is not None and int(top1_cand["product_id"]) in all_candidate_rows:
            top1_row = all_candidate_rows[int(top1_cand["product_id"])]
            top1_dist = float(top1_cand.get("distance", 0.0) if "distance" in top1_cand else 0.5)
            if top1_row.get("stock_quantity", 0) <= 0:
                generic_device_terms = {"tai", "nghe", "chuột", "bàn", "phím", "loa", "cáp", "sạc", "máy", "tính", "sản", "phẩm", "đồ", "hãng", "của", "cho", "tôi", "xem"}
                name_words = set(re.findall(r"\w+", top1_row["name"].lower()))
                q_words = set(re.findall(r"\w+", query.lower()))
                specific_matches = (name_words.intersection(q_words)) - generic_device_terms
                brand_ok = (not brand_req) or match_product_brand(top1_row, brand_req)
                if brand_ok and (len(specific_matches) >= 1 or top1_dist < 0.25):
                    oos_detected = top1_row

        # Step 6: Hybrid Scoring & Re-ranking with Product Type Alignment
        dense_distance_map: Dict[int, float] = {
            int(c["product_id"]): float(c.get("distance", 1.0))
            for c in dense_candidates
            if c.get("product_id") is not None
        }
        rrf_score_map: Dict[int, float] = {
            int(c["product_id"]): float(c.get("rrf_score", 0.0))
            for c in fused_candidates
            if c.get("product_id") is not None
        }

        scored_candidates: List[ScoredCandidate] = []
        for pid in candidate_pids:
            if pid is None:
                continue
            row = all_candidate_rows.get(pid)
            if not row:
                continue

            dist = dense_distance_map.get(pid, 0.45 if pid in brand_matched_pids else 0.8)
            dense_score = max(0.0, 1.0 - dist)
            lexical_score = self.compute_lexical_similarity(query, row.get("name") or "", row.get("description") or "")
            rrf_val = rrf_score_map.get(pid, 0.0)

            category_boost = 0.0
            if target_cats:
                if row.get("category_name") in target_cats:
                    category_boost = 0.30
                elif not (reqs.get("desired_capabilities") or reqs.get("device_compatibility")):
                    category_boost = -0.20 # Only penalize if user didn't request a capability

            # Bonus for matching target device type
            prod_type = classify_product_type(row)
            if reqs.get("target_type"):
                if prod_type == reqs["target_type"]:
                    category_boost += 0.40
                elif prod_type in ("mousepad", "cooler", "charger_cable") and reqs["target_type"] == "mouse":
                    category_boost -= 0.60 # Heavily demote accessories when user asks for mouse device

            # Capability & compatibility boost in hybrid scoring
            row_full_text = f"{row.get('name', '')} {row.get('category_name', '')} {row.get('description', '')}".lower()
            compat_list = reqs.get("device_compatibility") or []
            caps_list = reqs.get("desired_capabilities") or []
            if any("hdmi" in c.lower() for c in compat_list) and "hdmi" in row_full_text:
                category_boost += 0.50
            if any("type-c" in c.lower() or "usb-c" in c.lower() for c in compat_list) and re.search(r"\b(type-c|type c|usb-c)\b", row_full_text):
                category_boost += 0.30
            if any("sạc nhanh" in c.lower() for c in caps_list) and any(k in row_full_text for k in ["sạc nhanh", "pd", "gan"]):
                category_boost += 0.40
            if any("tản nhiệt" in c.lower() for c in caps_list) and any(k in row_full_text for k in ["tản nhiệt", "làm mát", "quạt"]):
                category_boost += 0.40
            if any("giá đỡ" in c.lower() for c in caps_list) and any(k in row_full_text for k in ["giá đỡ", "chân đế", "nâng"]):
                category_boost += 0.40

            # Bonus / penalty for brand matching
            if brand_req:
                if pid in brand_matched_pids:
                    category_boost += 0.60
                else:
                    category_boost -= 0.60

            # Combined hybrid score (incorporates RRF + Dense + Lexical + Category Boost)
            hybrid_score = (rrf_val * 10.0) + (dense_score * 0.4) + (lexical_score * 0.3) + category_boost
            scored_candidates.append({
                "product_id": pid,
                "row": row,
                "distance": dist,
                "dense_score": dense_score,
                "lexical_score": lexical_score,
                "rrf_score": rrf_val,
                "hybrid_score": hybrid_score
            })

        scored_candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)

        verified_products: List[Dict[str, Any]] = []
        alternative_products: List[Dict[str, Any]] = []
        notable_expensive_brand_products: List[Dict[str, Any]] = []
        out_of_stock_excluded: List[Dict[str, Any]] = []
        seen_pids: Set[int] = set()

        for sc in scored_candidates:
            p_data: Dict[str, Any] = sc["row"]
            raw_pid = p_data.get("id")
            if raw_pid is None:
                continue
            pid = int(raw_pid)
            if pid in seen_pids:
                continue
            seen_pids.add(pid)

            dist: float = sc["distance"]
            lex_score: float = sc["lexical_score"]

            # Cutoff filter: discard if distance exceeds threshold AND lexical score is low
            if dist > distance_cutoff and lex_score < 0.20:
                continue

            is_eligible, ineligibility_reason = check_product_eligibility(p_data, reqs, effective_budget)

            if is_eligible:
                verified_products.append(p_data)
                if len(verified_products) >= top_k:
                    break
            else:
                if p_data.get("stock_quantity", 0) <= 0:
                    out_of_stock_excluded.append({
                        "id": p_data["id"],
                        "name": p_data["name"],
                        "sku": p_data["sku"],
                        "stock_quantity": p_data.get("stock_quantity", 0),
                        "status": p_data.get("status", "")
                    })
                elif p_data.get("status") == "active":
                    price = float(p_data.get("selling_price", 0))
                    # Criteria for budget closeness:
                    # Alternative suggestions must remain viable shopping choices.
                    # If effective_budget is set, price should not exceed the budget by an excessive ratio or amount.
                    is_severely_over_budget = False
                    if effective_budget is not None and effective_budget > 0:
                        max_allowed_alt_price = min(effective_budget * 2.0, max(effective_budget * 1.5, effective_budget + 500_000))
                        if price > max_allowed_alt_price:
                            is_severely_over_budget = True

                    is_brand_match = brand_req and match_product_brand(p_data, brand_req)
                    if is_severely_over_budget:
                        if is_brand_match:
                            notable_expensive_brand_products.append(p_data)
                        # Do not include products with severe price disparity in shopping recommendations
                        continue

                    # Alternative filter: MUST address the same core function or product type!
                    # A product cannot be an alternative if it fails the core capability!
                    is_viable_alt = False
                    lacks_core_capability = ineligibility_reason and any(
                        k in ineligibility_reason.lower()
                        for k in [
                            "không hỗ trợ cổng xuất hình hdmi",
                            "không hỗ trợ chức năng xuất hình",
                            "không hỗ trợ tính năng",
                            "không phải sản phẩm giá đỡ",
                            "không hỗ trợ tính năng làm mát",
                            "không đúng loại sản phẩm"
                        ]
                    )

                    if not lacks_core_capability:
                        # 1. If brand requested:
                        if brand_req:
                            if reqs.get("target_type") and classify_product_type(p_data) == reqs["target_type"]:
                                is_viable_alt = True
                        # 2. If target type requested:
                        elif reqs.get("target_type"):
                            if classify_product_type(p_data) == reqs["target_type"]:
                                is_viable_alt = True
                        # 3. If functional capability requested:
                        elif reqs.get("desired_capabilities") or reqs.get("device_compatibility"):
                            is_viable_alt = True
                        else:
                            if lex_score >= 0.25:
                                is_viable_alt = True

                    if is_viable_alt:
                        alt_item = dict(p_data)
                        alt_item["ineligible_reason"] = ineligibility_reason
                        alt_item["match_reason"] = ineligibility_reason
                        alternative_products.append(alt_item)

        # If user specifically asked for an out-of-stock product, clear unrelated items
        if oos_detected and (not verified_products or top1_dist < 0.28):
            verified_products = []

        # If brand requested with no device type and no verified products, ensure alternatives are strictly empty
        if brand_req and not verified_products and not reqs.get("target_type"):
            alternative_products = []

        brand_name_display = brand_req["canonical_name"].title() if brand_req else ""
        brand_status = None
        brand_catalog_products = []
        brand_active_in_stock = []
        if brand_req:
            with get_db_connection() as conn:
                bc = conn.cursor()
                bc.execute("""
                    SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                           p.selling_price, p.stock_quantity, p.unit, p.status, p.description, p.image_url
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                """)
                for r in bc.fetchall():
                    if match_product_brand(dict(r), brand_req):
                        p_dict = dict(r)
                        brand_catalog_products.append(p_dict)
                        if p_dict.get("status") == "active" and p_dict.get("stock_quantity", 0) > 0:
                            brand_active_in_stock.append(p_dict)

            if not brand_catalog_products:
                brand_status = "brand_not_found"
            elif not brand_active_in_stock:
                brand_status = "brand_out_of_stock"
            else:
                if effective_budget is not None and effective_budget > 0 and all(float(p.get("selling_price", 0)) > effective_budget for p in brand_active_in_stock):
                    brand_status = "brand_over_budget"
                elif reqs.get("target_type") and all(classify_product_type(p) != reqs["target_type"] for p in brand_active_in_stock):
                    brand_status = "brand_attribute_mismatch"
                else:
                    brand_status = "brand_attribute_mismatch"

            if brand_status == "brand_over_budget" and not notable_expensive_brand_products:
                notable_expensive_brand_products = brand_active_in_stock[:2]

        # Step 7: Assemble Grounded Context for LLM
        context_lines = []
        if oos_detected:
            context_lines.append(
                f"CẢNH BÁO TỒN KHO THỰC TẾ: Sản phẩm '{oos_detected['name']}' (Mã SKU: {oos_detected['sku']}) "
                f"hiện ĐÃ HẾT HÀNG (tồn kho: 0). Cửa hàng tạm thời không còn hàng sản phẩm này."
            )

        if verified_products:
            context_lines.append("DANH SÁCH SẢN PHẨM PHÙ HỢP ĐỦ ĐIỀU KIỆN (VERIFIED ELIGIBLE IN SQL):")
            for idx, vp in enumerate(verified_products, start=1):
                price_fmt = f"{int(vp['selling_price']):,} đ"
                clean_desc = self._sanitize_text(vp.get('description', '') or 'Đang cập nhật')
                context_lines.append(
                    f"{idx}. [ID {vp['id']}] {vp['name']} (Mã SKU: {vp['sku']})\n"
                    f"   - Nhóm hàng: {vp.get('category_name') or 'Công nghệ'}\n"
                    f"   - Giá bán: {price_fmt}\n"
                    f"   - Tồn kho khả dụng: {vp['stock_quantity']} {vp['unit']} (CÒN HÀNG TRONG KHO)\n"
                    f"   - Mô tả / Thông số: {clean_desc}"
                )
            if alternative_products:
                context_lines.append("\nGỢI Ý THAM KHẢO KHÁC (CHƯA ĐÁP ỨNG ĐỦ TẤT CẢ TIÊU CHÍ):")
                for alt in alternative_products[:2]:
                    price_fmt = f"{int(alt['selling_price']):,} đ"
                    context_lines.append(
                        f"- [ID {alt['id']}] {alt['name']} (Mã SKU: {alt['sku']}, Giá: {price_fmt}, Tồn kho: {alt['stock_quantity']} {alt['unit']})\n"
                        f"  Lý do chưa khớp hoàn toàn: {alt.get('ineligible_reason', 'Chưa đáp ứng đủ tiêu chí')}"
                    )
        elif brand_req:
            if brand_status == "brand_over_budget" and effective_budget is not None:
                exp_list = notable_expensive_brand_products or brand_active_in_stock
                budget_fmt = f"{int(effective_budget):,} đ"
                for exp_p in exp_list[:1]:
                    context_lines.append(
                        f"XÁC NHẬN SẢN PHẨM THƯƠNG HIỆU (VƯỢT NGÂN SÁCH): Cửa hàng CÓ SẢN PHẨM thuộc thương hiệu {brand_name_display} đang CÒN HÀNG trong kho: "
                        f"'{exp_p['name']}' (Mã SKU: {exp_p['sku']}), giá bán thực tế là {int(exp_p['selling_price']):,} đ (tồn kho: {exp_p['stock_quantity']} {exp_p.get('unit', 'cái')}). "
                        f"Mức giá này cao hơn mức ngân sách {budget_fmt} của khách hàng. "
                        f"Hãy giải thích trung thực rằng cửa hàng có sản phẩm {brand_name_display} nhưng vượt ngân sách yêu cầu, "
                        f"TUYỆT ĐỐI KHÔNG khẳng định cửa hàng không có sản phẩm {brand_name_display} hay hết hàng. "
                        f"Khách hàng có thể tham khảo một số phương án thay thế cùng loại từ thương hiệu khác dưới đây."
                    )
            elif brand_status == "brand_out_of_stock":
                context_lines.append(
                    f"SẢN PHẨM THƯƠNG HIỆU TẠM HẾT HÀNG: Cửa hàng có kinh doanh các sản phẩm thuộc thương hiệu {brand_name_display}, "
                    f"tuy nhiên hiện tại tất cả các sản phẩm này đều tạm thời HẾT HÀNG trong kho (tồn kho: 0). "
                    f"Hãy thông báo rõ ràng điều này và gợi ý các sản phẩm thay thế cùng loại nếu có."
                )
            elif brand_status == "brand_attribute_mismatch":
                sample_p = brand_active_in_stock[0] if brand_active_in_stock else brand_catalog_products[0]
                context_lines.append(
                    f"KHÁC CHỦNG LOẠI THIẾT BỊ: Cửa hàng có kinh doanh sản phẩm thuộc thương hiệu {brand_name_display} (ví dụ: '{sample_p['name']}'), "
                    f"nhưng hiện chưa có sản phẩm đúng loại hoặc tính năng '{reqs.get('target_type') or 'yêu cầu'}' của thương hiệu này."
                )
            else:  # brand_not_found
                context_lines.append(
                    f"THƯƠNG HIỆU CHƯA CÓ TRONG DANH MỤC: Cửa hàng hiện chưa kinh doanh các sản phẩm thuộc thương hiệu {brand_name_display}.\n"
                    f"Hãy thông báo rõ ràng cửa hàng chưa có thương hiệu {brand_name_display} và hỏi khách hàng đang tìm loại thiết bị nào để tư vấn phù hợp."
                )

            if alternative_products:
                context_lines.append("\nCÁC PHƯƠNG ÁN THAY THẾ GẦN NHẤT CÓ THỂ THAM KHẢO (THƯƠNG HIỆU KHÁC):")
                for alt in alternative_products[:3]:
                    price_fmt = f"{int(alt['selling_price']):,} đ"
                    context_lines.append(
                        f"- [ID {alt['id']}] {alt['name']} (Mã SKU: {alt['sku']}, Giá: {price_fmt}, Tồn kho: {alt['stock_quantity']} {alt['unit']})\n"
                        f"  Lý do tham khảo: {alt.get('ineligible_reason', 'Phương án thay thế')}"
                    )
        elif not oos_detected:
            context_lines.append("THÔNG BÁO TỒN KHO THỰC TẾ: Kho hàng hiện tại KHÔNG CÓ sản phẩm nào đáp ứng đầy đủ tất cả tiêu chí và ngân sách của khách hàng.")
            context_lines.append("CHỈ DẪN BẮT BUỘC CHO TRỢ LÝ: Hãy thông báo trung thực, rõ ràng rằng cửa hàng hiện chưa có sản phẩm đáp ứng đầy đủ yêu cầu này. TUYỆT ĐỐI KHÔNG tự sáng tác, bịa đặt tên sản phẩm, mã SKU, giá bán hoặc số lượng tồn kho.")
            if alternative_products:
                context_lines.append("\nCÁC PHƯƠNG ÁN THAY THẾ GẦN NHẤT CÓ THỂ THAM KHẢO:")
                for alt in alternative_products[:3]:
                    price_fmt = f"{int(alt['selling_price']):,} đ"
                    context_lines.append(
                        f"- [ID {alt['id']}] {alt['name']} (Mã SKU: {alt['sku']}, Giá: {price_fmt}, Tồn kho: {alt['stock_quantity']} {alt['unit']})\n"
                        f"  Lý do: {alt.get('ineligible_reason', 'Phương án thay thế')}"
                    )

        final_status = "success" if verified_products else (brand_status if brand_req else ("out_of_stock" if oos_detected else "empty"))

        # Strict deduplication: Alternative products must never contain any verified eligible product
        verified_pids = {p["id"] for p in verified_products}
        deduped_alternatives = []
        seen_alt_pids = set()
        for alt in alternative_products:
            a_pid = alt["id"]
            if a_pid not in verified_pids and a_pid not in seen_alt_pids:
                seen_alt_pids.add(a_pid)
                deduped_alternatives.append(alt)

        return {
            "products": verified_products,
            "alternative_products": deduped_alternatives[:3],
            "notable_expensive_brand_products": notable_expensive_brand_products,
            "effective_budget": effective_budget,
            "context_text": "\n\n".join(context_lines),
            "out_of_stock_detected": oos_detected,
            "out_of_stock_excluded": out_of_stock_excluded,
            "total_verified": len(verified_products),
            "status": final_status,
            "brand_name": brand_name_display if brand_req else None,
            "intent": intent,
        }

    def _fallback_sqlite_search(
        self,
        query: str,
        top_k: int = 5,
        budget_max: Optional[float] = None,
        reqs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Fallback direct SQL keyword search if vector search returns zero results."""
        if self.is_out_of_domain(query):
            return {
                "products": [],
                "alternative_products": [],
                "effective_budget": budget_max,
                "context_text": "Cửa hàng hiện không kinh doanh các mặt hàng này.",
                "out_of_stock_detected": None,
                "out_of_stock_excluded": [],
                "total_verified": 0,
                "status": "out_of_domain"
            }

        effective_budget = resolve_effective_budget(query, budget_max)
        parsed_reqs = reqs or parse_query_requirements(query)

        keyword = f"%{query.strip()}%"
        with get_db_connection() as conn:
            c = conn.cursor()
            params: List[Any] = [keyword, keyword, keyword]
            budget_clause = ""
            if effective_budget is not None and effective_budget > 0:
                budget_clause = " AND p.selling_price <= ? "
                params.append(effective_budget)
            params.append(top_k * 3)

            c.execute(f"""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description, p.image_url
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE (p.name LIKE ? OR p.description LIKE ? OR c.name LIKE ?)
                  AND p.status = 'active'
                  AND p.stock_quantity > 0
                  {budget_clause}
                ORDER BY p.stock_quantity DESC
                LIMIT ?
            """, params)
            rows = [dict(r) for r in c.fetchall()]

        verified_rows = []
        alt_rows = []
        brand_req = parsed_reqs.get("brand")
        for r in rows:
            is_el, reason = check_product_eligibility(r, parsed_reqs, effective_budget)
            if is_el:
                verified_rows.append(r)
                if len(verified_rows) >= top_k:
                    break
            else:
                if not brand_req:
                    r_copy = dict(r)
                    r_copy["ineligible_reason"] = reason
                    r_copy["match_reason"] = reason
                    alt_rows.append(r_copy)
                elif parsed_reqs.get("target_type") and classify_product_type(r) == parsed_reqs["target_type"]:
                    r_copy = dict(r)
                    r_copy["ineligible_reason"] = reason
                    r_copy["match_reason"] = reason
                    alt_rows.append(r_copy)

        is_brand_not_found = bool(brand_req and not verified_rows)
        brand_name_display = brand_req["canonical_name"].title() if brand_req else ""
        if is_brand_not_found and not parsed_reqs.get("target_type"):
            alt_rows = []

        context_lines = []
        if verified_rows:
            context_lines.append("DANH SÁCH SẢN PHẨM KHẢ DỤNG TẠI CỬA HÀNG (TRA CỨU TRỰC TIẾP SQL):")
            for idx, vp in enumerate(verified_rows, start=1):
                price_fmt = f"{int(vp['selling_price']):,} đ"
                clean_desc = self._sanitize_text(vp.get('description', '') or 'Đang cập nhật')
                context_lines.append(
                    f"{idx}. [ID {vp['id']}] {vp['name']} (Mã SKU: {vp['sku']})\n"
                    f"   - Nhóm hàng: {vp.get('category_name') or 'Công nghệ'}\n"
                    f"   - Giá bán: {price_fmt}\n"
                    f"   - Tồn kho: {vp['stock_quantity']} {vp['unit']}\n"
                    f"   - Mô tả: {clean_desc}"
                )
        elif is_brand_not_found:
            context_lines.append(
                f"KHÔNG TÌM THẤY SẢN PHẨM: Không tìm thấy sản phẩm {brand_name_display} đang có hàng tại cửa hàng."
            )
        else:
            context_lines.append("KHÔNG CÓ SẢN PHẨM PHÙ HỢP CÒN TỒN KHO TRONG HỆ THỐNG.")
            if alt_rows:
                context_lines.append("\nCÁC PHƯƠNG ÁN THAY THẾ GẦN NHẤT:")
                for alt in alt_rows[:3]:
                    price_fmt = f"{int(alt['selling_price']):,} đ"
                    context_lines.append(f"- {alt['name']} (SKU: {alt['sku']}, Giá: {price_fmt}) — {alt.get('ineligible_reason', '')}")

        return {
            "products": verified_rows,
            "alternative_products": alt_rows[:3],
            "effective_budget": effective_budget,
            "context_text": "\n\n".join(context_lines),
            "out_of_stock_detected": None,
            "out_of_stock_excluded": [],
            "total_verified": len(verified_rows),
            "status": "brand_not_found" if is_brand_not_found else ("success" if verified_rows else "empty"),
            "brand_name": brand_name_display if is_brand_not_found else None,
        }

    def reverify_products_in_sqlite(self, pids: List[int]) -> Dict[int, Dict[str, Any]]:
        """
        Re-verifies products directly against SQLite database (Lần 2 pre-response check).
        Returns mapping of pid -> live row data.
        """
        if not pids:
            return {}
        placeholders = ",".join("?" for _ in pids)
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute(f"""
                    SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                           p.selling_price, p.stock_quantity, p.unit, p.status, p.description, p.image_url
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    WHERE p.id IN ({placeholders})
                """, pids)
                return {r["id"]: dict(r) for r in c.fetchall()}
        except Exception as e:
            logger.warning(f"Error reverifying products in SQLite: {e}")
            return {}


# Global singleton instance
rag_service = RAGService()