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


if __name__ == "__main__":
    unittest.main()
