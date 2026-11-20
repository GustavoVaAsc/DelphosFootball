"""The allowlist that guards the fallback inference endpoint.

Input: the configured fallback URL and the peer's range.
Output: the validated URL, or a ValueError naming the variable that is wrong.
Responsibility: decide whether the fallback endpoint may be configured at all.
The rules are an allowlist, not a syntax check: the peer must be an IP literal
inside the configured range, because a well-formed address outside it — a
transposed peer IP, a public host — would receive the club's prompts in
cleartext.

A hostname is refused: it could resolve anywhere, and DNS would defeat the
allowlist. Loopback, link-local, unspecified, multicast and reserved addresses
are refused whatever the range says, because none of them names another
machine. No userinfo, no query string, no fragment and no whitespace: an
operator may put an API key in the query, and it must not reach the logs.

The limit of this rule is honest: a transposed address INSIDE the allowed
range still passes it. What stops that case is the probe the backend makes
before it gives the peer anything, and the ZeroTier ACL that pins the
published port to the peer.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

FALLBACK_URL_VARIABLE = "DELPHOS_LLM_FALLBACK_API_URL"
"""The name of the fallback URL variable, named in the error a bad value raises."""

FALLBACK_CIDR_VARIABLE = "DELPHOS_LLM_FALLBACK_PEER_CIDR"
"""The name of the peer range variable, named in the error a bad value raises."""

_PRIVATE_BLOCKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)
"""The RFC1918 blocks a peer's range must sit inside."""


def validate_fallback_url(value: str) -> str:
    """The validated fallback URL, or a ValueError naming its variable."""
    url = value.strip()
    if not url:
        return url
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise ValueError(f"{FALLBACK_URL_VARIABLE} is not a valid URL: {exc}") from exc
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"{FALLBACK_URL_VARIABLE} must be empty or an http(s) URL, got {parsed.scheme!r}"
        )
    if not parsed.hostname:
        raise ValueError(f"{FALLBACK_URL_VARIABLE} must name a host")
    if parsed.username or parsed.password:
        raise ValueError(f"{FALLBACK_URL_VARIABLE} must not carry credentials")
    if parsed.query:
        raise ValueError(f"{FALLBACK_URL_VARIABLE} must not carry a query string")
    if parsed.fragment:
        raise ValueError(f"{FALLBACK_URL_VARIABLE} must not carry a fragment")
    if any(char.isspace() for char in url):
        raise ValueError(f"{FALLBACK_URL_VARIABLE} must not contain whitespace")
    _reject_unreachable_address(parsed.hostname)
    return url


def validate_peer_cidr(value: str) -> str:
    """The validated peer range, or a ValueError naming its variable.

    The range must be a subset of an RFC1918 private block: the peer sits on
    the club's private network (the ZeroTier overlay assigns private
    addresses), so a range that admits the public internet would void the
    allowlist it is meant to provide.
    """
    cidr = value.strip()
    if not cidr:
        return cidr  # an empty range is refused only when a fallback URL is set
    try:
        network = ipaddress.ip_network(cidr, strict=False)
    except ValueError as exc:
        raise ValueError(f"{FALLBACK_CIDR_VARIABLE} is not a valid CIDR: {exc}") from exc
    if network.version != 4:
        raise ValueError(f"{FALLBACK_CIDR_VARIABLE} must be an IPv4 range")
    if not any(network.subnet_of(block) for block in _PRIVATE_BLOCKS):
        raise ValueError(
            f"{FALLBACK_CIDR_VARIABLE} must be inside a private range "
            f"({', '.join(str(block) for block in _PRIVATE_BLOCKS)}); "
            "the peer sits on the club's private network"
        )
    return cidr


def check_fallback_in_range(url: str, cidr: str) -> None:
    """Whether the fallback's address sits inside the peer's range.

    The range is not optional when a fallback URL is set: without it there is
    no allowlist, and the allowlist is the point of the check.
    """
    if not url.strip():
        return
    range_text = cidr.strip()
    if not range_text:
        raise ValueError(
            f"{FALLBACK_CIDR_VARIABLE} must name the peer's range when "
            f"{FALLBACK_URL_VARIABLE} is set"
        )
    try:
        network = ipaddress.ip_network(range_text, strict=False)
    except ValueError as exc:
        raise ValueError(f"{FALLBACK_CIDR_VARIABLE} is not a valid CIDR: {exc}") from exc
    host = urlsplit(url.strip()).hostname or ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return  # the URL validator already refused a hostname
    if address not in network:
        raise ValueError(
            f"{FALLBACK_URL_VARIABLE} must name an address inside "
            f"{FALLBACK_CIDR_VARIABLE} ({range_text}), got {host}"
        )


def _reject_unreachable_address(host: str) -> None:
    """Refuse an address that is never a peer, and a host that is not an address."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError(
            f"{FALLBACK_URL_VARIABLE} must name an IP address, not the hostname {host!r}"
        ) from exc
    if address.is_loopback:
        reason = "a loopback address"
    elif address.is_link_local:
        reason = "a link-local address"
    elif address.is_unspecified:
        reason = "the unspecified address"
    elif address.is_multicast:
        reason = "a multicast address"
    elif address.is_reserved:
        reason = "a reserved address"
    else:
        return
    raise ValueError(f"{FALLBACK_URL_VARIABLE} must not name {reason}: {host}")
