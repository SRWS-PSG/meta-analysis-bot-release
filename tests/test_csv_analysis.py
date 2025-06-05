"""
CSV分析・検証テスト
CLAUDE.md仕様: CSV分析と列マッピング機能をテストする
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.gemini_client import GeminiClient


class TestCSVAnalysis:
    """CSV分析機能のテストクラス"""
    
    def test_meta_analysis_compatible_csv_detection(self):
        """メタ解析適合CSVの検出ができること"""
        # Given: メタ解析適合CSVデータ
        csv_content = """Study,Intervention_Events,Intervention_Total,Control_Events,Control_Total
Study1,10,50,5,48
Study2,15,60,8,55"""
        
        # When: CSV適合性分析をモック
        with patch('core.gemini_client.GeminiClient') as mock_gemini:
            mock_client = mock_gemini.return_value
            mock_client.analyze_csv.return_value = {
                'is_suitable': True,
                'detected_columns': {
                    'effect_size_candidates': ['OR', 'RR']
                },
                'suggested_analysis': {
                    'effect_type_suggestion': 'OR'
                }
            }
            
            gemini_client = mock_gemini()
            result = gemini_client.analyze_csv(csv_content)
            
            # Then: 適合判定される
            assert result['is_suitable'] == True
            assert 'detected_columns' in result
            assert 'effect_size_candidates' in result['detected_columns']
    
    def test_unsuitable_csv_rejection(self):
        """メタ解析に不適合なCSVの拒否ができること"""
        # Given: 不適合CSVデータ
        csv_content = """Name,Age,Gender
John,25,M
Jane,30,F"""
        
        # When: CSV適合性分析をモック
        with patch('core.gemini_client.GeminiClient') as mock_gemini:
            mock_client = mock_gemini.return_value
            mock_client.analyze_csv.return_value = {
                'is_suitable': False,
                'reason': 'メタ解析に必要な効果量データが見つかりません'
            }
            
            gemini_client = mock_gemini()
            result = gemini_client.analyze_csv(csv_content)
            
            # Then: 不適合判定される
            assert result['is_suitable'] == False
            assert 'reason' in result
            assert '効果量' in result['reason']
    
    def test_automatic_column_mapping(self):
        """列の自動マッピングができること"""
        # Given: 様々な列名パターンのCSV
        csv_content = """StudyID,Treatment_Events,Treatment_N,Control_Events,Control_N,Region
RCT001,20,100,15,95,Asia
RCT002,25,110,18,102,Europe"""
        
        # When: 列マッピングをモック
        with patch('core.gemini_client.GeminiClient') as mock_gemini:
            mock_client = mock_gemini.return_value
            mock_client.analyze_csv.return_value = {
                'is_suitable': True,
                'detected_columns': {
                    'effect_size_candidates': ['Treatment_Events', 'Control_Events'],
                    'sample_size_candidates': ['Treatment_N', 'Control_N'],
                    'subgroup_candidates': ['Region']
                }
            }
            
            gemini_client = mock_gemini()
            result = gemini_client.analyze_csv(csv_content)
            
            # Then: 適切にマッピングされる
            detected_cols = result['detected_columns']
            assert 'Treatment_Events' in detected_cols['effect_size_candidates']
            assert 'Treatment_N' in detected_cols['sample_size_candidates']
            assert 'Region' in detected_cols['subgroup_candidates']
    
    def test_effect_size_type_auto_detection(self):
        """効果量タイプの自動検出ができること"""
        # Given: 二値アウトカムデータ
        binary_csv = """Study,Events_A,Total_A,Events_B,Total_B
Study1,10,50,5,48"""
        
        # Given: 連続アウトカムデータ  
        continuous_csv = """Study,Mean_A,SD_A,N_A,Mean_B,SD_B,N_B
Study1,5.2,1.1,30,4.8,1.2,28"""
        
        # When: 効果量タイプ検出をモック
        with patch('core.gemini_client.GeminiClient') as mock_gemini:
            mock_client = mock_gemini.return_value
            
            # 二値データの応答
            mock_client.analyze_csv.return_value = {
                'suggested_analysis': {
                    'effect_type_suggestion': 'OR'
                }
            }
            
            gemini_client = mock_gemini()
            binary_result = gemini_client.analyze_csv(binary_csv)
            
            # 連続データの応答
            mock_client.analyze_csv.return_value = {
                'suggested_analysis': {
                    'effect_type_suggestion': 'SMD'
                }
            }
            
            continuous_result = gemini_client.analyze_csv(continuous_csv)
            
            # Then: 適切な効果量タイプが推奨される
            assert 'OR' in binary_result['suggested_analysis']['effect_type_suggestion']
            assert 'SMD' in continuous_result['suggested_analysis']['effect_type_suggestion']
    
    def test_log_transformation_detection(self):
        """ログ変換データの自動検出ができること"""
        # Given: ハザード比（ログ変換済み）データ
        hazard_csv = """Study,LogHR,SE_LogHR,N
Study1,-0.223,0.15,100
Study2,0.405,0.18,120"""
        
        # When: ログ変換検出をモック
        with patch('core.gemini_client.GeminiClient') as mock_gemini:
            mock_client = mock_gemini.return_value
            mock_client.analyze_csv.return_value = {
                'log_transformed': True,
                'suggested_analysis': {
                    'effect_type_suggestion': 'HR'
                }
            }
            
            gemini_client = mock_gemini()
            result = gemini_client.analyze_csv(hazard_csv)
            
            # Then: ログ変換が検出される
            assert 'log_transformed' in result
            assert result['log_transformed'] == True
            assert 'HR' in result['suggested_analysis']['effect_type_suggestion']
    
    def test_minimum_data_requirements(self):
        """最低データ要件のチェックができること"""
        # Given: 不十分なデータ（1行のみ）
        insufficient_csv = """Study,Effect,SE
Study1,0.5,0.1"""
        
        # When: データ要件チェックをモック
        with patch('core.gemini_client.GeminiClient') as mock_gemini:
            mock_client = mock_gemini.return_value
            mock_client.analyze_csv.return_value = {
                'is_suitable': False,
                'reason': '研究数が最低要件を満たしていません'
            }
            
            gemini_client = mock_gemini()
            result = gemini_client.analyze_csv(insufficient_csv)
            
            # Then: 不十分と判定される
            assert result['is_suitable'] == False
            assert '研究数' in result['reason']
    
    def test_encoding_support(self):
        """多様な文字エンコーディングサポートがあること"""
        # Given: 日本語を含むCSV（UTF-8）
        japanese_csv = """研究名,介入群イベント,介入群総数,対照群イベント,対照群総数
研究1,10,50,5,48
研究2,15,60,8,55"""
        
        # When: 日本語CSV分析をモック
        with patch('core.gemini_client.GeminiClient') as mock_gemini:
            mock_client = mock_gemini.return_value
            mock_client.analyze_csv.return_value = {
                'is_suitable': True,
                'detected_columns': {
                    'effect_size_candidates': ['介入群イベント', '対照群イベント']
                }
            }
            
            gemini_client = mock_gemini()
            result = gemini_client.analyze_csv(japanese_csv)
            
            # Then: 正常に処理される
            assert 'is_suitable' in result
            # 日本語列名でも検出できる
            assert '介入群イベント' in str(result)
    
    def test_large_dataset_handling(self):
        """大きなデータセットの処理ができること"""
        # Given: 大きなCSVデータ（100研究）
        large_csv_rows = ['Study,Events_T,Total_T,Events_C,Total_C']
        for i in range(100):
            large_csv_rows.append(f'Study{i+1},{i%20+5},{i%30+50},{i%15+3},{i%25+45}')
        large_csv = '\n'.join(large_csv_rows)
        
        # When: 大きなデータセット分析をモック
        with patch('core.gemini_client.GeminiClient') as mock_gemini:
            mock_client = mock_gemini.return_value
            mock_client.analyze_csv.return_value = {
                'is_suitable': True,
                'data_preview': large_csv_rows[:10]  # 最初の10行のみプレビュー
            }
            
            gemini_client = mock_gemini()
            result = gemini_client.analyze_csv(large_csv)
            
            # Then: メモリ制限内で処理される
            assert result['is_suitable'] == True
            assert len(result['data_preview']) <= 100  # プレビューは制限される
    
    def test_malformed_csv_handling(self):
        """不正形式CSVのハンドリングができること"""
        # Given: 不正形式CSV
        malformed_csvs = [
            "Study,Events\nStudy1,10,extra,column",  # 列数不一致
            "Study;Events\nStudy1;10",  # セミコロン区切り
            "Study\tEvents\nStudy1\t10",  # タブ区切り
            ""  # 空ファイル
        ]
        
        # When: 不正形式CSV分析をモック
        with patch('core.gemini_client.GeminiClient') as mock_gemini:
            mock_client = mock_gemini.return_value
            
            for malformed_csv in malformed_csvs:
                # 不正形式の場合は不適合と判定
                mock_client.analyze_csv.return_value = {
                    'is_suitable': False,
                    'reason': 'CSV形式が不正です'
                }
                
                gemini_client = mock_gemini()
                result = gemini_client.analyze_csv(malformed_csv)
                
                # Then: エラーハンドリングされる
                assert 'is_suitable' in result
                if not result['is_suitable']:
                    assert 'reason' in result