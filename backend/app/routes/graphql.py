"""GraphQL API via Strawberry with intentional security weaknesses.

Exposes a GraphQL endpoint at ``/api/graphql`` with three deliberate
vulnerabilities: introspection enabled (information disclosure),
IDOR on order queries (no ownership check), and user info disclosure
(exposes email/role/full_name without authentication).

The GraphQL endpoint does NOT appear in Swagger/OpenAPI — it uses
Strawberry's built-in GraphiQL UI, creating a hidden attack surface.
"""

from typing import Optional

import strawberry
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from strawberry.fastapi import GraphQLRouter

from app.database import get_db
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User


# ---------------------------------------------------------------------------
# Strawberry GraphQL types
# ---------------------------------------------------------------------------


@strawberry.type
class ProductType:
    """GraphQL representation of a product."""

    id: int
    name: str
    description: str
    price: float
    stock: int
    category: str
    image_url: Optional[str]
    seller_id: int
    is_active: bool


@strawberry.type
class UserType:
    """GraphQL representation of a user.

    VULN: Exposes sensitive fields (email, role, full_name) without
    requiring authentication or ownership verification.
    """

    id: int
    email: str
    username: str
    role: str
    full_name: Optional[str]
    is_active: bool


@strawberry.type
class OrderItemType:
    """GraphQL representation of an order line item."""

    id: int
    product_id: int
    quantity: int
    unit_price: float


@strawberry.type
class OrderType:
    """GraphQL representation of an order with nested user and items."""

    id: int
    user_id: int
    status: str
    total: float
    shipping_addr: Optional[str]
    created_at: str

    user: Optional[UserType] = None
    items: list[OrderItemType] = strawberry.field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper: convert ORM instances to Strawberry types
# ---------------------------------------------------------------------------


def _product_to_type(product: Product) -> ProductType:
    """Map a Product ORM instance to its GraphQL type.

    Args:
        product: SQLAlchemy Product model instance.

    Returns:
        Strawberry ProductType with all fields populated.
    """
    return ProductType(
        id=product.id,
        name=product.name,
        description=product.description,
        price=float(product.price),
        stock=product.stock,
        category=product.category,
        image_url=product.image_url,
        seller_id=product.seller_id,
        is_active=product.is_active,
    )


def _user_to_type(user: User) -> UserType:
    """Map a User ORM instance to its GraphQL type.

    Args:
        user: SQLAlchemy User model instance.

    Returns:
        Strawberry UserType exposing email, role, and full_name.
    """
    return UserType(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        full_name=user.full_name,
        is_active=user.is_active,
    )


def _order_item_to_type(item: OrderItem) -> OrderItemType:
    """Map an OrderItem ORM instance to its GraphQL type.

    Args:
        item: SQLAlchemy OrderItem model instance.

    Returns:
        Strawberry OrderItemType with quantity and price.
    """
    return OrderItemType(
        id=item.id,
        product_id=item.product_id,
        quantity=item.quantity,
        unit_price=float(item.unit_price),
    )


def _order_to_type(order: Order, include_user: bool = True) -> OrderType:
    """Map an Order ORM instance to its GraphQL type with nested relations.

    Args:
        order: SQLAlchemy Order model instance (with relations loaded).
        include_user: Whether to include the nested user object.

    Returns:
        Strawberry OrderType with optional user and items.
    """
    user_type = None
    if include_user and order.user:
        user_type = _user_to_type(order.user)

    items = [_order_item_to_type(item) for item in order.items]

    return OrderType(
        id=order.id,
        user_id=order.user_id,
        status=order.status,
        total=float(order.total),
        shipping_addr=order.shipping_addr,
        created_at=order.created_at.isoformat(),
        user=user_type,
        items=items,
    )


# ---------------------------------------------------------------------------
# Query resolvers
# ---------------------------------------------------------------------------


@strawberry.type
class Query:
    """Root GraphQL query type with intentional access control weaknesses."""

    @strawberry.field
    async def product(self, id: int, info: strawberry.types.Info) -> Optional[ProductType]:
        """Fetch a single product by ID (secure — parameterized ORM query).

        Args:
            id: Product primary key.
            info: Strawberry resolver context.

        Returns:
            ProductType if found, None otherwise.
        """
        db: AsyncSession = info.context["db"]
        result = await db.execute(
            select(Product).where(Product.id == id, Product.is_active.is_(True))
        )
        product = result.scalar_one_or_none()
        if not product:
            return None
        return _product_to_type(product)

    @strawberry.field
    async def products(
        self,
        info: strawberry.types.Info,
        category: Optional[str] = None,
    ) -> list[ProductType]:
        """List active products with optional category filter (secure).

        Args:
            info: Strawberry resolver context.
            category: Optional category to filter by.

        Returns:
            List of active products matching the filter.
        """
        db: AsyncSession = info.context["db"]
        query = select(Product).where(Product.is_active.is_(True))
        if category:
            query = query.where(Product.category == category)
        result = await db.execute(query)
        return [_product_to_type(p) for p in result.scalars().all()]

    # VULN: IDOR - Any user (or unauthenticated) can access any order by guessing
    # sequential IDs. No authorization check verifies order ownership.
    # Ref: https://hackerone.com/reports/489146
    @strawberry.field
    async def order(self, id: int, info: strawberry.types.Info) -> Optional[OrderType]:
        """Fetch any order by ID without ownership verification.

        This resolver intentionally omits authorization checks,
        allowing any caller to access any order by its sequential ID.

        Args:
            id: Order primary key (sequential, guessable).
            info: Strawberry resolver context.

        Returns:
            OrderType with user details and items, or None.
        """
        db: AsyncSession = info.context["db"]
        result = await db.execute(
            select(Order)
            .where(Order.id == id)
            .options(
                selectinload(Order.user),
                selectinload(Order.items),
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            return None
        return _order_to_type(order)

    # VULN: Info Disclosure - Exposes user email, role, and full_name to anyone
    # No authentication required, no ownership check
    # Ref: https://hackerone.com/reports/508459
    @strawberry.field
    async def user(self, id: int, info: strawberry.types.Info) -> Optional[UserType]:
        """Fetch any user profile by ID without authentication.

        Intentionally exposes sensitive user fields (email, role,
        full_name) without requiring any authentication or
        verifying that the caller owns the requested profile.

        Args:
            id: User primary key (sequential, guessable).
            info: Strawberry resolver context.

        Returns:
            UserType with email and role exposed, or None.
        """
        db: AsyncSession = info.context["db"]
        result = await db.execute(select(User).where(User.id == id))
        user = result.scalar_one_or_none()
        if not user:
            return None
        return _user_to_type(user)


# ---------------------------------------------------------------------------
# Schema and router
# ---------------------------------------------------------------------------

# VULN: GraphQL Introspection - Schema introspection left enabled in production,
# allowing attackers to discover all types, fields, and query capabilities
# Ref: https://hackerone.com/reports/291531
schema = strawberry.Schema(query=Query)


async def get_graphql_context(db: AsyncSession = Depends(get_db)) -> dict:
    """Build the Strawberry context dict with a database session.

    Uses FastAPI's dependency injection to obtain an async session
    managed by the same lifecycle as regular route handlers.

    Args:
        db: Database session injected via Depends(get_db).

    Returns:
        Dict with the ``db`` session for resolver access.
    """
    return {"db": db}


# GraphQL router with GraphiQL IDE enabled (additional info disclosure)
graphql_app = GraphQLRouter(
    schema,
    context_getter=get_graphql_context,
    graphql_ide="graphiql",
)
