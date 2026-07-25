from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecommerce_agent.audit import AuditLogger


class AuditLoggerTests(unittest.TestCase):
    def test_sensitive_fields_are_scrubbed_recursively(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            AuditLogger(path).write(
                {
                    "token": "plain-token",
                    "authorization": "Bearer plain-token",
                    "nested": {"api_key": "plain-api-key", "safe": "keep-me"},
                    "items": [{"secret": "plain-secret"}],
                }
            )

            record = json.loads(path.read_text(encoding="utf-8").strip())

            self.assertEqual("***", record["token"])
            self.assertEqual("***", record["authorization"])
            self.assertEqual("***", record["nested"]["api_key"])
            self.assertEqual("keep-me", record["nested"]["safe"])
            self.assertEqual("***", record["items"][0]["secret"])

    def test_each_event_is_appended_as_one_json_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "audit.jsonl"
            logger = AuditLogger(path)
            logger.write({"session_id": "s1", "path": "rag"})
            logger.write({"session_id": "s2", "path": "tool"})

            records = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]

            self.assertEqual(2, len(records))
            self.assertEqual(["s1", "s2"], [item["session_id"] for item in records])
            self.assertTrue(all("timestamp" in item for item in records))


if __name__ == "__main__":
    unittest.main(verbosity=2)
