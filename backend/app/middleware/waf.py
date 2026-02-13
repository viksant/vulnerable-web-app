"""Web Application Firewall middleware with intentional bypasses.

Inspects incoming requests against blacklist patterns for SQL injection,
XSS, command injection, and path traversal. Difficulty level controls
how thorough the inspection is — lower difficulties have more bypass vectors.
"""

import re
import urllib.parse

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings

# Paths excluded from WAF inspection (health checks, documentation)
EXCLUDED_PATHS: set[str] = {
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
}

# ---------------------------------------------------------------------------
# Blacklist patterns — compiled at module level for performance
# ---------------------------------------------------------------------------

# VULN: WAF Bypass - Case-sensitive patterns allow evasion via mixed case
# (e.g., "UnIoN", "sElEcT") — only enforced case-insensitive on hard mode
SQL_PATTERNS: list[str] = [
    r"UNION",
    r"SELECT",
    r"INSERT",
    r"UPDATE",
    r"DELETE",
    r"DROP",
    r"--",
    r";",
    r"'",
    r"OR\s+1\s*=\s*1",
]

XSS_PATTERNS: list[str] = [
    r"<script",
    r"onerror\s*=",
    r"onload\s*=",
    r"javascript:",
    r"alert\s*\(",
    r"eval\s*\(",
    r"document\.",
]

CMD_PATTERNS: list[str] = [
    r";",
    r"\|",
    r"`",
    r"\$\(",
    r"&&",
]

PATH_PATTERNS: list[str] = [
    r"\.\./",
    r"\.\.\\",
]

ALL_PATTERNS: list[str] = SQL_PATTERNS + XSS_PATTERNS + CMD_PATTERNS + PATH_PATTERNS


def _compile_patterns(case_insensitive: bool) -> list[re.Pattern[str]]:
    """Compile all blacklist patterns with optional case sensitivity.

    Args:
        case_insensitive: Whether to compile with re.IGNORECASE flag.

    Returns:
        List of compiled regex pattern objects.
    """
    flags = re.IGNORECASE if case_insensitive else 0
    return [re.compile(p, flags) for p in ALL_PATTERNS]


# Pre-compiled pattern sets for each difficulty tier
_PATTERNS_MEDIUM = _compile_patterns(case_insensitive=False)
_PATTERNS_HARD = _compile_patterns(case_insensitive=True)


def _check_patterns(payload: str, patterns: list[re.Pattern[str]]) -> bool:
    """Test whether any pattern matches the given payload.

    Args:
        payload: The concatenated string to inspect.
        patterns: Pre-compiled regex patterns to test against.

    Returns:
        True if at least one pattern matched.
    """
    return any(p.search(payload) for p in patterns)


def _extract_inspectable_data(
    request: Request,
    body: bytes,
    difficulty: str,
) -> str:
    """Build the string that the WAF inspects for malicious patterns.

    Args:
        request: The incoming HTTP request.
        body: Raw request body bytes.
        difficulty: Current difficulty level from settings.

    Returns:
        Concatenated string of all inspectable request data.
    """
    parts: list[str] = []

    # --- Query string ---
    # VULN: WAF Bypass - No URL decode on medium allows %27 to bypass single-quote detection
    # VULN: WAF Bypass - No double URL decode on hard allows %2527 to bypass after single unquote
    raw_query = str(request.url.query) if request.url.query else ""
    if difficulty == "hard":
        raw_query = urllib.parse.unquote(raw_query)
    parts.append(raw_query)

    # --- Request body ---
    # VULN: WAF Bypass - Content-Type gating: only inspects json and form-urlencoded
    # Requests with other Content-Types (e.g., text/plain, multipart) bypass body inspection
    #
    # VULN: WAF Bypass - JSON unicode escape: body is inspected as raw bytes, NOT
    # parsed JSON. JSON unicode escapes like \u0024\u0028 appear as literal backslash
    # sequences in raw bytes and do NOT match the compiled patterns (e.g., \$\( for
    # command injection). FastAPI's JSON parser decodes these AFTER the WAF check,
    # so the route handler receives the decoded characters (e.g., "$(" from \u0024\u0028).
    # Bypass example: {"date_range": "2024-01-01\u0024(id)"} bypasses $( detection.
    # Ref: https://hackerone.com/reports/297478
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type or "application/x-www-form-urlencoded" in content_type:
        try:
            parts.append(body.decode("utf-8", errors="ignore"))
        except Exception:
            pass

    # --- Headers ---
    # VULN: WAF Bypass - Limited header inspection: only checks User-Agent and Referer
    # Payloads in custom headers (X-Custom, Authorization, etc.) are never inspected
    parts.append(request.headers.get("user-agent", ""))
    parts.append(request.headers.get("referer", ""))

    return " ".join(parts)


class WAFMiddleware(BaseHTTPMiddleware):
    """Request-level Web Application Firewall.

    Inspects query strings, request bodies, and select headers against
    a blacklist of attack patterns. Difficulty level controls strictness:

    - **easy**: WAF disabled (all requests pass through).
    - **medium**: Case-sensitive patterns, no URL decoding, limited body/header inspection.
    - **hard**: Case-insensitive patterns with single URL decode, but still no double decode.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Inspect the request and block if malicious patterns are detected.

        Args:
            request: The incoming HTTP request.
            call_next: Callback to invoke the next middleware or route handler.

        Returns:
            403 JSON response if blocked, otherwise the downstream response.
        """
        # Easy mode: WAF completely disabled
        if settings.DIFFICULTY == "easy":
            return await call_next(request)

        # Skip excluded paths (health checks, Swagger docs)
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        # Read request body for inspection
        body = await request.body()

        # Select pattern set based on difficulty
        patterns = _PATTERNS_HARD if settings.DIFFICULTY == "hard" else _PATTERNS_MEDIUM

        # Build inspectable payload
        # VULN: WAF Bypass - No inline SQL comment handling (e.g., UN/**/ION passes)
        # VULN: WAF Bypass - No multiline detection (e.g., SEL\nECT passes)
        payload = _extract_inspectable_data(request, body, settings.DIFFICULTY)

        if _check_patterns(payload, patterns):
            return JSONResponse(
                status_code=403,
                content={"detail": "WAF: Request blocked"},
            )

        return await call_next(request)
