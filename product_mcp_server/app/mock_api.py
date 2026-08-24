"""
mock_api.py
-----------
A tiny stand-in for the external Product API, used ONLY for manual testing
of the MCP server. Implements just enough behaviour to exercise every code
path in product_client.py:

    GET /products         -> 200, list of products
    GET /products/{id}    -> 200, single product   (id in PRODUCTS)
    GET /products/{id}    -> 404, not found         (id not in PRODUCTS)

Run standalone:
    python mock_api.py
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PRODUCTS = {
    "p1": {
        "id": "p1", "name": "Wireless Mouse", "price": 19.99,
        "category": "Electronics", "in_stock": True,
        "description": "A reliable 2.4GHz wireless mouse.",
    },
    "p2": {
        "id": "p2", "name": "Mechanical Keyboard", "price": 89.99,
        "category": "Electronics", "in_stock": True,
        "description": "RGB backlit mechanical keyboard, blue switches.",
    },
    "p3": {
        "id": "p3", "name": "Standing Desk", "price": 249.00,
        "category": "Furniture", "in_stock": False,
        "description": "Electric height-adjustable standing desk.",
    },
}


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/products":
            self._send_json(200, {"products": list(PRODUCTS.values())})
        elif self.path.startswith("/products/"):
            product_id = self.path[len("/products/"):]
            product = PRODUCTS.get(product_id)
            if product:
                self._send_json(200, product)
            else:
                self._send_json(404, {"error": f"Product '{product_id}' not found"})
        else:
            self._send_json(404, {"error": "Unknown route"})

    def log_message(self, format, *args):
        pass  # keep test output clean


def run(port: int = 8000):
    server = HTTPServer(("localhost", port), Handler)
    print(f"Mock Product API listening on http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
