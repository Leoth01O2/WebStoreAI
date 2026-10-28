import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple

from app.schemas.ai import UserQueryIntent
from app.services.ai_providers.manager import ai_provider_manager
from app.services.rag_service import (
    extract_budget_from_query,
    resolve_effective_budget,
    extract_brand_from_query,
    parse_query_requirements,
    extract_negative_feature_clauses,
    rag_service,
)

logger = logging.getLogger(__name__)


INTENT_SYSTEM_PROMPT = """Bạn là Bộ phân tích Ý định (Intent Analyzer) của hệ sinh thái bán lẻ StoreFlow AI (chuyên thiết bị công nghệ: chuột, bàn phím, tai nghe, loa, tay cầm, gaming gear, phụ kiện điện tử).
Nhiệm vụ: Trích xuất ý định của người dùng thành DUY NHẤT một chuỗi JSON hợp lệ theo schema sau:

{
  "intent": "search_products" | "check_brand" | "check_stock" | "out_of_domain" | "general_inquiry",
  "brand": string hoặc null,
  "product_type": string hoặc null,
  "user_device": string hoặc null,
  "desired_capabilities": [string],
  "device_compatibility": [string],
  "required_attributes": [string],
  "negative_constraints": [string],
  "attributes": {
    "gaming": boolean,
    "wireless": boolean,
    "wired": boolean,
    "mechanical": boolean,
    "silent": boolean,
    "anc": boolean,
    "ergonomic": boolean
  },
  "min_price": number (VND) hoặc null,
  "max_price": number (VND) hoặc null,
  "needs_clarification": boolean,
  "clarification_question": string hoặc null,
  "is_out_of_domain": boolean
}

QUY TẮC BẮT BUỘC:
1. PHÂN BIỆT THIẾT BỊ NGƯỜI DÙNG ĐANG CÓ (user_device) VÀ SẢN PHẨM CẦN MUA (product_type) — Head Noun vs. Object Noun Disambiguation:
   - user_device: Thiết bị người dùng ĐANG SỞ HỮU (ví dụ: máy tính, laptop, điện thoại, máy tính bảng...).
   - product_type: Món đồ người dùng CẦN MUA: "laptop" / "máy tính xách tay" -> "laptop", "chuột" -> "mouse", "bàn phím" -> "keyboard", "tai nghe" -> "headphone", "loa" -> "speaker", "tay cầm" -> "gamepad", "hub chuyển đổi" -> "hub_adapter", "củ sạc" -> "charger", "cáp sạc" -> "cable", "pin dự phòng" -> "powerbank", "giá đỡ" -> "stand", "đế tản nhiệt" -> "cooler", "lót chuột" -> "mousepad".
   - KHI GẶP CÂU HỎI MUA MÁY TÍNH / LAPTOP / MACBOOK:
     + "mua laptop", "shop có macbook không", "cần laptop mỏng nhẹ", "máy tính xách tay", "macbook air" -> product_type: "laptop", user_device: null.
   - KHI GẶP CỤM TỪ PHỤ KIỆN / TRIỆU CHỨNG CÔNG NĂNG ĐI VỚI THIẾT BỊ (Universal Scenario Ontology):
     + "kê laptop", "nâng laptop", "đỡ laptop", "kê cao màn hình", "đỡ mỏi cổ", "đau vai gáy", "cúi đầu", "ngồi làm việc mỏi cổ", "chân đế", "giá đỡ" -> user_device: "laptop", product_type: "stand" (TUYỆT ĐỐI KHÔNG gán product_type: "laptop").
     + "sạc điện thoại", "sạc laptop", "hết pin", "sập nguồn", "đi công tác/du lịch không có ổ điện", "pin dự phòng" -> product_type: "powerbank" hoặc "charger".
     + "cắm vào laptop/macbook", "thiếu cổng USB/HDMI/Type-C", "chuyển đổi cổng", "xuất màn hình" -> product_type: "hub_adapter" hoặc "cable".
     + "chuột cho macbook", "bàn phím cho laptop", "chuột cắm máy tính" -> user_device: "laptop", product_type: "mouse" / "keyboard".
     + "di chuột mỏi tay", "đau cổ tay", "bấm không ồn ban đêm" -> product_type: "mouse".
     + "gõ văn bản/code mỏi tay", "gõ êm không ồn" -> product_type: "keyboard".
     + "họp trực tuyến", "phòng ồn", "nghe rõ giọng", "mic thu âm/đàm thoại" -> product_type: "headphone".
   - TUYỆT ĐỐI KHÔNG tự bịa đặt user_device hay desired_capabilities nếu câu hỏi người dùng không nhắc tới. Không sao chép các thông tin không có trong câu hỏi.

2. CHỨC NĂNG (desired_capabilities) & CHUẨN KẾT NỐI (device_compatibility):
   - desired_capabilities: Các khả năng/chức năng sản phẩm cần đáp ứng (ví dụ: "xuất hình ra màn HDMI", "chơi game", "sạc nhanh", "chống ồn", "làm mát tản nhiệt", "kê cao laptop").
   - device_compatibility: Các cổng hoặc chuẩn kết nối (ví dụ: "Type-C", "HDMI", "Bluetooth", "USB-A", "3.5mm").

3. ĐIỀU KIỆN PHỦ ĐỊNH & TÍNH NĂNG (attributes & negative_constraints):
   - MỆNH ĐỀ PHỦ ĐỊNH TÍNH NĂNG (Negative Feature Clauses):
     + Khi gặp cấu trúc "(không cần | không dùng | không lấy | không có | khỏi cần) + <tính năng X>" (ví dụ: "không cần quạt tản nhiệt"):
       Bắt buộc đưa vào negative_constraints: ["quạt tản nhiệt"], TUYỆT ĐỐI KHÔNG đưa vào desired_capabilities!
   - "không cần dây", "không dùng dây", "không dây", "wireless", "bluetooth" -> wireless: true, wired: false; negative_constraints: ["wired"].
   - "có dây", "cắm dây", "wired" -> wired: true, wireless: false; negative_constraints: ["wireless"].
   - "chơi game", "gaming", "game" -> gaming: true.
   - PHÂN BIỆT NGỮ CẢNH TỪ "ỒN":
     + Nếu người dùng nói "phòng ồn", "môi trường ồn", "nghe rõ trong phòng ồn", "lọc tiếng ồn mic" -> ĐÂY LÀ NHU CẦU TAI NGHE / ĐÀM THOẠI (anc: true, silent: false).
     + CHỈ đặt silent: true khi nói về bấm êm, gõ êm, click không ồn của chuột hoặc phím ("bấm không ồn", "click êm", "chuột silent", "gõ êm").
   - "chống ồn", "anc", "khử ồn" -> anc: true.
   - Các thuộc tính không nhắc đến: đặt false.

4. THƯƠNG HIỆU (brand):
   - "nhà táo", "hãng táo", "táo khuyết", "apple" -> brand: "Apple".
   - "sony" -> brand: "Sony".
   - "logitech", "logi" -> brand: "Logitech".
   - "ss" -> brand: "ss".
   - Không tự bịa thương hiệu nếu câu hỏi không có.

5. NGÂN SÁCH TỰ NHIÊN (VND):
   - "nửa triệu", "500k", "nửa tr", "nửa củ" -> max_price: 500000.
   - "triệu rưỡi", "1tr5" -> max_price: 1500000.
   - "2 củ", "2 triệu" -> max_price: 2000000.
   - "700 cành", "700k" -> max_price: 700000.
   - "đừng quá X", "không quá X", "dưới X", "tối đa X", "tầm X" -> max_price: X.

6. QUY TẮC HỎI LÀM RÕ (needs_clarification):
   - TUYỆT ĐỐI ĐẶT needs_clarification = false nếu người dùng đã nêu nhu cầu chức năng, thiết bị, thương hiệu, hoặc ngân sách. ĐÃ CÓ THÔNG TIN THÌ PHẢI TÌM KIẾM, KHÔNG ĐƯỢC HỎI LẠI!
   - CHỈ đặt needs_clarification = true khi:
     + Câu hỏi chỉ có từ viết tắt mơ hồ như "ss".
     + Câu hỏi hoàn toàn vô nghĩa (ví dụ: "tư vấn đi", "có gì hay không").

7. NGOÀI PHẠM VI KINH DOANH (is_out_of_domain):
   - Cửa hàng bán đồ công nghệ, thiết bị ngoại vi và phụ kiện.
   - CHỈ đặt is_out_of_domain = true khi hỏi các mặt hàng không thuộc công nghệ (quần áo, giày dép, đồ ăn, xe cộ, bất động sản).

8. CHỈ TRẢ VỀ JSON THUẦN TÚY, không có markdown hay văn bản giải thích.
"""


class IntentAnalyzer:
    """
    LLM-Powered Intent Analyzer for StoreFlow AI 2.0.
    Transforms natural language queries into strictly validated Pydantic intent objects.
    Features:
      1. Pluggable provider support (Local Ollama, Gemini Cloud, or Deterministic Rule Engine).
      2. Strict JSON validation & bounds checking via Pydantic schema.
      3. Ambiguity detector (e.g. 'ss' clarification rather than guessing).
      4. Safe fallback to deterministic rule-based extractor if LLM is unavailable or fails.
      5. Complete defense against arbitrary SQL injection or table hallucination.
    """

    def __init__(self):
        pass

    def analyze_intent(
        self,
        query: str,
        budget_input: Optional[float] = None,
        preferred_provider: Optional[str] = None
    ) -> UserQueryIntent:
        """
        Analyzes customer query and returns structured, validated UserQueryIntent.
        """
        # Step 0: Check for ambiguous abbreviations that always need clarification
        ambiguous_clarification = self._check_ambiguous_shortcuts(query)
        if ambiguous_clarification:
            return ambiguous_clarification

        # Step 1: Check out-of-domain first using domain guard
        if rag_service.is_out_of_domain(query):
            return UserQueryIntent(
                intent="out_of_domain",
                is_out_of_domain=True,
                source="domain_guard",
                confidence=1.0
            )

        # Step 2: Determine if we should call LLM
        target_provider = ai_provider_manager.get_provider(preferred_provider)
        if target_provider.name != "grounded":
            try:
                llm_intent = self._call_llm_for_intent(query, target_provider.name)
                if llm_intent:
                    # Reconcile LLM extraction with ground-truth verification
                    return self._reconcile_and_validate_intent(llm_intent, query, budget_input)
            except Exception as e:
                logger.warning(f"LLM Intent extraction with {target_provider.name} failed: {e}. Falling back to rule-based parser.")

        # Step 3: High-reliability Rule-based fallback
        return self._rule_based_analyze(query, budget_input)

    def _check_ambiguous_shortcuts(self, query: str) -> Optional[UserQueryIntent]:
        """
        Identifies ambiguous terms like 'ss' where guessing leads to bad UX.
        Promptly requests user clarification.
        """
        q_lower = query.lower()
        # Check for isolated 'ss' token
        if re.search(r"\b(ss)\b", q_lower):
            # Check if neither samsung nor steelseries is spelled out
            has_samsung = bool(re.search(r"\b(samsung|sam sung)\b", q_lower))
            has_steelseries = bool(re.search(r"\b(steelseries|steel series)\b", q_lower))
            if not has_samsung and not has_steelseries:
                return UserQueryIntent(
                    intent="general_inquiry",
                    needs_clarification=True,
                    clarification_question="Quý khách đang tìm kiếm sản phẩm của thương hiệu Samsung hay SteelSeries? Vui lòng làm rõ để cửa hàng có thể hỗ trợ tốt nhất!",
                    source="ambiguity_guard",
                    confidence=1.0
                )
        return None

    def _call_llm_for_intent(self, query: str, provider_name: str) -> Optional[UserQueryIntent]:
        """Calls the active LLM provider with strict JSON output contract."""
        user_prompt = f"Phân tích câu hỏi sau:\n\"{query}\""
        provider = ai_provider_manager.get_provider(provider_name)

        raw_output = provider.generate_text(
            prompt=user_prompt,
            system_instruction=INTENT_SYSTEM_PROMPT,
            temperature=0.1,  # Low temperature for deterministic JSON output
            max_tokens=512,
            format="json"     # Force JSON mode in Ollama
        )

        return self._parse_and_validate_json(raw_output, provider_name)

    def _parse_and_validate_json(self, raw_text: str, source: str) -> Optional[UserQueryIntent]:
        """Extracts JSON substring, parses, and validates with Pydantic UserQueryIntent."""
        if not raw_text:
            return None

        clean_text = raw_text.strip()
        # Strip markdown fences if present
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()

        # Extract first JSON object bounded by { and }
        start_idx = clean_text.find("{")
        end_idx = clean_text.rfind("}")
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            return None

        json_str = clean_text[start_idx:end_idx + 1]
        try:
            parsed_dict = json.loads(json_str)
        except json.JSONDecodeError:
            return None

        # Sanitize attributes dictionary
        raw_attrs = parsed_dict.get("attributes")
        attrs = {}
        if isinstance(raw_attrs, dict):
            for k, v in raw_attrs.items():
                if isinstance(v, bool):
                    attrs[k] = v

        # Price bounds validation
        min_p = parsed_dict.get("min_price")
        max_p = parsed_dict.get("max_price")
        if min_p is not None:
            try:
                min_p = float(min_p)
                if min_p < 0:
                    min_p = None
            except (ValueError, TypeError):
                min_p = None

        if max_p is not None:
            try:
                max_p = float(max_p)
                if max_p < 0:
                    max_p = None
            except (ValueError, TypeError):
                max_p = None

        if min_p is not None and max_p is not None and min_p > max_p:
            min_p, max_p = max_p, min_p  # Swap if inverted

        # Generalized list fields
        def _clean_str_list(val: Any) -> List[str]:
            if isinstance(val, list):
                return [str(x).strip() for x in val if x and isinstance(x, (str, int, float))]
            elif isinstance(val, str) and val.strip():
                return [val.strip()]
            return []

        desired_caps = _clean_str_list(parsed_dict.get("desired_capabilities"))
        device_compats = _clean_str_list(parsed_dict.get("device_compatibility"))
        req_attrs = _clean_str_list(parsed_dict.get("required_attributes"))
        pref_attrs = _clean_str_list(parsed_dict.get("preferred_attributes"))
        neg_constraints = _clean_str_list(parsed_dict.get("negative_constraints"))
        user_dev = parsed_dict.get("user_device")
        if isinstance(user_dev, str) and user_dev.strip():
            user_dev = user_dev.strip().lower()
        else:
            user_dev = None

        return UserQueryIntent(
            intent=str(parsed_dict.get("intent") or "search_products"),
            brand=parsed_dict.get("brand") if isinstance(parsed_dict.get("brand"), str) else None,
            product_type=parsed_dict.get("product_type") if isinstance(parsed_dict.get("product_type"), str) else None,
            user_device=user_dev,
            desired_capabilities=desired_caps,
            device_compatibility=device_compats,
            required_attributes=req_attrs,
            preferred_attributes=pref_attrs,
            negative_constraints=neg_constraints,
            attributes=attrs,
            min_price=min_p,
            max_price=max_p,
            needs_clarification=bool(parsed_dict.get("needs_clarification", False)),
            clarification_question=parsed_dict.get("clarification_question") if isinstance(parsed_dict.get("clarification_question"), str) else None,
            is_out_of_domain=bool(parsed_dict.get("is_out_of_domain", False)),
            confidence=0.95,
            source=f"llm_{source}"
        )

    def _reconcile_and_validate_intent(
        self,
        intent: UserQueryIntent,
        query: str,
        budget_input: Optional[float] = None
    ) -> UserQueryIntent:
        """
        Reconciles LLM extracted intent with ground truth verifications:
        1. Grounding check on product_type: Discards hallucinated product_type if query has no lexical evidence.
        2. Functional capabilities & compatibility extraction: Supplements capabilities from query.
        3. Fixes negative attribute phrasing (e.g. 'không cần dây' -> wireless=True, wired=False).
        4. Protects against brand hallucinations (e.g. 'nhà táo' -> Apple, not Samsung).
        5. Suppresses unwarranted clarification questions if actionable info exists.
        6. Reconciles natural Vietnamese budgets.
        """
        q_lower = query.lower()
        pos_query, extracted_neg_clauses = extract_negative_feature_clauses(query)
        pos_lower = pos_query.lower()

        # 1. Grounding check on boolean attributes & negative constraints:
        has_wireless_mention = bool(re.search(r"\b(không cần dây|không dùng dây|không có dây|không dây|wireless|bluetooth|tws|2\.4ghz)\b", q_lower))
        has_wired_mention = bool(re.search(r"\b(có dây|cắm dây|cắm usb|dây cáp|dây cắm|wired)\b", q_lower)) and not has_wireless_mention

        has_wireless_neg = bool(re.search(r"\b(không (?:dùng|cần|muốn|thích)?\s*(?:bluetooth|không dây|wireless))\b", q_lower))
        has_wired_neg = bool(re.search(r"\b(không (?:dùng|cần|muốn|thích)?\s*(?:loại\s*)?(?:có dây|dây cáp|dây lằng nhằng))\b", q_lower)) or bool(re.search(r"\b(không cần dây|không dùng dây|không có dây)\b", q_lower))

        # Sanitize LLM-provided negative constraints against actual query evidence & incorporate extracted negative clauses
        sanitized_neg = []
        for neg in intent.negative_constraints:
            neg_l = neg.lower().strip()
            if neg_l in ("wired", "có dây", "dây") and (has_wireless_mention or has_wired_neg):
                if "wired" not in sanitized_neg:
                    sanitized_neg.append("wired")
            elif neg_l in ("wireless", "không dây", "bluetooth") and (has_wired_mention or has_wireless_neg):
                if "wireless" not in sanitized_neg:
                    sanitized_neg.append("wireless")
            elif neg_l in q_lower:
                sanitized_neg.append(neg)

        for enc in extracted_neg_clauses:
            if enc not in sanitized_neg:
                sanitized_neg.append(enc)

        intent.negative_constraints = sanitized_neg

        # Only add wired/wireless negative constraints for relevant peripheral devices
        if (has_wireless_mention or has_wired_neg) and intent.product_type in ("mouse", "keyboard", "headphone") and "wired" not in intent.negative_constraints:
            intent.negative_constraints.append("wired")
        elif (has_wired_mention or has_wireless_neg) and intent.product_type in ("mouse", "keyboard", "headphone") and "wireless" not in intent.negative_constraints:
            intent.negative_constraints.append("wireless")

        has_battery_neg = bool(re.search(r"\b(không (?:dùng|cần|chơi|xài|muốn)?\s*(?:loại\s*)?(?:pin tiểu|pin aa|pin aaa|pin rời)|tuyệt đối không (?:dùng|chơi|xài)?\s*pin tiểu)\b", q_lower))
        if has_battery_neg and "pin tiểu" not in intent.negative_constraints:
            intent.negative_constraints.append("pin tiểu")

        intent.attributes["wireless"] = has_wireless_mention or has_wired_neg
        intent.attributes["wired"] = has_wired_mention or has_wireless_neg
        intent.attributes["gaming"] = bool(re.search(r"\b(gaming|chơi game|game|esport)\b", q_lower))
        # Noise Disambiguation: distinguish room/ambient noise (headphone/mic need) vs quiet click/typing (mouse/keyboard need)
        is_room_noise = bool(re.search(r"\b(phòng (?:khá\s*)?ồn|môi trường (?:khá\s*)?ồn|xung quanh (?:khá\s*)?ồn|tiếng ồn bên ngoài|phòng ồn)\b", q_lower))
        is_click_silent = bool(re.search(r"\b(bấm không ồn|click êm|gõ không ồn|không kêu lách cách|chống ồn click|không gây tiếng click|chuột êm|chuột yên tĩnh|phím yên tĩnh|chuột silent|phím silent)\b", q_lower))

        if is_click_silent:
            intent.attributes["silent"] = True
        elif is_room_noise and not any(k in q_lower for k in ["chuột", "phím", "click", "bấm", "gõ"]):
            intent.attributes["silent"] = False
        else:
            intent.attributes["silent"] = bool(re.search(r"\b(silent|yên tĩnh|không ồn|không ồn ào|không kêu|không tiếng|không lách cách|chống ồn click|bấm không ồn|gõ không ồn)\b", q_lower)) and not is_room_noise

        intent.attributes["anc"] = bool(re.search(r"\b(chống ồn|anc|khử ồn|noise cancel)\b", q_lower)) and not bool(re.search(r"\b(chống ồn click)\b", q_lower))
        intent.attributes["mechanical"] = bool(re.search(r"\b(cơ|phím cơ|switch|cherry|blue switch|red switch|brown switch)\b", q_lower))
        intent.attributes["ergonomic"] = bool(re.search(r"\b(công thái học|ergonomic|chống mỏi)\b", q_lower))

        # Audio / Meeting Scenario Detection
        has_audio_scenario = bool(re.search(
            r"\b(họp trực tuyến|họp online|zoom|meet|teams|đàm thoại|nghe rõ|nghe giọng|nghe tiếng|giọng người|lọc tiếng ồn mic|lọc ồn mic|mic lọc ồn|cách âm|chống ồn khi nghe|nghe trong phòng ồn)\b",
            q_lower
        )) or (
            bool(re.search(r"\b(họp|đàm thoại|gọi điện|voice|call)\b", q_lower)) and
            bool(re.search(r"\b(nghe|ồn|tiếng|mic|âm thanh|tai)\b", q_lower))
        )

        # 2. Grounding check on LLM product_type & Universal Scenario Ontology
        # Decouple host device (phone, tablet, pc) or laptop WHEN an accessory is being sought
        is_accessory_query = any(k in pos_lower for k in [
            "chuột", "phím", "bàn phím", "tai nghe", "loa", "tay cầm", "hub", "cáp", "sạc", "củ sạc",
            "pin dự phòng", "giá đỡ", "kê", "đỡ", "tản nhiệt", "lót chuột", "pad chuột", "cắm vào", "cho"
        ])
        if intent.product_type:
            pt_clean = intent.product_type.lower().strip()
            if pt_clean in ("phone", "điện thoại", "pc", "máy bàn", "tablet", "ipad"):
                if not intent.user_device:
                    intent.user_device = "phone" if pt_clean in ("phone", "điện thoại") else pt_clean
                intent.product_type = None
            elif pt_clean in ("laptop", "macbook", "máy tính"):
                if is_accessory_query:
                    if not intent.user_device:
                        intent.user_device = "macbook" if ("macbook" in q_lower or pt_clean == "macbook") else "laptop"
                    elif intent.user_device == "laptop" and "macbook" in q_lower:
                        intent.user_device = "macbook"
                    intent.product_type = None
                else:
                    intent.product_type = "laptop"

        type_keywords_map = {
            "laptop": ["laptop", "máy tính xách tay", "macbook", "notebook", "ultrabook"],
            "mouse": ["chuột", "mouse", "con chuột", "di chuột mỏi tay", "đau cổ tay"],
            "keyboard": ["bàn phím", "keyboard", "phím cơ", "phím", "keycap", "switch", "gõ văn bản", "đánh máy", "gõ máy tính", "gõ code", "soạn thảo", "đồ để gõ"],
            "headphone": [
                "tai nghe", "headphone", "earphone", "earbuds", "tws",
                "họp trực tuyến", "họp online", "zoom", "meet", "teams", "đàm thoại",
                "nghe rõ", "giọng người", "mic đàm thoại", "lọc ồn mic", "mic lọc ồn", "nghe giọng", "phòng khá ồn", "phòng ồn"
            ],
            "speaker": ["loa", "speaker", "soundbar"],
            "gamepad": ["tay cầm", "gamepad", "controller"],
            "cooler": ["tản nhiệt", "cooler"],
            "mousepad": ["lót chuột", "tấm lót chuột", "bàn di chuột", "pad chuột", "mousepad"],
            "hub_adapter": ["hub", "chuyển đổi", "adapter", "dock", "thiếu cổng", "thêm cổng", "xuất màn hình"],
            "charger": ["củ sạc", "cốc sạc"],
            "cable": ["dây cáp", "cáp sạc", "dây sạc"],
            "powerbank": ["pin dự phòng", "sạc dự phòng", "powerbank", "hết pin", "sập nguồn"],
            "stand": [
                "giá đỡ", "stand", "chân đế", "kê laptop", "nâng laptop", "đỡ laptop",
                "kê cao laptop", "kê máy", "nâng máy", "đỡ máy", "kê cao màn hình",
                "đỡ mỏi cổ", "đau vai gáy", "mỏi cổ", "mỏi vai gáy", "cúi đầu", "ngồi làm việc mỏi cổ"
            ],
            "smarthome": ["đèn", "đồng hồ", "cân", "quạt"],
        }
        if intent.product_type:
            pt_norm = intent.product_type.lower().strip()
            if pt_norm in type_keywords_map:
                if not any(k in q_lower for k in type_keywords_map[pt_norm]):
                    # Query does NOT mention this product type -> LLM hallucinated it from host device!
                    intent.product_type = None
            elif pt_norm not in q_lower:
                intent.product_type = None

        # Scenario detectors
        has_stand_keywords = any(k in pos_lower for k in [
            "giá đỡ", "chân đế", "kê laptop", "nâng laptop", "đỡ laptop", "kê cao laptop",
            "kê máy", "nâng máy", "đỡ máy", "kê cao màn hình", "nâng cao màn hình"
        ])
        has_neck_strain = bool(re.search(r"\b(mỏi cổ|đỡ mỏi cổ|đau vai gáy|mỏi vai gáy|cúi đầu|ngồi làm việc mỏi cổ)\b(?!\s*tay\b)", pos_lower))
        is_stand_scenario = (has_stand_keywords or has_neck_strain) and not any(k in pos_lower for k in ["chuột", "mouse", "bàn phím", "keyboard", "cổ tay", "mỏi tay"])

        is_mouse_scenario = (
            any(k in pos_lower for k in ["chuột", "con chuột", "mouse", "di chuột mỏi tay", "đau cổ tay", "chuột công thái học", "bấm không ồn", "click êm", "chuột silent"]) and
            not any(k in pos_lower for k in ["lót chuột", "tấm lót chuột", "bàn di chuột", "pad chuột"])
        )
        is_powerbank_scenario = any(k in pos_lower for k in [
            "pin dự phòng", "sạc dự phòng", "powerbank", "pin sạc dự phòng",
            "hết pin", "sập nguồn", "không có ổ điện", "không có ổ cắm",
            "đi công tác không có ổ điện", "du lịch không có ổ điện", "dự phòng pin"
        ])
        is_hub_scenario = any(k in pos_lower for k in [
            "hub", "chuyển đổi", "đầu chuyển", "cáp chuyển", "adapter", "dock",
            "cắm vào macbook", "cắm vào laptop", "thiếu cổng", "thêm cổng",
            "xuất màn hình", "xuất hình ra", "nối ra màn"
        ])

        # If negative constraint forbids cooler, clear accidental cooler classification
        has_cooler_in_neg = any(k in [n.lower() for n in intent.negative_constraints] for k in ["quạt tản nhiệt", "tản nhiệt", "cooler", "quạt"])
        if has_cooler_in_neg and intent.product_type == "cooler":
            intent.product_type = "stand" if is_stand_scenario else None

        is_laptop_scenario = (
            bool(re.search(r"\b(laptop|máy tính xách tay|notebook|ultrabook|mua macbook|bán macbook|có macbook không|cần macbook|tư vấn macbook|macbook air|macbook pro)\b", pos_lower)) and
            not is_stand_scenario and
            not (has_cooler_in_neg is False and any(k in pos_lower for k in ["tản nhiệt", "cooler"])) and
            not is_hub_scenario and
            not is_mouse_scenario and
            not any(k in pos_lower for k in ["chuột", "phím", "tai nghe", "củ sạc", "cáp", "lót chuột", "kê", "đỡ"])
        )

        # Override product_type if query explicitly names one with high precision or describes implicit functional scenario
        if re.search(r"\b(lót chuột|tấm lót chuột|bàn di chuột|pad chuột)\b", pos_lower):
            intent.product_type = "mousepad"
        elif is_stand_scenario:
            intent.product_type = "stand"
            if not intent.user_device and any(k in q_lower for k in ["laptop", "macbook", "máy tính"]):
                intent.user_device = "laptop"
        elif is_powerbank_scenario:
            intent.product_type = "powerbank"
        elif is_hub_scenario:
            intent.product_type = "hub_adapter"
        elif is_laptop_scenario:
            intent.product_type = "laptop"
        elif re.search(r"\b(củ sạc|cốc sạc)\b", pos_lower):
            intent.product_type = "charger"
        elif re.search(r"\b(dây cáp|cáp sạc|dây sạc)\b", pos_lower):
            intent.product_type = "cable"
        elif is_mouse_scenario:
            intent.product_type = "mouse"
        elif re.search(r"\b(tai nghe|headphone|earbuds)\b", pos_lower) or (has_audio_scenario and not any(k in pos_lower for k in ["chuột", "bàn phím", "pad chuột", "lót chuột", "củ sạc", "cáp sạc"])):
            intent.product_type = "headphone"
        elif any(k in pos_lower for k in ["bàn phím", "phím cơ", "keyboard", "gõ văn bản", "đánh máy", "gõ máy tính", "gõ code", "soạn thảo", "đồ để gõ"]) and not any(k in pos_lower for k in ["lót chuột", "bàn di chuột", "pad chuột", "lót bàn phím"]):
            intent.product_type = "keyboard"
        elif re.search(r"\b(loa|speaker|soundbar)\b", pos_lower):
            intent.product_type = "speaker"
        elif re.search(r"\b(tay cầm|gamepad)\b", pos_lower) and not re.search(r"\b(chuột)\b", pos_lower):
            intent.product_type = "gamepad"
        elif re.search(r"\b(tản nhiệt|đế tản nhiệt)\b", pos_lower) and not has_cooler_in_neg:
            intent.product_type = "cooler"

        if has_audio_scenario and not any(k in q_lower for k in ["chuột", "bàn phím", "pad chuột"]):
            if "họp trực tuyến đàm thoại" not in intent.desired_capabilities:
                intent.desired_capabilities.append("họp trực tuyến đàm thoại")
        if is_stand_scenario:
            if "giá đỡ laptop nâng hạ độ cao công thái học" not in intent.desired_capabilities:
                intent.desired_capabilities.append("giá đỡ laptop nâng hạ độ cao công thái học")

        # 3. Grounding check on desired_capabilities, device_compatibility, and user_device:
        # Purge any LLM hallucinations that have zero evidence in the query or that violate negative constraints
        stop_words = {"cho", "của", "để", "ra", "vào", "các", "những", "và", "với", "được", "có", "màn", "mình", "tôi", "em", "shop"}
        def _cap_has_evidence(c_text: str) -> bool:
            sig_words = [w for w in re.findall(r"\w+", c_text.lower()) if len(w) >= 2 and w not in stop_words]
            return any(w in q_lower for w in sig_words) if sig_words else False

        # Remove capabilities that conflict with negative constraints (e.g. 'quạt tản nhiệt')
        clean_caps = []
        for c in intent.desired_capabilities:
            c_l = c.lower()
            if has_cooler_in_neg and any(k in c_l for k in ["quạt", "tản nhiệt", "cooler"]):
                continue
            if _cap_has_evidence(c) or (is_stand_scenario and "giá đỡ" in c_l):
                clean_caps.append(c)
        intent.desired_capabilities = clean_caps

        def _compat_has_evidence(comp_text: str) -> bool:
            c_l = comp_text.lower().strip()
            if "hdmi" in c_l:
                return "hdmi" in q_lower
            if "type-c" in c_l or "usb-c" in c_l:
                return bool(re.search(r"\b(type-c|type c|usb-c)\b", q_lower))
            if "bluetooth" in c_l:
                return bool(re.search(r"\b(bluetooth|không dây|wireless|tws)\b", q_lower))
            if "usb-a" in c_l or "usb 3" in c_l or "usb" in c_l:
                return bool(re.search(r"\b(usb|usb-a|usb 3)\b", q_lower))
            if "lan" in c_l or "rj45" in c_l or "ethernet" in c_l:
                return bool(re.search(r"\b(lan|rj45|ethernet|mạng)\b", q_lower))
            if "3.5" in c_l or "aux" in c_l:
                return bool(re.search(r"\b(3\.5|aux|jack)\b", q_lower))
            return c_l in q_lower

        intent.device_compatibility = [c for c in intent.device_compatibility if _compat_has_evidence(c)]

        # Filter out boolean attribute keywords from desired_capabilities (e.g. 'game', 'gaming', 'silent', 'wireless')
        attr_cap_keywords = {"game", "gaming", "chơi game", "silent", "im lặng", "không ồn", "không dây", "wireless", "có dây", "wired"}
        intent.desired_capabilities = [
            c for c in intent.desired_capabilities
            if c.lower().strip() not in attr_cap_keywords
        ]

        if intent.user_device:
            host_device_terms = ["laptop", "macbook", "máy tính", "điện thoại", "iphone", "ipad", "tablet", "pc", "máy bàn", "tivi"]
            if not any(k in q_lower for k in host_device_terms):
                intent.user_device = None

        # Supplement verified capabilities & compatibility from rule parser
        reqs = parse_query_requirements(query)
        for cap in reqs.get("desired_capabilities", []):
            if cap not in intent.desired_capabilities:
                intent.desired_capabilities.append(cap)
        for comp in reqs.get("device_compatibility", []):
            if comp not in intent.device_compatibility:
                intent.device_compatibility.append(comp)
        if reqs.get("user_device"):
            if not intent.user_device or (intent.user_device == "laptop" and reqs["user_device"] == "macbook"):
                intent.user_device = reqs["user_device"]

        # Override product_type if rule ontology locks onto specific accessory scenario (hub, powerbank, stand)
        rule_target_type = reqs.get("target_type")
        if rule_target_type in ("hub_adapter", "powerbank", "stand", "mousepad", "cooler"):
            intent.product_type = rule_target_type
        elif not intent.product_type and rule_target_type:
            intent.product_type = rule_target_type

        # 4. Brand verification & hallucination guard
        # Strictly rely on ground-truth brand extractor; discard hallucinated brands or owned host device brands
        extracted_brand = extract_brand_from_query(query)
        if extracted_brand:
            intent.brand = extracted_brand["canonical_name"]
        else:
            intent.brand = None

        # 5. Attributes synchronization (silent click, ergonomics)
        if reqs.get("is_silent"):
            intent.attributes["silent"] = True
        if reqs.get("is_ergonomic"):
            intent.attributes["ergonomic"] = True

        # 6. Budget reconciliation
        resolved_budget = resolve_effective_budget(query, budget_input)
        if resolved_budget:
            intent.max_price = resolved_budget
        elif intent.max_price and budget_input:
            intent.max_price = min(intent.max_price, budget_input)
        elif budget_input:
            intent.max_price = budget_input

        # 7. Suppress unwarranted clarification if actionable info exists
        has_actionable_target = bool(intent.product_type or intent.brand or intent.desired_capabilities or intent.max_price)
        is_isolated_ss = bool(re.search(r"\b(ss)\b", q_lower)) and not bool(re.search(r"\b(samsung|steelseries)\b", q_lower))

        if has_actionable_target and not is_isolated_ss:
            intent.needs_clarification = False
            intent.clarification_question = None

        # 8. Intent classification alignment
        if intent.brand and not intent.product_type and not intent.desired_capabilities:
            intent.intent = "check_brand"
        elif intent.product_type or intent.desired_capabilities or intent.max_price:
            intent.intent = "search_products"

        # 9. Domain guard reconciliation
        if intent.product_type or intent.brand or intent.desired_capabilities or not rag_service.is_out_of_domain(query):
            intent.is_out_of_domain = False
            if intent.intent == "out_of_domain":
                intent.intent = "search_products"
        else:
            intent.is_out_of_domain = True
            intent.intent = "out_of_domain"

        return intent

    def _rule_based_analyze(self, query: str, budget_input: Optional[float] = None) -> UserQueryIntent:
        """
        Deterministic, robust Rule-based Intent Extractor.
        Guarantees that all known catalog types, brands, attributes, and budgets
        are parsed accurately without relying on external network or cloud models.
        """
        effective_budget = resolve_effective_budget(query, budget_input)
        reqs = parse_query_requirements(query)
        brand_info = extract_brand_from_query(query)

        brand_canonical = brand_info["canonical_name"] if brand_info else None
        target_type = reqs.get("target_type")

        # Map boolean attributes
        attributes = {
            "gaming": bool(reqs.get("is_gaming")),
            "wireless": bool(reqs.get("is_wireless")),
            "wired": bool(reqs.get("is_wired")),
            "mechanical": bool(reqs.get("is_mechanical")),
            "silent": bool(reqs.get("is_silent")),
            "anc": bool(reqs.get("is_anc")),
            "ergonomic": bool(reqs.get("is_ergonomic")),
        }

        negative_constraints = list(reqs.get("negative_constraints") or [])
        if reqs.get("target_type") in ("mouse", "keyboard", "headphone") and reqs.get("is_wireless") and not reqs.get("is_wired") and "wired" not in negative_constraints:
            negative_constraints.append("wired")
        elif reqs.get("target_type") in ("mouse", "keyboard", "headphone") and reqs.get("is_wired") and not reqs.get("is_wireless") and "wireless" not in negative_constraints:
            negative_constraints.append("wireless")

        if bool(re.search(r"\b(không (?:dùng|cần|chơi|xài|muốn)?\s*(?:loại\s*)?(?:pin tiểu|pin aa|pin aaa|pin rời)|tuyệt đối không (?:dùng|chơi|xài)?\s*pin tiểu)\b", query.lower())) and "pin tiểu" not in negative_constraints:
            negative_constraints.append("pin tiểu")

        # Check out of domain
        if rag_service.is_out_of_domain(query):
            return UserQueryIntent(
                intent="out_of_domain",
                brand=None,
                product_type=None,
                user_device=None,
                desired_capabilities=[],
                device_compatibility=[],
                required_attributes=[],
                negative_constraints=[],
                attributes=attributes,
                min_price=None,
                max_price=effective_budget,
                needs_clarification=False,
                clarification_question=None,
                is_out_of_domain=True,
                confidence=1.0,
                source="rule_based"
            )

        # Determine intent type
        if brand_canonical and not target_type and not reqs.get("desired_capabilities"):
            intent = "check_brand"
        else:
            intent = "search_products"

        # Check for vague queries that lack specific product type, brand, capability, or budget
        q_clean = query.strip().lower()
        has_actionable_spec = bool(target_type or brand_canonical or reqs.get("desired_capabilities") or reqs.get("device_compatibility") or effective_budget)
        needs_clarification = False
        clarification_q = None
        if not has_actionable_spec and any(k in q_clean for k in ["tư vấn", "gợi ý", "có gì hay", "đồ công nghệ", "sản phẩm tốt", "gợi ý đồ", "hàng tốt"]):
            needs_clarification = True
            clarification_q = "Quý khách đang quan tâm đến dòng sản phẩm nào (chuột, bàn phím cơ, tai nghe, hay phụ kiện)? Vui lòng cho biết thêm mức ngân sách mong muốn nhé!"

        return UserQueryIntent(
            intent=intent,
            brand=brand_canonical,
            product_type=target_type,
            user_device=reqs.get("user_device"),
            desired_capabilities=reqs.get("desired_capabilities") or [],
            device_compatibility=reqs.get("device_compatibility") or [],
            required_attributes=[],
            negative_constraints=negative_constraints,
            attributes=attributes,
            min_price=None,
            max_price=effective_budget,
            needs_clarification=needs_clarification,
            clarification_question=clarification_q,
            is_out_of_domain=False,
            confidence=1.0,
            source="rule_based"
        )


intent_analyzer = IntentAnalyzer()
