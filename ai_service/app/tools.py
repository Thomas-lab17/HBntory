# Tool schemas exposed to the agent (OpenAI-style JSON, as Ollama expects).
LIST_PRODUCTS = {
    "type": "function",
    "function": {
        "name": "list_products",
        "description": "List all products available in the catalog.",
        "parameters": {"type": "object", "properties": {}},
    },
}

GET_PRODUCT = {
    "type": "function",
    "function": {
        "name": "get_product",
        "description": "Get details for one product by its id or SKU.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "Product id or SKU to look up",
                }
            },
            "required": ["product_id"],
        },
    },
}

GET_STOCK = {
    "type": "function",
    "function": {
        "name": "get_stock",
        "description": (
            "Get the stock quantity of a product, optionally filtered to one branch. "
            "Branch names are things like 'Downtown' or 'Airport'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "Product id or SKU to check",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name (optional)",
                },
            },
            "required": ["product_id"],
        },
    },
}

TOOLS = [LIST_PRODUCTS, GET_PRODUCT, GET_STOCK]
