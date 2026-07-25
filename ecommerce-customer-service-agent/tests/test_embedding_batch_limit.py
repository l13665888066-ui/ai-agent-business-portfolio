from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecommerce_agent.rag import VectorRAGService


class EmbeddingBatchLimitTests(unittest.TestCase):
    def test_aliyun_embedding_batch_limit_is_configured(self):
        source = inspect.getsource(VectorRAGService._ensure_ready)

        self.assertIn("chunk_size=10", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
