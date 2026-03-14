#!/usr/bin/env python3
"""URL normalization and deduplication.

Stdlib only. No external packages.
"""

import hashlib
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

# Tracking parameters to strip
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_cid", "utm_reader", "utm_name", "utm_social-type",
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid",
    "msclkid", "twclid", "li_fat_id",
    "mc_cid", "mc_eid",
    "yclid", "ymclid",
    "_hsenc", "_hsmi", "hsCtaTracking",
    "vero_id", "vero_conv",
    "s_cid", "s_kwcid",
    "ref", "ref_",
    "mkt_tok",
}


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication.

    - Lowercase scheme and host
    - Strip www. prefix
    - Strip trailing slash from path
    - Strip common tracking parameters
    - Strip URL fragments
    """
    url = url.strip()
    if not url:
        return url

    parsed = urlparse(url)

    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    host = parsed.hostname or ""
    host = host.lower()

    # Strip www. prefix
    if host.startswith("www."):
        host = host[4:]

    # Reconstruct netloc with port if non-default
    port = parsed.port
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    else:
        netloc = host

    # Strip trailing slash from path (but keep "/" for root)
    path = parsed.path.rstrip("/") or "/"

    # Filter out tracking params
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {
            k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS
        }
        query = urlencode(filtered, doseq=True)
    else:
        query = ""

    # Strip fragment
    fragment = ""

    return urlunparse((scheme, netloc, path, parsed.params, query, fragment))


def url_hash(url: str) -> str:
    """Return first 12 chars of MD5 hex digest of the normalized URL."""
    normalized = normalize_url(url)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:12]


def is_duplicate(url: str, existing_urls: list) -> bool:
    """Check if normalized URL matches any existing URL in the list."""
    normalized = normalize_url(url)
    for existing in existing_urls:
        if normalize_url(existing) == normalized:
            return True
    return False
