"""
Dialog State Managerモジュール

Slack Botのダイアログ状態遷移を管理します。
"""
import logging

logger = logging.getLogger(__name__)

class DialogStateManager:
    """ダイアログ状態管理を責任とするクラス"""
    
    STATES = {
        "WAITING_FILE": {"type": "waiting_for_file", "state": "initial"},
        "PROCESSING_FILE": {"type": "processing_file", "state": "analyzing_csv"},
        "COLLECTING_PARAMS": {"type": "analysis_preference", "state": "collecting_params"},
        "ANALYSIS_RUNNING": {"type": "analysis_preference", "state": "analysis_running"},
        "POST_ANALYSIS": {"type": "post_analysis", "state": "ready_for_questions"}
    }
    
    @staticmethod
    def transition_to_collecting_params(context: dict, required_params_def: dict) -> dict:
        """CSV処理完了後、パラメータ収集状態へ遷移"""
        context["dialog_state"] = {
            "type": "analysis_preference",
            "state": "collecting_params",
            "collected_params": {
                "required": {},
                "optional": {},
                "missing_required": list(required_params_def.keys()),
                "asked_optional": []
            },
            "is_initial_response": True 
        }
        context["initial_csv_prompt_sent"] = False # Ensure initial prompt is sent
        return context

    @staticmethod
    def set_dialog_state(context: dict, state_key: str):
        if state_key in DialogStateManager.STATES:
            context["dialog_state"] = DialogStateManager.STATES[state_key].copy() # Use .copy() to avoid modifying the class attribute
        else:
            logger.error(f"Unknown state key: {state_key}")
            context["dialog_state"] = DialogStateManager.STATES["WAITING_FILE"].copy()
        return context
