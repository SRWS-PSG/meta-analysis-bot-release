import os
import json
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

class MCPPromptManager:
    def __init__(self):
        self.cache_dir = Path("mcp/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.prompts_cache = self._load_cache()
    
    def _load_cache(self):
        """キャッシュされたプロンプトを読み込む"""
        cache_file = self.cache_dir / "prompts.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"プロンプトキャッシュの読み込み中にエラーが発生しました: {e}")
        return {"prompts": []}
    
    def _save_cache(self):
        """プロンプトをキャッシュに保存する"""
        cache_file = self.cache_dir / "prompts.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(self.prompts_cache, f)
        except Exception as e:
            logger.error(f"プロンプトキャッシュの保存中にエラーが発生しました: {e}")
    
    def get_prompts(self, force_refresh=False):
        """利用可能なプロンプトの一覧を取得する"""
        if not force_refresh and self.prompts_cache["prompts"]:
            return self.prompts_cache["prompts"]
        
        mock_prompts = [
            {"id": "meta_analysis_basic", "name": "基本的なメタ解析", "description": "基本的なメタ解析を実行するためのプロンプト"},
            {"id": "meta_analysis_forest", "name": "フォレストプロット付きメタ解析", "description": "フォレストプロットを生成するメタ解析のプロンプト"},
            {"id": "meta_analysis_subgroup", "name": "サブグループ解析", "description": "サブグループ解析を含むメタ解析のプロンプト"},
            {"id": "meta_analysis_binary", "name": "バイナリアウトカム解析", "description": "オッズ比、リスク比、リスク差を計算するメタ解析"},
            {"id": "meta_analysis_continuous", "name": "連続変数アウトカム解析", "description": "平均差や標準化平均差を計算するメタ解析"},
            {"id": "meta_analysis_fixed", "name": "固定効果モデル", "description": "固定効果モデルを使用したメタ解析"},
            {"id": "meta_analysis_random", "name": "ランダム効果モデル", "description": "ランダム効果モデルを使用したメタ解析"},
            {"id": "meta_analysis_heterogeneity", "name": "異質性解析", "description": "Q統計量、I²統計量、τ²を計算する異質性解析"},
            {"id": "meta_analysis_regression", "name": "メタ回帰分析", "description": "共変量を用いたメタ回帰分析"}
        ]
        
        self.prompts_cache["prompts"] = mock_prompts
        self._save_cache()
        return mock_prompts
    
    def select_template(self, data_summary):
        """データの概要に基づいて最適なテンプレートを選択する"""
        columns = data_summary.get("columns", [])
        
        # バイナリアウトカムのデータかどうかを確認
        if any(col in columns for col in ["event_e", "n_e", "event_c", "n_c"]):
            return self.get_prompt_by_id("meta_analysis_binary")
        
        # 連続変数アウトカムのデータかどうかを確認
        if any(col in columns for col in ["mean_e", "sd_e", "n_e", "mean_c", "sd_c", "n_c"]):
            return self.get_prompt_by_id("meta_analysis_continuous")
        
        if all(col in columns for col in ["yi", "vi"]) and any(col in columns for col in ["moderator", "covariate", "mod"]):
            return self.get_prompt_by_id("meta_analysis_regression")
        
        if any(col in columns for col in ["group", "subgroup"]):
            return self.get_prompt_by_id("meta_analysis_subgroup")
        
        if all(col in columns for col in ["yi", "vi"]):
            return self.get_prompt_by_id("meta_analysis_forest")
        
        return self.get_prompt_by_id("meta_analysis_basic")
    
    def get_prompt_by_id(self, prompt_id):
        """IDによってプロンプトを取得する"""
        prompts = self.get_prompts()
        for prompt in prompts:
            if prompt["id"] == prompt_id:
                return prompt
        return None
    
    def get_template_by_id(self, prompt_id):
        """IDによってテンプレート情報を取得する（詳細な分析設定を含む）"""
        prompt = self.get_prompt_by_id(prompt_id)
        if not prompt:
            return None
        
        # 各プロンプトIDに対応する詳細な分析設定
        template_details = {
            "meta_analysis_basic": {
                "id": prompt_id,
                "name": prompt["name"],
                "description": prompt["description"],
                "default_parameters": {
                    "model_type": "random",
                    "method": "REML"
                    # "ai_interpretation": True, # Fixed
                    # "output_format": "basic" # Fixed to detailed
                },
                "required_columns": ["yi", "vi"],
                "optional_columns": ["study", "n"]
            },
            "meta_analysis_forest": {
                "id": prompt_id,
                "name": prompt["name"],
                "description": prompt["description"],
                "default_parameters": {
                    "model_type": "random",
                    "method": "REML",
                    "generate_forest_plot": True
                    # "ai_interpretation": True, # Fixed
                    # "output_format": "detailed" # Fixed
                },
                "required_columns": ["yi", "vi"],
                "optional_columns": ["study", "n"]
            },
            "meta_analysis_subgroup": {
                "id": prompt_id,
                "name": prompt["name"],
                "description": prompt["description"],
                "default_parameters": {
                    "model_type": "random",
                    "method": "REML",
                    "subgroup_analysis": True
                    # "ai_interpretation": True, # Fixed
                    # "output_format": "detailed" # Fixed
                },
                "required_columns": ["yi", "vi", "subgroup"],
                "optional_columns": ["study", "n"]
            },
            "meta_analysis_binary": {
                "id": prompt_id,
                "name": prompt["name"],
                "description": prompt["description"],
                "default_parameters": {
                    "data_type": "binary",
                    "measure": "OR",  # OR, RR, RD
                    "model_type": "random",
                    "method": "REML"
                    # "ai_interpretation": True, # Fixed
                    # "output_format": "detailed" # Fixed
                },
                "required_columns": ["event_e", "n_e", "event_c", "n_c"],
                "optional_columns": ["study"]
            },
            "meta_analysis_continuous": {
                "id": prompt_id,
                "name": prompt["name"],
                "description": prompt["description"],
                "default_parameters": {
                    "data_type": "continuous",
                    "measure": "SMD",  # SMD, MD
                    "model_type": "random",
                    "method": "REML"
                    # "ai_interpretation": True, # Fixed
                    # "output_format": "detailed" # Fixed
                },
                "required_columns": ["mean_e", "sd_e", "n_e", "mean_c", "sd_c", "n_c"],
                "optional_columns": ["study"]
            },
            "meta_analysis_regression": {
                "id": prompt_id,
                "name": prompt["name"],
                "description": prompt["description"],
                "default_parameters": {
                    "analysis_type": "regression",
                    "model_type": "random",
                    "method": "REML"
                    # "ai_interpretation": True, # Fixed
                    # "output_format": "detailed" # Fixed
                },
                "required_columns": ["yi", "vi"],
                "optional_columns": ["study", "n"],
                "requires_moderators": True
            }
        }
        
        return template_details.get(prompt_id, {
            "id": prompt_id,
            "name": prompt["name"],
            "description": prompt["description"],
            "default_parameters": {},
            "required_columns": ["yi", "vi"],
            "optional_columns": ["study"]
        })
    
    def build_analysis_preferences(self, template, user_parameters=None):
        """テンプレートとユーザーパラメータから分析設定を構築する"""
        if not template:
            return {}
        
        preferences = template.get("default_parameters", {}).copy()
        
        if user_parameters:
            preferences.update(user_parameters)
        
        # 分析タイプをprompt_idから推定
        preferences["analysis_type"] = template["id"]
        
        return preferences
    
    def validate_data_compatibility(self, template, data_columns):
        """データとテンプレートの互換性を検証する"""
        if not template:
            return False, ["テンプレートが見つかりません"]
        
        required_columns = template.get("required_columns", [])
        missing_columns = [col for col in required_columns if col not in data_columns]
        
        if missing_columns:
            return False, [f"必要な列が不足しています: {', '.join(missing_columns)}"]
        
        # メタ回帰分析の場合、モデレーター変数をチェック
        if template.get("requires_moderators", False):
            potential_moderators = [col for col in data_columns 
                                   if col not in required_columns and 
                                   col not in template.get("optional_columns", [])]
            if not potential_moderators:
                return False, ["メタ回帰分析に必要なモデレーター変数が見つかりません"]
        
        return True, []
    
    def invoke_prompt(self, prompt_id, data_summary):
        """プロンプトを呼び出して、テンプレートを取得する"""
        prompt = self.get_prompt_by_id(prompt_id)
        if not prompt:
            logger.error(f"プロンプトが見つかりません: {prompt_id}")
            return None
        
        mock_system_prompts = {
            "meta_analysis_basic": """あなたはRプログラミングとメタ解析の専門家です。
            基本的なメタ解析を実行するRスクリプトを生成してください。
            出力は実行可能なRコードのみにしてください。""",
            "meta_analysis_forest": """あなたはRプログラミングとメタ解析の専門家です。
            フォレストプロットを生成するメタ解析を実行するRスクリプトを生成してください。
            出力は実行可能なRコードのみにしてください。""",
            "meta_analysis_subgroup": """あなたはRプログラミングとメタ解析の専門家です。
            サブグループ解析を含むメタ解析を実行するRスクリプトを生成してください。
            出力は実行可能なRコードのみにしてください。""",
            "meta_analysis_binary": """あなたはRプログラミングとメタ解析の専門家です。
            バイナリアウトカムのメタ解析（オッズ比、リスク比、リスク差）を実行するRスクリプトを生成してください。
            metaforパッケージのescalc関数を使用して効果量を計算し、rma関数でメタ解析を実行してください。
            出力は実行可能なRコードのみにしてください。""",
            "meta_analysis_continuous": """あなたはRプログラミングとメタ解析の専門家です。
            連続変数アウトカムのメタ解析（平均差、標準化平均差）を実行するRスクリプトを生成してください。
            metaforパッケージのescalc関数を使用して効果量を計算し、rma関数でメタ解析を実行してください。
            出力は実行可能なRコードのみにしてください。""",
            "meta_analysis_fixed": """あなたはRプログラミングとメタ解析の専門家です。
            固定効果モデルを使用したメタ解析を実行するRスクリプトを生成してください。
            metaforパッケージのrma関数でmethod='FE'を指定してメタ解析を実行してください。
            出力は実行可能なRコードのみにしてください。""",
            "meta_analysis_random": """あなたはRプログラミングとメタ解析の専門家です。
            ランダム効果モデルを使用したメタ解析を実行するRスクリプトを生成してください。
            metaforパッケージのrma関数でmethod='REML'を指定してメタ解析を実行してください。
            出力は実行可能なRコードのみにしてください。""",
            "meta_analysis_heterogeneity": """あなたはRプログラミングとメタ解析の専門家です。
            異質性統計量（Q統計量、I²統計量、τ²）を計算するメタ解析を実行するRスクリプトを生成してください。
            metaforパッケージのrma関数を使用してメタ解析を実行し、結果から異質性指標を抽出してください。
            出力は実行可能なRコードのみにしてください。""",
            "meta_analysis_regression": """あなたはRプログラミングとメタ解析の専門家です。
            メタ回帰分析を実行するRスクリプトを生成してください。
            metaforパッケージのrma関数を使用して、共変量（moderator variables）を含むメタ回帰分析を実行してください。
            モデル式には共変量を含め、結果の解釈と可視化も行ってください。
            出力は実行可能なRコードのみにしてください。"""
        }
        
        return mock_system_prompts.get(prompt_id)
