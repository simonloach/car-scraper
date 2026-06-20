"""Unit tests for the otomoto search-page parser (no network)."""

import json

from src.car_scraper.scrapers.otomoto_search import parse_listings


def _make_html(nodes, total):
    """Wrap GraphQL nodes in the __NEXT_DATA__ / urqlState shape otomoto emits."""
    search = {
        "advertSearch": {
            "totalCount": total,
            "pageInfo": {"pageSize": 32},
            "edges": [{"node": n} for n in nodes],
        }
    }
    next_data = {
        "props": {"pageProps": {"urqlState": {"k": {"data": json.dumps(search)}}}}
    }
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'


def _advert(**params):
    return {
        "__typename": "Advert",
        "id": params.pop("id", "123"),
        "title": params.pop("title", "Lexus LC 500"),
        "url": "https://www.otomoto.pl/osobowe/oferta/lexus-lc.html",
        "createdAt": "2026-01-01T00:00:00Z",
        "price": {"amount": {"units": params.pop("price", 389000)}},
        "location": {"city": {"name": "Warszawa"}},
        "parameters": [
            {"key": k, "value": str(v), "displayValue": str(v)}
            for k, v in params.items()
        ],
    }


def test_parses_clean_fields():
    node = _advert(
        year=2017,
        mileage=31500,
        engine_power=477,
        engine_capacity=4969,
        fuel_type="petrol",
        gearbox="automatic",
    )
    listings, total = parse_listings(_make_html([node], total=1))
    assert total == 1
    assert len(listings) == 1
    got = listings[0]
    assert got["id"] == "123"
    assert got["price"] == 389000  # clean integer, not concatenated junk
    assert got["year"] == 2017
    assert got["mileage"] == 31500
    assert got["engine_power"] == 477
    assert got["engine_capacity"] == 4969
    assert got["fuel_type"] == "petrol"
    assert got["gearbox"] == "automatic"
    assert got["location"] == "Warszawa"


def test_skips_non_advert_nodes():
    listings, _ = parse_listings(
        _make_html([{"__typename": "PromotedBanner"}, _advert()], total=1)
    )
    assert len(listings) == 1


def test_missing_next_data_is_graceful():
    listings, total = parse_listings("<html>anti-bot wall</html>")
    assert listings == []
    assert total is None
