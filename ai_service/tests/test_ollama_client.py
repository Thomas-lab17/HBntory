"""Tests de l'interpréteur structuré Ollama sans appel réseau."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from app.ollama_client import OllamaQueryInterpreter


class OllamaQueryInterpreterTests(unittest.TestCase):
    @patch("app.ollama_client.urllib.request.urlopen")
    def test_disabled_does_not_call_ollama(self, urlopen: MagicMock) -> None:
        interpreter = OllamaQueryInterpreter(enabled=False)

        self.assertIsNone(interpreter.interpret("Question", []))
        urlopen.assert_not_called()

    @patch("app.ollama_client.urllib.request.urlopen")
    def test_parses_structured_plan(self, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {
                "message": {
                    "content": json.dumps(
                        {
                            "intents": ["stock_lookup"],
                            "product_query": "écran 27 pouces",
                            "branch": "Lyon",
                            "confidence": 0.9,
                        }
                    )
                }
            }
        ).encode()
        urlopen.return_value = response
        interpreter = OllamaQueryInterpreter(
            enabled=True,
            base_url="http://ollama.test",
            model="gemma3:1b",
            timeout=12,
        )

        result = interpreter.interpret("Un 27 pouces à Lyon ?", [])

        self.assertEqual(result["intents"], ["stock_lookup"])
        self.assertEqual(result["branch"], "Lyon")
        request = urlopen.call_args.args[0]
        request_payload = json.loads(request.data.decode())
        self.assertEqual(request_payload["model"], "gemma3:1b")
        self.assertEqual(request_payload["format"], "json")
        self.assertEqual(request_payload["messages"][0]["role"], "system")
        self.assertEqual(request_payload["options"]["num_ctx"], 512)
        self.assertEqual(request_payload["options"]["num_predict"], 64)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 12)

    @patch("app.ollama_client.urllib.request.urlopen")
    def test_invalid_json_falls_back_cleanly(self, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {"message": {"content": "pas du json"}}
        ).encode()
        urlopen.return_value = response
        interpreter = OllamaQueryInterpreter(enabled=True, timeout=5)

        self.assertIsNone(interpreter.interpret("Question", []))


if __name__ == "__main__":
    unittest.main()
