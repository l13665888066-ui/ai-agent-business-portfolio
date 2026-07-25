from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecommerce_agent.rag import VectorRAGService


class VectorStoreDedupTests(unittest.TestCase):
    def test_vector_documents_use_deterministic_ids(self):
        source = inspect.getsource(VectorRAGService._ensure_ready)

        self.assertIn("document_ids", source)
        self.assertIn("ids=document_ids", source)
        self.assertIn("sha256(knowledge_text.encode", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
