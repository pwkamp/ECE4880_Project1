from __future__ import annotations

import unittest

from tests._framework.redaction import redact


class RedactionTests(unittest.TestCase):
    def test_redacts_tokens_credentials_and_contact_details(self) -> None:
        value = redact(
            "Bearer abc.def password=hunter2 user@example.com +1 (319) 555-1212 "
            "mysql://user:dbpass@localhost/db"
        )
        self.assertNotIn("hunter2", value)
        self.assertNotIn("abc.def", value)
        self.assertNotIn("user@example.com", value)
        self.assertNotIn("dbpass", value)


if __name__ == "__main__":
    unittest.main()
