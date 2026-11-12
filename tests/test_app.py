import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import app as app_module


class AppStartupTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_home_returns_page_when_db_init_fails(self):
        with patch.object(app_module, "init_db", side_effect=Exception("db not ready")):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Midnight Post Office", response.get_data(as_text=True))

    def test_letters_are_html_escaped(self):
        fake = {"version": "test", "host": "h", "db_ok": True, "queue": 0, "mailroom": 0,
                "letters": [{"id": 1, "note": "<script>alert(1)</script>", "delivered": True,
                             "delivered_by": "postman-1", "written_at": None,
                             "delivered_at": None}]}
        with patch.object(app_module, "snapshot", return_value=fake):
            html = self.client.get("/").get_data(as_text=True)

        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("delivered by", html)

    def test_api_letters_reports_db_down(self):
        with patch.object(app_module, "init_db", side_effect=Exception("db not ready")):
            data = self.client.get("/api/letters").get_json()

        self.assertFalse(data["db_ok"])
        self.assertEqual(data["letters"], [])

    def test_empty_letter_is_rejected(self):
        response = self.client.post("/send", data={"note": "   "},
                                    headers={"Accept": "application/json"})

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
