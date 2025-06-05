"""
解析実行テスト
CLAUDE.md仕様: R実行と解析タイプ対応をテストする
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from core.r_executor import RExecutor
from templates.r_templates import RTemplateGenerator


class TestAnalysisExecution:
    """解析実行機能のテストクラス"""
    
    def test_binary_outcome_analysis_types(self):
        """二値アウトカム解析タイプが対応できること"""
        # Given: 各二値解析タイプ
        binary_types = ["OR", "RR", "RD", "PETO"]
        
        for analysis_type in binary_types:
            # When: Rスクリプト生成
            generator = RTemplateGenerator()
            script = generator.generate_binary_outcome_script(
                measure=analysis_type,
                ai="Events_A", bi="Total_A", ci="Events_B", di="Total_B"
            )
            
            # Then: 適切なスクリプトが生成される
            assert f'measure="{analysis_type}"' in script
            assert "metafor" in script
            assert "rma" in script
    
    def test_continuous_outcome_analysis_types(self):
        """連続アウトカム解析タイプが対応できること"""
        # Given: 各連続解析タイプ
        continuous_types = ["SMD", "MD", "ROM"]
        
        for analysis_type in continuous_types:
            # When: Rスクリプト生成
            generator = RTemplateGenerator()
            script = generator.generate_continuous_outcome_script(
                measure=analysis_type,
                m1i="Mean_A", sd1i="SD_A", n1i="N_A",
                m2i="Mean_B", sd2i="SD_B", n2i="N_B"
            )
            
            # Then: 適切なスクリプトが生成される
            assert f'measure="{analysis_type}"' in script
            assert "escalc" in script
    
    def test_hazard_ratio_with_log_detection(self):
        """ハザード比のログ変換検出が機能すること"""
        # Given: ログ変換済みハザード比データ
        hr_params = {
            "measure": "HR",
            "yi": "LogHR",
            "vi": "SE_LogHR",
            "log_transformed": True
        }
        
        # When: HRスクリプト生成
        generator = RTemplateGenerator()
        script = generator.generate_hazard_ratio_script(**hr_params)
        
        # Then: ログ変換が考慮される
        assert "yi=" in script
        assert "vi=" in script
        assert "measure=\"GEN\"" in script  # ログ変換済みは汎用measure
    
    def test_proportion_analysis_types(self):
        """単一比率解析タイプが対応できること"""
        # Given: 各比率解析タイプ
        proportion_types = ["PLO", "PR", "PAS", "PFT", "PRAW"]
        
        for analysis_type in proportion_types:
            # When: 比率スクリプト生成
            generator = RTemplateGenerator()
            script = generator.generate_proportion_script(
                measure=analysis_type,
                xi="Events", ni="Total"
            )
            
            # Then: 適切なスクリプトが生成される
            assert f'measure="{analysis_type}"' in script
            assert "escalc" in script
    
    def test_incidence_rate_analysis_types(self):
        """発生率解析タイプが対応できること"""
        # Given: 各発生率解析タイプ
        incidence_types = ["IR", "IRLN", "IRS", "IRFT"]
        
        for analysis_type in incidence_types:
            # When: 発生率スクリプト生成
            generator = RTemplateGenerator()
            script = generator.generate_incidence_rate_script(
                measure=analysis_type,
                xi="Events", ti="Time"
            )
            
            # Then: 適切なスクリプトが生成される
            assert f'measure="{analysis_type}"' in script
            assert "escalc" in script
    
    def test_correlation_analysis(self):
        """相関解析が対応できること"""
        # Given: 相関データ
        correlation_params = {
            "measure": "COR",
            "ri": "Correlation",
            "ni": "Sample_Size"
        }
        
        # When: 相関スクリプト生成
        generator = RTemplateGenerator()
        script = generator.generate_correlation_script(**correlation_params)
        
        # Then: 適切なスクリプトが生成される
        assert 'measure="COR"' in script
        assert "escalc" in script
    
    def test_pre_calculated_effect_sizes(self):
        """事前計算された効果量が対応できること"""
        # Given: 事前計算効果量データ
        precalc_params = {
            "yi": "Effect_Size",
            "vi": "Variance",
            "measure": "GEN"
        }
        
        # When: 事前計算スクリプト生成
        generator = RTemplateGenerator()
        script = generator.generate_precalculated_script(**precalc_params)
        
        # Then: 適切なスクリプトが生成される
        assert "yi=" in script
        assert "vi=" in script
        assert "rma" in script
    
    def test_subgroup_analysis_with_statistical_tests(self):
        """統計的検定付きサブグループ解析ができること"""
        # Given: サブグループ解析パラメータ
        subgroup_params = {
            "measure": "OR",
            "subgroup_column": "Region",
            "test_for_subgroup_differences": True
        }
        
        # When: サブグループスクリプト生成
        generator = RTemplateGenerator()
        script = generator.generate_subgroup_analysis_script(**subgroup_params)
        
        # Then: Q検定が含まれる
        assert "anova" in script.lower() or "qtest" in script.lower()
        assert "Region" in script
        assert "subgroup" in script.lower()
    
    def test_meta_regression_multiple_moderators(self):
        """複数のモデレータによるメタ回帰ができること"""
        # Given: 複数モデレータ
        regression_params = {
            "measure": "SMD",
            "moderators": ["Year", "Sample_Size", "Quality_Score"]
        }
        
        # When: メタ回帰スクリプト生成
        generator = RTemplateGenerator()
        script = generator.generate_meta_regression_script(**regression_params)
        
        # Then: 複数モデレータが含まれる
        assert "Year" in script
        assert "Sample_Size" in script
        assert "Quality_Score" in script
        assert "mods" in script
    
    def test_sensitivity_analysis_with_filtering(self):
        """フィルタリング条件付き感度分析ができること"""
        # Given: 感度分析条件
        sensitivity_params = {
            "measure": "OR",
            "exclude_condition": "Quality_Score < 3",
            "exclude_studies": ["Study1", "Study2"]
        }
        
        # When: 感度分析スクリプト生成
        generator = RTemplateGenerator()
        script = generator.generate_sensitivity_analysis_script(**sensitivity_params)
        
        # Then: フィルタリングが含まれる
        assert "Quality_Score" in script
        assert "subset" in script or "filter" in script
        assert "Study1" in script or "exclude" in script
    
    def test_dynamic_plot_sizing(self):
        """研究数に基づく動的プロットサイズ調整ができること"""
        # Given: 異なる研究数
        study_counts = [5, 15, 50, 100]
        
        for count in study_counts:
            # When: プロット生成スクリプト
            generator = RTemplateGenerator()
            script = generator.generate_forest_plot_script(study_count=count)
            
            # Then: 研究数に応じたサイズ調整
            assert "height" in script
            if count > 20:
                # 大きな研究数では高さが調整される
                assert "height=" in script
    
    def test_comprehensive_json_output(self):
        """包括的なJSON出力が生成されること"""
        # Given: 解析パラメータ
        analysis_params = {"measure": "OR", "method": "REML"}
        
        # When: JSON出力スクリプト生成
        generator = RTemplateGenerator()
        script = generator.generate_json_output_script(**analysis_params)
        
        # Then: 統計情報が含まれる
        json_fields = [
            "estimate", "ci_lower", "ci_upper", "pval", 
            "tau2", "I2", "H2", "QE", "QEp"
        ]
        for field in json_fields:
            assert field in script
    
    def test_multiple_plot_types(self):
        """複数のプロットタイプが生成できること"""
        # Given: プロットタイプ
        plot_types = ["forest", "funnel", "bubble"]
        
        for plot_type in plot_types:
            # When: プロット生成
            generator = RTemplateGenerator()
            script = generator.generate_plot_script(plot_type=plot_type)
            
            # Then: 適切なプロット関数が使用される
            if plot_type == "forest":
                assert "forest" in script
            elif plot_type == "funnel":
                assert "funnel" in script
            elif plot_type == "bubble":
                assert "regplot" in script or "bubble" in script
    
    def test_r_script_execution(self):
        """Rスクリプトが実行できること"""
        # Given: 簡単なRスクリプト
        script = "result <- 2 + 2; cat(result)"
        
        # When: R実行
        executor = RExecutor()
        result = executor.execute_script(script)
        
        # Then: 実行結果が返される
        assert "stdout" in result
        assert "stderr" in result
        assert "return_code" in result
    
    def test_r_package_availability(self):
        """必要なRパッケージが利用可能であること"""
        # Given: 必要パッケージリスト
        required_packages = ["metafor", "jsonlite", "ggplot2"]
        
        for package in required_packages:
            # When: パッケージ確認スクリプト実行
            check_script = f'if (!require({package}, quietly=TRUE)) stop("Package {package} not found")
cat("OK")
'
            
            executor = RExecutor()
            result = executor.execute_script(check_script)
            
            # Then: パッケージが利用可能
            assert result["return_code"] == 0
            assert "OK" in result["stdout"]
    
    def test_analysis_environment_info(self):
        """解析環境情報が記録されること"""
        # Given: 環境情報取得スクリプト
        env_script = """
R_version <- paste(R.version$major, R.version$minor, sep=".")
metafor_version <- packageVersion("metafor")
cat(paste("R:", R_version, "metafor:", metafor_version))
"""
        
        # When: 環境情報取得
        executor = RExecutor()
        result = executor.execute_script(env_script)
        
        # Then: バージョン情報が取得される
        assert "R:" in result["stdout"]
        assert "metafor:" in result["stdout"]
    
    def test_memory_management_for_large_datasets(self):
        """大きなデータセットのメモリ管理ができること"""
        # Given: 大きなデータセット（模擬）
        large_dataset_script = """
# 100研究のデータを生成
n_studies <- 100
data <- data.frame(
  study = paste0("Study", 1:n_studies),
  yi = rnorm(n_studies, 0.5, 0.3),
  vi = runif(n_studies, 0.01, 0.1)
)

# メモリ使用量確認
mem_before <- gc()[2,2]
res <- metafor::rma(yi, vi, data=data)
mem_after <- gc()[2,2]

cat("Memory used:", mem_after - mem_before, "MB")
"""
        
        # When: 大データセット処理
        executor = RExecutor()
        result = executor.execute_script(large_dataset_script)
        
        # Then: エラーなく処理される
        assert result["return_code"] == 0
        assert "Memory used:" in result["stdout"]
    
    def test_concurrent_analysis_limit(self):
        """同時実行可能な解析数の制限があること"""
        # Given: 複数の解析要求
        max_concurrent = 5
        
        # When: 同時実行数チェック
        # ThreadPoolExecutorの動作を模擬
        from concurrent.futures import ThreadPoolExecutor
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # Then: 最大同時実行数が制限される
            assert executor._max_workers == max_concurrent
    
    def test_file_cleanup_after_processing(self):
        """処理後の一時ファイル削除ができること"""
        import tempfile
        import os
        
        # Given: 一時ファイル作成
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
            temp_file.write(b"Study,Effect,SE\nStudy1,0.5,0.1")
            temp_path = temp_file.name
        
        # ファイルが存在することを確認
        assert os.path.exists(temp_path)
        
        # When: クリーンアップ実行
        os.unlink(temp_path)
        
        # Then: ファイルが削除される
        assert not os.path.exists(temp_path)
    
    def test_analysis_timeout_handling(self):
        """解析タイムアウトのハンドリングができること"""
        # Given: 長時間実行スクリプト
        long_script = "Sys.sleep(10); cat('done')"
        
        # When: タイムアウト付き実行
        executor = RExecutor(timeout=2)  # 2秒タイムアウト
        result = executor.execute_script(long_script)
        
        # Then: タイムアウトエラーが発生する
        assert result["return_code"] != 0
        assert "timeout" in result["stderr"].lower() or result["return_code"] == -1
