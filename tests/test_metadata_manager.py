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
        # 8KB制限のテスト（辞書型データで圧縮テスト）
        large_dict = {"items": ["x" * 100] * 100}  # 大きな辞書データ
        large_payload = {"data": large_dict}
        metadata = MetadataManager.create_metadata("large_event", large_payload)
        
        # メタデータが作成されることを確認（圧縮が動作すること）
        self.assertIsNotNone(metadata)
        # 圧縮により "data_ref" キーが作成されることを確認
        self.assertIn("data_ref", metadata["event_payload"])

if __name__ == "__main__":
    unittest.main()
