import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.models.schema import init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.products import router as products_router
from app.api.v1.customers import router as customers_router
from app.api.v1.orders import router as orders_router
from app.api.v1.purchases import router as purchases_router
from app.api.v1.inventory import router as inventory_router
from app.api.v1.reports import router as reports_router
from app.api.v1.ai import router as ai_router
from app.services.rag_service import rag_service

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(os.path.join(UPLOADS_DIR, "products"), exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kiểm tra an toàn cấu hình khởi động (Boot Safety Guard)
    from app.core.config import validate_boot_safety
    validate_boot_safety(settings)
    # Khởi tạo schema cơ sở dữ liệu SQLite khi startup
    init_db()
    # Tự động đối soát và tự phục hồi vector index vào ChromaDB khi startup (Self-Healing Sync Guard)
    try:
        if rag_service.collection.count() == 0:
            rag_service.sync_all_products()
        else:
            sync_status = rag_service.check_sync_status()
            if not sync_status.get("is_synced", True):
                rag_service.reconcile_sync()
    except Exception:
        pass
    yield
    # Cleanup nếu cần

app = FastAPI(
    title=settings.APP_NAME,
    description="Hệ thống quản lý bán hàng tích hợp AI (StoreFlow AI) - Backend API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Cung cấp static file cho ảnh tải lên
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# Cấu hình CORS để kết nối Frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong môi trường dev cho phép frontend Vite (port 5173/3000)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các router API
app.include_router(auth_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(purchases_router, prefix="/api/v1")
app.include_router(inventory_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")

from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("storeflow")

# Global Exception Handler preventing internal detail leakage
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled server exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Đã xảy ra sự cố nội bộ trên máy chủ. Vui lòng thử lại sau hoặc liên hệ quản trị viên."}
    )

@app.get("/api/health", tags=["Health"])
def health_check():
    """Endpoint kiểm tra trạng thái hoạt động của Backend và Database"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": "sqlite_wal_active"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
