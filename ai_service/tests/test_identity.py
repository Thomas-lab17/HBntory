"""Tests de résolution d'identité sans appel réseau."""

from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from app.domain import UserRole
from app.identity import IdentityResolver, IdentityServiceError


class IdentityResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = IdentityResolver(auth_api_url="http://backoffice.test")

    @patch("app.identity.urllib.request.urlopen")
    def test_absence_cookie_reste_anonyme_sans_appel(self, urlopen: MagicMock) -> None:
        user = self.resolver.resolve(None)

        self.assertEqual(user.role, UserRole.ANONYMOUS)
        urlopen.assert_not_called()

    @patch("app.identity.urllib.request.urlopen")
    def test_cookie_invalide_reste_anonyme(self, urlopen: MagicMock) -> None:
        urlopen.side_effect = urllib.error.HTTPError(
            "http://backoffice.test/auth/me",
            401,
            "Unauthorized",
            {},
            None,
        )

        user = self.resolver.resolve("invalid-token")

        self.assertEqual(user.role, UserRole.ANONYMOUS)

    @patch("app.identity.urllib.request.urlopen")
    def test_identite_valide_est_issue_du_backoffice(self, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {
                "id": 7,
                "username": "alice",
                "role": "common",
                "branch_id": 2,
                "branch_name": "Lyon",
            }
        ).encode()
        urlopen.return_value = response

        user = self.resolver.resolve("valid-token")

        self.assertEqual(user.role, UserRole.COMMON)
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.branch_name, "Lyon")

    @patch("app.identity.urllib.request.urlopen")
    def test_panne_identite_n_est_pas_transformee_en_anonyme(
        self,
        urlopen: MagicMock,
    ) -> None:
        urlopen.side_effect = urllib.error.URLError("offline")

        with self.assertRaises(IdentityServiceError):
            self.resolver.resolve("valid-looking-token")


if __name__ == "__main__":
    unittest.main()
