import asyncio
import json
import time
from slack_bolt import App
from slack_sdk.errors import SlackApiError
from core.metadata_manager import MetadataManager
from utils.slack_utils import create_parameter_modal_blocks, create_simple_parameter_selection_blocks
from handlers.analysis_handler import run_analysis_async 
from utils.file_utils import get_r_output_dir

# Legacy imports for natural language parameter collection
from mcp_legacy.parameter_collector import ParameterCollector
from mcp_legacy.gemini_utils import extract_parameters_from_user_input
from mcp_legacy.thread_context import ThreadContextManager
from mcp_legacy.dialog_state_manager import DialogStateManager

# Global instances for legacy parameter collection
_context_manager = None
_parameter_collector = None

def get_context_manager():
    """ThreadContextManagerのシングルトンを取得"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ThreadContextManager()
    return _context_manager

def get_parameter_collector():
    """ParameterCollectorのシングルトンを取得"""
    global _parameter_collector
    if _parameter_collector is None:
        context_manager = get_context_manager()
        _parameter_collector = ParameterCollector(context_manager, None)  # async_runnerは後で設定
    return _parameter_collector

def register_parameter_handlers(app: App):
    """パラメータ収集と解析開始に関連するハンドラーを登録"""

    @app.action("configure_analysis_parameters")
    async def handle_configure_parameters_action(ack, body, client, logger):
        """「パラメータを設定して解析」ボタンが押されたときの処理 - Legacyスタイル"""
        await ack()
        try:
            # 元のメッセージのmetadataからCSV分析結果を取得
            original_message_payload = MetadataManager.extract_from_body(body)
            
            if not original_message_payload or "csv_analysis" not in original_message_payload:
                logger.error("configure_analysis_parameters: CSV分析情報が見つかりません")
                await client.chat_postMessage(
                    channel=body["channel"]["id"],
                    thread_ts=body["message"]["ts"],
                    text="❌ 解析設定の取得に失敗しました。もう一度CSVファイルをアップロードしてください。"
                )
                return

            # Legacyスタイルのコンテキスト管理を初期化
            context_manager = get_context_manager()
            parameter_collector = get_parameter_collector()
            
            channel_id = body["channel"]["id"]
            thread_ts = body["message"]["ts"]
            user_id = body["user"]["id"]
            
            # Legacyコンテキストを初期化
            context = {
                "data_state": {
                    "gemini_analysis": original_message_payload["csv_analysis"],
                    "column_mappings": original_message_payload["csv_analysis"].get("detected_columns", {}),
                    "data_summary": {
                        "columns": list(original_message_payload["csv_analysis"].get("detected_columns", {}).keys())
                    }
                },
                "collected_params": {
                    "required": {},
                    "optional": {},
                    "missing_required": ["effect_size", "model_type"],
                    "asked_optional": []
                }
            }
            
            # DialogStateを設定
            DialogStateManager.set_dialog_state(context, "COLLECTING_PARAMETERS")
            context_manager.save_context(thread_ts, context, channel_id)
            
            # 最初のパラメータ収集質問を開始
            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="📋 解析パラメータを設定します。\n\nどのような効果量で解析しますか？\n例：「オッズ比でお願いします」「リスク比で」「Petoオッズ比で」"
            )
            
        except SlackApiError as e:
            logger.error(f"Legacyパラメータ収集開始エラー: {e.response.get('error', str(e))}")
        except Exception as e:
            logger.error(f"Legacyパラメータ収集開始中に予期せぬエラー: {e}", exc_info=True)

    @app.event("message")
    async def handle_parameter_message(body, event, client, logger):
        """パラメータ収集中のメッセージ処理"""
        # ボット自身のメッセージは無視
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return
            
        # スレッド内のメッセージかどうかチェック
        thread_ts = event.get("thread_ts")
        if not thread_ts:
            return  # スレッド外のメッセージは無視
            
        channel_id = event.get("channel")
        user_id = event.get("user")
        text = event.get("text", "")
        
        try:
            context_manager = get_context_manager()
            parameter_collector = get_parameter_collector()
            
            # コンテキストを取得
            context = context_manager.get_context(thread_id=thread_ts, channel_id=channel_id)
            if not context:
                return  # コンテキストがない場合は無視
            
            # パラメータ収集中かどうかチェック
            dialog_state = DialogStateManager.get_dialog_state(context)
            if dialog_state != "COLLECTING_PARAMETERS":
                return  # パラメータ収集中ではない
            
            logger.info(f"Processing parameter collection message: {text[:100]}...")
            
            # Geminiでパラメータを抽出
            data_summary = context.get("data_state", {}).get("data_summary", {})
            collection_context = collected_params_state
            
            # Legacyのgemini_utilsを使用
            extraction_result = extract_parameters_from_user_input(
                user_input=text,
                data_summary=data_summary,
                conversation_history=None,
                collection_context=collection_context
            )
            
            extracted_params = extraction_result.get("extracted_params", {}) if extraction_result else {}
            logger.info(f"Extracted parameters: {extracted_params}")
            
            # 現在の収集状態を取得
            collected_params_state = context.get("collected_params", {})
            data_summary = context.get("data_state", {}).get("data_summary", {})
            
            # パラメータを更新し、次の質問を取得
            is_complete, next_question = parameter_collector._update_collected_params_and_get_next_question(
                extracted_params, collected_params_state, data_summary, thread_ts, channel_id
            )
            
            # コンテキストを保存
            context["collected_params"] = collected_params_state
            context_manager.save_context(thread_ts, context, channel_id)
            
            if is_complete:
                # パラメータ収集完了
                await client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text="✅ パラメータ収集が完了しました！解析を開始します..."
                )
                
                # 解析を実行
                analysis_params = {
                    "measure": collected_params_state["required"].get("effect_size", "OR"),
                    "method": "REML" if collected_params_state["required"].get("model_type") == "random" else "FE",
                    "model_type": collected_params_state["required"].get("model_type", "random")
                }
                
                # ダイアログ状態を更新
                DialogStateManager.set_dialog_state(context, "RUNNING_ANALYSIS")
                context_manager.save_context(thread_ts, context, channel_id)
                
                # 解析を非同期で実行
                original_payload = context.get("data_state", {})
                await run_analysis_async(
                    original_payload,
                    analysis_params,
                    channel_id,
                    thread_ts,
                    client,
                    logger
                )
                
            elif next_question:
                # 次の質問を送信
                await client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=next_question
                )
            
        except Exception as e:
            logger.error(f"Parameter message processing error: {e}", exc_info=True)
            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"❌ パラメータ処理中にエラーが発生しました: {str(e)}"
            )

    # Legacyスタイルの自然言語処理に変更したため、以下のハンドラーは不要
    # select_effect_size, select_model_type, start_analysis_with_selected_params, cancel_parameter_selection


    @app.view("analysis_params_submission")
    async def handle_analysis_params_submission(ack, body, client, view, logger):
        """パラメータ設定モーダルが送信されたときの処理"""
        
        user_submitted_values = view["state"]["values"]
        user_parameters = {}
        
        # モーダルから値を取得
        # 各input blockのblock_idとaction_idを元に値を取得
        # 例: user_submitted_values["effect_type_block"]["effect_type_select"]["selected_option"]["value"]
        try:
            user_parameters["measure"] = user_submitted_values.get("effect_type_block", {}).get("effect_type_select", {}).get("selected_option", {}).get("value")
            user_parameters["model"] = user_submitted_values.get("model_type_block", {}).get("model_type_select", {}).get("selected_option", {}).get("value")
            
            study_id_col_val = user_submitted_values.get("study_id_col_block", {}).get("study_id_col_select", {}).get("selected_option", {}).get("value")
            if study_id_col_val and study_id_col_val != "no_columns_detected":
                 user_parameters["data_columns"] = user_parameters.get("data_columns", {})
                 user_parameters["data_columns"]["study_label"] = study_id_col_val # study_labelとして扱う

            subgroup_cols_selected = user_submitted_values.get("subgroup_cols_block", {}).get("subgroup_cols_select", {}).get("selected_options", [])
            user_parameters["subgroup_columns"] = [opt["value"] for opt in subgroup_cols_selected if opt["value"] != "no_columns_detected"]
            
            moderator_cols_selected = user_submitted_values.get("moderator_cols_block", {}).get("moderator_cols_select", {}).get("selected_options", [])
            user_parameters["moderator_columns"] = [opt["value"] for opt in moderator_cols_selected if opt["value"] != "no_columns_detected"]

            # TODO: 効果量の種類に応じて、ai, bi, ci, di や n1i, m1i, sd1i などの列マッピングも収集する必要がある
            # create_parameter_modal_blocks と連携して、これらの入力フィールドを追加し、ここで収集する

            logger.info(f"ユーザーが設定した解析パラメータ: {user_parameters}")
            await ack() # viewの送信に対してはack()のみで良い場合がある。応答メッセージは不要。

        except Exception as e:
            logger.error(f"モーダルからのパラメータ抽出エラー: {e}")
            # エラーの場合はモーダルに応答を返す
            await ack(response_action="errors", errors={"effect_type_block": "パラメータの取得に失敗しました。"})
            return

        # private_metadataから元のメッセージの情報を復元
        private_metadata_str = view.get("private_metadata")
        if not private_metadata_str:
            logger.error("analysis_params_submission: private_metadata が見つかりません。")
            # ユーザーにエラー通知も検討
            return
        
        original_message_payload = json.loads(private_metadata_str)
        job_id = original_message_payload.get("job_id")
        channel_id = body["user"]["id"] # DMで送るか、元のチャンネルか。ここでは一旦DMを想定。
                                        # いや、元のチャンネルの元のスレッドに送るべき。
                                        # body["view"]["previous_view_id"] などから元の情報を辿る必要があるかもしれない。
                                        # しかし、private_metadataにchannel_idとthread_tsを含めるのが確実。
                                        # csv_handlerでmetadataにchannel_idとthread_tsも保存するように修正が必要。
                                        # ここでは、original_message_payload にそれらが含まれると仮定する。
        
        # csv_handler.py の metadata 作成部分で channel_id と thread_ts を含めるように修正が必要
        # ここでは、それらが original_message_payload にあると仮定する
        # original_channel_id = original_message_payload.get("channel_id")
        # original_thread_ts = original_message_payload.get("thread_ts")
        # 上記はボタンイベントのbodyから取得できるので、private_metadataには不要かもしれない。
        # views.open したときの body (configure_analysis_parameters の body) を参照する必要がある。
        # これは Slack Bolt の設計上、view submission の body からは直接取れない。
        # 解決策：
        # 1. configure_analysis_parameters で private_metadata に channel_id, thread_ts を含める。
        # 2. または、解析開始メッセージをユーザーにDMで送り、元のスレッドにはリンクを投稿する。
        # ここでは、1. の戦略を想定し、original_message_payload に channel_id, thread_ts が含まれるとする。
        # (csv_handler.py の metadata 作成部分で、event["channel_id"] と event["ts"] または message["ts"] を含める)
        # 今回は、元のメッセージがあったチャンネルとスレッドに投稿する。
        # ボタンを押したときの body["channel"]["id"] と body["message"]["ts"] を private_metadata に含める。
        
        # private_metadata に含めた元のメッセージのチャンネルIDとスレッドTSを取得
        # これは configure_analysis_parameters の呼び出し元 (csv_handler の投稿メッセージ) の情報
        # csv_handler の metadata に channel_id と message_ts を含める必要がある
        # ここでは、original_message_payload にそれらが含まれると仮定
        # payload_channel_id = original_message_payload.get("channel_id_from_event")
        # payload_message_ts = original_message_payload.get("message_ts_from_event")

        # viewオブジェクトから元のチャンネルIDとメッセージTSを取得する方が確実かもしれない
        # しかし、viewオブジェクトには直接それらの情報はない。
        # 確実なのは、configure_analysis_parameters を呼び出す際に、
        # private_metadata に channel_id と thread_ts を含めること。
        # csv_handler.py での metadata 作成時に、
        # "channel_id_of_button_message": event["channel_id"],
        # "ts_of_button_message": message["ts"] のように保存する。
        # ここでは、original_message_payload にそれらが含まれると仮定する。
        
        # 実際には、モーダルを開いたときのインタラクションのbodyから取得した情報を
        # private_metadataに含めるのが最も確実。
        # configure_analysis_parameters の body["channel"]["id"] と body["message"]["ts"] を
        # private_metadata に含める。
        
        # private_metadata には original_message_payload (csv_analyzed の payload) が入っている。
        # この payload には job_id, csv_analysis, file_id, stage, user_id がある。
        # 解析実行に必要なのは、この payload と、今回収集した user_parameters。
        # 投稿先の channel_id と thread_ts は、モーダルを開いたときのインタラクション(ボタンクリック)の
        # body から取得し、private_metadata に含める必要がある。
        # csv_handler.py の create_metadata で "response_channel_id", "response_thread_ts" のようなキーで保存する。
        
        response_channel_id = original_message_payload.get("response_channel_id")
        response_thread_ts = original_message_payload.get("response_thread_ts")

        if not response_channel_id or not response_thread_ts:
            logger.error("モーダル送信処理: 応答先のチャンネルIDまたはスレッドTSが不明です。")
            # ユーザーにエラーを通知 (例: DM)
            try:
                await client.chat_postMessage(user=body["user"]["id"], text="エラー: 解析結果の投稿先が不明です。")
            except Exception:
                pass
            return

        # 更新されたパラメータを元のpayloadにマージ
        original_message_payload["user_parameters"] = user_parameters
        original_message_payload["stage"] = "parameters_configured" # ステージ更新

        # MetadataManager を使って新しい metadata を作成し、元のメッセージを更新 (または新しいメッセージを投稿)
        # ここでは、解析開始の通知を元のスレッドに行う
        await client.chat_postMessage(
            channel=response_channel_id,
            thread_ts=response_thread_ts,
            text=f"⚙️ パラメータを設定しました。解析を開始します。(Job ID: {job_id})"
        )

        r_output_dir = get_r_output_dir(job_id)
        
        asyncio.create_task(run_analysis_async(
            payload=original_message_payload, # 更新されたpayload
            user_parameters=user_parameters,
            channel_id=response_channel_id,
            thread_ts=response_thread_ts,
            user_id=body["user"]["id"], # モーダルを操作したユーザー
            client=client,
            logger=logger,
            r_output_dir=r_output_dir,
            original_file_url=original_message_payload.get("file_url"),
            original_file_name=original_message_payload.get("csv_analysis", {}).get("original_filename", "data.csv")
        ))


    @app.action("start_analysis_with_defaults")
    async def handle_start_with_defaults_action(ack, body, client, logger):
        """「推奨設定で解析開始」ボタンが押されたときの処理"""
        await ack()
        
        payload = MetadataManager.extract_from_body(body)
        if not payload or "csv_analysis" not in payload:
            logger.error("start_analysis_with_defaults: csv_analysisが見つかりません。")
            await client.chat_postMessage(
                channel=body["channel"]["id"],
                thread_ts=body["message"]["ts"],
                text="❌ 解析情報が見つかりません。CSVファイルを再アップロードしてください。"
            )
            return

        job_id = payload.get("job_id")
        csv_analysis_res = payload.get("csv_analysis", {})
        suggested_params = csv_analysis_res.get("suggested_analysis", {})
        
        # Geminiからの推奨を基にパラメータを設定
        default_parameters = {
            "measure": suggested_params.get("effect_type_suggestion", "SMD"), # デフォルトSMD
            "model": suggested_params.get("model_type_suggestion", "REML"),   # デフォルトREML
            # data_columns は Gemini の detected_columns から類推する必要がある
            # ここでは簡略化のため、主要なものだけを渡すか、R側でフォールバックさせる
            "data_columns": {
                # 例: "yi": detected_cols.get("effect_size_candidates")[0] if detected_cols.get("effect_size_candidates") else None
            },
            "subgroup_columns": [], # デフォルトではなし
            "moderator_columns": [] # デフォルトではなし
        }
        
        payload["user_parameters"] = default_parameters # payloadにマージ
        payload["stage"] = "defaults_confirmed"

        await client.chat_postMessage(
            channel=body["channel"]["id"],
            thread_ts=body["message"]["ts"],
            text=f"🚀 推奨設定で解析を開始します。(Job ID: {job_id})"
        )
        
        r_output_dir = get_r_output_dir(job_id)

        asyncio.create_task(run_analysis_async(
            payload=payload,
            user_parameters=default_parameters,
            channel_id=body["channel"]["id"],
            thread_ts=body["message"]["ts"],
            user_id=body["user"]["id"],
            client=client,
            logger=logger,
            r_output_dir=r_output_dir,
            original_file_url=payload.get("file_url"),
            original_file_name=payload.get("csv_analysis", {}).get("original_filename", "data.csv")
        ))

    @app.action("cancel_analysis_request")
    async def handle_cancel_analysis_action(ack, body, client, logger):
        """「キャンセル」ボタンが押されたときの処理"""
        await ack()
        
        payload = MetadataManager.extract_from_body(body)
        job_id = payload.get("job_id", "不明なジョブ")

        # 元のメッセージを更新して、キャンセルされたことを示す
        # (ボタンを消す、または「キャンセルされました」と表示する)
        try:
            await client.chat_update(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
                text=f"🗑️ 解析リクエスト (Job ID: {job_id}) はキャンセルされました。",
                blocks=[] # ボタンを消すために空のblocks
            )
            logger.info(f"解析リクエストがキャンセルされました。Job ID: {job_id}")
        except SlackApiError as e:
            logger.error(f"キャンセルメッセージの更新に失敗: {e.response['error']}")
        
        # 必要であれば、関連するmetadataをクリアする処理などをここに追加
        # (例: 特定のストレージからこのjob_idの情報を削除する)
