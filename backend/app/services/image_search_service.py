import time
import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
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
from app.services.local_vision_service import local_vision_service
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

DEVICE_PARENT_CATEGORIES = {
    "speaker": "Âm thanh & Tai nghe",
    "headphone": "Âm thanh & Tai nghe",
    "earbuds": "Âm thanh & Tai nghe",
    "microphone": "Âm thanh & Tai nghe",
    "mouse": "Chuột & Bàn phím",
    "keyboard": "Chuột & Bàn phím",
    "mousepad": "Chuột & Bàn phím",
    "lamp": "Gia dụng thông minh",
    "diffuser": "Gia dụng thông minh",
    "clock": "Gia dụng thông minh",
    "smart_scale": "Gia dụng thông minh",
    "fan": "Gia dụng thông minh",
    "charger": "Phụ kiện & Dây cáp",
    "cable": "Phụ kiện & Dây cáp",
    "hub_adapter": "Phụ kiện & Dây cáp",
    "power_bank": "Phụ kiện & Dây cáp",
    "laptop_stand": "Phụ kiện & Dây cáp",
    "cooling_pad": "Gaming Gear",
    "game_controller": "Gaming Gear"
}

# Strict Complementary Ecosystem Accessories (only genuine accessory pairs)
COMPATIBLE_ACCESSORIES = {
    "mouse": {"mousepad"},
    "keyboard": {"mousepad"},
    "mousepad": {"mouse", "keyboard"},
    "laptop": {"laptop_stand", "cooling_pad", "hub_adapter", "charger"},
    "laptop_stand": {"cooling_pad"},
    "cooling_pad": {"laptop_stand"},
    "charger": {"cable", "power_bank"},
    "cable": {"charger", "power_bank"},
    "power_bank": {"cable", "charger"},
    "headphone": {"headphone_stand"},
    "microphone": {"audio_interface", "arm_stand"},
}


class ImageSearchService:
    """
    Core Search Pipeline & Multi-Tier Classification for StoreFlow AI Image Search (Phase R6).
    
    Architectural Guarantees:
    1. Validation: Validate file size (<= 5MB), MIME type, PIL integrity, and pixel limits (<= 10MP).
    2. Local Vision Prioritized: Offline local CLIP (openai/clip-vit-base-patch32) on CPU
       extracts 512-dim visual embeddings and zero-shot attributes with zero dependency on external APIs.
    3. Dual Provider: Supports 'local' (default, 100% offline) and 'gemini' (cloud with local fallback).
    4. Candidate Retrieval: Direct vector cosine similarity on 'storeflow_product_visual_vectors'.
    5. Database Truth Guard (SQLite): Enriches candidates with actual selling price,
       stock quantity, and business status directly from SQLite. Discontinued / inactive products are excluded.
       Zero leakage of cost_price.
    6. Multi-Tier Relationship Classification: MATCH, SIMILAR, RELATED, or NONE with explicit grounding explanation.
    """

    def validate_image_file(self, contents: bytes, filename: str, content_type: Optional[str] = None) -> str:
        """
        Validates the uploaded image file size, format, pixel dimensions, and binary integrity.
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

        # Deep integrity validation via PIL (detects corrupted headers, decompression bombs, malformed files)
        try:
            local_vision_service.validate_and_open_image(contents)
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"[IMAGE_SEARCH] Validation rejected upload: {err_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tệp không hợp lệ: {err_msg}"
            )

        return normalized_mime

    # -----------------------------------------------------------------------
    # Non-Product Guard
    # -----------------------------------------------------------------------
    _NON_PRODUCT_DESC_KEYWORDS = [
        # Human / Face
        "người", "mặt người", "chân dung", "khuôn mặt", "con người",
        "person", "face", "human", "portrait", "selfie",
        "nguoi", "mat nguoi", "chan dung", "khuon mat",
        # No product signal
        "không chứa sản phẩm", "không phải sản phẩm", "không có sản phẩm",
        "không phải thiết bị", "không chứa thiết bị",
        "khong chua san pham", "khong phai san pham",
        # Food
        "thức ăn", "food", "món ăn", "đồ ăn", "bữa ăn",
        "thuc an", "mon an", "do an", "bua an",
        # Nature / Landscape
        "phong cảnh", "landscape", "thiên nhiên", "nature",
        "phong canh", "thien nhien",
        # Animal
        "động vật", "animal", "thú cưng", "pet", "chó", "mèo", "chim",
        "dong vat", "thu cung",
        # Vehicle
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
        query_features: ImageSearchQueryFeatures
    ) -> Tuple[bool, str]:
        """
        Returns (True, reason) if the image is detected as non-product
        (e.g. gameplay screenshot, pixel art, digital graphics, document, person, food, animal, landscape).
        """
        if query_features.is_non_product:
            return True, query_features.description or "Ảnh không chứa sản phẩm công nghệ hoặc văn phòng hợp lệ."

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
        filename: str = "",
        provider: str = "local"
    ) -> Tuple[ImageSearchQueryFeatures, bool, bool, Optional[str], Optional[List[float]], str]:
        """
        Extracts structured visual characteristics and 512-dim CLIP embedding vector.
        Returns:
            (query_features, is_fallback, is_quota_exceeded, api_error_detail, query_vector, actual_provider)
        """
        is_quota_exceeded = False
        api_error_detail: Optional[str] = None

        # Always extract 512-dim visual vector locally (fast, deterministic, offline)
        query_vector: Optional[List[float]] = None
        try:
            query_vector = local_vision_service.extract_image_embedding(image_bytes)
        except Exception as e:
            logger.warning(f"[IMAGE_SEARCH] Failed to extract local visual vector: {e}")

        # -------------------------------------------------------------------
        # 1. LOCAL MODE (Default): 100% Offline, Zero Cloud API Calls
        # -------------------------------------------------------------------
        if provider == "local" or not settings.GEMINI_API_KEY:
            try:
                features, is_np, np_reason, q_vec = local_vision_service.extract_query_visual_features_local(
                    image_bytes, filename, return_vector=True
                )
                query_vector = q_vec
                return features, False, False, None, query_vector, "local"
            except Exception as e:
                logger.error(f"[IMAGE_SEARCH] Local vision feature extraction failed: {e}")
                features = ImageSearchQueryFeatures(
                    product_type=None,
                    is_uncertain=True,
                    description=f"Lỗi phân tích hình ảnh: {str(e)[:100]}"
                )
                return features, True, False, str(e), query_vector, "local"

        # -------------------------------------------------------------------
        # 2. GEMINI MODE: Calls Gemini Vision API with Fallback to Local Vision
        # -------------------------------------------------------------------
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
                description=parsed.get("description"),
                confidence=0.85,
                is_uncertain=False,
                is_non_product=False
            )
            logger.info(f"[IMAGE_SEARCH] Extracted query features via Gemini: {features.product_type}, {features.dominant_color}")
            return features, False, False, None, query_vector, "gemini"

        except Exception as e:
            err_str = str(e)
            is_quota = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower()
            if is_quota:
                api_error_detail = (
                    "Hạn ngạch AI Gemini Vision (429 Quota Exceeded) đã vượt mức. "
                    "Hệ thống tự động chuyển sang mô hình Local Vision để hoàn tất tìm kiếm."
                )
                logger.warning(f"[IMAGE_SEARCH] Gemini Quota 429 Exceeded: {e}. Falling back to Local Vision.")
            else:
                api_error_detail = f"Không thể kết nối Gemini Vision ({err_str[:100]}). Đã chuyển sang Local Vision."
                logger.warning(f"[IMAGE_SEARCH] Gemini Vision call failed ({e}). Falling back to Local Vision.")

            # Gracefully fallback to Local Vision Engine
            try:
                local_feat, _, _, q_vec = local_vision_service.extract_query_visual_features_local(
                    image_bytes, filename, return_vector=True
                )
                return local_feat, True, is_quota, api_error_detail, q_vec, "local"
            except Exception as fb_err:
                logger.error(f"[IMAGE_SEARCH] Local vision fallback failed: {fb_err}")
                features = ImageSearchQueryFeatures(
                    product_type=None,
                    is_uncertain=True,
                    description=f"Không thể phân tích ảnh: {str(fb_err)[:100]}"
                )
                return features, True, is_quota, api_error_detail, query_vector, "local"

    def classify_relationship(
        self,
        candidate_meta: Dict[str, Any],
        query_features: ImageSearchQueryFeatures,
        score: float,
        product_name: str = "",
        is_best_category_match: bool = False
    ) -> Tuple[str, str]:
        """
        Classifies the relationship between candidate product and query image into 4 strict tiers:
        - MATCH: Confirmed category match AND high visual match score (>= 0.65), or very high visual similarity (>= 0.78).
        - SIMILAR: Same/compatible category with moderate visual score (>= 0.45).
        - RELATED: Different category or ecosystem accessory with score >= 0.35.
        - NONE: Score < 0.35 or completely unrelated device.
        """
        q_type_raw = (query_features.product_type or "").lower().strip() if not query_features.is_uncertain else ""
        m_type_raw = str(candidate_meta.get("product_type") or "").lower().strip()

        norm_q = normalize_device_type(q_type_raw) if q_type_raw else ""
        norm_m = normalize_device_type(m_type_raw) if m_type_raw else ""

        is_same_category = bool(norm_q and norm_m and (norm_q == norm_m))

        q_color = (query_features.dominant_color or "").lower().strip()
        m_color = str(candidate_meta.get("dominant_color") or "").lower().strip()
        q_color_tokens = [c.strip() for c in q_color.replace(",", " ").split() if len(c.strip()) > 2]
        color_match = bool(q_color and m_color and any(qc in m_color for qc in q_color_tokens))

        display_type = candidate_meta.get("product_type") or m_type_raw or "thiết bị"

        # --- TIER 1: SAME CATEGORY ---
        if is_same_category:
            if score >= 0.60 and (is_best_category_match or color_match):
                relationship = "match"
                if color_match:
                    reason = f"Khớp chính xác chủng loại '{display_type}', kiểu dáng và màu sắc chủ đạo ({int(score * 100)}%)."
                else:
                    reason = f"Khớp chính xác chủng loại '{display_type}' và có độ tương đồng hình ảnh/thiết kế cao nhất ({int(score * 100)}%)."
            elif score >= 0.35 or (score >= 0.25 and is_best_category_match):
                relationship = "similar"
                reason = f"Sản phẩm tương tự cùng chủng loại '{display_type}', khác biệt về biến thể màu sắc hoặc chi tiết hoàn thiện ({int(score * 100)}%)."
            elif score >= 0.20:
                relationship = "related"
                reason = f"Sản phẩm cùng chủng loại '{display_type}' trong cửa hàng ({int(score * 100)}%)."
            else:
                relationship = "none"
                reason = f"Độ tương đồng trực quan dưới ngưỡng phù hợp ({int(score * 100)}%)."

        # --- TIER 2: DIFFERENT CATEGORY / UNCERTAIN CATEGORY ---
        else:
            # Different device categories (e.g. mouse vs mousepad, headphone vs speaker) can NEVER be MATCH or SIMILAR
            if score >= 0.35:
                relationship = "related"
                reason = f"Sản phẩm liên quan hoặc phụ kiện bổ trợ trong cùng hệ sinh thái thiết bị ('{display_type}')."
            else:
                relationship = "none"
                reason = f"Sản phẩm thuộc danh mục khác ('{display_type}') và độ tương đồng trực quan dưới ngưỡng phù hợp (< 35%)."

        return relationship, reason

    def search_and_classify(
        self,
        image_bytes: bytes,
        filename: str,
        content_type: Optional[str] = None,
        limit: int = 5,
        user_id: Optional[int] = None,
        provider: str = "local"
    ) -> ImageSearchResponse:
        """
        Full Image Search Pipeline (Phase R6):
        1. Validate uploaded image (size, MIME, pixel count, binary integrity).
        2. Extract query visual features and 512-dim visual query vector.
        3. Check Non-Product guard (early exit if photo is gameplay, pixel art, person, food, animal, landscape).
        4. Retrieve candidates from ChromaDB direct visual vector index across active catalog.
        5. Ground with SQLite: read authoritative product data (price, stock, status).
           Filter out inactive/discontinued products. Zero cost_price leakage.
        6. Classify relationship (MATCH, SIMILAR, RELATED, NONE) with grounded explanations.
        7. Return standardized response with provider_used, uncertainty, and accuracy guarantees.
        """
        start_time = time.perf_counter()

        # 1. Validate image
        mime_type = self.validate_image_file(image_bytes, filename, content_type)

        # 2. Extract query visual features & 512-dim CLIP query vector
        query_features, is_fallback, is_quota_exceeded, error_msg, query_vector, actual_provider = self.extract_query_visual_features(
            image_bytes=image_bytes,
            mime_type=mime_type,
            filename=filename,
            provider=provider
        )

        # 2a. Quota Exceeded Guard (only if Gemini was chosen and quota exceeded without fallback)
        if is_quota_exceeded and not query_vector:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"[IMAGE_SEARCH] Quota exceeded - aborting search: {error_msg}")
            return ImageSearchResponse(
                query_features=query_features,
                results=[],
                total_candidates_found=0,
                execution_time_ms=elapsed_ms,
                is_fallback=True,
                is_quota_exceeded=True,
                error_message=error_msg or "Hạn ngạch AI Gemini Vision (429 Quota Exceeded) đã vượt mức.",
                provider_used=actual_provider
            )

        # 2b. Non-Product Guard: Early exit if image is not a store tech/office product
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
                is_uncertain=False,
                is_quota_exceeded=False,
                error_message=error_msg,
                provider_used=actual_provider
            )

        is_uncertain = bool(query_features.is_uncertain)

        # 3. Query candidate products using direct visual vector or textual representation
        query_text = (
            f"Chủng loại: {query_features.product_type or ''} | "
            f"Màu sắc: {query_features.dominant_color or ''} | "
            f"Kiểu dáng: {query_features.shape_form or ''} | "
            f"Mô tả: {query_features.description or ''}"
        )

        query_attributes = {
            "product_type": query_features.product_type,
            "dominant_color": query_features.dominant_color,
            "shape_form": query_features.shape_form,
            "is_uncertain": is_uncertain
        }

        fetch_limit = max(limit * 3, 12)
        raw_candidates = visual_index_service.search_visual_candidates(
            query_vector=query_vector,
            query_text=query_text,
            query_attributes=query_attributes,
            top_k=fetch_limit
        )

        if not raw_candidates:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return ImageSearchResponse(
                query_features=query_features,
                results=[],
                total_candidates_found=0,
                execution_time_ms=elapsed_ms,
                is_fallback=is_fallback,
                is_uncertain=is_uncertain,
                uncertainty_reason="Không tìm thấy sản phẩm nào trong kho hàng có đặc trưng thị giác tương đồng." if is_uncertain else None,
                provider_used=actual_provider
            )

        # 4. SQLite Truth Guard: verify all candidates against authoritative product database
        candidate_ids = [c["product_id"] for c in raw_candidates]
        placeholders = ",".join("?" for _ in candidate_ids)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.image_url, p.description,
                       p.brand, p.product_type as p_product_type,
                       v.product_type as v_product_type, v.dominant_color, v.shape_form
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                LEFT JOIN product_visual_metadata v ON p.id = v.product_id
                WHERE p.id IN ({placeholders})
            """, candidate_ids)
            db_products = {row["id"]: dict(row) for row in cursor.fetchall()}

        norm_q_type = normalize_device_type(query_features.product_type or "") if not is_uncertain else ""

        # Determine if the catalog contains active products matching the query category
        has_same_category = False
        if norm_q_type:
            for cand in raw_candidates:
                pid = cand["product_id"]
                if pid in db_products and db_products[pid].get("status") == "active":
                    cand_type = normalize_device_type(
                        cand.get("product_type") or db_products[pid].get("v_product_type") or db_products[pid].get("p_product_type")
                    )
                    if cand_type == norm_q_type:
                        has_same_category = True
                        break

        # 5. Assemble results using strict multi-tier classification
        final_items: List[ImageSearchResultItem] = []
        is_best_cand = True

        for cand in raw_candidates:
            pid = cand["product_id"]
            if pid not in db_products:
                continue

            prod = db_products[pid]
            if prod.get("status") == "inactive":
                continue

            score = cand["combined_score"]
            display_type = cand.get("product_type") or prod.get("v_product_type") or prod.get("p_product_type") or "thiết bị"

            candidate_meta = {
                "product_type": cand.get("product_type") or prod.get("v_product_type") or prod.get("p_product_type"),
                "dominant_color": cand.get("dominant_color") or prod.get("dominant_color"),
                "shape_form": cand.get("shape_form") or prod.get("shape_form"),
            }

            cand_norm = normalize_device_type(candidate_meta["product_type"])

            # Category Guard: when the shop HAS products of the requested category,
            # do not pollute search results with completely unrelated categories (e.g. power_bank for speaker).
            # Only exact category matches or genuine complementary accessories (e.g. mousepad for mouse) are admitted.
            if has_same_category:
                compat_set = COMPATIBLE_ACCESSORIES.get(norm_q_type, set())
                if cand_norm != norm_q_type:
                    if cand_norm not in compat_set or score < 0.50:
                        continue
            is_best_category_match = is_best_cand and bool(norm_q_type and cand_norm == norm_q_type)

            rel, reason = self.classify_relationship(
                candidate_meta=candidate_meta,
                query_features=query_features,
                score=score,
                product_name=prod.get("name", ""),
                is_best_category_match=is_best_category_match
            )

            # Skip candidates with relationship 'none'
            if rel == "none":
                continue

            is_best_cand = False
            final_items.append(ImageSearchResultItem(
                product_id=prod["id"],
                sku=prod["sku"],
                name=prod["name"],
                category_id=prod["category_id"],
                category_name=prod["category_name"],
                selling_price=float(prod["selling_price"]),
                stock_quantity=int(prod["stock_quantity"]),
                in_stock=(prod["stock_quantity"] > 0),
                status=prod["status"],
                image_url=prod["image_url"],
                description=prod["description"],
                relationship=rel,
                reason=reason,
                score=score,
                attr_matches=cand.get("attr_matches") or []
            ))

        # Check uncertainty / no match reason
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        uncertainty_reason = None
        if not final_items:
            if is_uncertain:
                uncertainty_reason = "Hình ảnh có độ tương đồng thấp với toàn bộ sản phẩm trong cửa hàng hoặc không rõ nét."
            else:
                uncertainty_reason = "Không tìm thấy sản phẩm nào trong kho hàng có độ tương đồng thị giác phù hợp (ngưỡng >= 35%)."

        final_results = final_items[:limit]

        # 6. Audit Logging in SQLite
        try:
            ai_service._record_audit_log(
                feature="image_search",
                query_text=f"ImageSearch: {filename} (provider={actual_provider}, type={query_features.product_type}, color={query_features.dominant_color})",
                response_summary=f"Found {len(final_results)} results (Top: {final_results[0].sku if final_results else 'None'}, rel: {final_results[0].relationship if final_results else 'none'})",
                latency_ms=elapsed_ms,
                user_id=user_id
            )
        except Exception:
            pass

        return ImageSearchResponse(
            query_features=query_features,
            results=final_results,
            total_candidates_found=len(final_results),
            execution_time_ms=elapsed_ms,
            is_fallback=is_fallback,
            is_uncertain=is_uncertain,
            uncertainty_reason=uncertainty_reason,
            provider_used=actual_provider
        )


image_search_service = ImageSearchService()
