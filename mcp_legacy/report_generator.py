import os
import tempfile
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def generate_report(analysis_results: dict, report_type="detailed", academic_writing=None): # report_type is now always "detailed" effectively
    """RmarkdownテンプレートからPDFレポートを生成する"""
    try:
        # output_format is always "detailed", so we use basic_report.Rmd which handles plots.
        # If "academic" was a distinct Rmd, that logic would be here.
        # For now, "detailed" implies basic_report.Rmd and academic_writing is handled by Gemini.
        template_path = Path("templates/rmarkdown/basic_report.Rmd") # Always use basic_report.Rmd for "detailed" output

        if not template_path.exists():
            logger.error(f"テンプレートファイルが見つかりません: {template_path}")
            return None

        # analysis_resultsから必要なパスを取得
        data_path = analysis_results.get("csv_path")
        result_path = analysis_results.get("result_data_path")
        # r_code = analysis_results.get("r_code") # RコードはRmdテンプレート内で直接参照しない想定
        # plots = analysis_results.get("plots", {}) # プロットもRmdテンプレート内で生成または参照

        if not data_path or not result_path:
            logger.error("レポート生成に必要な data_path または result_path が analysis_results に含まれていません。")
            return None

        output_dir_param = analysis_results.get("output_dir")
        if output_dir_param and os.path.isdir(output_dir_param):
             output_dir = output_dir_param # 既存の出力ディレクトリを使用
        else:
            output_dir = tempfile.mkdtemp() # 新規作成

        output_pdf = os.path.join(output_dir, "meta_analysis_report.pdf")

        academic_writing_json = "NULL"
        if academic_writing:
            import json
            # JSON文字列として渡すために、さらにエスケープが必要な場合がある
            # R側で parse_json する想定ならこのままで良い
            academic_writing_json = json.dumps(academic_writing)
            # Rの list() 内で文字列として扱うためにシングルクォートで囲む
            # academic_writing_json = f"'{json.dumps(academic_writing)}'"


        # Rmdのparamsに渡す情報を整理
        # Rmdテンプレート側でこれらのパスを解釈してファイルを利用する
        # プロットのパスも渡す場合は、plots辞書をparamsに追加する
        params_list = {
            "data_path": str(Path(data_path).absolute()).replace('\\', '/'),
            "result_path": str(Path(result_path).absolute()).replace('\\', '/'),
            "academic_writing_json": academic_writing_json # R側でJSONとしてパースする想定
            # "r_code_string": r_code, # Rコード文字列を渡す場合
            # "forest_plot_path_param": str(Path(plots.get("forest")).absolute()).replace('\\', '/'), # 例
            # "funnel_plot_path_param": str(Path(plots.get("funnel")).absolute()).replace('\\', '/'), # 例
        }
        
        # paramsをRのlist形式の文字列に変換
        # academic_writing_json は既にJSON文字列なので、そのまま挿入
        # 他の文字列パラメータはダブルクォートで囲む
        params_r_string = ", ".join(
            f'{key} = "{value}"' if key != "academic_writing_json" else f'{key} = {value}'
            for key, value in params_list.items() if value is not None # Noneのパラメータは含めない
        )


        r_render_script = f"""
        library(rmarkdown)
        render(
            input = "{str(template_path.absolute()).replace('\\', '/')}",
            output_file = "{str(Path(output_pdf).absolute()).replace('\\', '/')}",
            params = list(
                {params_r_string}
            ),
            envir = new.env() # レンダリング環境を分離
        )
        """
        
        render_script_path = os.path.join(output_dir, "render_report.R")
        with open(render_script_path, "w") as f:
            f.write(r_render_script)
        
        try:
            # Determine Rscript executable path
            r_executable = None
            docker_rscript_path = "/usr/bin/Rscript"
            r_executable_from_env = os.environ.get("R_EXECUTABLE_PATH")

            if os.path.exists(docker_rscript_path):
                logger.info(f"Found Rscript at standard Docker path: '{docker_rscript_path}'. This will be preferred.")
                r_executable = docker_rscript_path
            
            if r_executable_from_env:
                if r_executable and r_executable_from_env != docker_rscript_path:
                    logger.info(f"R_EXECUTABLE_PATH is set to '{r_executable_from_env}', but standard Docker path '{docker_rscript_path}' also exists and is preferred.")
                elif not r_executable: # /usr/bin/Rscript was not found
                    logger.info(f"Using Rscript path from R_EXECUTABLE_PATH: '{r_executable_from_env}'.")
                    r_executable = r_executable_from_env
            
            if not r_executable: # Neither standard Docker path nor ENV var (or ENV var was "Rscript" and Docker path not found)
                logger.info("Rscript not found at standard Docker path or via R_EXECUTABLE_PATH. Falling back to 'Rscript' (relies on system PATH).")
                r_executable = "Rscript" # Fallback

            logger.info(f"Attempting to run R script using resolved executable: '{r_executable}'")
            result = subprocess.run(
                [r_executable, render_script_path],
                check=False,  # Don't raise exception on non-zero exit
                capture_output=True,
                text=True,
                timeout=300 # Added timeout, consistent with meta_analysis.py
            )
            if result.returncode != 0:
                logger.error(f"Rmarkdownレンダリングエラー: {result.stderr}")
                error_log_path = os.path.join(output_dir, "render_error.log")
                with open(error_log_path, "w") as f:
                    f.write(f"Stdout:\n{result.stdout}\n\nStderr:\n{result.stderr}")
                logger.error(f"詳細なエラーログ: {error_log_path}")
                return None
        except Exception as e:
            logger.error(f"Rscriptの実行中にエラーが発生しました: {e}")
            return None
        
        if os.path.exists(output_pdf):
            logger.info(f"PDFレポートが正常に生成されました: {output_pdf}")
            return output_pdf
        else:
            logger.error("PDFレポートの生成に失敗しました")
            logger.error(f"Stdout: {result.stdout}")
            logger.error(f"Stderr: {result.stderr}")
            return None
    
    except Exception as e:
        logger.error(f"レポート生成中にエラーが発生しました: {e}")
        return None
