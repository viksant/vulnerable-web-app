"""HTML input sanitizer with intentional bypasses for security testing.

Strips dangerous HTML patterns from user input. The sanitization depth
varies by difficulty level, leaving progressively fewer bypass vectors
as difficulty increases.
"""

import re

from app.config import settings

# Tags removed on medium difficulty (case-sensitive)
_MEDIUM_TAG_PATTERN = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL)

# Tags removed on hard difficulty (case-insensitive + extended tag list)
_HARD_TAG_PATTERN = re.compile(
    r"<(?:script|svg|iframe|body|details|math)\b[^>]*>.*?</(?:script|svg|iframe|body|details|math)>",
    re.DOTALL | re.IGNORECASE,
)

# Event handler attributes (medium: case-sensitive, hard: case-insensitive)
_MEDIUM_EVENT_PATTERN = re.compile(r"\bon[a-z]+=", re.ASCII)
_HARD_EVENT_PATTERN = re.compile(r"\bon[a-z]+=", re.ASCII | re.IGNORECASE)

# javascript: in href/src attributes (medium: case-sensitive, hard: case-insensitive)
_MEDIUM_JS_PROTO_PATTERN = re.compile(r"(?:href|src)\s*=\s*[\"']?\s*javascript:", re.ASCII)
_HARD_JS_PROTO_PATTERN = re.compile(
    r"(?:href|src)\s*=\s*[\"']?\s*javascript:", re.ASCII | re.IGNORECASE
)


def sanitize_html(input_string: str, difficulty: str | None = None) -> str:
    """Remove dangerous HTML patterns from an input string.

    Applies progressive sanitization based on difficulty level. Lower
    difficulty levels have more bypass vectors for security testing.

    Args:
        input_string: The raw user input to sanitize.
        difficulty: Override difficulty level. Uses ``settings.DIFFICULTY``
            when not provided.

    Returns:
        The sanitized string with dangerous patterns removed.
    """
    level = difficulty or settings.DIFFICULTY

    # Easy mode: no sanitization at all
    if level == "easy":
        return input_string

    result = input_string

    # --- Null byte handling ---
    # VULN: Sanitizer Bypass - Null byte truncation: content after \x00 is silently
    # dropped, allowing attackers to hide payloads after a null byte that may
    # be processed differently by downstream consumers
    null_pos = result.find("\x00")
    if null_pos != -1:
        result = result[:null_pos]

    if level == "hard":
        # Hard mode: case-insensitive matching with extended tag list
        # Case variation bypass (ONERROR=, OnLoad=) is blocked here via re.IGNORECASE
        result = _HARD_TAG_PATTERN.sub("", result)

        # VULN: Sanitizer Bypass - No mutation XSS handling: browser DOM mutations
        # (e.g., <noscript><p title="</noscript><img src=x onerror=alert(1)>">)
        # are not accounted for since we only do regex string-level sanitization

        # VULN: Sanitizer Bypass - HTML entity bypass: &lt;script&gt; or
        # &#x3C;script&#x3E; are not decoded before pattern matching, so
        # entity-encoded payloads pass through undetected

        # VULN: Sanitizer Bypass - Double encoding: %253Cscript%253E is not
        # URL-decoded before matching, bypassing pattern detection
        result = _HARD_EVENT_PATTERN.sub("", result)
        result = _HARD_JS_PROTO_PATTERN.sub("", result)
    else:
        # Medium mode: case-sensitive matching, limited tag coverage
        # VULN: Sanitizer Bypass - Case-sensitive tag matching: <Script>, <SCRIPT>,
        # <sCrIpT> all bypass the lowercase-only <script> pattern
        result = _MEDIUM_TAG_PATTERN.sub("", result)

        # VULN: Sanitizer Bypass (PRIMARY) - Case-sensitive event handler regex:
        # \bon[a-z]+= only matches lowercase. Mixed/upper case bypasses:
        #   <img src=x ONERROR=alert(1)>    — passes (upper case)
        #   <svg Onload=alert(1)>            — passes (mixed case)
        #   <details open ONTOGGLE=alert(1)> — passes (upper case)
        # NOTE: lowercase onerror=, ontoggle=, onload= ARE caught and stripped.
        # VULN: Sanitizer Bypass (SECONDARY) - Incomplete tag coverage: only
        # <script> tags are stripped. <img>, <svg>, <iframe>, <details>, <body>,
        # <math> tags all pass through — but their lowercase event handlers are
        # still removed by the regex above. Combine unfiltered tags WITH case-varied
        # event handlers for a working XSS payload.
        result = _MEDIUM_EVENT_PATTERN.sub("", result)

        # VULN: Sanitizer Bypass - HTML entity bypass: &lt;script&gt; or
        # &#x3C;script&#x3E; are not decoded before pattern matching, so
        # entity-encoded payloads pass through undetected
        result = _MEDIUM_JS_PROTO_PATTERN.sub("", result)

    return result
