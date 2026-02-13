"""API route modules for VulnShop."""

from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.cart import router as cart_router
from app.routes.export_import import export_router, import_router
from app.routes.orders import invoices_router
from app.routes.orders import router as orders_router
from app.routes.products import router as products_router
from app.routes.reviews import router as reviews_router
from app.routes.seller import router as seller_router
from app.routes.tickets import router as tickets_router
from app.routes.profile import router as profile_router
from app.routes.uploads import router as uploads_router

__all__ = [
    "admin_router",
    "auth_router",
    "cart_router",
    "export_router",
    "import_router",
    "invoices_router",
    "orders_router",
    "products_router",
    "profile_router",
    "reviews_router",
    "seller_router",
    "tickets_router",
    "uploads_router",
]
