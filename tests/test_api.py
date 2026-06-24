from __future__ import annotations

import pytest
from fastapi import HTTPException

from voidbroker.api import _valid_slug


def test_valid_slug_accepts_real_market_slugs():
    # warframe.market url_name slugs are lowercase, underscore-separated; some weapon
    # slugs use hyphens. All of these must pass the boundary validator.
    for slug in ("primed_flow", "ash_prime_set", "mirage_prime_blueprint", "kuva-bramma", "1999"):
        assert _valid_slug(slug) == slug


@pytest.mark.parametrize(
    "bad",
    [
        "",  # empty
        "Ash_Prime",  # uppercase
        "../etc/passwd",  # path traversal
        "ash prime",  # space
        "a" * 200,  # over length cap
        "-leading-hyphen",  # must start alphanumeric
    ],
)
def test_valid_slug_rejects_malformed(bad):
    with pytest.raises(HTTPException):
        _valid_slug(bad)
