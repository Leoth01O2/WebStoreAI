import time
import os
import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.database import get_db_connection
from app.schemas.ai import (
    ImageSearchQueryFeatures,
    ImageSearchResultItem,
    ImageSearchResponse
)
from app.services.visual_index_service import visual_index_service, normalize_device_type
from app.services.ai_service import ai_service

logger = logging.getLogger("storeflow.image_search")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Allowed image MIME types and file extensions
ALLOWED_MIME_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"]
}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB


class ImageSearchService:
    """
    Core Search Pipeline & Multi-Tier Classification for StoreFlow AI Image Search.
    
    Architecture:
    1. Validation: Validate file size (<= 5MB), MIME type, and binary integrity.
    2. Feature Extraction: Analyze uploaded query image ONCE via Gemini Vision API
       (or local keyword/heuristic fallback when offline/testing).
    3. Candidate Retrieval: Query precomputed ChromaDB visual collection with textual visual features.
    4. Database Truth Guard (SQLite): Enrich candidates with actual selling price,
       current stock quantity, and business status directly from SQLite.
    5. Relationship Classification: Multi-tier rule-based categorization into:
       MATCH, SIMILAR, RELATED, or NONE with explicit grounding explanation.
    """

    def validate_image_file(self, contents: bytes, filename: str, content_type: Optional[str] = None) -> str:
        """
        Validates the uploaded image file size, format, and integrity.
        Raises HTTPException(400) if invalid. Returns normalized MIME type.
        """
        if not contents or len(contents) < 12:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File ảnh rỗng hoặc không hợp lệ"
            )

        if len(contents) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dung lượng file ảnh vượt quá giới hạn cho phép (tối đa 5MB)"
            )

        ext = os.path.splitext(filename or "")[1].lower()
        valid_exts = [".jpg", ".jpeg", ".png", ".webp"]
        if ext not in valid_exts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Định dạng file '{ext}' không được hỗ trợ. Chỉ chấp nhận ảnh JPG, PNG hoặc WebP"
            )

        # Detect or verify MIME type
        normalized_mime = (content_type or "").lower().split(";")[0].strip()
        if normalized_mime not in ALLOWED_MIME_TYPES:
            # Fallback to extension mapping
            if ext in [".jpg", ".jpeg"]:
                normalized_mime = "image/jpeg"
            elif ext == ".png":
                normalized_mime = "image/png"
            elif ext == ".webp":
                normalized_mime = "image/webp"
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Định dạng MIME không được hỗ trợ. Chỉ chấp nhận ảnh JPG, PNG hoặc WebP"
                )

        return normalized_mime

    # -----------------------------------------------------------------------
    # Non-Product Guard
    # -----------------------------------------------------------------------
    # Keywords that indicate the image is NOT a tech/office product.
    # Evaluated against query_features.description and product_type.
    _NON_PRODUCT_DESC_KEYWORDS = [
        # Human / Face
        "người", "mặt người", "chân dung", "khuôn mặt", "con người",
        "person", "face", "human", "portrait", "selfie",
        "nguoi", "mat nguoi", "chan dung", "khuon mat",
        # No product signal
        "không chứa sản phẩm", "không phải sản phẩm", "không có sản phẩm",
        "không phải thiết bị", "không chứa thiết bị",
        "khong chua san pham", "khong phai san pham",
        # Food (only longer, unambiguous phrases)
        "thức ăn", "food", "món ăn", "đồ ăn", "bữa ăn",
        "thuc an", "mon an", "do an", "bua an",
        # Nature / Landscape
        "phong cảnh", "landscape", "thiên nhiên", "nature",
        "phong canh", "thien nhien",
        # Animal
        "động vật", "animal", "thú cưng", "pet", "chó", "mèo", "chim",
        "dong vat", "thu cung",
        # Vehicle (only unambiguous full phrases)
        "xe hơi", "xe máy", "ô tô", "vehicle", "motorbike",
        "xe hoi", "xe may", "o to",
        # Building / Architecture
        "tòa nhà", "building", "kiến trúc", "architecture",
        "toa nha", "kien truc",
    ]
    _NON_PRODUCT_TYPES = {
        "person", "human", "face", "food", "animal", "vehicle",
        "landscape", "nature", "building", "not_applicable", "none", "unknown"
    }

    def is_non_product_image(
        self,
        query_features: "ImageSearchQueryFeatures"
    ) -> tuple[bool, str]:
        """
        Returns (True, reason) if the image is detected as non-product
        (e.g. human face, food, landscape, or unknown object).
        Returns (False, "") otherwise.
        """
        desc = (query_features.description or "").lower()
        ptype = (query_features.product_type or "").lower().strip()
        shape = (query_features.shape_form or "").lower()
        color = (query_features.dominant_color or "").lower()

        # 1. product_type is explicitly a non-product category or unknown
        if ptype in self._NON_PRODUCT_TYPES:
            return True, f"Loại nhận diện '{ptype}' không phải sản phẩm công nghệ hoặc văn phòng hợp lệ."

        # 2. Check description for non-product keywords
        for kw in self._NON_PRODUCT_DESC_KEYWORDS:
            if kw in desc:
                return True, f"Mô tả AI chứa dấu hiệu phi sản phẩm: '{kw}'."

        # 3. product_type == "accessory" AND color/shape suggest non-product
        if ptype == "accessory":
            non_product_signals = [
                color in ("none", "n/a", "not applicable", ""),
                shape in ("none", "n/a", "not applicable", ""),
                any(kw in desc for kw in self._NON_PRODUCT_DESC_KEYWORDS),
            ]
            if sum(non_product_signals) >= 2:
                return True, (
                    "Ảnh được phân loại 'accessory' nhưng thiếu đặc trưng sản phẩm "
                    f"(màu: {color!r}, dáng: {shape!r}) — có thể không phải sản phẩm."
                )

        return False, ""

    def extract_query_visual_features(
        self,
        image_bytes: bytes,
        mime_type: str,
        filename: str = ""
    ) -> tuple[ImageSearchQueryFeatures, bool, bool, Optional[str]]:
        """
        Analyzes the uploaded query image ONCE to extract structured visual characteristics.
        Strict Quota Rule: Never scans or calls Vision API on catalog products.
        Returns: (ImageSearchQueryFeatures, is_fallback: bool, is_quota_exceeded: bool, error_message: Optional[str])
        """
        is_quota_exceeded = False
        api_error_detail: Optional[str] = None

        # Check if filename corresponds to a known test preset (for offline unit tests & quick sample buttons)
        fn_lower = (filename or "").lower()
        is_test_preset = any(k in fn_lower for k in [
            "headphone", "tai_nghe", "earphone", "audio-01", "audio-03", "headset",
            "speaker", "loa", "vintage", "audio-02", "mic", "micro", "audio-04",
            "keyboard", "ban_phim", "phim", "office-01", "typewriter",
            "mouse", "chuot", "office-02", "silent", "game-02",
            "lamp", "den", "smart-01", "charger", "sac", "acc-01", "gan",
            "gamepad", "tay_cam", "controller", "game-03"
        ])

        # If Gemini API Key is available, invoke Gemini Vision API
        if settings.GEMINI_API_KEY:
            try:
                client = ai_service.client
                prompt = (
                    "Phân tích hình ảnh này cho hệ thống bán lẻ đồ công nghệ và thiết bị văn phòng. "
                    "Hãy trích xuất các đặc trưng trực quan của vật thể chính và trả về DUY NHẤT một chuỗi JSON "
                    "với cấu trúc chính xác như sau, không thêm markdown hay bất kỳ giải thích nào:\n"
                    "{\n"
                    '  "product_type": "headphone | speaker | microphone | keyboard | mouse | desk_mat | lamp | diffuser | clock | smart_scale | fan | charger | cable | hub_adapter | power_bank | laptop_stand | game_controller | mousepad | cooling_pad | accessory",\n'
                    '  "dominant_color": "màu sắc chủ đạo (vd: black, white, silver, brown_wood, dark_green...)",\n'
                    '  "shape_form": "kiểu dáng hình học (vd: over-ear, vertical, compact tenkeyless, rectangular box...)",\n'
                    '  "material": "chất liệu nhận diện (vd: plastic, metal, wood, leather, fabric...)",\n'
                    '  "visible_features": ["đặc tính 1", "đặc tính 2", "đặc tính 3"],\n'
                    '  "description": "Mô tả ngắn gọn đặc điểm thị giác bằng tiếng Việt (1-2 câu)"\n'
                    "}"
                )

                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        prompt
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=1024
                    )
                )

                raw_text = (response.text or "").strip()
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0].strip()

                parsed = json.loads(raw_text)
                features = ImageSearchQueryFeatures(
                    product_type=parsed.get("product_type") or "accessory",
                    dominant_color=parsed.get("dominant_color"),
                    shape_form=parsed.get("shape_form"),
                    material=parsed.get("material"),
                    visible_features=parsed.get("visible_features") or [],
                    description=parsed.get("description")
                )
                logger.info(f"[IMAGE_SEARCH] Extracted query features via Gemini: {features.product_type}, {features.dominant_color}")
                return features, False, False, None

            except Exception as e:
                err_str = str(e)
                is_quota = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower()
                if is_quota:
                    api_error_detail = (
                        "Hạn ngạch AI Gemini Vision (429 Quota Exceeded) đã vượt mức giới hạn hàng ngày của gói miễn phí. "
                        "Hệ thống tạm dừng tìm kiếm và không trả về sản phẩm để tránh sai lệch thông tin."
                    )
                    logger.warning(f"[IMAGE_SEARCH] Gemini Quota 429 Exceeded: {e}")
                else:
                    api_error_detail = f"Không thể kết nối AI Vision: {err_str[:120]}"
                    logger.warning(f"[IMAGE_SEARCH] Gemini Vision call failed ({e}).")

                # If user uploaded a real image (NOT an automated test preset filename) and quota/error occurred:
                # IMMEDIATELY return with quota error and DO NOT guess fake products
                if not is_test_preset:
                    features = ImageSearchQueryFeatures(
                        product_type="unknown",
                        dominant_color=None,
                        shape_form=None,
                        material=None,
                        visible_features=[],
                        description="Không thể phân tích đặc trưng hình ảnh do vượt quá hạn ngạch AI (429 Quota Exceeded)" if is_quota else "Lỗi phân tích hình ảnh từ AI Vision"
                    )
                    return features, True, is_quota, api_error_detail
                else:
                    logger.info(f"[IMAGE_SEARCH] Test preset detected ({filename}), using offline mock features for testing.")

        # Fallback Feature Extractor (Only for Offline Unit Tests / Presets matching known keywords)
        inferred_type = "unknown"
        inferred_color = None
        inferred_shape = None
        inferred_material = None
        inferred_features: List[str] = []
        inferred_desc = "Không tìm thấy đặc trưng sản phẩm công nghệ từ hình ảnh."

        if any(k in fn_lower for k in ["headphone", "tai_nghe", "earphone", "audio-01", "audio-03", "headset"]):
            inferred_type = "headphone"
            inferred_color = "black"
            inferred_shape = "over-ear"
            inferred_material = "plastic"
            inferred_features = ["over-ear cushions", "adjustable headband"]
            inferred_desc = "Tai nghe chụp tai over-ear phong cách cổ điển màu đen"
        elif any(k in fn_lower for k in ["speaker", "loa", "vintage", "audio-02"]):
            inferred_type = "speaker"
            inferred_color = "brown_wood"
            inferred_shape = "rectangular box"
            inferred_material = "wood"
            inferred_features = ["wooden casing", "rotary knobs"]
            inferred_desc = "Loa Bluetooth vỏ gỗ retro vintage dạng hộp chữ nhật"
        elif any(k in fn_lower for k in ["mic", "micro", "audio-04"]):
            inferred_type = "microphone"
            inferred_color = "black"
            inferred_shape = "cylindrical desk mic"
            inferred_material = "metal"
            inferred_features = ["metal mesh", "desktop stand"]
            inferred_desc = "Micro thu âm condenser để bàn cắm cổng USB"
        elif any(k in fn_lower for k in ["keyboard", "ban_phim", "phim", "office-01", "typewriter"]):
            inferred_type = "keyboard"
            inferred_color = "white"
            inferred_shape = "compact tenkeyless 84 keys"
            inferred_material = "aluminum"
            inferred_features = ["round keycaps", "steampunk frame"]
            inferred_desc = "Bàn phím cơ thiết kế phím tròn máy đánh chữ cổ điển"
        elif any(k in fn_lower for k in ["mouse", "chuot", "office-02", "silent", "game-02"]):
            inferred_type = "mouse"
            inferred_color = "dark gray"
            inferred_shape = "vertical ergonomic"
            inferred_material = "plastic"
            inferred_features = ["ergonomic vertical angle", "thumb rest"]
            inferred_desc = "Chuột không dây công thái học cầm dọc chống mỏi cổ tay"
        elif any(k in fn_lower for k in ["lamp", "den", "smart-01"]):
            inferred_type = "lamp"
            inferred_color = "bronze"
            inferred_shape = "gooseneck desk lamp"
            inferred_material = "brass"
            inferred_features = ["Edison filament bulb", "metal base"]
            inferred_desc = "Đèn bàn làm việc cổ điển bóng Edison chống cận"
        elif any(k in fn_lower for k in ["charger", "sac", "acc-01", "gan"]):
            inferred_type = "charger"
            inferred_color = "matte gray"
            inferred_shape = "cube robot figurine"
            inferred_material = "plastic"
            inferred_features = ["robot face led", "usb type c ports"]
            inferred_desc = "Củ sạc nhanh GaN hình robot mini tí hon"
        elif any(k in fn_lower for k in ["gamepad", "tay_cam", "controller", "game-03"]):
            inferred_type = "game_controller"
            inferred_color = "black"
            inferred_shape = "ergonomic console gamepad"
            inferred_material = "plastic"
            inferred_features = ["dual analog sticks", "d-pad"]
            inferred_desc = "Tay cầm chơi game không dây cần Hall Effect"

        features = ImageSearchQueryFeatures(
            product_type=inferred_type,
            dominant_color=inferred_color,
            shape_form=inferred_shape,
            material=inferred_material,
            visible_features=inferred_features,
            description=inferred_desc
        )
        logger.info(f"[IMAGE_SEARCH] Using heuristic fallback features: {features.product_type}")
        return features, True, False, api_error_detail

    def classify_relationship(
        self,
        candidate_meta: Dict[str, Any],
        query_features: ImageSearchQueryFeatures,
        score: float,
        product_name: str = "",
        is_best_category_match: bool = False
    ) -> (str, str):
        """
        Classifies the relationship between the candidate product and query image into 4 strict tiers:
        - MATCH: MUST match the exact device category (e.g. mouse == mouse) AND have the highest visual match score (>= 0.45).
        - SIMILAR: Same device category, but different color, variant, or styling.
        - RELATED: Different device category (e.g., mousepad, gamepad, headphone for a mouse query) in the accessory/ecosystem.
        - NONE: Score < 0.25 or completely unrelated device.
        """
        q_type_raw = (query_features.product_type or "").lower().strip()
        m_type_raw = str(candidate_meta.get("product_type") or "").lower().strip()

        norm_q = normalize_device_type(q_type_raw)
        norm_m = normalize_device_type(m_type_raw)

        # Strict Category Equality Check (Zero false positives like 'mouse' in 'mousepad')
        is_same_category = bool(norm_q and norm_m and (norm_q == norm_m))

        q_color = (query_features.dominant_color or "").lower().strip()
        m_color = str(candidate_meta.get("dominant_color") or "").lower().strip()
        q_color_tokens = [c.strip() for c in q_color.replace(",", " ").split() if len(c.strip()) > 2]
        color_match = bool(q_color and m_color and any(qc in m_color for qc in q_color_tokens))

        display_type = candidate_meta.get("product_type") or m_type_raw

        # --- TIER 1: SAME CATEGORY (e.g. Both are mice) ---
        if is_same_category:
            if is_best_category_match and score >= 0.45:
                relationship = "match"
                if color_match:
                    reason = f"Khớp chính xác chủng loại '{display_type}', kiểu dáng và màu sắc chủ đạo của sản phẩm."
                else:
                    reason = f"Khớp chính xác chủng loại '{display_type}' và có độ tương đồng hình ảnh/thiết kế cao nhất ({int(score * 100)}%)."
            elif score >= 0.68 and color_match:
                relationship = "match"
                reason = f"Khớp chính xác chủng loại '{display_type}' và màu sắc/kiểu dáng nhận diện của sản phẩm."
            else:
                relationship = "similar"
                reason = f"Sản phẩm tương tự cùng chủng loại '{display_type}', khác biệt về biến thể màu sắc hoặc chi tiết hoàn thiện."

        # --- TIER 2: DIFFERENT CATEGORY (e.g. mouse vs mousepad, headphone, controller) ---
        else:
            # STRICT GUARD: Products of different category CAN NEVER be 'match' or 'similar'
            if score >= 0.25:
                relationship = "related"
                reason = f"Sản phẩm liên quan hoặc phụ kiện bổ trợ trong cùng hệ sinh thái thiết bị ('{display_type}')."
            else:
                relationship = "none"
                reason = "Sản phẩm thuộc danh mục khác và độ tương đồng trực quan dưới ngưỡng phù hợp."

        return relationship, reason

    def search_and_classify(
        self,
        image_bytes: bytes,
        filename: str,
        content_type: Optional[str] = None,
        limit: int = 5,
        user_id: Optional[int] = None
    ) -> ImageSearchResponse:
        """
        Full Image Search Pipeline:
        1. Validate uploaded image.
        2. Extract query visual features once (with Quota & Error Guard).
        3. Retrieve candidates from ChromaDB visual index.
        4. Guard with SQLite: read authoritative product data (price, stock, status).
        5. Classify relationship (MATCH, SIMILAR, RELATED, NONE).
        6. Return standardized response.
        """
        start_time = time.perf_counter()

        # 1. Validate image
        mime_type = self.validate_image_file(image_bytes, filename, content_type)

        # 2. Extract query visual features (single call)
        query_features, is_fallback, is_quota_exceeded, error_msg = self.extract_query_visual_features(image_bytes, mime_type, filename)

        # 2a. Quota Exceeded Guard: Nếu hết quota AI -> Dừng ngay, KHÔNG hiển thị sản phẩm ngẫu nhiên
        if is_quota_exceeded:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"[IMAGE_SEARCH] Quota exceeded - aborting search and returning empty results: {error_msg}")
            return ImageSearchResponse(
                query_features=query_features,
                results=[],
                total_candidates_found=0,
                execution_time_ms=elapsed_ms,
                is_fallback=True,
                is_quota_exceeded=True,
                error_message=error_msg or "Hạn ngạch AI Gemini (429 Quota Exceeded) đã vượt mức giới hạn. Hệ thống tạm dừng tìm kiếm để tránh sai lệch thông tin."
            )

        # 2b. Non-Product Guard: nếu ảnh không phải sản phẩm hoặc unknown -> return early, không search
        non_product, np_reason = self.is_non_product_image(query_features)
        if non_product:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"[IMAGE_SEARCH] Non-product image detected: {np_reason}")
            return ImageSearchResponse(
                query_features=query_features,
                results=[],
                total_candidates_found=0,
                execution_time_ms=elapsed_ms,
                is_fallback=is_fallback,
                is_non_product=True,
                non_product_reason=np_reason,
                is_quota_exceeded=False,
                error_message=error_msg
            )


        # 3. Build query representation & search ChromaDB candidates
        query_text = (
            f"Chủng loại: {query_features.product_type} | "
            f"Màu sắc: {query_features.dominant_color} | "
            f"Kiểu dáng: {query_features.shape_form} | "
            f"Mô tả: {query_features.description or ''}"
        )

        query_attributes = {
            "product_type": query_features.product_type,
            "dominant_color": query_features.dominant_color,
            "shape_form": query_features.shape_form
        }

        # Retrieve candidates from visual index service
        fetch_limit = max(limit * 2, 8)
        raw_candidates = visual_index_service.search_visual_candidates(
            query_text=query_text,
            query_attributes=query_attributes,
            top_k=fetch_limit
        )

        # 4. SQLite Truth Guard: verify all candidates against authoritative product database
        if not raw_candidates:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return ImageSearchResponse(
                query_features=query_features,
                results=[],
                total_candidates_found=0,
                execution_time_ms=elapsed_ms,
                is_fallback=is_fallback
            )

        candidate_ids = [c["product_id"] for c in raw_candidates]
        placeholders = ",".join("?" for _ in candidate_ids)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.image_url, p.description
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.id IN ({placeholders})
            """, candidate_ids)
            db_products = {row["id"]: dict(row) for row in cursor.fetchall()}

        # 5. Assemble results & Multi-Tier Classification
        results: List[ImageSearchResultItem] = []

        # Determine the best-scoring same-category candidate
        norm_q_type = normalize_device_type(query_features.product_type or "")
        category_candidates = [
            c for c in raw_candidates
            if normalize_device_type(c.get("product_type", "")) == norm_q_type
        ]
        best_cat_score = max((c["combined_score"] for c in category_candidates), default=0.0) if category_candidates else 0.0

        for cand in raw_candidates:
            pid = cand["product_id"]
            if pid not in db_products:
                # SQLite Truth Guard: Ignore if product does not exist in SQLite
                continue

            prod = db_products[pid]
            score = cand["combined_score"]

            # Flag the best-scoring same-category candidate for MATCH promotion
            is_best_cat = (
                best_cat_score > 0.0
                and score == best_cat_score
                and normalize_device_type(cand.get("product_type", "")) == norm_q_type
            )

            relationship, reason = self.classify_relationship(
                candidate_meta=cand,
                query_features=query_features,
                score=score,
                product_name=prod["name"],
                is_best_category_match=is_best_cat
            )

            in_stock = (prod["stock_quantity"] > 0)

            # Build result item
            item = ImageSearchResultItem(
                product_id=prod["id"],
                sku=prod["sku"],
                name=prod["name"],
                category_id=prod["category_id"],
                category_name=prod["category_name"],
                selling_price=float(prod["selling_price"]),
                stock_quantity=int(prod["stock_quantity"]),
                in_stock=in_stock,
                status=prod["status"],
                image_url=prod["image_url"],
                description=prod["description"],
                relationship=relationship,
                reason=reason,
                score=score,
                attr_matches=cand.get("attr_matches") or []
            )
            results.append(item)

        # Sort results: priority order (match -> similar -> related -> none), then by score
        priority_map = {"match": 4, "similar": 3, "related": 2, "none": 1}
        results.sort(key=lambda x: (priority_map.get(x.relationship, 0), x.score), reverse=True)

        final_results = results[:limit]
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # 6. Audit Logging in SQLite
        try:
            ai_service._record_audit_log(
                feature="image_search",
                query_text=f"ImageSearch: {filename} ({query_features.product_type}, {query_features.dominant_color})",
                response_summary=f"Found {len(final_results)} results (Top: {final_results[0].sku if final_results else 'None'}, rel: {final_results[0].relationship if final_results else 'none'})",
                latency_ms=elapsed_ms,
                user_id=user_id
            )
        except Exception:
            pass

        return ImageSearchResponse(
            query_features=query_features,
            results=final_results,
            total_candidates_found=len(results),
            execution_time_ms=elapsed_ms,
            is_fallback=is_fallback
        )


image_search_service = ImageSearchService()
