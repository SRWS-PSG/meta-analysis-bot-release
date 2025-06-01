import unittest
import json
from core.metadata_manager import MetadataManager

class TestMetadataManager(unittest.TestCase):
    def test_create_metadata(self):
        payload = {"job_id": "test123", "stage": "test"}
        metadata = MetadataManager.create_metadata("test_event", payload)
        
        self.assertEqual(metadata["event_type"], "test_event")
        self.assertEqual(metadata["event_payload"]["job_id"], "test123")
    
    def test_size_limit(self):
        # 8KB制限のテスト
        large_payload = {"data": "x" * 10000}
        metadata = MetadataManager.create_metadata("large_event", large_payload)
        
        # メタデータが制限内に収まっているかチェック
        self.assertLess(len(json.dumps(metadata)), 8000)

if __name__ == "__main__":
    unittest.main()
