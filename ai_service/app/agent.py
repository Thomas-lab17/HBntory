# Agent loop: DeepSeek (OpenAI-compatible chat completions) with tool calling.
# The model may call tools; we execute them and feed results back until it
# produces a final answer (bounded loop). No information is invented: if the
# tools return nothing useful, the model must say the info is unavailable.
import json
import os
import urllib.request

from . import product_client, stock_client, tools

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
MAX_STEPS = 6

SYSTEM = (
    "You are the HBntory assistant. You answer questions about products and "
    "stock using only the provided tools. Supported question types: product "
    "details, where a product is available, what products a branch has, and "
    "which branch can satisfy a shopping list. Never invent product names, "
    "prices, or stock quantities. If a tool fails or lacks the information, "
    "say clearly that the information is unavailable. Answer in the same "
    "language as the question."
)


def _chat(messages: list[dict]) -> dict:
    """Call DeepSeek and return the assistant message dict."""
    body = json.dumps(
        {"model": MODEL, "messages": messages, "tools": tools.TOOLS, "stream": False}
    ).encode("utf-8")
    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            # Custom User-Agent for provider compatibility.
            "User-Agent": "hbntory-ai/0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]


def _execute(tool_call: dict) -> tuple[str, dict]:
    """Run one tool call, log it, and return (name, result)."""
    name = tool_call["function"]["name"]
    try:
        # OpenAI-compatible APIs send arguments as a JSON string.
        args = json.loads(tool_call["function"].get("arguments") or "{}")
    except json.JSONDecodeError:
        args = {}
    if name == "list_products":
        result = product_client.list_products()
    elif name == "get_product":
        result = product_client.get_product(args.get("product_id", ""))
    elif name == "get_stock":
        result = stock_client.stock_by_product(args.get("product_id", ""), args.get("branch"))
    elif name == "get_branch_stock":
        result = stock_client.stock_by_branch(args.get("branch", ""))
    else:
        result = {"success": False, "message": f"Unknown tool: {name}"}
    print(f"[tool] {name}({json.dumps(args)}) -> {json.dumps(result)[:200]}", flush=True)
    return name, result


def answer(question: str) -> dict:
    """Run the agent on a question; return {"answer", "tool_calls"}."""
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]
    calls: list[str] = []
    if not API_KEY:
        return {
            "answer": "Le service IA n'est pas configuré : la clé API "
                      "(DEEPSEEK_API_KEY) est manquante.",
            "tool_calls": calls,
        }
    try:
        for _ in range(MAX_STEPS):
            message = _chat(messages)
            messages.append(message)
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return {"answer": (message.get("content") or "").strip(), "tool_calls": calls}
            for call in tool_calls:
                name, result = _execute(call)
                calls.append(name)
                messages.append(
                    {
                        "role": "tool",
                        "content": json.dumps(result),
                        "tool_call_id": call.get("id"),
                    }
                )
    except urllib.error.HTTPError as exc:
        # 401/403 = clé API absente ou invalide ; le reste = panne ou limite.
        if exc.code in (401, 403):
            return {
                "answer": "Le service IA n'est pas autorisé : vérifiez la clé "
                          "API (DEEPSEEK_API_KEY).",
                "tool_calls": calls,
            }
        return {
            "answer": "Le service de réponse est temporairement indisponible "
                      f"(erreur {exc.code}). Réessayez dans quelques instants.",
            "tool_calls": calls,
        }
    except (urllib.error.URLError, OSError):
        return {
            "answer": "Le service de réponse est temporairement indisponible. Réessayez.",
            "tool_calls": calls,
        }
    return {
        "answer": "I could not complete the answer within the allowed number of steps.",
        "tool_calls": calls,
    }
