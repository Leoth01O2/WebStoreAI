import os
import io
import time
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from PIL import Image
import torch

from app.schemas.ai import ImageSearchQueryFeatures

logger = logging.getLogger("storeflow.local_vision")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Ensure HuggingFace cache is pinned to Drive D (large disk, preventing Drive C bloat)
os.environ.setdefault("HF_HOME", "D:/huggingface_cache")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Decompression bomb guard: limit max pixels to 10 Megapixels
Image.MAX_IMAGE_PIXELS = 10_000_000

# Canonical Store Categories & Multi-Prompt Ensembling for Zero-Shot Classification
STORE_CATEGORIES = {
    "headphone": [
        "a photo of headphones, gaming headset or wireless over-ear earphones",
        "a studio product photo of over-ear headphones on a clean background",
    ],
    "earbuds": [
        "a photo of in-ear earbuds or true wireless earphone charging case",
        "a product photo of compact wireless earbuds",
    ],
    "mouse": [
        "a photo of a computer mouse, gaming mouse or ergonomic wireless mouse",
        "a product photo of a desktop computer mouse",
    ],
    "keyboard": [
        "a photo of a computer keyboard, mechanical keyboard or typewriter keyboard",
        "a product photo of a desktop computer mechanical keyboard",
    ],
    "speaker": [
        "a photo of an audio speaker, desktop bluetooth speaker or wooden soundbox",
        "a product photo of a wireless audio speaker",
    ],
    "microphone": [
        "a photo of a desktop microphone, condenser mic or studio recording mic",
        "a product photo of a usb condenser microphone",
    ],
    "game_controller": [
        "a photo of a game controller, console gamepad or joystick",
        "a product photo of a gaming gamepad controller",
    ],
    "mousepad": [
        "a product photo of a computer mousepad, mouse pad mat or gamer desk mat",
        "a photo of a neoprene cloth mousepad or gaming desk mat",
    ],
    "lamp": [
        "a photo of a desk lamp, table light or retro edison bulb lamp",
        "a product photo of an adjustable desk reading lamp",
    ],
    "diffuser": [
        "a photo of an aroma diffuser, humidifier or ultrasonic essential oil mist diffuser",
        "a product photo of an aroma mist diffuser",
    ],
    "clock": [
        "a photo of a digital desk clock, nixie tube clock or wooden table clock",
        "a product photo of a modern desk clock",
    ],
    "smart_scale": [
        "a photo of an electronic weight scale, smart body fat scale or digital bathroom scale",
        "a product photo of a glass digital body weight scale",
    ],
    "fan": [
        "a photo of a desktop electric fan, mini cooling fan or bladeless usb fan",
        "a product photo of a small portable desk fan",
    ],
    "charger": [
        "a photo of a fast phone charger, GaN wall power adapter or plug charger",
        "a product photo of a compact usb-c wall charger adapter",
    ],
    "cable": [
        "a photo of a usb cable, lightning charging wire or braided cable",
        "a product photo of a usb type-c charging cable wire",
    ],
    "hub_adapter": [
        "a photo of a usb hub adapter, multi-port dongle or type-c docking station",
        "a product photo of a multiport usb-c hub docking station",
    ],
    "power_bank": [
        "a photo of a portable power bank, battery pack or external battery charger",
        "a product photo of a portable battery power bank",
    ],
    "laptop_stand": [
        "a photo of an aluminum laptop stand, notebook elevator or foldable tablet holder",
        "a product photo of a metal laptop riser stand",
    ],
    "cooling_pad": [
        "a photo of a laptop cooling pad with fans and rgb light",
        "a product photo of a notebook cooling pad base with cooling fans",
    ],
}

# Open-Set Non-Product Reference Categories for Robust Zero-Shot Guard
NON_PRODUCT_LABELS = {
    "gameplay_screenshot": [
        "a video game screenshot, gaming gameplay scene, virtual 3D game environment or gaming HUD",
        "a screenshot of a pixelated block building game, voxel world, or Minecraft video game",
        "a screenshot of a computer game display or gaming user interface",
        "a video game screenshot, gaming world, blocks or gameplay",
    ],
    "digital_graphics": [
        "a digital illustration, anime artwork, cartoon drawing, vector graphic, or abstract wallpaper",
        "a graphic design, computer-generated artwork, pixel art, or digital painting",
        "a digital wallpaper, computer game scene, or virtual environment",
    ],
    "document_screen": [
        "a photo or screenshot of a text document, paper, webpage, code editor, or software UI",
        "a scanned sheet of paper with text, table, diagram, or chart",
    ],
    "person": [
        "a portrait photo of a human person, man, woman, child, or human face",
        "a selfie or photograph of a person",
    ],
    "food": [
        "a photo of delicious food, dish, cooked meal, fruit, vegetables, or restaurant drink",
        "a plate of food or snack",
    ],
    "animal": [
        "a photo of an animal, dog, cat, bird, pet, or wildlife creature",
    ],
    "vehicle": [
        "a photo of a car, automobile, motorcycle, bicycle, truck, or street vehicle",
    ],
    "landscape_nature": [
        "a landscape photo of outdoor nature, mountains, forest, trees, sky, beach, or ocean",
        "an architectural photo of an outdoor building, house, or street scene",
    ],
    "indoor_interior": [
        "a photo of an empty room, wall, floor, furniture, bed, or interior decor",
    ],
}

COLOR_LABELS = {
    "black": "black color",
    "white": "white color",
    "silver": "silver metallic gray color",
    "dark_gray": "dark charcoal gray color",
    "brown_wood": "brown wooden walnut color",
    "pink": "pink pastel color",
    "blue": "blue or navy color",
    "green": "dark green or olive color",
    "red": "red color",
    "gold": "gold brass color",
    "yellow": "yellow color",
}

SHAPE_LABELS = {
    "over-ear": "over-ear circular earcups with headband",
    "in-ear": "compact in-ear buds with stem",
    "vertical": "vertical ergonomic angled curve grip",
    "compact tenkeyless": "compact rectangular keyboard tenkeyless layout",
    "rectangular box": "rectangular cubic box enclosure",
    "cylindrical": "cylindrical tall tube stand",
    "flat mat": "flat rectangular thin surface mat",
    "gooseneck": "gooseneck curved slender stem",
    "cube": "compact cube block figurine",
}

MATERIAL_LABELS = {
    "plastic": "matte plastic polymer surface",
    "metal": "aluminum metal body finish",
    "wood": "natural wood wooden grain finish",
    "leather": "leather soft cushion padding",
    "fabric": "woven fabric mesh cloth",
}


class LocalVisionService:
    """
    Offline Local Vision & Feature Extractor Service using lightweight CLIP (openai/clip-vit-base-patch32).

    Architectural Guarantees:
    - Runs 100% locally on CPU without demanding GPU VRAM (leaving GPU 100% for Ollama text model).
    - Cache pinned to Drive D (D:/huggingface_cache) to protect Drive C.
    - Zero network calls to Google Gemini Vision or third-party cloud APIs.
    - Direct 512-dim visual embeddings matching text and catalog images in the same metric space.
    - Open-set Zero-Shot classification for category identification, non-product detection, and uncertainty.
    - Pre-computed static text embeddings: evaluates categories, colors, shapes in a SINGLE forward pass.
    - Strict image validation (MIME, max size, pixel bomb guard, corruption check, no dummy fallback canvas).
    """

    def __init__(self, model_id: str = "openai/clip-vit-base-patch32"):
        self.model_id = model_id
        self._model = None
        self._processor = None
        self._device = "cpu"
        self._cached_cat_embeds: Optional[torch.Tensor] = None
        self._cat_keys: List[Tuple[str, str]] = []
        self._cached_color_embeds: Optional[torch.Tensor] = None
        self._color_keys: List[str] = []
        self._cached_shape_embeds: Optional[torch.Tensor] = None
        self._shape_keys: List[str] = []
        self._cached_material_embeds: Optional[torch.Tensor] = None
        self._material_keys: List[str] = []
        logger.info("[LOCAL_VISION] Initialized LocalVisionService singleton.")

    def _ensure_loaded(self):
        """Lazy loads CLIP model and precomputes static text embeddings (offline-first)."""
        if self._model is None or self._processor is None:
            logger.info(f"[LOCAL_VISION] Loading CLIP model '{self.model_id}' on CPU...")
            t0 = time.perf_counter()
            from transformers import CLIPProcessor, CLIPModel

            cache_dir = os.environ.get("HF_HOME", "D:/huggingface_cache")
            snapshot_dir = os.path.join(
                cache_dir, "hub", "models--openai--clip-vit-base-patch32",
                "snapshots", "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
            )

            load_target = snapshot_dir if os.path.exists(snapshot_dir) else self.model_id
            try:
                self._processor = CLIPProcessor.from_pretrained(load_target)
                self._model = CLIPModel.from_pretrained(load_target)
            except Exception as e:
                logger.warning(f"[LOCAL_VISION] Failed loading from target '{load_target}': {e}. Falling back to default hub cache.")
                self._processor = CLIPProcessor.from_pretrained(self.model_id, cache_dir=cache_dir)
                self._model = CLIPModel.from_pretrained(self.model_id, cache_dir=cache_dir)

            self._model.to(self._device)
            self._model.eval()

            # Pre-compute static text embeddings for categories, colors, and shapes
            self._precompute_text_embeddings()

            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(f"[LOCAL_VISION] CLIP model & text embeddings loaded in {elapsed_ms:.1f}ms.")

    def _precompute_text_embeddings(self):
        """Pre-computes and normalizes centroid text embeddings for store & non-product categories."""
        with torch.no_grad():
            self._cat_keys = []
            cat_centroid_list = []

            # 1. Store categories: compute prompt ensemble centroid per category
            for cat_key, prompts in STORE_CATEGORIES.items():
                p_inputs = self._processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
                p_inputs = {k: v.to(self._device) for k, v in p_inputs.items()}
                p_out = self._model.get_text_features(**p_inputs)
                p_emb = p_out.pooler_output if hasattr(p_out, "pooler_output") and p_out.pooler_output is not None else p_out
                # Normalize individual prompts, then average into centroid, then renormalize
                p_emb = p_emb / p_emb.norm(dim=-1, keepdim=True)
                centroid = p_emb.mean(dim=0, keepdim=True)
                centroid = centroid / centroid.norm(dim=-1, keepdim=True)
                cat_centroid_list.append(centroid)
                self._cat_keys.append(("store", cat_key))

            # 2. Non-product categories: compute prompt ensemble centroid per class
            for np_key, prompts in NON_PRODUCT_LABELS.items():
                p_inputs = self._processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
                p_inputs = {k: v.to(self._device) for k, v in p_inputs.items()}
                p_out = self._model.get_text_features(**p_inputs)
                p_emb = p_out.pooler_output if hasattr(p_out, "pooler_output") and p_out.pooler_output is not None else p_out
                p_emb = p_emb / p_emb.norm(dim=-1, keepdim=True)
                centroid = p_emb.mean(dim=0, keepdim=True)
                centroid = centroid / centroid.norm(dim=-1, keepdim=True)
                cat_centroid_list.append(centroid)
                self._cat_keys.append(("non_product", np_key))

            self._cached_cat_embeds = torch.cat(cat_centroid_list, dim=0)

            # 3. Colors
            self._color_keys = list(COLOR_LABELS.keys())
            color_texts = list(COLOR_LABELS.values())
            c_inputs = self._processor(text=color_texts, return_tensors="pt", padding=True, truncation=True)
            c_inputs = {k: v.to(self._device) for k, v in c_inputs.items()}
            c_out = self._model.get_text_features(**c_inputs)
            c_emb = c_out.pooler_output if hasattr(c_out, "pooler_output") and c_out.pooler_output is not None else c_out
            self._cached_color_embeds = c_emb / c_emb.norm(dim=-1, keepdim=True)

            # 4. Shapes
            self._shape_keys = list(SHAPE_LABELS.keys())
            shape_texts = list(SHAPE_LABELS.values())
            s_inputs = self._processor(text=shape_texts, return_tensors="pt", padding=True, truncation=True)
            s_inputs = {k: v.to(self._device) for k, v in s_inputs.items()}
            s_out = self._model.get_text_features(**s_inputs)
            s_emb = s_out.pooler_output if hasattr(s_out, "pooler_output") and s_out.pooler_output is not None else s_out
            self._cached_shape_embeds = s_emb / s_emb.norm(dim=-1, keepdim=True)

            # 5. Materials
            self._material_keys = list(MATERIAL_LABELS.keys())
            material_texts = list(MATERIAL_LABELS.values())
            m_inputs = self._processor(text=material_texts, return_tensors="pt", padding=True, truncation=True)
            m_inputs = {k: v.to(self._device) for k, v in m_inputs.items()}
            m_out = self._model.get_text_features(**m_inputs)
            m_emb = m_out.pooler_output if hasattr(m_out, "pooler_output") and m_out.pooler_output is not None else m_out
            self._cached_material_embeds = m_emb / m_emb.norm(dim=-1, keepdim=True)

    def validate_and_open_image(self, image_data: Union[bytes, Image.Image]) -> Image.Image:
        """
        Validates raw image bytes or PIL Image object:
        - Checks binary integrity and valid format (JPEG, PNG, WEBP).
        - Prevents decompression bombs (Image.MAX_IMAGE_PIXELS).
        - Checks minimum and maximum dimensions.
        Returns a normalized RGB PIL.Image.
        Never falls back to a fake canvas on corrupt files.
        """
        if isinstance(image_data, Image.Image):
            return image_data.convert("RGB")

        if not isinstance(image_data, (bytes, bytearray)):
            raise ValueError("Dữ liệu hình ảnh phải là bytes hoặc PIL.Image.")

        if len(image_data) < 12:
            raise ValueError("File ảnh rỗng hoặc không đủ dữ liệu nhị phân.")

        if len(image_data) > 5 * 1024 * 1024:
            raise ValueError("Dung lượng file ảnh vượt quá giới hạn cho phép (tối đa 5MB).")

        # Magic bytes check (strictly verifies actual file binary header, preventing fake extensions)
        has_png_magic = image_data.startswith(b"\x89PNG\r\n\x1a\n")
        has_jpeg_magic = image_data.startswith(b"\xff\xd8\xff")
        has_webp_magic = (image_data.startswith(b"RIFF") and b"WEBP" in image_data[:16])

        if not (has_png_magic or has_jpeg_magic or has_webp_magic):
            raise ValueError("Nội dung file không đúng định dạng ảnh hợp lệ (magic bytes không khớp).")

        try:
            bio = io.BytesIO(image_data)
            img = Image.open(bio)
            img.verify()

            bio.seek(0)
            img = Image.open(bio)
            format_name = (img.format or "").upper()
            if format_name not in ["JPEG", "JPG", "PNG", "WEBP"]:
                raise ValueError(f"Định dạng ảnh '{format_name}' không được hỗ trợ. Chỉ chấp nhận JPG, PNG, WebP.")

            width, height = img.size
            if width < 1 or height < 1:
                raise ValueError("Kích thước ảnh không hợp lệ (tối thiểu 1x1 pixel).")
            if width > 5000 or height > 5000:
                raise ValueError("Kích thước ảnh quá lớn (tối đa 5000x5000 pixels).")

            return img.convert("RGB")

        except Exception as e:
            err_msg = str(e)
            if "không được hỗ trợ" in err_msg or "vượt quá" in err_msg or "không hợp lệ" in err_msg or "quá lớn" in err_msg:
                raise
            logger.warning(f"[LOCAL_VISION] Image validation failed: {e}")
            raise ValueError("File ảnh bị hỏng hoặc không đúng định dạng hình ảnh hợp lệ.")

    def extract_image_embedding(self, image_input: Union[bytes, Image.Image]) -> List[float]:
        """
        Extracts normalized 512-dimensional visual embedding vector from image.
        Latency: ~60ms on CPU.
        """
        self._ensure_loaded()
        img = self.validate_and_open_image(image_input)

        inputs = self._processor(images=img, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            out = self._model.get_image_features(**inputs)
            emb = out.pooler_output if hasattr(out, "pooler_output") and out.pooler_output is not None else out
            emb = emb / emb.norm(dim=-1, keepdim=True)
            vector = emb.squeeze(0).cpu().tolist()
            return vector

    def extract_text_embedding(self, text: str) -> List[float]:
        """
        Extracts normalized 512-dimensional text embedding vector in the SAME joint CLIP space.
        """
        self._ensure_loaded()
        inputs = self._processor(text=[text], return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            out = self._model.get_text_features(**inputs)
            emb = out.pooler_output if hasattr(out, "pooler_output") and out.pooler_output is not None else out
            emb = emb / emb.norm(dim=-1, keepdim=True)
            vector = emb.squeeze(0).cpu().tolist()
            return vector

    def extract_query_visual_features_local(
        self,
        image_input: Union[bytes, Image.Image],
        filename: str = "",
        return_vector: bool = False
    ) -> Union[Tuple[ImageSearchQueryFeatures, bool, str], Tuple[ImageSearchQueryFeatures, bool, str, List[float]]]:
        """
        Performs local zero-shot visual classification in a SINGLE forward pass:
        1. Encodes the image once with CLIP vision encoder to get normalized 512-dim embedding.
        2. Evaluates raw cosine similarity and calibrated probabilities across store & non-product classes.
        3. Open-set rejection: detects non-products (gameplay screenshots, pixel art, documents, people, food, etc.).
        4. Uncertainty detection: detects low confidence or ambiguous classification without forcing closed-set labels.
        5. Returns structured visual features and query vector.
        """
        self._ensure_loaded()
        img = self.validate_and_open_image(image_input)

        inputs = self._processor(images=img, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            # Single image forward pass
            out = self._model.get_image_features(**inputs)
            img_emb = out.pooler_output if hasattr(out, "pooler_output") and out.pooler_output is not None else out
            img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True)
            query_vector = img_emb.squeeze(0).cpu().tolist()

            logit_scale = self._model.logit_scale.exp()

            # Raw cosine similarities: shape [1, total_cats]
            cos_sims = (img_emb @ self._cached_cat_embeds.T).squeeze(0)
            # Softmax probabilities for calibrated margin comparison
            probs = (cos_sims * logit_scale).softmax(dim=0)

            store_sims: Dict[str, float] = {}
            store_probs: Dict[str, float] = {}
            non_product_sims: Dict[str, float] = {}
            non_product_probs: Dict[str, float] = {}

            for idx, (group, key) in enumerate(self._cat_keys):
                sim_val = float(cos_sims[idx].item())
                prob_val = float(probs[idx].item())
                if group == "store":
                    store_sims[key] = sim_val
                    store_probs[key] = prob_val
                else:
                    non_product_sims[key] = sim_val
                    non_product_probs[key] = prob_val

            # Top Store Category & Second Top
            sorted_store = sorted(store_sims.items(), key=lambda x: x[1], reverse=True)
            top_store_key, top_store_sim = sorted_store[0]
            second_store_sim = sorted_store[1][1] if len(sorted_store) > 1 else 0.0
            store_margin = top_store_sim - second_store_sim

            # Top Non-Product Category
            sorted_np = sorted(non_product_sims.items(), key=lambda x: x[1], reverse=True)
            top_non_prod_key, top_non_prod_sim = sorted_np[0]

            sum_store_prob = sum(store_probs.values())
            sum_np_prob = sum(non_product_probs.values())

            # -------------------------------------------------------------------
            # Decision 1: Definite Non-Product Rejection
            # -------------------------------------------------------------------
            # Triggered if top non-product exceeds top store similarity OR
            # non-product probability dominates with high similarity
            is_non_product = False
            np_reason = ""
            reason_map = {
                "gameplay_screenshot": "Ảnh chụp màn hình trò chơi hoặc đồ họa ảo (gameplay/screenshot), không phải sản phẩm công nghệ vật lý.",
                "digital_graphics": "Ảnh vẽ kỹ thuật số, hình nền hoặc tranh minh họa (digital art), không phải sản phẩm công nghệ vật lý.",
                "document_screen": "Ảnh tài liệu, văn bản hoặc giao diện phần mềm, không phải sản phẩm công nghệ vật lý.",
                "person": "Hình ảnh chứa khuôn mặt hoặc con người, không phải sản phẩm công nghệ.",
                "food": "Hình ảnh chứa món ăn hoặc thực phẩm, không phải sản phẩm công nghệ.",
                "animal": "Hình ảnh chứa động vật hoặc thú cưng, không phải sản phẩm công nghệ.",
                "vehicle": "Hình ảnh chứa phương tiện giao thông, không thuộc danh mục kinh doanh.",
                "landscape_nature": "Hình ảnh chụp phong cảnh ngoài trời hoặc kiến trúc, không phải sản phẩm.",
                "indoor_interior": "Hình ảnh không gian nội thất/phòng ở, không phải sản phẩm công nghệ."
            }

            if (
                top_non_prod_sim >= top_store_sim
                or (top_non_prod_sim >= 0.20 and top_non_prod_sim >= (top_store_sim - 0.018))
                or (sum_np_prob > 0.40 and top_non_prod_sim >= 0.20)
            ):
                is_non_product = True
                np_reason = reason_map.get(top_non_prod_key, "Ảnh không chứa sản phẩm công nghệ hợp lệ.")
                features = ImageSearchQueryFeatures(
                    product_type=None,
                    dominant_color=None,
                    shape_form=None,
                    material=None,
                    visible_features=[],
                    confidence=round(top_non_prod_sim, 4),
                    is_uncertain=False,
                    is_non_product=True,
                    description=f"Nhận diện phi sản phẩm: {np_reason}"
                )
                logger.info(f"[LOCAL_VISION] Non-product detected: {top_non_prod_key} (sim={top_non_prod_sim:.4f} vs store={top_store_sim:.4f})")
                if return_vector:
                    return features, True, np_reason, query_vector
                return features, True, np_reason

            # -------------------------------------------------------------------
            # Decision 2: Open-Set Uncertainty (Low Confidence / Ambiguous Image)
            # -------------------------------------------------------------------
            # When max store similarity is below threshold or very close to non-product,
            # do not force a wrong store category.
            is_uncertain = (
                top_store_sim < 0.25
                or (top_store_sim - top_non_prod_sim) < 0.025
                or (store_margin < 0.018 and top_store_sim < 0.28)
            )

            if is_uncertain:
                features = ImageSearchQueryFeatures(
                    product_type=None,
                    dominant_color=None,
                    shape_form=None,
                    material=None,
                    visible_features=[],
                    confidence=round(top_store_sim, 4),
                    is_uncertain=True,
                    is_non_product=False,
                    description="Độ tin cậy nhận diện loại thiết bị thấp hoặc hình ảnh chưa rõ ràng."
                )
                logger.info(
                    f"[LOCAL_VISION] Low confidence / uncertain classification: top_store={top_store_key} ({top_store_sim:.4f}), "
                    f"top_np={top_non_prod_key} ({top_non_prod_sim:.4f}), store_margin={store_margin:.4f}"
                )
                if return_vector:
                    return features, False, "", query_vector
                return features, False, ""

            # -------------------------------------------------------------------
            # Decision 3: Confident Store Product Detection
            # -------------------------------------------------------------------
            # 2. Color Classification via dot product
            c_logits = (img_emb @ self._cached_color_embeds.T) * logit_scale
            c_probs = c_logits.softmax(dim=1).squeeze(0)
            top_color_idx = int(torch.argmax(c_probs).item())
            detected_color = self._color_keys[top_color_idx]

            # 3. Shape Classification via dot product
            s_logits = (img_emb @ self._cached_shape_embeds.T) * logit_scale
            s_probs = s_logits.softmax(dim=1).squeeze(0)
            top_shape_idx = int(torch.argmax(s_probs).item())
            detected_shape = self._shape_keys[top_shape_idx]

            # 4. Material Classification via dot product
            m_logits = (img_emb @ self._cached_material_embeds.T) * logit_scale
            m_probs = m_logits.softmax(dim=1).squeeze(0)
            top_mat_idx = int(torch.argmax(m_probs).item())
            detected_material = self._material_keys[top_mat_idx]

        # Inferred description
        viet_category_map = {
            "headphone": "tai nghe chụp tai",
            "earbuds": "tai nghe nhét tai",
            "mouse": "chuột máy tính",
            "keyboard": "bàn phím máy tính",
            "speaker": "loa để bàn",
            "microphone": "micro thu âm",
            "game_controller": "tay cầm chơi game",
            "mousepad": "bàn di chuột",
            "lamp": "đèn bàn làm việc",
            "diffuser": "máy xông tinh dầu",
            "clock": "đồng hồ để bàn",
            "smart_scale": "cân điện tử sức khỏe",
            "fan": "quạt để bàn",
            "charger": "củ sạc nhanh",
            "cable": "cáp sạc",
            "hub_adapter": "bộ chia cổng hub",
            "power_bank": "pin sạc dự phòng",
            "laptop_stand": "giá đỡ laptop",
            "cooling_pad": "đế tản nhiệt laptop"
        }
        cat_vn = viet_category_map.get(top_store_key, top_store_key)
        description = f"Nhận diện thị giác cục bộ (Local CLIP): {cat_vn}, màu {detected_color}, kiểu dáng {detected_shape}."

        features = ImageSearchQueryFeatures(
            product_type=top_store_key,
            dominant_color=detected_color,
            shape_form=detected_shape,
            material=detected_material,
            visible_features=[top_store_key, detected_color, detected_shape],
            confidence=round(top_store_sim, 4),
            is_uncertain=False,
            is_non_product=False,
            description=description
        )

        logger.info(
            f"[LOCAL_VISION] Extracted confident features: type={top_store_key} ({top_store_sim:.4f}), "
            f"color={detected_color}, shape={detected_shape}, material={detected_material}"
        )
        if return_vector:
            return features, False, "", query_vector
        return features, False, ""


# Singleton instance
local_vision_service = LocalVisionService()
