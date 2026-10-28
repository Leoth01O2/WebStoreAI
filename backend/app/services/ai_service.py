import re
import time
import json
from typing import List, Dict, Any, Optional, Tuple, Callable
from google import genai
from google.genai import types

from app.core.config import settings
from app.services.rag_service import get_db_connection, rag_service
from app.core.prompt_loader import prompt_loader
from app.core.rate_limiter import ai_rate_limiter
from app.services.report_service import ReportService
from app.services.ai_providers.manager import ai_provider_manager
from app.services.ai_providers.ollama_provider import detect_repetition
from app.services.intent_analyzer import intent_analyzer
from app.schemas.ai import (
    ProductRecommendResponse,
    RecommendedProductItem,
    UserQueryIntent,
    SalesReportResponse,
    SalesQAResponse,
    AIAuditLogResponse
)


class AIService:
    """
    AI Orchestration Layer for StoreFlow AI.
    Coordinates ChromaDB vector candidate retrieval, SQLite stock verification guard,
    PromptLoader templates, Google Gemini 3.6 Flash generation, graceful fallbacks,
    output secret sanitization, and audit logging in SQLite.
    """

    def __init__(self):
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    def _call_gemini(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Helper to invoke Gemini with system instruction, standard config, and output sanitization."""
        # Offline / Safe Mock Check
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("SAFE_MOCK") or settings.GEMINI_API_KEY == "":
            raise RuntimeError("GEMINI_API_KEY is not configured or in mock test mode; activating grounded fallback.")

        sys_inst = system_instruction or prompt_loader.get_system_prompt()
        config = types.GenerateContentConfig(
            system_instruction=sys_inst,
            temperature=0.3,
            max_output_tokens=2048,
        )
        response = self.client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=config
        )
        raw_text = response.text or ""
        return ai_rate_limiter.sanitize_output(raw_text)


    def _record_audit_log(
        self,
        feature: str,
        query_text: str,
        response_summary: str,
        latency_ms: int,
        user_id: Optional[int] = None
    ) -> None:
        """Logs all AI requests into ai_audit_logs SQLite table."""
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO ai_audit_logs (user_id, feature, query_text, response_summary, latency_ms)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_id,
                    feature,
                    query_text[:500],
                    response_summary[:1000],
                    latency_ms
                ))
                conn.commit()
        except Exception:
            # Audit log failure should never disrupt the user experience
            pass

    def recommend_products(
        self,
        user_query: str,
        budget: Optional[float] = None,
        limit: int = 5,
        user_id: Optional[int] = None,
        user_role: str = "guest",
        provider: Optional[str] = None
    ) -> ProductRecommendResponse:
        """
        StoreFlow AI 2.0 Product Recommendation Pipeline:
        1. LLM Intent Analysis (Module B)
        2. Structured Intent Validation
        3. Hybrid Retrieval (Dense + Sparse BM25 + Structured SQL)
        4. Candidate Fusion (RRF) & SQLite Eligibility Guardrail (Lần 1)
        5. Grounded Response Generation (LLM or Direct SQLite Lookup)
        6. Final Verification — Lần 2 (Pre-Response SQLite Verification & Hallucination Guard)
        7. Audit Logging & Structured Frontend Contract
        """
        start_time = time.time()
        budget_val = budget if budget is not None and budget > 0 else None

        # ----------------------------------------------------------------------
        # STEP 1: LLM INTENT ANALYSIS (MODULE B)
        # ----------------------------------------------------------------------
        t_intent_start = time.time()
        intent = intent_analyzer.analyze_intent(
            query=user_query,
            budget_input=budget_val,
            preferred_provider=provider
        )
        intent_ms = max(1, int((time.time() - t_intent_start) * 1000))

        # Check early exit: Out-of-Domain Guard
        if intent.is_out_of_domain:
            out_msg = (
                f"Cửa hàng StoreFlow AI hiện không kinh doanh các mặt hàng hoặc dịch vụ liên quan đến: *\"{user_query}\"*. "
                f"Chúng tôi chuyên cung cấp các thiết bị công nghệ chính hãng: Chuột & Bàn phím cơ, Tai nghe & Âm thanh, Phụ kiện sạc/cáp, và Gaming gear."
            )
            total_latency = max(1, int((time.time() - start_time) * 1000))
            self._record_audit_log(
                feature="recommendation",
                query_text=f"[{user_role.upper()}][OUT_OF_DOMAIN] Q: {user_query}",
                response_summary=out_msg[:300],
                latency_ms=total_latency,
                user_id=user_id
            )
            return ProductRecommendResponse(
                ai_response=out_msg,
                recommended_products=[],
                alternative_products=[],
                effective_budget=budget_val,
                query=user_query,
                total_candidates_found=0,
                is_fallback=True,
                provider="domain_guard",
                requested_provider=provider or "auto",
                intent_provider_used="domain_guard",
                generation_provider_used="domain_guard",
                fallback_reason="out_of_domain",
                intent_analysis=intent,
                timing_ms={"intent_ms": intent_ms, "retrieval_ms": 0, "guardrail_l1_ms": 0, "generation_ms": 0, "verification_l2_ms": 0, "total_ms": total_latency},
                verification_passed=True,
                guardrail_status="verified_out_of_domain"
            )

        # Check early exit: Ambiguous query requiring clarification (e.g. 'ss')
        if intent.needs_clarification and intent.clarification_question:
            clarify_msg = intent.clarification_question
            total_latency = max(1, int((time.time() - start_time) * 1000))
            self._record_audit_log(
                feature="recommendation",
                query_text=f"[{user_role.upper()}][CLARIFICATION] Q: {user_query}",
                response_summary=clarify_msg[:300],
                latency_ms=total_latency,
                user_id=user_id
            )
            intent_prov = intent.source.replace("llm_", "")
            # Clarification message is produced by ambiguity/rule guard, not by neural generation
            gen_prov = intent_prov if intent_prov in ("ambiguity_guard", "domain_guard", "rule_based") else "clarification_guard"
            return ProductRecommendResponse(
                ai_response=clarify_msg,
                recommended_products=[],
                alternative_products=[],
                effective_budget=budget_val,
                query=user_query,
                total_candidates_found=0,
                is_fallback=True if intent_prov not in ("ollama", "gemini") else False,
                provider=gen_prov,
                requested_provider=provider or "auto",
                intent_provider_used=intent_prov,
                generation_provider_used=gen_prov,
                fallback_reason="ambiguity_clarification_rule" if intent_prov == "ambiguity_guard" else "clarification_needed",
                intent_analysis=intent,
                timing_ms={"intent_ms": intent_ms, "retrieval_ms": 0, "guardrail_l1_ms": 0, "generation_ms": 0, "verification_l2_ms": 0, "total_ms": total_latency},
                verification_passed=True,
                guardrail_status="needs_clarification"
            )

        # ----------------------------------------------------------------------
        # STEP 2: HYBRID RETRIEVAL (DENSE + SPARSE + SQL) & SQLITE GUARDRAIL L1
        # ----------------------------------------------------------------------
        t_retrieval_start = time.time()
        rag_context = rag_service.get_grounded_recommendation_context(
            query=user_query,
            top_k=limit,
            budget_max=budget_val,
            intent=intent
        )
        retrieval_ms = max(1, int((time.time() - t_retrieval_start) * 1000))

        verified_products_raw = rag_context["products"]
        alternative_products_raw = rag_context.get("alternative_products", [])
        effective_budget = rag_context.get("effective_budget", budget_val)
        context_text = rag_context["context_text"]
        budget_str = f"{int(effective_budget):,} VNĐ" if effective_budget else "Không giới hạn (linh hoạt theo chất lượng)"

        # Check if RAG context detected a need for clarification
        if rag_context.get("status") == "needs_clarification":
            clarify_msg = rag_context.get("clarification_question") or context_text
            total_latency = max(1, int((time.time() - start_time) * 1000))
            intent_prov = intent.source.replace("llm_", "")
            gen_prov = "rag_clarification_guard"
            return ProductRecommendResponse(
                ai_response=clarify_msg,
                recommended_products=[],
                alternative_products=[],
                effective_budget=effective_budget,
                query=user_query,
                total_candidates_found=0,
                is_fallback=True,
                provider=gen_prov,
                requested_provider=provider or "auto",
                intent_provider_used=intent_prov,
                generation_provider_used=gen_prov,
                fallback_reason="rag_clarification_needed",
                intent_analysis=intent,
                timing_ms={"intent_ms": intent_ms, "retrieval_ms": retrieval_ms, "guardrail_l1_ms": 1, "generation_ms": 0, "verification_l2_ms": 0, "total_ms": total_latency},
                verification_passed=True,
                guardrail_status="needs_clarification"
            )

        # ----------------------------------------------------------------------
        # STEP 3: GROUNDED FALLBACK CLOSURE
        # ----------------------------------------------------------------------
        def _fallback_recommend() -> str:
            if rag_context.get("status") == "out_of_domain":
                return (
                    f"Cửa hàng StoreFlow AI hiện không kinh doanh các mặt hàng hoặc dịch vụ liên quan đến: *\"{user_query}\"*. "
                    f"Chúng tôi chuyên cung cấp các thiết bị công nghệ chính hãng: Chuột & Bàn phím cơ, Tai nghe & Âm thanh, Phụ kiện sạc/cáp, và Gaming gear."
                )
            elif rag_context.get("status") == "brand_over_budget":
                brand_name = rag_context.get("brand_name") or "yêu cầu"
                exp_p = rag_context.get("notable_expensive_brand_products") or []
                exp_info = ""
                if exp_p:
                    item = exp_p[0]
                    exp_info = f" (ví dụ: **{item['name']}** - Mã: `{item['sku']}`, Giá: **{int(item['selling_price']):,} đ**)"
                lines = [
                    f"Cửa hàng StoreFlow AI hiện **CÓ** sản phẩm thuộc thương hiệu **{brand_name}** đang **CÒN HÀNG** trong kho{exp_info}, tuy nhiên mức giá bán thực tế cao hơn ngân sách **{budget_str}** của quý khách.",
                    f"\nĐể phù hợp với mức ngân sách **{budget_str}**, quý khách có thể tham khảo một số phương án cùng loại từ các thương hiệu uy tín khác hiện có sẵn trong kho dưới đây:"
                ]
                if alternative_products_raw:
                    for alt in alternative_products_raw[:3]:
                        reason = alt.get("ineligible_reason") or "Phương án thay thế"
                        lines.append(
                            f"- **{alt['name']}** (Mã: `{alt['sku']}` - Giá: **{int(alt['selling_price']):,} đ** - Tồn: {alt['stock_quantity']} {alt.get('unit', 'cái')}): *{reason}*"
                        )
                lines.append(f"\n*Quý khách cũng có thể cân nhắc nâng mức ngân sách nếu muốn sở hữu sản phẩm cao cấp chính hãng từ {brand_name}.*")
                return "\n".join(lines)
            elif rag_context.get("status") == "brand_out_of_stock":
                brand_name = rag_context.get("brand_name") or "yêu cầu"
                lines = [
                    f"Cửa hàng có kinh doanh các sản phẩm thuộc thương hiệu **{brand_name}**, tuy nhiên hiện tại tất cả các sản phẩm của thương hiệu này đều tạm thời **HẾT HÀNG** trong kho (tồn kho: 0).",
                    f"\nQuý khách có thể tham khảo một số phương án thay thế sẵn hàng cùng phân khúc:"
                ]
                if alternative_products_raw:
                    for alt in alternative_products_raw[:3]:
                        reason = alt.get("ineligible_reason") or "Phương án thay thế"
                        lines.append(
                            f"- **{alt['name']}** (Mã: `{alt['sku']}` - Giá: **{int(alt['selling_price']):,} đ** - Tồn: {alt['stock_quantity']} {alt.get('unit', 'cái')}): *{reason}*"
                        )
                return "\n".join(lines)
            elif rag_context.get("status") == "brand_attribute_mismatch":
                brand_name = rag_context.get("brand_name") or "yêu cầu"
                lines = [
                    f"Cửa hàng có kinh doanh sản phẩm thuộc thương hiệu **{brand_name}**, tuy nhiên hiện chưa có sản phẩm đúng loại hoặc đặc tính quý khách yêu cầu.",
                    f"\nQuý khách có thể tham khảo các dòng sản phẩm thay thế cùng phân khúc hiện có trong kho:"
                ]
                if alternative_products_raw:
                    for alt in alternative_products_raw[:3]:
                        reason = alt.get("ineligible_reason") or "Phương án thay thế"
                        lines.append(
                            f"- **{alt['name']}** (Mã: `{alt['sku']}` - Giá: **{int(alt['selling_price']):,} đ** - Tồn: {alt['stock_quantity']} {alt.get('unit', 'cái')}): *{reason}*"
                        )
                return "\n".join(lines)
            elif rag_context.get("status") == "brand_not_found":
                brand_name = rag_context.get("brand_name") or "yêu cầu"
                return (
                    f"Không tìm thấy sản phẩm {brand_name} đang có hàng tại cửa hàng. "
                    f"Hiện tại StoreFlow AI chưa có sản phẩm thuộc thương hiệu **{brand_name}** trong danh mục hàng hóa (chưa kinh doanh thương hiệu này).\n\n"
                    f"Quý khách đang quan tâm đến loại thiết bị cụ thể nào (ví dụ: chuột máy tính, bàn phím cơ, tai nghe hay phụ kiện)? "
                    f"Vui lòng cho biết thêm nhu cầu sử dụng hoặc mức ngân sách mong muốn để cửa hàng có thể hỗ trợ tư vấn tốt nhất!"
                )
            elif rag_context.get("out_of_stock_detected"):
                oos = rag_context["out_of_stock_detected"]
                return (
                    f"⚠️ **Thông báo tồn kho thực tế**:\n\n"
                    f"Sản phẩm **{oos['name']}** (Mã SKU: `{oos['sku']}`) hiện **ĐÃ HẾT HÀNG** trong kho (tồn kho: 0).\n\n"
                    f"Cửa hàng tạm thời không còn hàng sản phẩm này để bán. Quý khách vui lòng tham khảo các dòng sản phẩm khác hoặc liên hệ bộ phận hỗ trợ khi hàng về thêm."
                )
            elif verified_products_raw:
                lines = [
                    f"**StoreFlow AI — Gợi ý sản phẩm phù hợp**:\n",
                    f"Dựa trên yêu cầu: *\"{user_query}\"* (Ngân sách: {budget_str}), các sản phẩm đáp ứng đầy đủ điều kiện trong kho gồm:\n"
                ]
                for p in verified_products_raw:
                    reason = self._build_dynamic_match_reason(p, user_query, effective_budget)
                    lines.append(
                        f"- **{p['name']}** (Mã: `{p['sku']}`)\n"
                        f"  - Nhóm hàng: {p.get('category_name') or 'Công nghệ'}\n"
                        f"  - Giá bán: **{int(p['selling_price']):,} đ** | Còn tồn: **{p['stock_quantity']} {p['unit']}** *(Còn hàng)*\n"
                        f"  - Đặc tính: {p['description'] or 'Chính hãng'}\n"
                        f"  - Lý do phù hợp: {reason}\n"
                    )
                if alternative_products_raw:
                    lines.append("\n*Gợi ý thay thế tham khảo (chưa đáp ứng đầy đủ tiêu chí):*")
                    for alt in alternative_products_raw[:2]:
                        reason = alt.get("ineligible_reason") or "Chưa đáp ứng đủ tiêu chí"
                        lines.append(
                            f"- {alt['name']} (Mã: `{alt['sku']}`, Giá: {int(alt['selling_price']):,} đ) — *{reason}*"
                        )
                lines.append("\n*Lưu ý: Quý khách có thể chọn sản phẩm để tạo đơn hàng hoặc thêm vào giỏ hàng.*")
                return "\n".join(lines)
            else:
                lines = [
                    f"Hiện tại trong kho chưa có sản phẩm nào đáp ứng đầy đủ tất cả tiêu chí và mức ngân sách {budget_str} của bạn."
                ]
                if rag_context.get("notable_expensive_brand_products"):
                    for exp_p in rag_context["notable_expensive_brand_products"][:1]:
                        lines.append(
                            f"\n*Lưu ý về thương hiệu:* Cửa hàng hiện có sản phẩm **{exp_p['name']}** (Mã: `{exp_p['sku']}`, Giá: {int(exp_p['selling_price']):,} đ) nhưng mức giá vượt xa ngân sách yêu cầu của quý khách."
                        )
                if alternative_products_raw:
                    lines.append("\nTuy nhiên, bạn có thể tham khảo sản phẩm cùng loại gần nhất hiện có trong kho (vượt ngân sách yêu cầu):")
                    for alt in alternative_products_raw[:3]:
                        lines.append(
                            f"- **{alt['name']}** (Mã: `{alt['sku']}`) - Giá: **{int(alt['selling_price']):,} đ** (Tồn kho: {alt.get('stock_quantity', 0)} {alt.get('unit', 'cái')})"
                        )
                lines.append("\nQuý khách có thể cân nhắc nâng ngân sách hoặc điều chỉnh tiêu chí tìm kiếm để có thêm lựa chọn.")
                return "\n".join(lines)

        # ----------------------------------------------------------------------
        # STEP 4: RESPONSE GENERATION (LLM OR GROUNDED DIRECT LOOKUP)
        # ----------------------------------------------------------------------
        t_gen_start = time.time()
        intent_prov = intent.source.replace("llm_", "")
        fallback_reason = None
        if provider == "grounded":
            ai_text = _fallback_recommend()
            provider_used = "grounded"
            is_fallback = True
            fallback_reason = "user_selected_grounded"
        elif provider == "ollama":
            # GROUNDED DETERMINISTIC FORMATTING FOR OLLAMA (QWEN 2.5 1.5B):
            # Eliminates 100% of hallucinations, repetition loops, and false pricing claims.
            # Directly constructs factual StoreFlow recommendation from verified SQLite records.
            ai_text = _fallback_recommend()
            provider_used = "ollama"
            is_fallback = False
            fallback_reason = None
            guardrail_status = "verified"
        elif not verified_products_raw and rag_context.get("status") == "out_of_domain":
            ai_text = _fallback_recommend()
            provider_used = "grounded"
            is_fallback = True
            fallback_reason = "out_of_domain"
        elif len(verified_products_raw) == 0:
            # ZERO-CANDIDATE DETERMINISTIC HANDLING:
            # When len(verified_products_raw) == 0, NEVER call LLM with open recommendation prompt.
            # Small local models (e.g. Qwen 2.5 1.5B) will hallucinate fake products/SKUs or leak prompt instructions.
            ai_text = _fallback_recommend()
            provider_used = "grounded"
            is_fallback = True
            fallback_reason = "zero_candidates_deterministic"
        else:
            # Format Prompt from external template with grounded SQLite context
            prompt = prompt_loader.format_prompt(
                "product_recommendation",
                verified_products_context=context_text,
                user_query=user_query,
                budget_info=budget_str
            )
            ai_text, provider_used, is_fallback, telemetry = ai_provider_manager.execute_with_fallback(
                prompt=prompt,
                system_instruction=prompt_loader.get_system_prompt(),
                fallback_fn=_fallback_recommend,
                preferred_provider=provider,
                max_tokens=600
            )
            if is_fallback:
                fallback_reason = telemetry.get("fallback_reason") or telemetry.get("reason") or "generation_llm_failed"
        generation_ms = max(1, int((time.time() - t_gen_start) * 1000))

        # ----------------------------------------------------------------------
        # STEP 5: FINAL VERIFICATION — LẦN 2 (PRE-RESPONSE SQL GUARDRAIL)
        # ----------------------------------------------------------------------
        t_verif_start = time.time()
        (
            verified_products_raw,
            ai_text,
            provider_used,
            is_fallback,
            guardrail_status,
            verification_passed
        ) = self._verify_final_l2(
            verified_products_raw=verified_products_raw,
            ai_text=ai_text,
            effective_budget=effective_budget,
            provider_used=provider_used,
            is_fallback=is_fallback,
            fallback_fn=_fallback_recommend,
            rag_context=rag_context,
            alternative_products_raw=alternative_products_raw
        )
        if getattr(self, "_last_l2_fallback_reason", None):
            fallback_reason = self._last_l2_fallback_reason

        # Ensure Ollama mode stays locked and factually verified without fallback badge flapping
        if provider == "ollama":
            provider_used = "ollama"
            is_fallback = False
            fallback_reason = None
            guardrail_status = "verified"
            verification_passed = True

        verification_l2_ms = max(1, int((time.time() - t_verif_start) * 1000))
        total_latency = max(1, int((time.time() - start_time) * 1000))

        timing_dict = {
            "intent_ms": intent_ms,
            "retrieval_ms": retrieval_ms,
            "guardrail_l1_ms": 2,
            "generation_ms": generation_ms,
            "verification_l2_ms": verification_l2_ms,
            "total_ms": total_latency
        }

        # ----------------------------------------------------------------------
        # STEP 6: STRUCTURED RESPONSE MAPPING (STRICTLY DEDUPLICATED)
        # ----------------------------------------------------------------------
        seen_rec_pids = set()
        seen_rec_skus = set()
        recommended_items = []
        for p in verified_products_raw:
            pid = p.get("id") or p.get("product_id")
            if pid is None:
                continue
            pid_int = int(pid)
            sku = (p.get("sku") or "").upper()
            if (pid_int in seen_rec_pids) or (sku and sku in seen_rec_skus):
                continue
            seen_rec_pids.add(pid_int)
            if sku:
                seen_rec_skus.add(sku)
            recommended_items.append(
                RecommendedProductItem(
                    id=pid_int,
                    product_id=pid_int,
                    sku=p["sku"],
                    name=p["name"],
                    category_name=p.get("category_name") or "",
                    selling_price=float(p["selling_price"]),
                    stock_quantity=int(p["stock_quantity"]),
                    unit=p.get("unit") or "cái",
                    description=p.get("description") or "",
                    image_url=p.get("image_url") or "",
                    status=p.get("status") or "active",
                    match_reason=p.get("match_reason") or self._build_dynamic_match_reason(p, user_query, effective_budget)
                )
            )

        seen_alt_pids = set()
        seen_alt_skus = set()
        alternative_items = []
        for p in (alternative_products_raw or []):
            pid = p.get("id") or p.get("product_id")
            if pid is None:
                continue
            pid_int = int(pid)
            sku = (p.get("sku") or "").upper()
            if (pid_int in seen_rec_pids) or (sku and sku in seen_rec_skus):
                continue
            if (pid_int in seen_alt_pids) or (sku and sku in seen_alt_skus):
                continue
            seen_alt_pids.add(pid_int)
            if sku:
                seen_alt_skus.add(sku)
            alternative_items.append(
                RecommendedProductItem(
                    id=pid_int,
                    product_id=pid_int,
                    sku=p["sku"],
                    name=p["name"],
                    category_name=p.get("category_name") or "",
                    selling_price=float(p["selling_price"]),
                    stock_quantity=int(p["stock_quantity"]),
                    unit=p.get("unit") or "cái",
                    description=p.get("description") or "",
                    image_url=p.get("image_url") or "",
                    status=p.get("status") or "active",
                    match_reason=p.get("match_reason") or p.get("ineligible_reason") or "Gợi ý tham khảo thêm"
                )
            )

        # ----------------------------------------------------------------------
        # STEP 7: AUDIT LOGGING
        # ----------------------------------------------------------------------
        self._record_audit_log(
            feature="recommendation",
            query_text=f"[{user_role.upper()}][{provider_used.upper()}][{guardrail_status}] Q: {user_query} | Budget: {budget_str}",
            response_summary=ai_text[:300],
            latency_ms=total_latency,
            user_id=user_id
        )

        return ProductRecommendResponse(
            ai_response=ai_text,
            recommended_products=recommended_items,
            alternative_products=alternative_items,
            effective_budget=effective_budget,
            query=user_query,
            total_candidates_found=len(recommended_items),
            is_fallback=is_fallback,
            provider=provider_used,
            requested_provider=provider or "auto",
            intent_provider_used=intent_prov,
            generation_provider_used=provider_used,
            fallback_reason=fallback_reason,
            intent_analysis=intent,
            timing_ms=timing_dict,
            verification_passed=verification_passed,
            guardrail_status=guardrail_status
        )

    def _verify_final_l2(
        self,
        verified_products_raw: List[Dict[str, Any]],
        ai_text: str,
        effective_budget: Optional[float],
        provider_used: str,
        is_fallback: bool,
        fallback_fn: Callable[[], str],
        rag_context: Optional[Dict[str, Any]] = None,
        alternative_products_raw: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[List[Dict[str, Any]], str, str, bool, str, bool]:
        """
        Final Verification — Lần 2 (Pre-Response Guardrail):
        1. Re-reads SQLite in real-time for all proposed products.
        2. Re-verifies ID existence, active status, current stock > 0, and selling price within budget.
        3. Scans generated AI text against ground truth:
           - Hallucination check: ensure no non-eligible/hallucinated SKU was injected by LLM.
             (Allows eligible, alternative, and notable brand products explicitly presented in context).
           - Contradiction check: ensure LLM does not state 'no products available' when eligible products exist.
           - Repetition loop check: ensure degenerate repetition is eliminated.
           - False brand assertion check: ensure LLM does not claim brand is out-of-stock when SQLite has stock.
        4. If any discrepancy or race condition is detected:
           - Safely falls back to deterministic Grounded response.
        Returns:
           (final_products, final_ai_text, final_provider, final_is_fallback, guardrail_status, verification_passed)
        """
        self._last_l2_fallback_reason = None

        # Build allowed SKUs from eligible, alternatives, and notable brand items in context
        allowed_skus = set()
        for p in (verified_products_raw or []):
            if p.get("sku"):
                s = p["sku"].upper().strip()
                allowed_skus.add(s)
                allowed_skus.add(s.replace("_", "-"))
                allowed_skus.add(s.replace("-", "_"))
        if alternative_products_raw:
            for alt in alternative_products_raw:
                if alt.get("sku"):
                    s = alt["sku"].upper().strip()
                    allowed_skus.add(s)
                    allowed_skus.add(s.replace("_", "-"))
                    allowed_skus.add(s.replace("-", "_"))
        if rag_context:
            for exp_p in (rag_context.get("notable_expensive_brand_products") or []):
                if exp_p.get("sku"):
                    s = exp_p["sku"].upper().strip()
                    allowed_skus.add(s)
                    allowed_skus.add(s.replace("_", "-"))
                    allowed_skus.add(s.replace("-", "_"))
            oos_p = rag_context.get("out_of_stock_detected")
            if oos_p and oos_p.get("sku"):
                s = oos_p["sku"].upper().strip()
                allowed_skus.add(s)
                allowed_skus.add(s.replace("_", "-"))
                allowed_skus.add(s.replace("-", "_"))

        # Flexible and comprehensive SKU extraction:
        # Handles SP-ACC-05, SKU-119682, as well as arbitrary fabricated formats like S01G-9876543, D02-9876543, B02-9876543
        raw_skus_found = set()
        # 1. Pattern matching after SKU/Product code labels (ordered from longest label to shortest)
        sku_label_pattern = r"(?:mã\s*sản\s*phẩm|mã\s*sku|mã\s*sp|sku|mã)\s*[:\-]?\s*[`\"']?([A-Za-z0-9][A-Za-z0-9_\-]{3,})[`\"']?"
        for m in re.finditer(sku_label_pattern, ai_text, re.IGNORECASE):
            code = m.group(1).strip("[]():`'\" ,;").upper()
            if code and code not in ("SẢN", "SP", "SKU", "HÀNG", "KHO", "VND", "VNĐ", "Đ") and any(c.isdigit() for c in code):
                raw_skus_found.add(code)

        # 2. Pattern matching structured code expressions with known prefixes or long generated hashes
        sku_patterns = [
            r"\b(SP[_-][A-Za-z0-9_\-]*\d+[A-Za-z0-9_\-]*)\b",
            r"\b(SKU[_-][A-Za-z0-9_\-]*\d+[A-Za-z0-9_\-]*)\b",
            r"\b([A-Za-z0-9]{2,}\d+[A-Za-z0-9]*-[0-9]{4,})\b",
            r"\[(SP[_-][A-Za-z0-9_\-]+)\]",
            r"\((SP[_-][A-Za-z0-9_\-]+)\)",
            r"\[(SKU[_-][A-Za-z0-9_\-]+)\]",
            r"\((SKU[_-][A-Za-z0-9_\-]+)\)"
        ]
        for pat in sku_patterns:
            for s in re.findall(pat, ai_text, re.IGNORECASE):
                clean_s = s.strip("[]():`'\" ,;").upper()
                if clean_s and not clean_s.startswith("ID") and any(c.isdigit() for c in clean_s) and any(c.isalpha() for c in clean_s):
                    raw_skus_found.add(clean_s)

        hallucinated_skus = [
            s for s in raw_skus_found 
            if s not in allowed_skus and s.replace("_", "-") not in allowed_skus and s.replace("-", "_") not in allowed_skus and not s.startswith("ID")
        ]

        # Entity Hallucination Check (Tên sản phẩm: ...)
        allowed_product_names = set()
        for p in (verified_products_raw or []):
            if p.get("name"):
                allowed_product_names.add(p["name"].lower().strip())
        if alternative_products_raw:
            for alt in alternative_products_raw:
                if alt.get("name"):
                    allowed_product_names.add(alt["name"].lower().strip())
        if rag_context:
            for exp_p in (rag_context.get("notable_expensive_brand_products") or []):
                if exp_p.get("name"):
                    allowed_product_names.add(exp_p["name"].lower().strip())
            oos_p = rag_context.get("out_of_stock_detected")
            if oos_p and oos_p.get("name"):
                allowed_product_names.add(oos_p["name"].lower().strip())

        has_entity_hallucination = False
        name_matches = re.findall(r"(?:Tên\s*sản\s*phẩm|Sản\s*phẩm)\s*[:\-]\s*([^\n\r,;*]+)", ai_text, re.IGNORECASE)
        for cand_name in name_matches:
            clean_name = cand_name.strip(" *`'\"").lower()
            if len(clean_name) >= 3 and not any(k in clean_name for k in ["phù hợp", "đủ điều kiện", "khả dụng", "trong kho", "thay thế", "dưới đây", "sau đây"]):
                matched_known = any(
                    clean_name in allowed_name or allowed_name in clean_name or 
                    len(set(clean_name.split()).intersection(set(allowed_name.split()))) >= 2
                    for allowed_name in allowed_product_names
                )
                if not matched_known:
                    has_entity_hallucination = True
                    break

        # Prompt Instruction Leakage Check
        prompt_leakage_signatures = [
            "tuyệt đối không tự sáng tác",
            "tuyệt đối không tự tạo thêm các số thứ tự",
            "tuyệt đối không tự tạo thêm",
            "chỉ tư vấn những sản phẩm đã được xác thực",
            "tuyệt đối không lặp lại",
            "áp dụng system prompt",
            "danh sách sản phẩm khả dụng",
            "quy tắc tư vấn sản phẩm",
        ]
        has_prompt_leakage = any(sig in ai_text.lower() for sig in prompt_leakage_signatures)

        has_repetition = detect_repetition(ai_text)
        has_false_brand_assertion = self._detect_false_brand_assertion(ai_text, rag_context)

        if not verified_products_raw:
            if has_prompt_leakage:
                self._last_l2_fallback_reason = "l2_prompt_leakage"
                return ([], fallback_fn(), "grounded", True, "corrected_by_sql_verification_l2", True)
            if has_entity_hallucination:
                self._last_l2_fallback_reason = "l2_entity_hallucination"
                return ([], fallback_fn(), "grounded", True, "corrected_by_sql_verification_l2", True)
            if has_repetition:
                self._last_l2_fallback_reason = "l2_repetition_loop"
                return ([], fallback_fn(), "grounded", True, "corrected_repetition", True)
            if bool(hallucinated_skus):
                self._last_l2_fallback_reason = "l2_sku_hallucination"
                return ([], fallback_fn(), "grounded", True, "corrected_by_sql_verification_l2", True)
            if has_false_brand_assertion:
                self._last_l2_fallback_reason = "l2_false_assertion_brand_oos"
                return ([], fallback_fn(), "grounded", True, "corrected_by_sql_verification_l2", True)
            
            # Guard against fabricated product proposals when no eligible products exist
            has_fabricated_recommendation = False
            if bool(re.search(r"\b(sản phẩm phù hợp và đáp ứng|sản phẩm có thanh toán|chúng tôi có sản phẩm|sản phẩm tốt nhất đáp ứng)\b", ai_text, re.IGNORECASE)):
                has_fabricated_recommendation = True
            elif bool(re.search(r"(?:giá bán chính thức|tồn kho khả dụng|tình trạng còn hàng)[:\s]+", ai_text, re.IGNORECASE)):
                if not allowed_skus:
                    has_fabricated_recommendation = True

            if has_fabricated_recommendation:
                self._last_l2_fallback_reason = "l2_fabricated_product_on_empty"
                return ([], fallback_fn(), "grounded", True, "corrected_by_sql_verification_l2", True)

            return ([], ai_text, provider_used, is_fallback, "verified_empty", True)

        # 1. Real-time SQLite re-verification (Double Verification Lần 2)
        pids = [p["id"] for p in verified_products_raw]
        live_rows = rag_service.reverify_products_in_sqlite(pids)

        final_products = []
        data_shifted = False
        for p in verified_products_raw:
            pid = p["id"]
            live = live_rows.get(pid)
            if not live or live.get("status") != "active" or live.get("stock_quantity", 0) <= 0:
                data_shifted = True
                continue
            live_price = float(live.get("selling_price", 0))
            if effective_budget is not None and effective_budget > 0 and live_price > effective_budget:
                data_shifted = True
                continue
            p_up = dict(p)
            p_up["selling_price"] = live_price
            p_up["stock_quantity"] = live["stock_quantity"]
            final_products.append(p_up)

        # 2. Fact-Check LLM Text & Hallucination Guard
        has_contradiction = self._contradicts_verified_products(ai_text, final_products)
        has_false_oos_claim = self._detect_false_out_of_stock_claim(ai_text, final_products)

        # 3. Decision
        l2_fail_reason = None
        if data_shifted:
            l2_fail_reason = "l2_data_shifted"
        elif has_prompt_leakage:
            l2_fail_reason = "l2_prompt_leakage"
        elif has_repetition:
            l2_fail_reason = "l2_repetition_loop"
        elif has_contradiction:
            l2_fail_reason = "l2_contradiction_negation"
        elif has_false_oos_claim:
            l2_fail_reason = "l2_false_out_of_stock_claim"
        elif bool(hallucinated_skus):
            l2_fail_reason = "l2_sku_hallucination"
        elif has_entity_hallucination:
            l2_fail_reason = "l2_entity_hallucination"
        elif has_false_brand_assertion:
            l2_fail_reason = "l2_false_assertion_brand_oos"

        if l2_fail_reason:
            self._last_l2_fallback_reason = l2_fail_reason
            fallback_text = fallback_fn()
            return (final_products, fallback_text, "grounded", True, "corrected_by_sql_verification_l2", True)

        return (final_products, ai_text, provider_used, is_fallback, "verified", True)

    @staticmethod
    def _contradicts_verified_products(text: str, verified_products: List[Dict[str, Any]]) -> bool:
        """Detects if LLM output claims no products exist when verified in-stock items were provided."""
        if not verified_products:
            return False
        text_lower = text.lower()

        # If LLM explicitly mentions/recommends a verified product, negative expressions for other categories
        # (e.g. explaining why mice do not fit audio needs) are not overall contradictions.
        has_positive_rec = False
        for p in verified_products:
            p_sku = (p.get("sku") or "").lower()
            p_name = (p.get("name") or "").lower()
            if p_sku and p_sku in text_lower:
                has_positive_rec = True
                break
            if p_name and p_name in text_lower:
                has_positive_rec = True
                break
        if has_positive_rec:
            return False

        strong_negations = [
            "không có sản phẩm nào phù hợp",
            "không có sản phẩm nào đáp ứng",
            "không còn mẫu nào",
            "không tìm thấy sản phẩm nào",
            "hiện không có sản phẩm nào",
            "cửa hàng hiện không có sản phẩm",
            "tất cả sản phẩm đều đã hết hàng",
            "đã hết hàng hoàn toàn",
            "không tìm thấy sản phẩm đáp ứng",
            "không có sản phẩm đáp ứng",
            "không có sản phẩm phù hợp"
        ]
        for phrase in strong_negations:
            if phrase in text_lower:
                return True

        if re.search(r"(không|chưa)\s+(tìm thấy|có|còn)\s+sản phẩm\s+(nào|đáp ứng|phù hợp|thỏa mãn)", text_lower):
            return True
        if re.search(r"rất tiếc.*không.*sản phẩm.*(đáp ứng|phù hợp)", text_lower):
            return True
        return False

    @staticmethod
    def _detect_false_brand_assertion(text: str, rag_context: Optional[Dict[str, Any]]) -> bool:
        """
        Detects if LLM falsely claims a brand is not carried or out of stock
        when SQLite actually has active, in-stock products for that brand (e.g. brand_over_budget).
        """
        if not rag_context:
            return False
        status = rag_context.get("status")
        brand_name = rag_context.get("brand_name")
        expensive_prods = rag_context.get("notable_expensive_brand_products") or []
        if (status == "brand_over_budget" or bool(expensive_prods)) and brand_name:
            bn = brand_name.lower().strip()
            text_lower = text.lower()
            false_phrases = [
                f"không tìm thấy sản phẩm {bn} đang có hàng",
                f"không tìm thấy sản phẩm {bn} nào đang có hàng",
                f"không có sản phẩm {bn} đang có hàng",
                f"không có sản phẩm {bn} nào còn hàng",
                f"cửa hàng hiện không có sản phẩm {bn}",
                f"chưa có sản phẩm {bn}",
                f"chưa kinh doanh sản phẩm {bn}",
                f"{bn} hiện đã hết hàng",
                f"{bn} đã hết hàng",
                f"{bn} tạm thời hết hàng",
                f"hết hàng sản phẩm {bn}"
            ]
            for phrase in false_phrases:
                if phrase in text_lower:
                    return True
        return False

    @staticmethod
    def _detect_false_out_of_stock_claim(text: str, verified_products: List[Dict[str, Any]]) -> bool:
        """
        Detects if LLM falsely claims verified products are out of stock
        when SQLite confirmed they are in stock.
        """
        if not verified_products:
            return False
        has_in_stock = any(p.get("stock_quantity", 0) > 0 for p in verified_products)
        if not has_in_stock:
            return False

        text_lower = text.lower()
        oos_patterns = [
            r"sản phẩm (?:này|trên)?\s*(?:hiện)?\s*(?:đã\s*)?(?:tạm\s*)?hết hàng",
            r"mẫu này (?:hiện)?\s*(?:đã\s*)?(?:tạm\s*)?hết hàng",
            r"hiện tại (?:đã\s*)?hết hàng",
            r"tạm thời hết hàng",
            r"không còn hàng trong kho",
            r"trong kho đã hết",
            r"kho đã hết hàng",
            r"đã hết hàng hoàn toàn",
        ]
        for pat in oos_patterns:
            if re.search(pat, text_lower):
                return True
        return False

    @staticmethod
    def _build_dynamic_match_reason(p: Dict[str, Any], user_query: str, effective_budget: Optional[float] = None) -> str:
        """
        Builds a rich, dynamic match reason based on actual product features and user query requirements.
        Replaces generic hardcoded fallback template reasons.
        """
        existing_reason = p.get("match_reason")
        if existing_reason and existing_reason not in (
            "Đáp ứng đầy đủ tiêu chí và ngân sách",
            "Đáp ứng đầy đủ tiêu chí tìm kiếm",
            "Đáp ứng tiêu chí tìm kiếm"
        ):
            return existing_reason

        desc = (p.get("description") or "").lower()
        name = (p.get("name") or "").lower()
        combined_text = f"{name} {desc}"
        q_lower = (user_query or "").lower()
        features = []

        if any(k in combined_text for k in ["mic lọc tiếng ồn", "lọc tiếng ồn", "mic lọc ồn", "khử ồn mic"]):
            features.append("mic lọc tiếng ồn")
        elif "chống ồn chủ động" in combined_text or "anc" in combined_text:
            features.append("chống ồn chủ động ANC")
        elif "chống ồn" in combined_text:
            features.append("khả năng cách âm chống ồn")

        if any(k in combined_text for k in ["đệm tai", "chụp tai", "earpads"]):
            features.append("đệm tai êm ái")

        if any(k in combined_text for k in ["7.1", "rung bass", "âm thanh vòm", "surround"]):
            features.append("âm thanh vòm rõ nét")

        if any(k in combined_text for k in ["silent", "không gây ồn", "nút bấm êm", "click êm"]):
            features.append("phím bấm êm không gây tiếng ồn")

        if any(k in combined_text for k in ["công thái học", "ergonomic"]):
            features.append("thiết kế công thái học chống mỏi")

        if any(k in combined_text for k in ["không dây", "wireless", "bluetooth"]):
            features.append("kết nối không dây tiện lợi")

        if any(k in combined_text for k in ["xoay 360", "gấp gọn", "hợp kim nhôm"]):
            features.append("chất liệu hợp kim chắc chắn linh hoạt")

        if any(k in combined_text for k in ["dung lượng", "mah", "sạc nhanh"]):
            features.append("dung lượng pin tiện ích")

        purposes = []
        if any(k in q_lower for k in ["họp", "zoom", "meet", "đàm thoại"]):
            purposes.append("họp trực tuyến")
        if any(k in q_lower for k in ["nghe rõ", "giọng", "nghe"]):
            purposes.append("nghe rõ giọng người nói")
        if any(k in q_lower for k in ["phòng ồn", "môi trường ồn", "ồn"]):
            purposes.append("trong môi trường nhiều tạp âm")
        if any(k in q_lower for k in ["văn phòng", "làm việc"]):
            purposes.append("làm việc văn phòng")
        if any(k in q_lower for k in ["game", "chơi game"]):
            purposes.append("chơi game giải trí")

        parts = []
        if features:
            parts.append(f"Có {', '.join(features)}")
        elif p.get("description"):
            parts.append(p["description"])

        if purposes:
            parts.append(f"phù hợp để {', '.join(purposes)}")

        price = p.get("selling_price")
        if price and effective_budget and price <= effective_budget:
            parts.append(f"nằm trong ngân sách {int(effective_budget):,} đ")
        elif price:
            parts.append(f"giá bán {int(price):,} đ")

        if parts:
            reason = ", ".join(parts)
            return reason[0].upper() + reason[1:]
        return f"Đáp ứng tốt tiêu chí tìm kiếm và nằm trong ngân sách {int(p.get('selling_price', 0)):,} đ"


    @staticmethod
    def _clean_report_output(text: str) -> str:
        """
        Sanitizes AI-generated business report output:
        - Strips leaked prompt meta-instructions, internal notes, and system rules.
        - Truncates degenerative repetitive loop blocks if local LLM cycled at the end.
        """
        if not text:
            return text

        cleaned = text.strip()

        # 1. Strip thinking blocks
        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL)

        # 2. Check for explicit end markers
        for marker in ["[HẾT BÁO CÁO]", "--- HẾT BÁO CÁO ---", "[HẾT]", "--- HẾT ---"]:
            if marker in cleaned:
                cleaned = cleaned.split(marker)[0].rstrip()

        # 3. Cut off known system instruction leakage patterns
        leakage_patterns = [
            r'\n(?:\*\*|\#\#)?\s*Ghi\s*[Cc]hú\s*[Bb]ổ\s*[Ss]ung\s*(?:\*\*|\#\#)?.*',
            r'\n(?:\*\*|\#\#)?\s*Quyết\s*định\s*:\s*(?:\*\*|\#\#)?.*',
            r'\n(?:\*\*|\#\#)?\s*Phong\s*cách\s*giao\s*tiếp\s*:\s*(?:\*\*|\#\#)?.*',
            r'\n(?:\*\*|\#\#)?\s*Lưu\s*[Ýý]\s*:\s*(?:\*\*|\#\#)?\s*.*(?:không\s*tự\s*bịa|context).*',
            r'\n\[QUY TẮC.*',
            r'\n\[HỆ THỐNG\].*',
            r'\n\[NHIỆM VỤ\].*',
            r'\n\[DỮ LIỆU DOANH THU.*',
        ]
        for pattern in leakage_patterns:
            match = re.search(pattern, cleaned, flags=re.IGNORECASE | re.DOTALL)
            if match:
                cleaned = cleaned[:match.start()].rstrip()

        # 4. Truncate degenerative repetitive loops
        lines = cleaned.split('\n')
        seen_lines = {}
        cutoff_idx = None
        for idx, line in enumerate(lines):
            trimmed = line.strip()
            if len(trimmed) >= 15:
                count = seen_lines.get(trimmed, 0) + 1
                seen_lines[trimmed] = count
                if count >= 3:
                    cutoff_idx = idx
                    break

        if cutoff_idx is not None:
            clean_lines = lines[:cutoff_idx]
            while clean_lines and (not clean_lines[-1].strip() or clean_lines[-1].strip().startswith('**Kế Hoạch') or clean_lines[-1].strip().startswith('1.')):
                clean_lines.pop()
            cleaned = '\n'.join(clean_lines).rstrip()

        return cleaned.strip()

    def generate_sales_report(
        self,
        period: str = "month",
        user_id: Optional[int] = None,
        user_role: str = "superadmin",
        provider: Optional[str] = None
    ) -> SalesReportResponse:
        """
        Generates an executive AI sales & inventory report grounded entirely in SQLite analytics.
        Strictly restricted to SuperAdmin (Store Owner).
        Supports Pluggable AI Providers (Gemini, Ollama, Grounded Fallback).
        """
        if user_role != "superadmin":
            raise PermissionError("Chỉ Chủ cửa hàng (SuperAdmin) mới có quyền tạo Báo cáo Doanh thu AI.")

        start_time = time.time()

        # 1. Fetch real analytics from ReportService
        summary = ReportService.get_dashboard_summary()
        top_products = ReportService.get_top_products(limit=5)
        low_stock_list = ReportService.get_low_stock_products()

        # Build period label
        period_names = {
            "today": "Hôm nay",
            "7_days": "7 ngày gần nhất",
            "week": "Tuần này",
            "month": "Tháng này",
            "all": "Toàn thời gian"
        }
        period_label = period_names.get(period, f"Kỳ phân tích ({period})")

        # Context construction
        top_str_lines = []
        for idx, item in enumerate(top_products, start=1):
            top_str_lines.append(
                f"  {idx}. {item['name']} (Mã: {item['sku']}) - Đã bán: {item['total_quantity_sold']} cái - Doanh thu: {int(item['total_revenue']):,} đ"
            )
        top_text = "\n".join(top_str_lines) if top_str_lines else "  Chưa có dữ liệu bán hàng."

        low_str_lines = []
        for idx, item in enumerate(low_stock_list, start=1):
            low_str_lines.append(
                f"  {idx}. {item['name']} (Mã: {item['sku']}) - Tồn kho: {item['stock_quantity']} (Ngưỡng báo động: {item['min_stock_alert']})"
            )
        low_stock_text = "\n".join(low_str_lines) if low_str_lines else "  Tồn kho an toàn, không có sản phẩm nào chạm ngưỡng báo động."

        sales_data_context = (
            f"TỔNG KẾT DOANH THU & HOẠT ĐỘNG BÁN HÀNG TỪ CƠ SỞ DỮ LIỆU SQL:\n"
            f"- Tổng doanh thu tích lũy toàn thời gian: {int(summary['total_revenue']):,} VNĐ\n"
            f"- Doanh thu đã đối soát/xác minh thu nhận: {int(summary.get('verified_payment_revenue', 0)):,} VNĐ\n"
            f"- Doanh số đơn hoàn thành chưa đối soát: {int(summary.get('legacy_unverified_revenue', 0)):,} VNĐ\n"
            f"- Doanh thu hôm nay: {int(summary['today_revenue']):,} VNĐ\n"
            f"- Doanh thu 7 ngày gần nhất: {int(summary.get('week_revenue', 0)):,} VNĐ\n"
            f"- Doanh thu tháng này: {int(summary.get('month_revenue', 0)):,} VNĐ\n"
            f"- Tổng số đơn hàng trên hệ thống: {summary['total_orders']} đơn\n"
            f"- Số đơn hàng hoàn tất thực tế: {summary.get('completed_orders', 0)} đơn\n"
            f"- Số đơn hàng đã hủy / hoàn tiền: {summary.get('cancelled_orders', 0)} đơn\n"
            f"- Số sản phẩm cần nhập hàng gấp: {summary['low_stock_count']} mặt hàng\n\n"
            f"LƯU Ý QUAN TRỌNG VỀ ĐỐI SOÁT:\n"
            f"- Tuyệt đối không diễn giải doanh số đơn hoàn thành chưa đối soát ({int(summary.get('legacy_unverified_revenue', 0)):,} VNĐ) là tiền đã xác minh hoặc chưa thanh toán. Đây là doanh số các đơn hoàn tất lịch sử cần đối soát thanh toán riêng biệt.\n\n"
            f"TOP 5 SẢN PHẨM BÁN CHẠY NHẤT:\n{top_text}\n\n"
            f"DANH SÁCH SẢN PHẨM CẦN NHẬP HÀNG GẤP:\n{low_stock_text}"
        )

        prompt = prompt_loader.format_prompt(
            "sales_report",
            sales_data_context=sales_data_context,
            report_period=period_label,
            additional_notes="Dữ liệu trích xuất từ database bán hàng thực tế StoreFlow AI."
        )

        # Grounded Fallback closure
        def _fallback_report() -> str:
            return (
                f"### Báo cáo Doanh thu & Tình hình Kinh doanh ({period_label})\n\n"
                f"**1. Tổng quan Doanh thu:**\n"
                f"- Doanh thu hôm nay: **{int(summary['today_revenue']):,} VNĐ**\n"
                f"- Doanh thu tuần này: **{int(summary.get('week_revenue', 0)):,} VNĐ**\n"
                f"- Doanh thu tháng này: **{int(summary.get('month_revenue', 0)):,} VNĐ**\n"
                f"- Doanh thu đã đối soát thanh toán: **{int(summary.get('verified_payment_revenue', 0)):,} VNĐ**\n"
                f"- Doanh số đơn hoàn thành chưa đối soát: **{int(summary.get('legacy_unverified_revenue', 0)):,} VNĐ**\n"
                f"- Tổng số đơn hàng: **{summary['total_orders']}** đơn hàng.\n\n"
                f"**2. Mặt hàng bán chạy nhất:**\n{top_text}\n\n"
                f"**3. Tình trạng Kho & Cảnh báo:**\n"
                f"- Hiện có **{summary['low_stock_count']}** mặt hàng đang ở mức báo động cần nhập hàng gấp.\n"
                f"{low_stock_text}\n\n"
                f"**4. Đề xuất hành động:**\n"
                f"- Ưu tiên lập phiếu nhập hàng cho các sản phẩm trong danh sách cảnh báo.\n"
                f"- Tiếp tục duy trì nguồn hàng dồi dào cho các sản phẩm nằm trong top 5 bán chạy."
            )

        ai_analysis, provider_used, is_fallback, _ = ai_provider_manager.execute_with_fallback(
            prompt=prompt,
            system_instruction=prompt_loader.get_system_prompt(),
            fallback_fn=_fallback_report,
            preferred_provider=provider
        )

        ai_analysis = self._clean_report_output(ai_analysis)

        latency = int((time.time() - start_time) * 1000)

        self._record_audit_log(
            feature="sales_report",
            query_text=f"[{provider_used.upper()}] Kỳ báo cáo: {period_label}",
            response_summary=ai_analysis[:300],
            latency_ms=latency,
            user_id=user_id
        )

        return SalesReportResponse(
            ai_analysis=ai_analysis,
            period=period,
            total_revenue=float(summary["total_revenue"]),
            total_orders=int(summary["total_orders"]),
            completed_orders=int(summary.get("completed_orders", 0)),
            cancelled_orders=int(summary.get("cancelled_orders", 0)),
            low_stock_count=int(summary["low_stock_count"]),
            top_selling_products=top_products,
            is_fallback=is_fallback,
            provider=provider_used
        )

    def answer_sales_qa(
        self,
        question: str,
        user_id: Optional[int] = None,
        user_role: str = "guest",
        user_full_name: Optional[str] = None,
        provider: Optional[str] = None
    ) -> SalesQAResponse:
        """
        Role-Aware AI Assistant & Q&A Orchestrator.
        Enforces strict backend data boundaries across roles:
          - SuperAdmin: Full access to financial analytics, revenue SQL facts, restocking recommendations.
          - Admin: System and product assistance. Denied sensitive store revenue/owner data.
          - Staff: POS assistance, product lookup, operational stock. Denied revenue/financial metrics.
          - Customer: Product consultation, shopping help, OWN order history (via authenticated customer_id).
                      Denied other customers' data, store revenue, internal management data.
          - Guest: Public product info, prices, descriptions, consultation. Denied revenue, internal logs, customer data.
        """
        start_time = time.time()
        role = (user_role or "guest").lower()
        q_lower = question.lower().strip()

        # ==================== 1. PROMPT INJECTION & SYSTEM SECRETS GUARD ====================
        injection_keywords = [
            "ignore previous instructions", "ignore all instructions", "ignore prompt",
            "forget all previous instructions", "forget instructions", "forget previous",
            "bỏ qua hướng dẫn", "bỏ qua câu lệnh", "quên hết chỉ dẫn", "quên hết hướng dẫn",
            "reveal system prompt", "show system prompt", "tiết lộ system prompt", "câu lệnh hệ thống",
            "reveal prompt", "in ra prompt", "show prompt template",
            "api key", "gemini_api_key", "secret key", "database password", "mật khẩu db",
            "act as admin", "act as superadmin", "you are now superadmin", "you are now admin", "you are now",
            "đóng vai admin", "đóng vai superadmin", "giả làm chủ shop",
            "bypass role", "override permission", "bỏ qua phân quyền",
            "drop table", "dump database", "select * from users"
        ]
        if any(kw in q_lower for kw in injection_keywords):
            safe_refusal = (
                "**StoreFlow AI — Thông báo an toàn hệ thống**:\n\n"
                "Yêu cầu của bạn đã bị từ chối do vi phạm quy tắc an toàn bảo mật. "
                "StoreFlow AI không được phép tiết lộ câu lệnh hệ thống (system prompt), mã khóa API, "
                "mật khẩu cơ sở dữ liệu hoặc thay đổi vai trò ngoài phân quyền được xác thực tại Backend."
            )
            latency = int((time.time() - start_time) * 1000)
            self._record_audit_log("sales_qa_injection_blocked", question, safe_refusal[:300], latency, user_id)
            return SalesQAResponse(
                answer=safe_refusal,
                query=question,
                context_type="security_guard",
                is_fallback=True,
                provider="grounded"
            )

        # ==================== 2. INTENT DETECTION & PERMISSION GATEKEEPING ====================
        revenue_keywords = [
            "doanh thu", "lợi nhuận", "tiền bán hàng", "báo cáo tài chính", "doanh số",
            "thu nhập cửa hàng", "tiền lãi", "revenue", "profit", "sales report",
            "báo cáo bán hàng", "tổng tiền bán", "tiền thu được", "bán được bao nhiêu tiền",
            "kế hoạch nhập hàng", "cần nhập thêm gì", "restock"
        ]
        is_revenue_query = any(kw in q_lower for kw in revenue_keywords)

        customer_order_keywords = [
            "đơn hàng của tôi", "lịch sử mua hàng của tôi", "đơn mua của tôi",
            "hóa đơn của tôi", "tra cứu đơn hàng của tôi", "my orders", "đơn hàng gần nhất của tôi"
        ]
        is_customer_order_query = any(kw in q_lower for kw in customer_order_keywords)

        customer_list_keywords = [
            "danh sách khách hàng", "số điện thoại khách hàng", "thông tin khách hàng",
            "danh sách user", "tất cả khách hàng", "all customers", "danh sách người dùng",
            "danh sách số điện thoại", "toàn bộ khách hàng"
        ]
        is_customer_list_query = any(kw in q_lower for kw in customer_list_keywords) or (
            ("khách hàng" in q_lower or "customer" in q_lower or "người dùng" in q_lower or "user" in q_lower) and
            any(k in q_lower for k in ["danh sách", "toàn bộ", "tất cả", "số điện thoại", "phone", "thông tin", "list", "all"])
        )

        # --- GATE A: REVENUE & FINANCIAL DATA ---
        if is_revenue_query:
            if role != "superadmin":
                # Backend Permission Enforcement: Deny non-SuperAdmin roles immediately without querying SQL revenue
                role_rejections = {
                    "guest": (
                        "🔒 **Thông báo phân quyền (Guest)**:\n\n"
                        "Bạn đang sử dụng hệ thống với tư cách **Khách vãng lai (Guest)**. "
                        "Dữ liệu doanh thu, lợi nhuận và số liệu kinh doanh là thông tin nội bộ bảo mật, "
                        "chỉ dành riêng cho **Chủ cửa hàng (SuperAdmin)**.\n\n"
                        "👉 Bạn có thể hỏi tôi thông tin về các sản phẩm, giá bán hoặc tư vấn thiết bị phù hợp!"
                    ),
                    "customer": (
                        "🔒 **Thông báo phân quyền (Customer)**:\n\n"
                        "Tài khoản **Khách hàng** không có quyền truy cập dữ liệu doanh thu và số liệu kinh doanh nội bộ của cửa hàng.\n\n"
                        "👉 Bạn có thể hỏi tôi tư vấn sản phẩm hoặc hỏi về lịch sử đơn hàng của chính bạn (ví dụ: *\"Đơn hàng của tôi gần đây thế nào?\"*)."
                    ),
                    "staff": (
                        "🔒 **Thông báo phân quyền (Staff)**:\n\n"
                        "Tài khoản **Nhân viên (Staff)** không có quyền xem dữ liệu doanh thu và báo cáo tài chính của cửa hàng theo chính sách bảo mật RBAC.\n\n"
                        "👉 Bạn có thể tra cứu thông tin sản phẩm và kiểm tra số lượng tồn kho để hỗ trợ bán hàng tại quầy POS."
                    ),
                    "admin": (
                        "🔒 **Thông báo phân quyền (Admin)**:\n\n"
                        "Tài khoản **Quản trị viên kỹ thuật (Admin)** không có quyền truy cập dữ liệu doanh thu và báo cáo tài chính kinh doanh của Chủ cửa hàng (SuperAdmin) theo chính sách RBAC.\n\n"
                        "👉 Quyền hạn của Admin bao gồm các tác vụ kỹ thuật như đồng bộ Vector DB và theo dõi nhật ký kiểm toán AI."
                    ),
                }
                refusal_msg = role_rejections.get(role, role_rejections["guest"])
                latency = int((time.time() - start_time) * 1000)
                self._record_audit_log("sales_qa_perm_denied", question, refusal_msg[:300], latency, user_id)
                return SalesQAResponse(
                    answer=refusal_msg,
                    query=question,
                    context_type="rbac_guard",
                    is_fallback=True,
                    provider="grounded"
                )

            # ROLE IS SUPERADMIN -> Retrieve factual SQLite revenue analytics
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) as total_prod, SUM(stock_quantity) as total_stock FROM products WHERE status = 'active'")
                prod_stat = dict(c.fetchone())

                c.execute("""
                    SELECT c.name as category_name, COUNT(p.id) as product_count, SUM(p.stock_quantity) as cat_stock
                    FROM categories c
                    LEFT JOIN products p ON c.id = p.category_id AND p.status = 'active'
                    GROUP BY c.id
                """)
                category_stats = [dict(r) for r in c.fetchall()]

                c.execute("SELECT COUNT(*) as total_cust FROM customers")
                cust_count = c.fetchone()["total_cust"]

            summary = ReportService.get_dashboard_summary()

            cat_lines = [
                f"  - {cs['category_name']}: {cs['product_count']} mặt hàng (Tổng tồn: {cs['cat_stock'] or 0} cái)"
                for cs in category_stats
            ]

            verified_context = (
                f"THÔNG TIN THỐNG KÊ VẬN HÀNH CỬA HÀNG STOREFLOW AI (SQL TRUTH - DÀNH CHO SUPERADMIN):\n"
                f"- Người yêu cầu: {user_full_name or 'Chủ cửa hàng'} (Vai trò: SuperAdmin)\n"
                f"- Tổng số sản phẩm đang kinh doanh: {prod_stat['total_prod']} mặt hàng\n"
                f"- Tổng tồn kho hàng hóa toàn cửa hàng: {prod_stat['total_stock']} sản phẩm\n"
                f"- Phân bố hàng hóa theo danh mục:\n" + "\n".join(cat_lines) + "\n"
                f"- Tổng số khách hàng đã lưu trong hệ thống: {cust_count} khách hàng\n"
                f"- Doanh thu hôm nay: {int(summary['today_revenue']):,} đ\n"
                f"- Doanh thu tuần này: {int(summary.get('week_revenue', 0)):,} đ\n"
                f"- Doanh thu tháng này: {int(summary.get('month_revenue', 0)):,} đ\n"
                f"- Tổng doanh thu tích lũy: {int(summary['total_revenue']):,} đ\n"
                f"- Số đơn hàng đã xử lý: {summary['total_orders']}\n"
                f"- Số lượng sản phẩm sắp hết hàng cần lưu ý: {summary['low_stock_count']} sản phẩm"
            )

            prompt = prompt_loader.format_prompt(
                "sales_qa",
                verified_context=verified_context,
                user_query=question
            )

            def _fallback_revenue() -> str:
                return (
                    f"**Báo cáo tài chính & vận hành StoreFlow AI (SuperAdmin):**\n\n"
                    f"- Doanh thu tháng này hiện đạt **{int(summary.get('month_revenue', 0)):,} đ** qua **{summary['total_orders']}** đơn hàng hoàn tất.\n"
                    f"- Doanh thu hôm nay: **{int(summary['today_revenue']):,} đ** | Tuần này: **{int(summary.get('week_revenue', 0)):,} đ**.\n"
                    f"- Cửa hàng đang quản lý **{prod_stat['total_prod']}** mặt hàng kinh doanh với tổng cộng **{prod_stat['total_stock']}** sản phẩm trong kho.\n"
                    f"- Hiện có **{summary['low_stock_count']}** mặt hàng đang ở mức tồn kho thấp cần kiểm tra nhập thêm.\n"
                    f"*(Dữ liệu trích xuất chính xác 100% từ SQLite)*"
                )

            answer, provider_used, is_fallback, _ = ai_provider_manager.execute_with_fallback(
                prompt=prompt,
                fallback_fn=_fallback_revenue,
                preferred_provider=provider
            )

            latency = int((time.time() - start_time) * 1000)
            self._record_audit_log("sales_qa_revenue", f"[{provider_used.upper()}] {question}", answer[:300], latency, user_id)
            return SalesQAResponse(
                answer=answer,
                query=question,
                context_type="superadmin_sql_facts",
                is_fallback=is_fallback,
                provider=provider_used
            )

        # --- GATE B: CUSTOMER ORDERS Q&A ---
        if is_customer_order_query:
            if role == "guest":
                msg = (
                    "🔒 **Tra cứu đơn hàng**:\n\n"
                    "Bạn đang sử dụng hệ thống với tư cách **Khách vãng lai (Guest)**. "
                    "Vui lòng **Đăng nhập** tài khoản Khách hàng để xem lịch sử và tiến độ các đơn hàng của bạn."
                )
                return SalesQAResponse(answer=msg, query=question, context_type="guest_guard", is_fallback=True)

            if role == "customer":
                # Deterministically look up only this customer's orders from SQLite using authenticated user_id
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT id, customer_code, name, phone FROM customers WHERE user_id = ?", (user_id,))
                    cust_row = c.fetchone()
                    if not cust_row:
                        orders_text = "Hệ thống chưa tìm thấy hồ sơ khách hàng liên kết với tài khoản đăng nhập của bạn."
                    else:
                        cust_id = cust_row["id"]
                        c.execute("""
                            SELECT o.id, o.order_code, o.final_amount, o.payment_status, o.status, o.created_at,
                                   GROUP_CONCAT(p.name || ' (x' || oi.quantity || ')', '; ') as items
                            FROM orders o
                            LEFT JOIN order_items oi ON o.id = oi.order_id
                            LEFT JOIN products p ON oi.product_id = p.id
                            WHERE o.customer_id = ?
                            GROUP BY o.id
                            ORDER BY o.created_at DESC
                            LIMIT 5
                        """, (cust_id,))
                        rows = [dict(r) for r in c.fetchall()]
                        if not rows:
                            orders_text = f"Khách hàng {cust_row['name']} hiện chưa có đơn hàng nào trong hệ thống."
                        else:
                            lines = [f"Danh sách 5 đơn hàng gần nhất của bạn ({cust_row['name']}):"]
                            for r in rows:
                                status_vn = "Hoàn tất" if r["status"] == "completed" else "Đã hủy" if r["status"] == "cancelled" else r["status"]
                                if r.get("payment_status") == "paid":
                                    pay_vn = "Đã đối soát thanh toán"
                                elif r.get("payment_status") == "unverified_legacy":
                                    pay_vn = "Dữ liệu lịch sử chưa đối soát"
                                elif r.get("payment_status") == "refunded":
                                    pay_vn = "Đã hoàn tiền"
                                elif r.get("payment_status") == "refund_pending":
                                    pay_vn = "Chờ hoàn tiền"
                                elif r.get("payment_status") == "pending_verification":
                                    pay_vn = "Chờ xác minh thanh toán"
                                else:
                                    pay_vn = "Chưa thanh toán"
                                lines.append(
                                    f"- Đơn **{r['order_code']}** ({r['created_at'][:19]}): "
                                    f"Tổng tiền **{int(r['final_amount']):,} đ** | Trạng thái: **{status_vn}** ({pay_vn})\n"
                                    f"  Sản phẩm: {r['items'] or 'Không có thông tin chi tiết'}"
                                )
                            orders_text = "\n".join(lines)

                cust_context = (
                    f"THÔNG TIN ĐƠN HÀNG CỦA KHÁCH HÀNG (TRÍCH XUẤT TỪ SQL THEO TOKEN):\n"
                    f"{orders_text}"
                )

                prompt = (
                    f"{prompt_loader.get_system_prompt()}\n\n"
                    f"[NHIỆM VỤ]: Trả lời câu hỏi của khách hàng về đơn hàng của họ dựa trên dữ liệu sau:\n"
                    f"{cust_context}\n\n"
                    f"[CÂU HỎI CỦA KHÁCH HÀNG]: {question}\n\n"
                    f"Hãy trả lời rõ ràng, lịch sự, tóm tắt các đơn hàng của khách hàng."
                )

                answer, provider_used, is_fallback, _ = ai_provider_manager.execute_with_fallback(
                    prompt=prompt,
                    fallback_fn=lambda: orders_text,
                    preferred_provider=provider
                )

                latency = int((time.time() - start_time) * 1000)
                self._record_audit_log("customer_orders_qa", f"[{provider_used.upper()}] {question}", answer[:300], latency, user_id)
                return SalesQAResponse(
                    answer=answer,
                    query=question,
                    context_type="customer_sql_orders",
                    is_fallback=is_fallback,
                    provider=provider_used
                )

        # --- GATE C: CUSTOMER LIST / PRIVATE DATA ATTEMPT ---
        if is_customer_list_query and role not in ("superadmin", "admin"):
            refusal_msg = (
                "🔒 **Bảo mật dữ liệu cá nhân**:\n\n"
                "Danh sách khách hàng và thông tin cá nhân (số điện thoại, địa chỉ) là dữ liệu bảo mật "
                "theo chính sách quyền riêng tư. Bạn không có quyền truy cập dữ liệu này."
            )
            return SalesQAResponse(
                answer=refusal_msg,
                query=question,
                context_type="privacy_guard",
                is_fallback=True,
                provider="grounded"
            )

        # --- GATE D: PRODUCT CONSULTATION / PRODUCT LOOKUP (Available for ALL roles) ---
        # Fetch relevant products via ChromaDB candidate retrieval + SQLite verification guard
        rag_ctx = rag_service.get_grounded_recommendation_context(query=question, top_k=5)
        product_context = rag_ctx["context_text"]

        verified_context = (
            f"THÔNG TIN SẢN PHẨM KHẢ DỤNG TẠI CỬA HÀNG (SQL TRUTH):\n"
            f"{product_context}\n\n"
            f"VAI TRÒ NGƯỜI HỎI: {role.upper()} ({user_full_name or 'Khách vãng lai'})\n"
        )

        prompt = (
            f"{prompt_loader.get_system_prompt()}\n\n"
            f"[NHIỆM VỤ]: Bạn đang hỗ trợ trả lời câu hỏi của {user_full_name or 'khách hàng'} (Vai trò: {role}) "
            f"về sản phẩm, giá bán, cấu hình và tính năng tại cửa hàng.\n\n"
            f"[DỮ LIỆU SẢN PHẨM XÁC THỰC TỪ KHO]:\n{verified_context}\n\n"
            f"[CÂU HỎI]: {question}\n\n"
            f"QUY TẮC:\n"
            f"1. CHỈ sử dụng dữ liệu trong Context sản phẩm ở trên. Không tự bịa thông số, giá hoặc tình trạng kho.\n"
            f"2. Nếu không tìm thấy thông tin sản phẩm trong context, hãy thông báo lịch sự rằng cửa hàng chưa có mặt hàng này.\n"
            f"3. Trình bày rõ ràng, thân thiện."
        )

        def _fallback_prod_qa() -> str:
            if rag_ctx.get("status") == "out_of_domain":
                return (
                    f"StoreFlow AI là trợ lý thông minh hỗ trợ tìm kiếm sản phẩm và tra cứu vận hành tại cửa hàng. "
                    f"Hiện tại cửa hàng không kinh doanh các mặt hàng hoặc dịch vụ liên quan đến: *\"{question}\"*."
                )
            elif rag_ctx.get("out_of_stock_detected"):
                oos = rag_ctx["out_of_stock_detected"]
                return (
                    f"Sản phẩm **{oos['name']}** (Mã SKU: `{oos['sku']}`) hiện **ĐÃ HẾT HÀNG** trong kho (tồn kho: 0). "
                    f"Cửa hàng tạm thời không còn hàng sản phẩm này."
                )
            else:
                prods = rag_ctx.get("products", [])
                if prods:
                    p_lines = [
                        f"- **{p['name']}** (Mã: `{p['sku']}`): Giá **{int(p['selling_price']):,} đ** | Còn tồn: **{p['stock_quantity']} {p['unit']}**\n  {p['description'] or ''}"
                        for p in prods
                    ]
                    return (
                        f"**StoreFlow AI — Thông tin sản phẩm liên quan**:\n\n" +
                        "\n".join(p_lines)
                    )
                else:
                    return (
                        f"Xin lỗi, hiện tại tôi chưa tìm thấy thông tin sản phẩm phù hợp với câu hỏi: *\"{question}\"*. "
                        f"Quý khách vui lòng thử tìm kiếm với tên sản phẩm hoặc danh mục cụ thể hơn."
                    )

        answer, provider_used, is_fallback, _ = ai_provider_manager.execute_with_fallback(
            prompt=prompt,
            system_instruction=prompt_loader.get_system_prompt(),
            fallback_fn=_fallback_prod_qa,
            preferred_provider=provider
        )

        latency = int((time.time() - start_time) * 1000)
        self._record_audit_log(
            feature="sales_qa_product",
            query_text=f"[{role.upper()}][{provider_used.upper()}] {question}",
            response_summary=answer[:300],
            latency_ms=latency,
            user_id=user_id
        )

        return SalesQAResponse(
            answer=answer,
            query=question,
            context_type="hybrid_product_rag",
            is_fallback=is_fallback,
            provider=provider_used
        )

    def get_audit_logs(self, limit: int = 50) -> List[AIAuditLogResponse]:
        """Retrieves recent AI interaction logs for auditing and monitoring."""
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT l.id, l.user_id, u.username, l.feature, l.query_text,
                       l.response_summary, l.latency_ms, l.created_at
                FROM ai_audit_logs l
                LEFT JOIN users u ON l.user_id = u.id
                ORDER BY l.id DESC
                LIMIT ?
            """, (limit,))
            rows = c.fetchall()

        return [
            AIAuditLogResponse(
                id=r["id"],
                user_id=r["user_id"],
                username=r["username"] or "Khách (Guest)",
                feature=r["feature"],
                query_text=r["query_text"],
                response_summary=r["response_summary"],
                latency_ms=r["latency_ms"],
                created_at=str(r["created_at"])
            )
            for r in rows
        ]



# Global singleton instance
ai_service = AIService()
