from __future__ import annotations

import unittest
import urllib.parse
from unittest.mock import Mock

from product_mcp_server.app.product_client import ProductAPIClient, ProductAPIError


class ProductAPIClientPaginationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = ProductAPIClient(base_url="http://products.test")

    @staticmethod
    def _query(path: str) -> dict[str, list[str]]:
        return urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)

    def test_list_products_fetches_every_page_beyond_supplier_limit(self) -> None:
        catalog = [{"id": product_id} for product_id in range(250)]
        requested_offsets: list[int] = []

        def fake_get(path: str):
            query = self._query(path)
            limit = int(query["limit"][0])
            offset = int(query["offset"][0])
            requested_offsets.append(offset)
            self.assertEqual(limit, 100)
            self.assertEqual(query["sort"], ["name"])
            return 200, {
                "count": len(catalog),
                "limit": limit,
                "offset": offset,
                "results": catalog[offset : offset + limit],
            }

        self.client._do_get = Mock(side_effect=fake_get)

        self.assertEqual(self.client.list_products(), catalog)
        self.assertEqual(requested_offsets, [0, 100, 200])

    def test_list_products_stops_without_requesting_an_extra_empty_page(self) -> None:
        catalog = [{"id": product_id} for product_id in range(200)]

        def fake_get(path: str):
            query = self._query(path)
            limit = int(query["limit"][0])
            offset = int(query["offset"][0])
            return 200, {
                "count": len(catalog),
                "limit": limit,
                "offset": offset,
                "results": catalog[offset : offset + limit],
            }

        self.client._do_get = Mock(side_effect=fake_get)

        self.assertEqual(self.client.list_products(), catalog)
        self.assertEqual(self.client._do_get.call_count, 2)

    def test_list_products_rejects_an_empty_page_before_announced_count(self) -> None:
        self.client._do_get = Mock(
            side_effect=[
                (
                    200,
                    {
                        "count": 101,
                        "limit": 100,
                        "offset": 0,
                        "results": [{"id": product_id} for product_id in range(100)],
                    },
                ),
                (
                    200,
                    {
                        "count": 101,
                        "limit": 100,
                        "offset": 100,
                        "results": [],
                    },
                ),
            ]
        )

        with self.assertRaisesRegex(ProductAPIError, r"100/101"):
            self.client.list_products()

    def test_list_products_keeps_legacy_unpaginated_shapes(self) -> None:
        products = [{"id": 1}, {"id": 2}]

        for payload in (
            products,
            {"products": products},
            {"results": [{"id": product_id} for product_id in range(100)]},
        ):
            with self.subTest(payload=payload):
                self.client._do_get = Mock(return_value=(200, payload))
                expected = payload if isinstance(payload, list) else next(
                    value
                    for key, value in payload.items()
                    if key in {"products", "results"}
                )
                self.assertEqual(self.client.list_products(), expected)
                self.client._do_get.assert_called_once()

    def test_list_products_rejects_a_repeated_paginated_page(self) -> None:
        page = [{"id": product_id} for product_id in range(100)]
        self.client._do_get = Mock(
            return_value=(
                200,
                {
                    "limit": 100,
                    "offset": 0,
                    "results": page,
                },
            )
        )

        with self.assertRaisesRegex(ProductAPIError, "repeated a page"):
            self.client.list_products()


if __name__ == "__main__":
    unittest.main()
