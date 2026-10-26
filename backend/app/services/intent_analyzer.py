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
1. PHÂN BIỆT THIẾT BỊ NGƯỜI DÙNG ĐANG CÓ (user_device) VÀ SẢN PHẨM CẦN MUA (product_type):
   - user_device: Thiết bị người dùng ĐANG SỞ HỮU (ví dụ: máy tính, điện thoại, máy tính bảng...).
   - product_type: Món đồ người dùng CẦN MUA.
   - CHỈ điền product_type khi người dùng gọi tên rõ ràng loại sản phẩm muốn mua: "chuột" -> "mouse", "bàn phím" -> "keyboard", "tai nghe" -> "headphone", "loa" -> "speaker", "tay cầm" -> "gamepad", "hub chuyển đổi" -> "hub_adapter", "củ sạc" -> "charger", "cáp sạc" -> "cable", "pin dự phòng" -> "powerbank", "giá đỡ" -> "stand", "đế tản nhiệt" -> "cooler", "lót chuột" -> "mousepad".
   - Nếu người dùng chỉ mô tả nhu cầu, sự cố hoặc chức năng (ví dụ: gõ văn bản, sạc nhanh, xuất hình): ĐẶT product_type tương ứng nếu rõ ràng hoặc null và trích xuất vào desired_capabilities.
   - TUYỆT ĐỐI KHÔNG tự bịa đặt user_device hay desired_capabilities nếu câu hỏi người dùng không nhắc tới. Không sao chép các thông tin không có trong câu hỏi.

2. CHỨC NĂNG (desired_capabilities) & CHUẨN KẾT NỐI (device_compatibility):
   - desired_capabilities: Các khả năng/chức năng sản phẩm cần đáp ứng (ví dụ: "xuất hình ra màn HDMI", "chơi game", "sạc nhanh", "chống ồn", "làm mát tản nhiệt", "kê cao laptop").
   - device_compatibility: Các cổng hoặc chuẩn kết nối (ví dụ: "Type-C", "HDMI", "Bluetooth", "USB-A", "3.5mm").

3. ĐIỀU KIỆN PHỦ ĐỊNH & TÍNH NĂNG (attributes & negative_constraints):
   - "không cần dây", "không dùng dây", "không dây", "wireless", "bluetooth" -> wireless: true, wired: false; negative_constraints: ["wired"].
   - "có dây", "cắm dây", "wired" -> wired: true, wireless: false; negative_constraints: ["wireless"].
   - "chơi game", "gaming", "game" -> gaming: true.
   - "không ồn", "silent", "êm" -> silent: true.
   - "chống ồn", "anc" -> anc: true.
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
        if not isinstance(user_dev, str) or not user_dev.strip():
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

        # 1. Grounding check on boolean attributes & negative constraints:
        has_wireless_mention = bool(re.search(r"\b(không cần dây|không dùng dây|không có dây|không dây|wireless|bluetooth|tws|2\.4ghz|pin sạc)\b", q_lower))
        has_wired_mention = bool(re.search(r"\b(có dây|cắm dây|cắm usb|dây cáp|dây cắm|wired)\b", q_lower)) and not has_wireless_mention

        has_wireless_neg = bool(re.search(r"\b(không (?:dùng|cần|muốn|thích)?\s*(?:bluetooth|không dây|wireless))\b", q_lower))
        has_wired_neg = bool(re.search(r"\b(không (?:dùng|cần|muốn|thích)?\s*(?:loại\s*)?(?:có dây|dây cáp|dây lằng nhằng))\b", q_lower)) or bool(re.search(r"\b(không cần dây|không dùng dây|không có dây)\b", q_lower))

        # Sanitize LLM-provided negative constraints against actual query evidence
        sanitized_neg = []
        for neg in intent.negative_constraints:
            neg_l = str(neg).lower().strip()
            if neg_l in ("wired", "có dây", "dây") and (has_wireless_mention or has_wired_neg):
                if "wired" not in sanitized_neg:
                    sanitized_neg.append("wired")
            elif neg_l in ("wireless", "không dây", "bluetooth") and (has_wired_mention or has_wireless_neg):
                if "wireless" not in sanitized_neg:
                    sanitized_neg.append("wireless")
            elif neg_l in q_lower:
                sanitized_neg.append(neg)
        intent.negative_constraints = sanitized_neg

        if (has_wireless_mention or has_wired_neg) and "wired" not in intent.negative_constraints:
            intent.negative_constraints.append("wired")
        elif (has_wired_mention or has_wireless_neg) and "wireless" not in intent.negative_constraints:
            intent.negative_constraints.append("wireless")

        has_battery_neg = bool(re.search(r"\b(không (?:dùng|cần|chơi|xài|muốn)?\s*(?:loại\s*)?(?:pin tiểu|pin aa|pin aaa|pin rời)|tuyệt đối không (?:dùng|chơi|xài)?\s*pin tiểu)\b", q_lower))
        if has_battery_neg and "pin tiểu" not in intent.negative_constraints:
            intent.negative_constraints.append("pin tiểu")

        intent.attributes["wireless"] = has_wireless_mention or has_wired_neg
        intent.attributes["wired"] = has_wired_mention or has_wireless_neg
        intent.attributes["gaming"] = bool(re.search(r"\b(gaming|chơi game|game|esport)\b", q_lower))
        intent.attributes["silent"] = bool(re.search(r"\b(silent|êm|yên tĩnh|không ồn|không ồn ào|không kêu|không tiếng|không lách cách|chống ồn click|bấm êm)\b", q_lower))
        intent.attributes["anc"] = bool(re.search(r"\b(chống ồn|anc|khử ồn|noise cancel)\b", q_lower)) and not bool(re.search(r"\b(chống ồn click)\b", q_lower))
        intent.attributes["mechanical"] = bool(re.search(r"\b(cơ|phím cơ|switch|cherry|blue switch|red switch|brown switch)\b", q_lower))
        intent.attributes["ergonomic"] = bool(re.search(r"\b(công thái học|ergonomic|chống mỏi)\b", q_lower))

        # 2. Grounding check on LLM product_type: Purge hallucinated types
        type_keywords_map = {
            "mouse": ["chuột", "mouse", "con chuột"],
            "keyboard": ["bàn phím", "keyboard", "phím cơ", "phím", "keycap", "switch", "gõ văn bản", "đánh máy", "gõ máy tính", "gõ code", "soạn thảo", "đồ để gõ"],
            "headphone": ["tai nghe", "headphone", "earphone", "earbuds", "tws"],
            "speaker": ["loa", "speaker", "soundbar"],
            "gamepad": ["tay cầm", "gamepad", "controller"],
            "cooler": ["tản nhiệt", "cooler"],
            "mousepad": ["lót chuột", "tấm lót chuột", "bàn di chuột", "pad chuột", "mousepad"],
            "hub_adapter": ["hub", "chuyển đổi", "adapter", "dock"],
            "charger": ["củ sạc", "cốc sạc"],
            "cable": ["dây cáp", "cáp sạc", "dây sạc"],
            "powerbank": ["pin dự phòng", "sạc dự phòng", "powerbank"],
            "stand": ["giá đỡ", "stand", "chân đế"],
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

        # Override product_type if query explicitly names one with high precision
        if re.search(r"\b(lót chuột|tấm lót chuột|bàn di chuột|pad chuột)\b", q_lower):
            intent.product_type = "mousepad"
        elif re.search(r"\b(chuột|con chuột|mouse)\b", q_lower) and not any(k in q_lower for k in ["lót chuột", "bàn di chuột", "pad chuột"]):
            intent.product_type = "mouse"
        elif re.search(r"\b(tai nghe|headphone|earbuds)\b", q_lower):
            intent.product_type = "headphone"
        elif any(k in q_lower for k in ["bàn phím", "phím cơ", "keyboard", "gõ văn bản", "đánh máy", "gõ máy tính", "gõ code", "soạn thảo", "đồ để gõ"]) and not any(k in q_lower for k in ["lót chuột", "bàn di chuột", "pad chuột", "lót bàn phím"]):
            intent.product_type = "keyboard"
        elif re.search(r"\b(loa|speaker|soundbar)\b", q_lower):
            intent.product_type = "speaker"
        elif re.search(r"\b(tay cầm|gamepad)\b", q_lower) and not re.search(r"\b(chuột)\b", q_lower):
            intent.product_type = "gamepad"
        elif re.search(r"\b(tản nhiệt|đế tản nhiệt)\b", q_lower):
            intent.product_type = "cooler"
        elif re.search(r"\b(hub|chuyển đổi|adapter|dock)\b", q_lower):
            intent.product_type = "hub_adapter"
        elif re.search(r"\b(giá đỡ|chân đế|kê laptop)\b", q_lower):
            intent.product_type = "stand"
        elif re.search(r"\b(pin dự phòng|sạc dự phòng|powerbank)\b", q_lower):
            intent.product_type = "powerbank"

        # 3. Grounding check on desired_capabilities, device_compatibility, and user_device:
        # Purge any LLM hallucinations that have zero evidence in the query
        stop_words = {"cho", "của", "để", "ra", "vào", "các", "những", "và", "với", "được", "có", "màn", "mình", "tôi", "em", "shop"}
        def _cap_has_evidence(c_text: str) -> bool:
            sig_words = [w for w in re.findall(r"\w+", c_text.lower()) if len(w) >= 2 and w not in stop_words]
            return any(w in q_lower for w in sig_words) if sig_words else False

        intent.desired_capabilities = [c for c in intent.desired_capabilities if _cap_has_evidence(c)]

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
        if reqs.get("user_device") and not intent.user_device:
            intent.user_device = reqs["user_device"]

        # 4. Brand verification & hallucination guard
        extracted_brand = extract_brand_from_query(query)
        if extracted_brand:
            intent.brand = extracted_brand["canonical_name"]
        elif intent.brand:
            # Check if LLM brand actually exists in the query words
            b_norm = intent.brand.lower().strip()
            if b_norm == "apple" and any(k in q_lower for k in ["táo", "apple"]):
                intent.brand = "Apple"
            elif b_norm in q_lower:
                intent.brand = intent.brand
            else:
                intent.brand = None

        # 5. Budget reconciliation
        resolved_budget = resolve_effective_budget(query, budget_input)
        if resolved_budget:
            intent.max_price = resolved_budget
        elif intent.max_price and budget_input:
            intent.max_price = min(intent.max_price, budget_input)
        elif budget_input:
            intent.max_price = budget_input

        # 6. Suppress unwarranted clarification if actionable info exists
        has_actionable_target = bool(intent.product_type or intent.brand or intent.desired_capabilities or intent.max_price)
        is_isolated_ss = bool(re.search(r"\b(ss)\b", q_lower)) and not bool(re.search(r"\b(samsung|steelseries)\b", q_lower))

        if has_actionable_target and not is_isolated_ss:
            intent.needs_clarification = False
            intent.clarification_question = None

        # 7. Intent classification alignment
        if intent.brand and not intent.product_type and not intent.desired_capabilities:
            intent.intent = "check_brand"
        elif intent.product_type or intent.desired_capabilities or intent.max_price:
            intent.intent = "search_products"

        # 8. Domain guard reconciliation
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

        negative_constraints = []
        if reqs.get("is_wireless") and not reqs.get("is_wired"):
            negative_constraints.append("wired")
        elif reqs.get("is_wired") and not reqs.get("is_wireless"):
            negative_constraints.append("wireless")

        if bool(re.search(r"\b(không (?:dùng|cần|chơi|xài|muốn)?\s*(?:loại\s*)?(?:pin tiểu|pin aa|pin aaa|pin rời)|tuyệt đối không (?:dùng|chơi|xài)?\s*pin tiểu)\b", query.lower())):
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
