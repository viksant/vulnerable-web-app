-- =============================================================================
-- VulnShop P02 — Database Schema + Seed Data
-- PostgreSQL 16 — Deliberately vulnerable e-commerce platform
-- =============================================================================
--
-- VULN MARKERS (intentional weaknesses in schema):
--   - SERIAL PRIMARY KEY on users/orders → predictable IDs (IDOR vector)
--   - No CHECK constraint on users.role → arbitrary role injection
--   - products.description is TEXT without sanitization → stored HTML/XSS
--   - reviews.body is TEXT without sanitization → stored XSS vector
--   - cart_items.quantity has no CHECK > 0 → negative quantity attack
--   - cart_items.unit_price is client-supplied → price manipulation
--   - No UNIQUE(coupon_id, user_id) on coupon_uses → race condition
--   - Some users have MD5 password hashes → weak hash cracking
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- 1. users
-- VULN: IDOR - Sequential SERIAL IDs are predictable
-- VULN: Broken Auth - No CHECK on role allows arbitrary role values
-- VULN: Weak Hash - Some passwords stored as MD5 instead of bcrypt
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id                   SERIAL PRIMARY KEY,
    email                VARCHAR(255) NOT NULL UNIQUE,
    username             VARCHAR(100) NOT NULL UNIQUE,
    password_hash        VARCHAR(255) NOT NULL,
    role                 VARCHAR(50)  NOT NULL DEFAULT 'customer',
    full_name            VARCHAR(200),
    phone                VARCHAR(30),
    payment_method_last4 VARCHAR(4),
    address              VARCHAR(500),
    card_type            VARCHAR(20),
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 2. products
-- VULN: Stored XSS - description is unescaped TEXT (HTML allowed)
-- ---------------------------------------------------------------------------
CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200)   NOT NULL,
    description TEXT           NOT NULL DEFAULT '',
    price       NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    stock       INTEGER        NOT NULL DEFAULT 0 CHECK (stock >= 0),
    category    VARCHAR(100)   NOT NULL DEFAULT 'general',
    image_url   VARCHAR(500),
    seller_id   INTEGER        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active   BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE INDEX idx_products_category  ON products(category);
CREATE INDEX idx_products_seller_id ON products(seller_id);

-- ---------------------------------------------------------------------------
-- 3. reviews
-- VULN: Stored XSS - body is unescaped TEXT (HTML injection)
-- ---------------------------------------------------------------------------
CREATE TABLE reviews (
    id         SERIAL PRIMARY KEY,
    product_id INTEGER      NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id    INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      VARCHAR(255) NOT NULL DEFAULT '',
    rating     INTEGER      NOT NULL CHECK (rating >= 1 AND rating <= 5),
    body       TEXT         NOT NULL DEFAULT '',
    image_path VARCHAR(500),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE(product_id, user_id)
);

CREATE INDEX idx_reviews_product_id ON reviews(product_id);

-- ---------------------------------------------------------------------------
-- 4. cart_items
-- VULN: Business Logic - No CHECK on quantity > 0 (negative qty = negative price)
-- VULN: Price Manipulation - unit_price stored from client, not validated server-side
-- ---------------------------------------------------------------------------
CREATE TABLE cart_items (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER        NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity   INTEGER        NOT NULL DEFAULT 1,
    unit_price NUMERIC(10, 2) NOT NULL,
    added_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),
    UNIQUE(user_id, product_id)
);

-- ---------------------------------------------------------------------------
-- 5. coupons
-- ---------------------------------------------------------------------------
CREATE TABLE coupons (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(50)    NOT NULL UNIQUE,
    discount_type   VARCHAR(20)    NOT NULL CHECK (discount_type IN ('percent', 'fixed')),
    discount_value  NUMERIC(10, 2) NOT NULL CHECK (discount_value > 0),
    min_order_total NUMERIC(10, 2) NOT NULL DEFAULT 0,
    max_uses        INTEGER,
    times_used      INTEGER        NOT NULL DEFAULT 0,
    is_active       BOOLEAN        NOT NULL DEFAULT TRUE,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 6. coupon_uses
-- VULN: Race Condition - No UNIQUE(coupon_id, user_id) allows double-redeem
-- ---------------------------------------------------------------------------
CREATE TABLE coupon_uses (
    id        SERIAL PRIMARY KEY,
    coupon_id INTEGER     NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    user_id   INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    used_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 7. orders
-- VULN: IDOR - Sequential SERIAL IDs are predictable
-- VULN: Business Logic - No CHECK constraint on total — allows negative totals (fraudulent credit)
-- ---------------------------------------------------------------------------
CREATE TABLE orders (
    id             SERIAL PRIMARY KEY,
    uuid           VARCHAR(36)    NOT NULL UNIQUE DEFAULT gen_random_uuid()::text,
    user_id        INTEGER        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status         VARCHAR(30)    NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    total          NUMERIC(10, 2) NOT NULL,
    shipping_addr  TEXT,
    coupon_id      INTEGER        REFERENCES coupons(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE INDEX idx_orders_user_id ON orders(user_id);

-- ---------------------------------------------------------------------------
-- 8. order_items
-- ---------------------------------------------------------------------------
CREATE TABLE order_items (
    id         SERIAL PRIMARY KEY,
    order_id   INTEGER        NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER        NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity   INTEGER        NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0)
);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);

-- ---------------------------------------------------------------------------
-- 9. tickets
-- ---------------------------------------------------------------------------
CREATE TABLE tickets (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject    VARCHAR(300) NOT NULL,
    status     VARCHAR(30)  NOT NULL DEFAULT 'open'
                   CHECK (status IN ('open', 'in_progress', 'closed')),
    priority   VARCHAR(20)  NOT NULL DEFAULT 'medium'
                   CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_tickets_user_id ON tickets(user_id);

-- ---------------------------------------------------------------------------
-- 10. ticket_messages
-- ---------------------------------------------------------------------------
CREATE TABLE ticket_messages (
    id          SERIAL PRIMARY KEY,
    ticket_id   INTEGER     NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    user_id     INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body        TEXT        NOT NULL,
    is_internal BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ticket_messages_ticket_id ON ticket_messages(ticket_id);

-- ---------------------------------------------------------------------------
-- 11. ticket_attachments
-- ---------------------------------------------------------------------------
CREATE TABLE ticket_attachments (
    id            SERIAL PRIMARY KEY,
    ticket_id     INTEGER      NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    user_id       INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename      VARCHAR(300) NOT NULL,
    filepath      VARCHAR(500) NOT NULL,
    content_type  VARCHAR(100) NOT NULL DEFAULT 'application/octet-stream',
    file_size     INTEGER      NOT NULL DEFAULT 0,
    uploaded_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_ticket_attachments_ticket_id ON ticket_attachments(ticket_id);


-- =============================================================================
-- SEED DATA
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Users (5)
-- Admin/support/seller use bcrypt via pgcrypto; user1/user2 use MD5 (VULN)
-- ---------------------------------------------------------------------------
INSERT INTO users (email, username, password_hash, role, full_name, phone, payment_method_last4, address, card_type) VALUES
    ('admin@vulnshop.com',   'admin',   crypt('Admin2024Secure!', gen_salt('bf', 12)), 'admin',    'Platform Admin',  '+1-555-0100', '4242', NULL, NULL),
    ('support@vulnshop.com', 'support', crypt('Support2024!',     gen_salt('bf', 12)), 'support',  'Support Agent',   '+1-555-0101', NULL,   NULL, NULL),
    ('seller@vulnshop.com',  'seller',  crypt('Seller2024!',      gen_salt('bf', 12)), 'seller',   'Demo Seller',     '+1-555-0102', '1234', NULL, NULL),
    -- VULN: Weak Hash - MD5 passwords are trivially crackable
    ('user1@test.com',       'user1',   '482c811da5d5b4bc6d497ffa98491e38',             'customer', 'Alice Johnson',   '+1-555-0104', '5678', '123 Main St, Springfield, IL 62701', 'visa'),
    ('user2@test.com',       'user2',   'd8578edf8458ce06fbc5bb76a58c5ca4',             'customer', 'Bob Smith',       '+1-555-0105', '9012', '456 Oak Ave, Portland, OR 97201',    'mastercard');

-- ---------------------------------------------------------------------------
-- Products (12) — all owned by seller (id=3)
-- ---------------------------------------------------------------------------
INSERT INTO products (name, description, price, stock, category, image_url, seller_id) VALUES
    -- Electronics (4)
    ('Wireless Bluetooth Headphones',
     'Premium noise-cancelling headphones with 30h battery life. <b>Best seller!</b>',
     79.99,  150, 'electronics', '/images/headphones.jpg', 3),

    ('USB-C Fast Charger 65W',
     'GaN charger compatible with laptops, tablets and phones.',
     34.99,  300, 'electronics', '/images/charger.jpg', 3),

    ('Mechanical Keyboard RGB',
     'Hot-swappable switches, PBT keycaps, USB-C connection.',
     89.99,  80,  'electronics', '/images/keyboard.jpg', 3),

    ('Portable SSD 1TB',
     'NVMe external drive, 1050 MB/s read speed. Ultra compact.',
     109.99, 60,  'electronics', '/images/ssd.jpg', 3),

    -- Home & Garden (4)
    ('Smart LED Bulb Pack (4)',
     'Wi-Fi enabled, 16M colors, voice assistant compatible.',
     29.99,  200, 'home', '/images/bulbs.jpg', 3),

    ('Stainless Steel Water Bottle',
     'Double-wall vacuum insulated, keeps drinks cold 24h.',
     19.99,  500, 'home', '/images/bottle.jpg', 3),

    ('Bamboo Desk Organizer',
     'Eco-friendly desk caddy with 5 compartments and phone stand.',
     24.99,  120, 'home', '/images/organizer.jpg', 3),

    ('Aromatherapy Diffuser',
     'Ultrasonic 300ml diffuser with 7 LED color modes.',
     39.99,  90,  'home', '/images/diffuser.jpg', 3),

    -- Accessories (4)
    ('Laptop Stand Aluminum',
     'Ergonomic adjustable stand, fits 10-17 inch laptops.',
     44.99,  110, 'accessories', '/images/stand.jpg', 3),

    ('Webcam 1080p with Mic',
     'Auto-focus, built-in noise reduction microphone.',
     49.99,  70,  'accessories', '/images/webcam.jpg', 3),

    ('Phone Case - Universal',
     'Shockproof TPU case. Available for major brands.',
     12.99,  400, 'accessories', '/images/phonecase.jpg', 3),

    ('Wireless Mouse Ergonomic',
     'Silent clicks, adjustable DPI, USB receiver included.',
     22.99,  180, 'accessories', '/images/mouse.jpg', 3);

-- ---------------------------------------------------------------------------
-- Coupons (4)
-- ---------------------------------------------------------------------------
INSERT INTO coupons (code, discount_type, discount_value, min_order_total, max_uses, is_active, expires_at) VALUES
    ('WELCOME10', 'percent', 10.00,  0.00,   NULL, TRUE,  '2026-12-31 23:59:59+00'),
    ('SUMMER50',  'fixed',   50.00,  100.00, 200,  TRUE,  '2026-08-31 23:59:59+00'),
    ('VIPFREE',   'percent', 100.00, 0.00,   5,    TRUE,  '2026-12-31 23:59:59+00'),
    ('EXPIRED20', 'percent', 20.00,  50.00,  100,  FALSE, '2025-01-01 00:00:00+00');

-- ---------------------------------------------------------------------------
-- Reviews (10) — distributed across products and users
-- Two reviews include benign HTML to demonstrate stored XSS surface
-- ---------------------------------------------------------------------------
INSERT INTO reviews (product_id, user_id, title, rating, body) VALUES
    (1, 4, 'Amazing headphones!',        5, 'Amazing headphones! Noise cancellation is top notch.'),
    (1, 5, 'Great sound quality',         4, 'Great sound quality. Battery lasts as advertised.'),
    (2, 4, 'Fast and compact charger',    4, 'Charges my laptop quickly. Compact design.'),
    (3, 5, 'Love this keyboard!',         5, '<b>Absolutely love this keyboard!</b> The switches feel great.'),
    (4, 4, 'Gets warm under load',        3, 'Fast drive but gets warm under sustained write loads.'),
    (5, 5, 'Easy Alexa setup',            4, 'Easy setup with Alexa. Colors are <i>vivid</i> and bright.'),
    (6, 4, 'Keeps water ice cold',        5, 'Keeps water ice cold for a full day. Highly recommend.'),
    (7, 5, 'Nice but narrow slot',        3, 'Looks nice but the phone stand slot is a bit narrow.'),
    (9, 4, 'Sturdy laptop stand',         4, 'Sturdy build. My neck thanks me for the better posture.'),
    (10, 5, 'Average webcam',             2, 'Auto-focus hunts in low light. Mic quality is average.');

-- ---------------------------------------------------------------------------
-- Orders (5) — different users and statuses
-- ---------------------------------------------------------------------------
INSERT INTO orders (uuid, user_id, status, total, shipping_addr, coupon_id) VALUES
    ('a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d', 4, 'delivered',  114.98, '123 Main St, Springfield, IL 62701',      NULL),
    ('b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e', 4, 'shipped',    89.99,  '123 Main St, Springfield, IL 62701',      1),
    ('c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f', 5, 'confirmed',  64.98,  '456 Oak Ave, Portland, OR 97201',         NULL),
    ('d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a', 5, 'pending',    109.99, '456 Oak Ave, Portland, OR 97201',         2),
    ('e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b', 4, 'cancelled',  44.99,  '123 Main St, Springfield, IL 62701',      NULL);

-- ---------------------------------------------------------------------------
-- Order items
-- ---------------------------------------------------------------------------
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    -- Order 1: headphones + charger
    (1, 1, 1, 79.99),
    (1, 2, 1, 34.99),
    -- Order 2: keyboard (with WELCOME10 coupon)
    (2, 3, 1, 89.99),
    -- Order 3: water bottle + desk organizer
    (3, 6, 1, 19.99),
    (3, 7, 1, 24.99),
    -- Order 4: portable SSD (with SUMMER50 coupon, pending)
    (4, 4, 1, 109.99),
    -- Order 5: laptop stand (cancelled)
    (5, 9, 1, 44.99);

-- ---------------------------------------------------------------------------
-- Coupon uses (track redemptions for orders that used coupons)
-- ---------------------------------------------------------------------------
INSERT INTO coupon_uses (coupon_id, user_id) VALUES
    (1, 4),
    (2, 5);

-- ---------------------------------------------------------------------------
-- Tickets (3)
-- ---------------------------------------------------------------------------
INSERT INTO tickets (user_id, subject, status, priority) VALUES
    (4, 'Order #1 arrived damaged',           'open',        'high'),
    (5, 'How to return a product?',           'closed',      'medium'),
    (4, 'Cannot apply coupon code SUMMER50',  'in_progress', 'medium');

-- ---------------------------------------------------------------------------
-- Ticket messages
-- ---------------------------------------------------------------------------
INSERT INTO ticket_messages (ticket_id, user_id, body, is_internal) VALUES
    -- Ticket 1: open, high priority
    (1, 4, 'The headphones box arrived crushed and the left earcup is cracked. Please help.', FALSE),
    (1, 2, 'Sorry to hear that! We will send a replacement. Could you upload a photo of the damage?', FALSE),
    (1, 4, 'Sure, uploading now.', FALSE),
    (1, 2, 'INTERNAL: Customer is VIP, expedite replacement. Auth: refund $79.99', TRUE),
    -- Ticket 2: closed
    (2, 5, 'I would like to return the desk organizer. What is the process?', FALSE),
    (2, 2, 'You can initiate a return from your order page within 30 days. I have enabled the option for you.', FALSE),
    (2, 5, 'Got it, thanks!', FALSE),
    -- Ticket 3: in progress
    (3, 4, 'I keep getting "invalid coupon" when trying to apply SUMMER50 at checkout.', FALSE),
    (3, 2, 'Let me check the coupon configuration. One moment please.', FALSE),
    (3, 2, 'INTERNAL: Coupon SUMMER50 requires min $100 order. Customer cart is $89.99', TRUE);

-- ---------------------------------------------------------------------------
-- Ticket attachments (1 — for ticket 1)
-- ---------------------------------------------------------------------------
INSERT INTO ticket_attachments (ticket_id, user_id, filename, filepath, content_type, file_size) VALUES
    (1, 4, 'damaged_headphones.jpg', '/uploads/tickets/1/damaged_headphones.jpg', 'image/jpeg', 245760);
