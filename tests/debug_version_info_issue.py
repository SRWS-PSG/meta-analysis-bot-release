#!/usr/bin/env python3
"""
Debug script to test version information output in R script execution.

このスクリプトは、サブグループ解析でバージョン情報が消える問題を調査します。
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
import logging

# プロジェクトのルートディレクトリを Python パスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator
from core.r_executor import RAnalysisExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_csv(csv_path: Path):
    """テスト用CSVファイルを作成"""
    csv_content = """Study,Intervention_Events,Intervention_Total,Control_Events,Control_Total,Region
Study1,15,48,10,52,Asia
Study2,22,55,18,58,Europe
Study3,18,50,15,50,Asia
Study4,25,60,20,62,Europe
Study5,30,65,25,68,America
Study6,12,40,8,38,Asia
Study7,28,70,22,65,Europe
Study8,35,80,30,85,America
Study9,20,55,18,60,Asia
Study10,32,75,28,70,Europe"""
    
    with open(csv_path, 'w') as f:
        f.write(csv_content)
    logger.info(f"Created test CSV file at: {csv_path}")

def test_r_script_execution():
    """Rスクリプトの実行をテスト"""
    
    # 一時ディレクトリの作成
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        job_id = "debug_version_test"
        
        # テストCSVの作成
        csv_path = temp_path / "test_data.csv"
        create_test_csv(csv_path)
        
        # 出力ディレクトリの作成
        output_dir = temp_path / "output"
        output_dir.mkdir(exist_ok=True)
        
        # RAnalysisExecutorの初期化
        executor = RAnalysisExecutor(
            r_output_dir=output_dir,
            csv_file_path=csv_path,
            job_id=job_id
        )
        
        # 解析パラメータ（サブグループ解析を含む）
        analysis_params = {
            'measure': 'OR',
            'model': 'REML',
            'data_columns': {
                'ai': 'Intervention_Events',
                'ci': 'Control_Events',
                'n1i': 'Intervention_Total',
                'n2i': 'Control_Total',
                'study_label': 'Study'
            },
            'subgroup_columns': ['Region']
        }
        
        data_summary = {
            'columns': ['Study', 'Intervention_Events', 'Control_Events', 
                       'Intervention_Total', 'Control_Total', 'Region'],
            'shape': [10, 6]
        }
        
        # Rスクリプトの生成
        logger.info("Generating R script...")
        generator = RTemplateGenerator()
        r_code = generator.generate_full_r_script(
            analysis_params=analysis_params,
            data_summary=data_summary,
            output_paths=executor.output_paths_in_r,
            csv_file_path_in_script=str(csv_path)
        )
        
        # Rスクリプトの保存
        r_script_path = output_dir / f"debug_script_{job_id}.R"
        with open(r_script_path, 'w') as f:
            f.write(r_code)
        logger.info(f"Saved R script to: {r_script_path}")
        
        # Rスクリプトの実行
        logger.info("Executing R script...")
        try:
            result = subprocess.run(
                ['Rscript', str(r_script_path)],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            logger.info(f"R execution return code: {result.returncode}")
            logger.info(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                logger.warning(f"STDERR:\n{result.stderr}")
            
            # JSONファイルの確認
            json_path = Path(executor.output_paths_in_r["json_summary_path"])
            if json_path.exists():
                logger.info(f"JSON file created at: {json_path}")
                with open(json_path, 'r') as f:
                    json_content = json.load(f)
                
                # バージョン情報の確認
                logger.info("\n=== Version Information in JSON ===")
                has_r_version = 'r_version' in json_content
                has_metafor_version = 'metafor_version' in json_content
                has_analysis_environment = 'analysis_environment' in json_content
                
                logger.info(f"Has r_version: {has_r_version}")
                logger.info(f"Has metafor_version: {has_metafor_version}")
                logger.info(f"Has analysis_environment: {has_analysis_environment}")
                
                if has_r_version:
                    logger.info(f"R version: {json_content['r_version']}")
                if has_metafor_version:
                    logger.info(f"metafor version: {json_content['metafor_version']}")
                if has_analysis_environment:
                    logger.info(f"Analysis environment: {json.dumps(json_content['analysis_environment'], indent=2)}")
                
                # サブグループ解析結果の確認
                logger.info("\n=== Subgroup Analysis Results ===")
                has_subgroup = 'subgroup_analyses_Region' in json_content
                logger.info(f"Has subgroup_analyses_Region: {has_subgroup}")
                
                # 全体の統計結果
                if 'overall_analysis' in json_content:
                    overall = json_content['overall_analysis']
                    logger.info(f"\nOverall analysis:")
                    logger.info(f"  Studies: {overall.get('k', 'N/A')}")
                    logger.info(f"  Estimate: {overall.get('estimate', 'N/A')}")
                    logger.info(f"  95% CI: [{overall.get('ci_lb', 'N/A')}, {overall.get('ci_ub', 'N/A')}]")
                
                # JSONファイルの完全な内容を表示（デバッグ用）
                logger.info("\n=== Complete JSON Structure (keys only) ===")
                logger.info(f"Top-level keys: {list(json_content.keys())}")
                
            else:
                logger.error(f"JSON file not created at: {json_path}")
            
        except subprocess.TimeoutExpired:
            logger.error("R script execution timed out")
        except Exception as e:
            logger.error(f"Error during R execution: {e}")
            
if __name__ == "__main__":
    test_r_script_execution()