import os
import json
import asyncio
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from templates.r_templates import RTemplateGenerator # templatesからRTemplateGeneratorをインポート

logger = logging.getLogger(__name__)

class RAnalysisExecutor:
    """
    Rスクリプトの生成と実行を担当するクラス。
    """
    def __init__(self, r_output_dir: Path, csv_file_path: Path, job_id: str):
        """
        RAnalysisExecutorを初期化します。

        Args:
            r_output_dir: Rスクリプトの実行結果（プロット、サマリーファイルなど）を保存するディレクトリ。
            csv_file_path: Rスクリプトが読み込むCSVファイルのフルパス。
            job_id: 現在の解析ジョブID。
        """
        self.r_output_dir = r_output_dir
        self.csv_file_path = csv_file_path # Rスクリプト内で使用するCSVファイルのフルパス
        self.job_id = job_id
        self.r_script_path = self.r_output_dir / f"run_meta_{self.job_id}.R"
        self.template_generator = RTemplateGenerator()

        # Rスクリプトが出力する主要なファイルのパスを定義
        self.output_paths_in_r = {
            "forest_plot_path": str(self.r_output_dir / f"forest_plot_{self.job_id}.png"),
            "funnel_plot_path": str(self.r_output_dir / f"funnel_plot_{self.job_id}.png"),
            "rdata_path": str(self.r_output_dir / f"result_{self.job_id}.RData"),
            "json_summary_path": str(self.r_output_dir / f"summary_{self.job_id}.json"),
            "bubble_plot_path_prefix": str(self.r_output_dir / f"bubble_plot_{self.job_id}"), # プレフィックス
            "forest_plot_subgroup_prefix": str(self.r_output_dir / f"forest_plot_subgroup_{self.job_id}") # プレフィックス
        }

    async def execute_meta_analysis(self, analysis_params: Dict[str, Any], data_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        指定されたパラメータに基づいてメタ解析Rスクリプトを生成し、実行します。

        Args:
            analysis_params: ユーザーが指定した解析パラメータ。
                             例: {"measure": "OR", "model": "REML", "data_columns": {...}, ...}
            data_summary: CSVファイルの基本的な情報（列名など）。RTemplateGeneratorが参照します。

        Returns:
            解析結果を含む辞書。
            例: {
                "success": True/False,
                "stdout": "Rの標準出力",
                "stderr": "Rの標準エラー出力",
                "r_script_path": "実行されたRスクリプトのパス",
                "generated_plots_paths": [{"label": "plot_type", "path": "/path/to/plot.png"}, ...],
                "structured_summary_json_path": "/path/to/summary.json",
                "structured_summary_content": "{...}" (JSON文字列),
                "rdata_path": "/path/to/result.RData",
                "error": "エラーメッセージ (失敗時)"
            }
        """
        logger.info(f"Rメタ解析実行開始 (Job ID: {self.job_id})。パラメータ: {analysis_params}")
        
        try:
            r_code = self.template_generator.generate_full_r_script(
                analysis_params=analysis_params,
                data_summary=data_summary, # data_summaryを渡す
                output_paths=self.output_paths_in_r,
                csv_file_path_in_script=str(self.csv_file_path.resolve()) # Rスクリプト内で使われるCSVパス
            )
            
            with open(self.r_script_path, 'w', encoding='utf-8') as f:
                f.write(r_code)
            logger.info(f"Rスクリプトを {self.r_script_path} に保存しました。")

        except Exception as e_template_gen:
            logger.error(f"Rスクリプトのテンプレート生成中にエラー (Job ID: {self.job_id}): {e_template_gen}")
            return {
                "success": False,
                "error": f"Rスクリプトのテンプレート生成に失敗: {e_template_gen}",
                "r_script_path": None,
                "stdout": "", "stderr": str(e_template_gen)
            }

        r_executable = os.environ.get("R_EXECUTABLE_PATH", "Rscript") # 環境変数から取得、なければデフォルト
        logger.info(f"使用するR実行可能ファイル: {r_executable} (Job ID: {self.job_id})")

        try:
            # asyncio.to_thread を使って同期的な subprocess.run を非同期的に実行
            process_result = await asyncio.to_thread(
                subprocess.run,
                [r_executable, str(self.r_script_path)],
                capture_output=True,
                text=True,
                timeout=300, # 5分タイムアウト
                encoding='utf-8', # 明示的にエンコーディング指定
                check=False # check=False にして、エラー時も結果を処理できるようにする
            )

            stdout = process_result.stdout
            stderr = process_result.stderr
            
            logger.info(f"R stdout (Job ID: {self.job_id}):\n{stdout[:1000]}...")
            if stderr:
                logger.warning(f"R stderr (Job ID: {self.job_id}):\n{stderr[:1000]}...")

            if process_result.returncode != 0:
                logger.error(f"Rスクリプト実行失敗 (Job ID: {self.job_id})。Return code: {process_result.returncode}")
                # Geminiデバッグはここでは行わず、エラー情報を返す
                return {
                    "success": False,
                    "error": f"Rスクリプト実行失敗。Return code: {process_result.returncode}",
                    "stdout": stdout,
                    "stderr": stderr,
                    "r_script_path": str(self.r_script_path)
                }

            # Rスクリプトが正常に終了した場合、結果ファイルを収集
            structured_summary_content = None
            json_summary_file = Path(self.output_paths_in_r["json_summary_path"])
            if json_summary_file.exists():
                try:
                    with open(json_summary_file, 'r', encoding='utf-8') as f:
                        structured_summary_content = f.read() # JSON文字列として読み込む
                    logger.info(f"構造化サマリーJSONを読み込みました: {json_summary_file} (Job ID: {self.job_id})")
                except Exception as e_read_json:
                    logger.error(f"構造化サマリーJSONの読み込みに失敗: {json_summary_file} (Job ID: {self.job_id}): {e_read_json}")
                    # structured_summary_content は None のまま
            else:
                logger.warning(f"構造化サマリーJSONファイルが見つかりません: {json_summary_file} (Job ID: {self.job_id})")
            
            # 生成されたプロットのパスリストを取得 (summary.json内のgenerated_plots_pathsから)
            generated_plots_paths_list = []
            if structured_summary_content:
                try:
                    summary_data = json.loads(structured_summary_content)
                    generated_plots_paths_list = summary_data.get("generated_plots_paths", [])
                except json.JSONDecodeError:
                    logger.error(f"JSONサマリーのパースに失敗。プロットパスを取得できません。 (Job ID: {self.job_id})")


            return {
                "success": True,
                "stdout": stdout,
                "stderr": stderr,
                "r_script_path": str(self.r_script_path),
                "generated_plots_paths": generated_plots_paths_list, # Rスクリプトが出力したパス情報
                "structured_summary_json_path": str(json_summary_file) if json_summary_file.exists() else None,
                "structured_summary_content": structured_summary_content,
                "rdata_path": self.output_paths_in_r["rdata_path"] if Path(self.output_paths_in_r["rdata_path"]).exists() else None,
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Rスクリプト実行タイムアウト (Job ID: {self.job_id})")
            return {
                "success": False, "error": "R script execution timed out.",
                "stdout": "", "stderr": "Timeout occurred.",
                "r_script_path": str(self.r_script_path)
            }
        except FileNotFoundError:
            logger.error(f"R実行可能ファイル '{r_executable}' が見つかりません (Job ID: {self.job_id})。")
            return {
                "success": False, "error": f"R executable '{r_executable}' not found.",
                "stdout": "", "stderr": f"R executable '{r_executable}' not found.",
                "r_script_path": str(self.r_script_path)
            }
        except Exception as e_exec:
            logger.error(f"Rスクリプト実行中に予期せぬエラー (Job ID: {self.job_id}): {e_exec}")
            return {
                "success": False, "error": f"Unexpected error during R script execution: {e_exec}",
                "stdout": "", "stderr": str(e_exec),
                "r_script_path": str(self.r_script_path)
            }

if __name__ == '__main__':
    # このテストを実行するには、適切なCSVファイルと環境設定が必要
    async def run_test():
        logging.basicConfig(level=logging.INFO)
        logger.info("RAnalysisExecutor テスト開始")

        # テスト用のダミーCSVファイルを作成
        test_job_id = "testjob001"
        temp_dir = Path(tempfile.gettempdir()) / "meta_analysis_bot_test_r_executor"
        test_csv_dir = temp_dir / test_job_id
        test_csv_dir.mkdir(parents=True, exist_ok=True)
        test_csv_path = test_csv_dir / "test_data.csv"
        
        # 簡単なCSVデータ (yi と vi を含む)
        csv_data_content = "study_id,yi,vi,slab\n1,0.5,0.1,StudyA\n2,0.8,0.2,StudyB\n3,-0.2,0.05,StudyC"
        with open(test_csv_path, "w") as f:
            f.write(csv_data_content)
        
        r_output_dir = temp_dir / f"r_output_{test_job_id}"
        r_output_dir.mkdir(parents=True, exist_ok=True)

        executor = RAnalysisExecutor(r_output_dir=r_output_dir, csv_file_path=test_csv_path, job_id=test_job_id)
        
        test_params = {
            "measure": "PRE", # 事前計算済み
            "model": "REML",
            "data_columns": { # PREなのでescalcには直接使われないが、slab用
                "yi": "yi", 
                "vi": "vi",
                "study_label": "slab" 
            }
            # moderator_columns や subgroup_columns はなしでシンプルなテスト
        }
        test_data_summary = { # RTemplateGeneratorが参照する
            "columns": ["study_id", "yi", "vi", "slab"],
            "shape": [3, 4]
        }

        results = await executor.execute_meta_analysis(test_params, test_data_summary)
        
        print("\n--- R実行結果 ---")
        print(f"Success: {results.get('success')}")
        print(f"Error: {results.get('error')}")
        # print(f"Stdout: {results.get('stdout')}") # 長いのでコメントアウト
        # print(f"Stderr: {results.get('stderr')}")
        print(f"R Script Path: {results.get('r_script_path')}")
        print(f"Generated Plots: {results.get('generated_plots_paths')}")
        print(f"Summary JSON Path: {results.get('structured_summary_json_path')}")
        if results.get('structured_summary_content'):
            print(f"Summary Content: {json.dumps(json.loads(results['structured_summary_content']), indent=2, ensure_ascii=False)}")
        print(f"RData Path: {results.get('rdata_path')}")

        # クリーンアップ
        import shutil
        # shutil.rmtree(temp_dir, ignore_errors=True)
        # logger.info(f"テスト用一時ディレクトリ {temp_dir} をクリーンアップしました。 (手動確認のためコメントアウト)")
        logger.info(f"テスト完了。出力は {r_output_dir} を確認してください。")


    # asyncio.run(run_test())
    print("core/r_executor.py のテストは環境設定とRのインストールが必要です。メイン実行をスキップします。")
