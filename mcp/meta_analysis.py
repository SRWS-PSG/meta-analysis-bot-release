import os
import re
import json
import tempfile
import subprocess
import logging
from pathlib import Path
from typing import Optional
import pandas as pd
import requests
# import rpy2.robjects as robjects # rpy2 関連削除
# from rpy2.robjects import pandas2ri # rpy2 関連削除
# from rpy2.robjects import numpy2ri # Import numpy2ri # rpy2 関連削除
# from rpy2.robjects import conversion # rpy2 関連削除
# pandas2ri.activate() # rpy2 関連削除
# numpy2ri.activate() # Activate numpy2ri # rpy2 関連削除

# Import App from slack_bolt for upload_file_to_slack, assuming it's needed for app.client
from slack_bolt import App

# 新しく作成したRTemplateGeneratorをインポート
from mcp.r_template_generator import RTemplateGenerator
# Geminiデバッグ関数をインポート
from mcp.gemini_utils import regenerate_r_script_with_gemini_debugging
# 新しいGemini列マッピング関数をインポート
from mcp.gemini_utils import map_csv_columns_to_meta_analysis_roles


logger = logging.getLogger(__name__)

# This is a placeholder for the slack_bolt App instance.
# In a real scenario, this should be properly initialized or passed around.
# For now, we'll assume that the client methods used in upload_file_to_slack
# will be available through an App instance if this module is imported elsewhere
# where 'app' is defined. If 'app' is not available, upload_file_to_slack will fail.
# A better approach would be to pass the 'client' object directly to upload_file_to_slack.
# For now, to make it runnable as extracted, we define a placeholder.
# Consider refactoring upload_file_to_slack to accept a client instance.
try:
    app_instance = App(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
    )
except Exception:
    app_instance = None # Fallback if env vars are not set

def download_file(url: str, token: str, target_dir: Optional[str] = None, filename: str = "downloaded_file") -> str:
    """
    SlackのプライベートURLからファイルをダウンロードする。
    target_dirが指定された場合、そのディレクトリにファイルを保存する。
    そうでない場合は、ファイルコンテンツを返す。
    """
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    if target_dir:
        target_path = Path(target_dir) / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, 'wb') as f:
            f.write(response.content)
        logger.info(f"File downloaded to {target_path}")
        return str(target_path)
    else:
        # For analyze_csv, we might still want to pass content directly if not saving to thread_dir yet
        # However, the plan is to save to thread_dir, so this branch might become less used.
        # For now, returning content for backward compatibility or other uses.
        # If always saving, this function should always return a path.
        # Let's assume for now, if target_dir is not given, it's an error or needs specific handling.
        # For the current refactor, target_dir should ideally always be provided by the caller.
        # To strictly follow the plan, this function should perhaps *require* target_dir.
        # Let's adjust analyze_csv to prepare the path.
        # For now, if target_dir is None, we'll raise an error or return content.
        # Returning content for now.
        logger.warning("download_file called without target_dir. Returning content instead of path.")
        return response.content # This will likely need adjustment based on how analyze_csv calls it.

def analyze_csv(file_content: bytes, thread_dir: Optional[str] = None, input_filename: str = "data.csv"):
    """
    pandasを使用してCSVコンテンツを分析する。
    thread_dirが指定された場合、そのディレクトリにCSVファイルを保存して分析する。
    """
    if thread_dir:
        temp_path = Path(thread_dir) / input_filename
        temp_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
        with open(temp_path, 'wb') as f: # Write bytes
            f.write(file_content)
        logger.info(f"CSV content saved to {temp_path} for analysis.")
    else:
        # Fallback to old behavior if thread_dir is not provided
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='wb') as temp_file_obj:
            temp_file_obj.write(file_content)
            temp_path = Path(temp_file_obj.name)
        logger.warning(f"analyze_csv: thread_dir not provided, using tempfile: {temp_path}")

    try:
        df = pd.read_csv(str(temp_path))
        data_summary = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "head": df.head(5).to_dict(orient='records')
        }
        # MCPプロンプトマネージャーをインポートしてプロンプトを取得
        from mcp.prompt_manager import MCPPromptManager
        prompt_manager = MCPPromptManager()
        available_prompts = prompt_manager.get_prompts()
        
        # Gemini APIを呼び出して互換性を分析
        from mcp.gemini_utils import analyze_csv_compatibility_with_mcp_prompts
        gemini_analysis_result = analyze_csv_compatibility_with_mcp_prompts(data_summary, available_prompts)

        # 新しいGemini Function Callingを呼び出して列マッピングを試みる
        # ParameterCollector.REQUIRED_PARAMS_DEFINITION と OPTIONAL_PARAMS_DEFINITION を参考に、
        # 汎用的な役割のリストを作成
        # ここでは、ParameterCollectorを直接インポートせず、必要な役割をハードコードするか、
        # 別の方法で取得することを検討。循環参照を避けるため。
        # 一旦、必要な役割を直接リストとして定義します。
        target_roles_for_mapping = [
            "study_id", "publication_year", "region", "subgroup", "mean_age", 
            "intervention_dose", "follow_up_months", "risk_of_bias", 
            "events_treatment", "total_treatment", "events_control", "total_control",
            "ai", "bi", "ci", "di", "n1i", "n2i", "m1i", "m2i", "sd1i", "sd2i",
            "proportion_events", "proportion_total", "proportion_time", "yi", "vi",
            "study_label_author", "study_label_year", "study_label",
            "potential_subgroup_candidate", "potential_moderator_candidate" # 新しい役割
        ]

        column_mapping_result = map_csv_columns_to_meta_analysis_roles(
            csv_columns=df.columns.tolist(),
            csv_sample_data=df.head(5).to_dict(orient='records'),
            target_roles=target_roles_for_mapping
        )
        
        mapped_columns_data = column_mapping_result.get("mapped_columns", {}) if column_mapping_result else {}
        
        # final_column_mappings に mapped_columns_data の全内容をコピーする
        final_column_mappings = mapped_columns_data.copy() if mapped_columns_data else {}
        
        # 念のため、期待されるキーが存在しない場合に備えてデフォルト値を設定
        final_column_mappings.setdefault("target_role_mappings", {})
        final_column_mappings.setdefault("suggested_subgroup_candidates", [])
        final_column_mappings.setdefault("suggested_moderator_candidates", [])
        final_column_mappings.setdefault("detected_effect_size", None)
        final_column_mappings.setdefault("is_log_transformed", None)
        final_column_mappings.setdefault("data_format", None)
        final_column_mappings.setdefault("detected_columns", {})
        
        if gemini_analysis_result:
            return {
                "summary": data_summary,
                "suitable_for_meta_analysis": gemini_analysis_result.get("suitable_for_meta_analysis", False),
                "gemini_analysis": gemini_analysis_result, # Geminiからの詳細な分析結果
                "column_mappings": final_column_mappings, # 更新されたマッピング結果
                "file_path": temp_path
            }
        else:
            # Gemini API呼び出しに失敗した場合、基本的な列チェックにフォールバック
            logger.warning("Gemini APIによるCSV互換性分析に失敗しました。基本的な列チェックを行います。")
            has_required_columns = all(col in df.columns for col in ['yi', 'vi'])
            return {
                "summary": data_summary,
                "suitable_for_meta_analysis": has_required_columns,
                "gemini_analysis": None, # Gemini分析なし
                "column_mappings": final_column_mappings, # Gemini分析なしでもマッピング結果は含める
                "user_message": "Gemini APIとの連携に失敗したため、基本的な列チェックのみ行いました。" if not has_required_columns else None,
                "file_path": temp_path
            }
            
    except Exception as e:
        logger.error(f"CSVの分析中にエラーが発生しました: {e}")
        os.unlink(temp_path) # Ensure temp file is deleted on error
        # エラー時も column_mappings を空で返すようにする
        # エラー時も新しい構造で返す
        final_column_mappings_on_error = {
            "target_role_mappings": {},
            "suggested_subgroup_candidates": [],
            "suggested_moderator_candidates": []
        }
        return {"error": str(e), "file_path": str(temp_path), "suitable_for_meta_analysis": False, "gemini_analysis": None, "column_mappings": final_column_mappings_on_error} # Return path for cleanup

def run_meta_analysis(csv_path: str, analysis_preferences: dict = None, thread_dir: Optional[str] = None):
    logger.info("--- run_meta_analysis function started ---")
    """
    Rのmetaforパッケージを使用してメタ解析を実行する。
    thread_dirが指定された場合、そのディレクトリをoutput_dirとして使用する。
    RスクリプトはRTemplateGeneratorを使用して生成する。
    エラー発生時はGeminiによるデバッグを試行する。
    """
    if thread_dir:
        output_dir = Path(thread_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using thread_dir as output_dir: {output_dir}")
    else:
        output_dir = Path(tempfile.mkdtemp())
        logger.warning(f"run_meta_analysis: thread_dir not provided, using tempdir: {output_dir}")

    # 出力ファイルパスの定義
    # RTemplateGenerator がこれらのキー名でパスを期待する
    output_paths = {
        "forest_plot_path": str(output_dir / "forest_plot.png"),
        "funnel_plot_path": str(output_dir / "funnel_plot.png"),
        "rdata_path": str(output_dir / "result.RData"),
        "json_summary_path": str(output_dir / "summary.json"), # 構造化JSON
        "bubble_plot_path_prefix": str(output_dir / "bubble_plot"), # メタ回帰用
        "forest_plot_subgroup_prefix": str(output_dir / "forest_plot_subgroup") # サブグループ用プレフィックスを追加
    }
    
    # 個別の変数として抽出
    forest_plot_path = output_paths["forest_plot_path"]
    funnel_plot_path = output_paths["funnel_plot_path"]
    rdata_path = output_paths["rdata_path"]
    structured_summary_json_path = output_paths["json_summary_path"]
    
    r_script_path = str(output_dir / "run_meta.R")
    abs_csv_path = str(Path(csv_path).resolve())

    # CSVデータのサマリーを取得
    try:
        df = pd.read_csv(abs_csv_path)
        data_summary = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "head": df.head(5).to_dict(orient='records')
        }
    except Exception as e:
        logger.error(f"Failed to read or summarize CSV file {abs_csv_path}: {e}")
        return {
            "success": False,
            "error": f"CSVファイルの読み込みまたはサマリー作成に失敗: {e}",
            "r_script_path": None,
            "output_dir": str(output_dir),
            "csv_path": abs_csv_path,
            "r_code": None
        }

    # analysis_preferences が None の場合のデフォルト値を設定
    if analysis_preferences is None:
        analysis_preferences = {}
    
    # RTemplateGeneratorのインスタンス化
    template_generator = RTemplateGenerator()
    r_code = "" # 初期化

    max_retries = 3  # 最大試行回数 (テンプレート生成 -> Geminiデバッグ1 -> Geminiデバッグ2)
    current_r_code_source = "template" # 'template' or 'gemini_debug'

    for attempt in range(max_retries):
        logger.info(f"Rスクリプト実行試行 {attempt + 1}/{max_retries} (ソース: {current_r_code_source})")
        
        if attempt == 0: # 初回はテンプレートから生成
            try:
                r_code = template_generator.generate_full_r_script(
                    analysis_params=analysis_preferences,
                    data_summary=data_summary,
                    output_paths=output_paths,
                    csv_file_path_in_script=abs_csv_path # Rスクリプト内で使われるCSVパス
                )
                logger.info("RTemplateGeneratorによるRスクリプト生成に成功しました。")
            except Exception as e_template_gen:
                logger.error(f"RTemplateGeneratorによるRスクリプト生成中にエラー: {e_template_gen}")
                if attempt == max_retries - 1: # 最後の試行でもテンプレート生成失敗なら終了
                    return {
                        "success": False, "error": f"Rスクリプトのテンプレート生成に失敗: {e_template_gen}",
                        "r_script_path": None, "output_dir": str(output_dir),
                        "csv_path": abs_csv_path, "r_code": None
                    }
                # 次の試行でGeminiデバッグに移行するため、ここではエラーのまま続行
                # （ただし、r_codeが空のままなので、次のsubprocess.runで問題が出る可能性がある。
                #  より堅牢にするなら、テンプレート生成失敗時点でGeminiデバッグを試みるべきか検討）
                #  ここでは、subprocess.CalledProcessError をキャッチしてGeminiデバッグに進む想定
                pass # r_codeが空のまま次のループに進むか、エラーを投げる
        
        # r_codeが空の場合はスキップ（テンプレート生成失敗など）
        if not r_code and attempt > 0: # attempt 0 は上で生成されるはず
             logger.warning(f"試行 {attempt + 1}: r_codeが空のため、Rスクリプト実行をスキップします。")
             if attempt == max_retries -1: # 最後の試行でもr_codeが空ならエラー
                return {
                    "success": False, "error": "Rスクリプトが生成されませんでした。",
                    "r_script_path": r_script_path if os.path.exists(r_script_path) else None, 
                    "output_dir": str(output_dir), "csv_path": abs_csv_path, "r_code": None
                }
             continue # 次のデバッグ試行へ

        logger.info(f"実行対象のRスクリリプト (試行 {attempt + 1}):\n{r_code[:1000]}...") # 長すぎる場合は一部表示
        with open(r_script_path, 'w', encoding='utf-8') as f:
            f.write(r_code)

        try:
            # R実行可能ファイルのパス解決
            env_r_executable_path = os.environ.get("R_EXECUTABLE_PATH")
            logger.info(f"Environment R_EXECUTABLE_PATH: {env_r_executable_path}")

            r_executable = env_r_executable_path

            if not r_executable:
                logger.info("R_EXECUTABLE_PATH not set. Checking other options.")
                docker_rscript_path = "/usr/bin/Rscript"
                docker_path_exists = os.path.exists(docker_rscript_path)
                logger.info(f"Checking Docker path: {docker_rscript_path}, Exists: {docker_path_exists}")
                if docker_path_exists:
                    r_executable = docker_rscript_path
                    logger.info(f"Using Docker path: {r_executable}")
                else:
                    logger.info(f"Docker path {docker_rscript_path} not found.")
                    windows_default_r_path = r"C:\Program Files\R\R-4.4.1\bin\Rscript.exe"
                    windows_path_exists = os.path.exists(windows_default_r_path)
                    logger.info(f"Checking Windows default path: {windows_default_r_path}, Exists: {windows_path_exists}")
                    if windows_path_exists:
                        r_executable = windows_default_r_path
                        logger.info(f"Using Windows default path: {r_executable}")
                    else:
                        logger.info(f"Windows default path {windows_default_r_path} not found.")
                        r_executable = "Rscript" # 最終フォールバック
                        logger.info(f"Using default 'Rscript' command: {r_executable}")
            else:
                logger.info(f"Using R_EXECUTABLE_PATH from environment: {r_executable}")
            
            logger.info(f"Final R executable to be used: {r_executable}")
            
            # Execute R script using subprocess
            process_result = subprocess.run(
                [r_executable, r_script_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
                encoding='utf-8'
            )
            
            # Rスクリプト実行後、structured_summary.json (旧 analysis_summary.json) が生成されているはず
            structured_summary_content_str = None
            generated_plots_list = [] # generated_plotsを初期化
            if os.path.exists(structured_summary_json_path): # ★変更
                try:
                    with open(structured_summary_json_path, 'r', encoding='utf-8') as f: # ★変更
                        structured_summary_content_json = json.load(f) # JSONオブジェクトとして読み込む
                    structured_summary_content_str = json.dumps(structured_summary_content_json) # 文字列としても保持
                    generated_plots_list = structured_summary_content_json.get("generated_plots", [])
                    logger.info(f"Successfully read and parsed generated JSON file: {structured_summary_json_path}") # ★変更
                    logger.info(f"Extracted generated_plots: {generated_plots_list}")
                except Exception as e_read_json:
                    logger.error(f"Error reading or parsing generated JSON file {structured_summary_json_path}: {e_read_json}") # ★変更
                    # JSONファイルが読めない場合でも、他の処理は続行する可能性があるため、structured_summary_content_str は None のまま
            else:
                logger.error(f"Generated JSON file not found: {structured_summary_json_path}") # ★変更

            return_value = {
                "success": True, # Rスクリプトの実行自体は成功したと仮定（エラーは stderr で捕捉されるべき）
                "forest_plot_path": forest_plot_path, 
                "funnel_plot_path": funnel_plot_path, 
                "r_script_path": r_script_path,
                "output_dir": str(output_dir),
                "result_data_path": rdata_path,  # 修正: result_data_path -> rdata_path
                "structured_summary_json_path": structured_summary_json_path, # ★変更: 正しい構造化JSONファイルのパス
                "structured_summary_content": structured_summary_content_str, # ★変更: 正しい構造化JSONファイルの内容（文字列）
                "generated_plots": generated_plots_list, 
                "csv_path": abs_csv_path,
                "stdout": process_result.stdout,
                "stderr": process_result.stderr,
                "r_code": r_code
            }
            logger.info(f"Return value from run_meta_analysis (before summary update): { {k: (v[:200] + '...' if isinstance(v, str) and len(v) > 200 else v) for k, v in return_value.items()} }")

            # structured_summary_json_path が存在し、内容が読み込めた場合
            if structured_summary_content_str and structured_summary_content_str != "{}":
                try:
                    # 既存の summary.json の内容を読み込む
                    existing_summary_data = json.loads(structured_summary_content_str)

                    # analysis_results (return_value) の内容をそのままマージする
                    # structured_summary_content は循環参照になるので除外するか、
                    # マージ後のものを再度設定する
                    # ここでは、return_value のうち、structured_summary_content 以外のものをマージ対象とする
                    # ただし、return_value 自体が analysis_results に相当するため、
                    # return_value のキーと existing_summary_data のキーが衝突する場合、
                    # return_value の値で上書きする
                    
                    # マージするPython側のデータ (return_value全体を基本とするが、循環参照や不要なものは除く)
                    # structured_summary_content はマージ後に再設定するので、ここでは含めない
                    python_data_to_merge = {k: v for k, v in return_value.items() if k != "structured_summary_content"}

                    # 既存のサマリーデータにPython側の情報をマージ (Python側を優先)
                    merged_summary_data = {**existing_summary_data, **python_data_to_merge}
                    
                    # 更新されたサマリーデータを structured_summary_json_path に書き戻す
                    with open(structured_summary_json_path, 'w', encoding='utf-8') as f_rewrite:
                        json.dump(merged_summary_data, f_rewrite, indent=4)
                    logger.info(f"Successfully updated {structured_summary_json_path} with Python-side analysis_results.")

                    # return_value 内の structured_summary_content も更新後のものにする
                    return_value["structured_summary_content"] = json.dumps(merged_summary_data)

                except json.JSONDecodeError as e_json_decode:
                    logger.error(f"Error decoding existing summary JSON from {structured_summary_json_path}: {e_json_decode}")
                    # この場合、マージはできないが、他の処理は続行する可能性がある
                except IOError as e_io_rewrite:
                    logger.error(f"Error rewriting {structured_summary_json_path}: {e_io_rewrite}")
                    # 書き込みエラーの場合も、他の処理は続行する可能性がある
                except Exception as e_update_json:
                    logger.error(f"Unexpected error while updating {structured_summary_json_path} with analysis_results: {e_update_json}")
            else:
                logger.warning(f"{structured_summary_json_path} was not found or was empty. Cannot add analysis_results to it.")
            
            logger.info(f"Final return value from run_meta_analysis (after summary update attempt): { {k: (v[:200] + '...' if isinstance(v, str) and len(v) > 200 else v) for k, v in return_value.items()} }")
            return return_value
        except subprocess.CalledProcessError as e:
            logger.warning(f"R script execution failed (attempt {attempt+1}/{max_retries}): {e.stderr}")
            if attempt < max_retries - 1:
                try:
                    # from mcp.self_debugging import debug_r_script # 古いデバッグモジュール
                    # Geminiデバッグ関数を呼び出す
                    new_script = regenerate_r_script_with_gemini_debugging(
                        data_summary=data_summary,
                        error_message=e.stderr, # subprocess.CalledProcessError の stderr
                        failed_r_code=r_code
                    )
                    current_r_code_source = "gemini_debug"

                    if new_script:
                        logger.info(f"Geminiによるデバッグ成功。新しいRスクリプトで再試行します。")
                        # Geminiが生成したスクリプトの前処理 (例: ```r ``` の除去)
                        if new_script.startswith("```r"): new_script = new_script[4:]
                        if new_script.startswith("```"): new_script = new_script[3:]
                        if new_script.endswith("```"): new_script = new_script[:-3]
                        
                        # デバッグされたスクリプトの先頭に read.csv を追加 (Geminiデバッグ関数はこれを含まない想定)
                        if "dat <- read.csv" not in new_script:
                             new_script = f"dat <- read.csv('{abs_csv_path.replace('\\', '/')}')\n" + new_script.strip()
                        r_code = new_script.strip()
                        
                        # パスが正しく置換されているか確認（特にJSON保存パスなど、テンプレート由来のパス）
                        # これはGeminiがテンプレートのプレースホルダーを理解していない可能性があるため
                        for key, path_val in output_paths.items():
                            placeholder = f"{{{key}}}" # 例: {json_summary_path}
                            if placeholder in r_code:
                                r_code = r_code.replace(placeholder, path_val.replace('\\', '/'))
                        
                        logger.info(f"デバッグ後のRスクリプト (再実行前):\n{r_code[:1000]}...")
                        # with open(r_script_path, 'w', encoding='utf-8') as f: # 上で既に書き込み済み
                        #    f.write(r_code)
                    else:
                        logger.error("GeminiによるRスクリプトのデバッグに失敗しました。")
                        if attempt == max_retries - 1: # 最後の試行でもデバッグ失敗
                             return {
                                "success": False, "error": f"Rスクリプトの実行とデバッグに失敗: {e.stderr}",
                                "r_script_path": r_script_path, "output_dir": str(output_dir),
                                "csv_path": abs_csv_path, "r_code": r_code
                            }
                except ImportError:
                    logger.warning("gemini_utils.regenerate_r_script_with_gemini_debugging がインポートできませんでした。")
                    if attempt == max_retries - 1: # 最後の試行
                        return {
                            "success": False, "error": f"Rスクリプト実行失敗、デバッグモジュールなし: {e.stderr}",
                            "r_script_path": r_script_path, "output_dir": str(output_dir),
                            "csv_path": abs_csv_path, "r_code": r_code
                        }
                except Exception as dbg_e:
                    logger.error(f"Gemini Rスクリプトのデバッグ中に予期せぬエラー: {dbg_e}")
                    if attempt == max_retries - 1: # 最後の試行
                        return {
                            "success": False, "error": f"Rスクリプト実行失敗、デバッグ中にエラー: {e.stderr}, Debug Error: {dbg_e}",
                            "r_script_path": r_script_path, "output_dir": str(output_dir),
                            "csv_path": abs_csv_path, "r_code": r_code
                        }
            else: # 最後の試行で CalledProcessError
                logger.error(f"Rスクリプトの実行が{max_retries}回の試行後も失敗しました。最終エラー: {e.stderr}")
                return {
                    "success": False, "error": e.stderr,
                    "r_script_path": r_script_path, "output_dir": str(output_dir),
                    "csv_path": abs_csv_path, "r_code": r_code
                }
        except subprocess.TimeoutExpired:
            logger.error(f"メタ解析の実行がタイムアウトしました (試行 {attempt+1}/{max_retries})")
            if attempt == max_retries - 1:
                 return {
                    "success": False, "error": "R script execution timed out.",
                    "r_script_path": r_script_path, "output_dir": str(output_dir),
                    "csv_path": abs_csv_path, "r_code": r_code
                }
        except FileNotFoundError: # Rscript実行ファイルが見つからない場合
            logger.error(f"Rscript実行可能ファイルが見つかりません。R_EXECUTABLE_PATH環境変数を確認してください。")
            return { # このエラーはリトライしても解決しない可能性が高いので即時終了
                "success": False, "error": "Rscript executable not found. Check R_EXECUTABLE_PATH environment variable.",
                "r_script_path": r_script_path, "output_dir": str(output_dir),
                "csv_path": abs_csv_path, "r_code": r_code
            }
        except Exception as general_e: # その他の予期せぬエラー
            logger.error(f"Rスクリプト実行中に予期せぬエラー (試行 {attempt+1}/{max_retries}): {general_e}")
            if attempt == max_retries - 1:
                return {
                    "success": False, "error": f"Unexpected error during R script execution: {general_e}",
                    "r_script_path": r_script_path, "output_dir": str(output_dir),
                    "csv_path": abs_csv_path, "r_code": r_code
                }
    # ループが完了しても成功しなかった場合 (通常はループ内でreturnされるはず)
    logger.error(f"Rスクリプトの実行が{max_retries}回の試行後も成功しませんでした。")
    return {
        "success": False, "error": "All retries to execute R script failed.",
        "r_script_path": r_script_path, "output_dir": str(output_dir),
        "csv_path": abs_csv_path, "r_code": r_code
    }

def upload_file_to_slack(client, file_path, channel_id, title, thread_ts=None):
    """新しいfiles.getUploadURLExternal APIを使用してファイルをSlackにアップロードする"""
    try:
        get_url_response = client.files_getUploadURLExternal(
            filename=os.path.basename(file_path),
            length=os.path.getsize(file_path),
            # title=title # title is not a parameter for files_get_upload_url_external
        )
    except Exception as e:
        logger.error(f"files.getUploadURLExternalの呼び出し中にエラー: {e}")
        raise

    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    try:
        upload_response = requests.post(
            get_url_response["upload_url"],
            data=file_content,
            headers={"Content-Type": "application/octet-stream"},
            allow_redirects=True
        )
        upload_response.raise_for_status()
    except Exception as e:
        logger.error(f"ファイルコンテンツのアップロード中にエラー: {e}")
        raise
        
    files_data = [{
        "id": get_url_response["file_id"],
        "title": title,
    }]

    try:
        complete_response = client.files_completeUploadExternal(
            files=files_data, # Pass as a list of file objects
            channel_id=channel_id, # Corrected parameter name
            thread_ts=thread_ts,
            initial_comment=f"{title}をアップロードしました。"
        )
        return complete_response
    except Exception as e:
        logger.error(f"files.completeUploadExternalの呼び出し中にエラー: {e}")
        # Attempt to delete the file if completion fails to avoid orphaned uploads
        try:
            client.files_delete(file=get_url_response["file_id"])
            logger.info(f"アップロード完了失敗後、ファイル {get_url_response['file_id']} を削除しました。")
        except Exception as delete_e:
            logger.error(f"アップロード完了失敗後のファイル削除中にエラー: {delete_e}")
        raise

def cleanup_temp_files(*paths_to_delete):
    """一時ファイルやディレクトリをクリーンアップする"""
    for path_str in paths_to_delete:
        if not path_str or not os.path.exists(path_str):
            continue
        try:
            if os.path.isfile(path_str):
                os.unlink(path_str)
                logger.info(f"一時ファイル {path_str} を削除しました。")
            elif os.path.isdir(path_str):
                # Recursively delete directory contents
                for root, dirs, files in os.walk(path_str, topdown=False):
                    for name in files:
                        os.unlink(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(path_str) # Delete the now-empty directory
                logger.info(f"一時ディレクトリ {path_str} を削除しました。")
        except Exception as e:
            logger.error(f"一時ファイル/ディレクトリ {path_str} の削除中にエラー: {e}")
