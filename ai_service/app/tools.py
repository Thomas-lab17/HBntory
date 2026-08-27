# Tool schemas exposed to the agent (OpenAI-style JSON for DeepSeek).
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
            "Get the stock quantity of a product across branches, optionally "
            "filtered to one branch. Real branch names are French cities such "
            "as 'Paris', 'Lyon', 'Marseille', 'Toulouse', 'Bordeaux'."
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

GET_BRANCH_STOCK = {
    "type": "function",
    "function": {
        "name": "get_branch_stock",
        "description": (
            "Get the full stock of one branch: the list of products and their "
            "quantities available in that branch, in a single call. Real branch "
            "names are French cities such as 'Paris', 'Lyon', 'Marseille', "
            "'Toulouse', 'Bordeaux'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "branch": {
                    "type": "string",
                    "description": "Branch name (e.g. 'Paris' or 'Lyon')",
                },
            },
            "required": ["branch"],
        },
    },
}

TOOLS = [LIST_PRODUCTS, GET_PRODUCT, GET_STOCK, GET_BRANCH_STOCK]
