"""
Message Handlersモジュール

Slackの各種イベント（メッセージ、メンション、ファイル共有）を処理し、
適切なアクションにディスパッチします。
"""
import logging
import json
import time # 追加

from mcp.dialog_state_manager import DialogStateManager
# ParameterCollector と AnalysisExecutor は直接は使わないが、
# 呼び出し元の MetaAnalysisBot がそれらのインスタンスを持つ想定
# from mcp.parameter_collector import ParameterCollector
# from mcp.analysis_executor import AnalysisExecutor
from mcp.gemini_utils import interpret_meta_analysis_results, interpret_meta_regression_results


logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, context_manager, csv_processor, parameter_collector, analysis_executor, bot_user_id): # bot_user_id を引数に追加
        self.context_manager = context_manager
        self.csv_processor = csv_processor
        self.parameter_collector = parameter_collector
        self.analysis_executor = analysis_executor
        self.bot_user_id = bot_user_id # bot_user_id をインスタンス変数として保持
        # self.report_handler = report_handler # report_handlerはAnalysisExecutor経由で呼ばれる

    def handle_app_mention(self, event, client, context_manager_instance): # context_manager_instance を引数に追加
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        text = event.get("text", "")
        
        logger.info(f"=== APP_MENTION EVENT START ===")
        logger.info(f"APP_MENTION: event.ts={event.get('ts')}, event.thread_ts={event.get('thread_ts')}, channel={channel_id}, text='{text}'")
        
        context = context_manager_instance.get_context(thread_ts, channel_id) # 引数の context_manager_instance を使用
        if not context:
            context = {
                "thread_active": True, "thread_ts": thread_ts, "channel_id": channel_id,
                "dialog_state": {"type": "waiting_for_file", "state": "initial"},
                "processed_file_ids": [] # ファイルIDの重複チェック用リスト
            }
            logger.info(f"Created new context for thread {thread_ts}")
        else:
            context["thread_ts"] = thread_ts; context["channel_id"] = channel_id
            if "processed_file_ids" not in context: # 既存コンテキストにない場合追加
                context["processed_file_ids"] = []
            logger.info(f"Using existing context for thread {thread_ts}")

        files = event.get("files", [])
        csv_files = [f for f in files if f.get("name", "").lower().endswith(".csv")]
        
        if csv_files:
            # ファイル処理中か確認
            current_dialog_type = context.get("dialog_state", {}).get("type")
            if current_dialog_type in ["processing_file", "analysis_preference"]:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text="現在別のファイルを処理中です。処理完了後に再度お試しいただくか、別スレッドでご相談ください。"
                )
                context_manager_instance.save_context(thread_ts, context, channel_id)
                return

            file_obj = csv_files[0]
            file_id = file_obj.get("id")
            if file_id and file_id in context.get("processed_file_ids", []):
                logger.info(f"File {file_id} already processed in app_mention, skipping. Event ts: {event.get('ts')}")
                # client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=f"ファイル「{file_obj.get('name')}」は既に処理を開始しています。")
                context_manager_instance.save_context(thread_ts, context, channel_id)
                return

            # 最初のメッセージ送信は csv_processor に任せるか、ここで統一するか検討。
            # csv_processor.process_csv_file の冒頭で「分析を開始しています...」を送信しているので、
            # ここでの「受け取りました」メッセージは削除または変更する。
            # client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=f"CSVファイル「{file_obj.get('name')}」を受け取りました。分析を開始します。")
            
            self.csv_processor.process_csv_file(file_obj, thread_ts, channel_id, client, context)
            
            if file_id: # process_csv_file が正常に開始された場合のみ追加
                context.setdefault("processed_file_ids", []).append(file_id)
        else:
            # ファイルがないメンションの場合
            client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="こんにちは！メタアナリシスBotです。私を呼ぶのと同時にCSVファイルを共有していただければ、メタアナリシスを実行します。")
            DialogStateManager.set_dialog_state(context, "WAITING_FILE")
        
        context_manager_instance.save_context(thread_ts, context, channel_id)

    def handle_message(self, event, client, run_meta_analysis_wrapper_func, check_analysis_job_func):
        try:
            logger.info(f"=== RAW MESSAGE EVENT RECEIVED ===\n{json.dumps(event, indent=2, ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"Error logging raw event: {e}. Event: {event}")
        logger.info(f"=== MESSAGE EVENT START ===")
        subtype = event.get("subtype")
        
        # イベントデータの構造に応じてユーザーIDとテキスト、bot_idフィールドを取得
        # message_changed イベントの場合、ネストした message オブジェクトを参照
        if subtype == "message_changed":
            message_data = event.get("message", {})
            # message_changed の場合、トップレベルの event に channel がある
            channel_id = event.get("channel")
        else:
            message_data = event
            channel_id = event.get("channel")

        thread_ts = message_data.get("thread_ts")
        user_id = message_data.get("user")
        text = message_data.get("text", "")
        # bot_idフィールドは、Slack APIのイベント構造において、メッセージを投稿したのがBotである場合に設定される
        # アプリケーションが自身の投稿を識別するために使う
        bot_id_field_in_event = message_data.get("bot_id") 
        event_ts = event.get("ts") # イベント自体のタイムスタンプ (重複処理判定用)

        # --- ガード条件の強化 ---
        # 1. bot_id_field_in_event が存在する場合 (多くの場合Botからのメッセージ)
        if bot_id_field_in_event:
            logger.info(f"Ignoring message due to 'bot_id' field ('{bot_id_field_in_event}') present in event. Event: {event}")
            return
        
        # 2. スレッド情報がない場合 (スレッド外のメッセージは基本的に無視)
        if not thread_ts:
            logger.info(f"Ignoring message as it's not in a thread. Event: {event}")
            return

        # 3. 送信者(user_id)がBot自身(self.bot_user_id)である場合
        # self.bot_user_id が None の場合はこのチェックをスキップ (auth_test失敗時など)
        if self.bot_user_id and user_id == self.bot_user_id:
            logger.info(f"Ignoring message from self (bot_user_id: {self.bot_user_id}, event user_id: {user_id}). Event: {event}")
            return
            
        # --- ここまでガード条件 ---

        context = self.context_manager.get_context(thread_ts, channel_id)
        if not context:
            # スレッドIDが存在するがコンテキストがない場合、新規作成する
            if thread_ts: 
                logger.info(f"No context found for thread {thread_ts} in channel {channel_id}. Creating new context.")
                context = {
                    "thread_active": True, 
                    "thread_ts": thread_ts, 
                    "channel_id": channel_id,
                    "dialog_state": {"type": "waiting_for_file", "state": "initial"}, # app_mention と同じ初期状態
                    "processed_event_ts": [], # 新規作成時は空リスト
                    "processed_file_ids": [], # ファイルIDの重複チェック用リスト
                    "history": [] # 会話履歴を初期化
                }
                # self.context_manager.save_context(thread_ts, context, channel_id) # すぐに保存するかは検討
            else:
                # スレッドIDすらない場合は、本当に処理できないので無視
                logger.warning(f"No context and no thread_ts. Ignoring message. User: {user_id}, Text: '{text}'")
                return
        
        processed_event_ts_list = context.get("processed_event_ts", [])
        if event_ts in processed_event_ts_list:
            logger.info(f"Ignoring already processed event_ts: {event_ts}. User: {user_id}, Text: '{text}'")
            return
        
        logger.info(f"Processing user message in thread {thread_ts}. User: {user_id}, Text: '{text}'")

        event_files = event.get("files", []) # 通常のメッセージイベントの場合
        if subtype == "message_changed" and "files" not in message_data: # message_changedでfilesがトップレベルにある場合も考慮
             event_files = event.get("files", [])


        csv_files = [f for f in event_files if f.get("name", "").lower().endswith(".csv")]
        current_dialog_state = context.get("dialog_state", {})
        current_dialog_type = current_dialog_state.get("type")

        # messageイベントでは、app_mentionでファイルが処理されることを期待し、ファイル処理は行わない。
        # ただし、ユーザーがファイル処理中やパラメータ収集中に新しいファイルを投げた場合は拒否メッセージを出す。
        if csv_files:
            if current_dialog_type in ["processing_file", "analysis_preference"]:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text="現在別のファイルを処理中です。処理完了後に再度お試しいただくか、別スレッドでご相談ください。"
                )
                # このイベントは処理済みとしてマーク
                processed_event_ts_list.append(event_ts)
                context["processed_event_ts"] = processed_event_ts_list
                self.context_manager.save_context(thread_ts, context, channel_id)
                return
            else:
                # waiting_for_file の場合など、app_mention で処理されるはずなのでここでは何もしない
                logger.info(f"CSV file found in message event (type: {current_dialog_type}), but deferring to app_mention or ignoring. Event ts: {event_ts}")
                # このイベントは処理済みとしてマーク (応答はしない)
                processed_event_ts_list.append(event_ts)
                context["processed_event_ts"] = processed_event_ts_list
                self.context_manager.save_context(thread_ts, context, channel_id)
                return

        dialog_state = context.get("dialog_state", {}) # 再取得
        dialog_type = dialog_state.get("type") # 再取得
        
        # Botが最後にメッセージを送信した時刻を記録・取得
        last_bot_message_details = context.get("last_bot_message", {})
        last_bot_message_ts_numeric = last_bot_message_details.get("timestamp", 0)

        if dialog_type == "analysis_preference":
            text_to_pass = text 
            is_mention_only = False
            if self.bot_user_id: 
                bot_mention_str = f"<@{self.bot_user_id}>"
                cleaned_text = text.strip()
                if cleaned_text == bot_mention_str:
                    is_mention_only = True
                    logger.info(f"Original text was just a mention to the bot: '{text}'.")
                    
            # 謎のメンションイベント対策
            # メンションのみのイベントは基本的に無視する（ゴーストメンション対策）
            if is_mention_only:
                logger.info(f"Ignoring mention-only event. Event ts: {event_ts}")
                processed_event_ts_list.append(event_ts) # スキップするイベントも記録
                context["processed_event_ts"] = processed_event_ts_list
                self.context_manager.save_context(thread_ts, context, channel_id)
                return # 処理をスキップ
            
            logger.info(f"Calling handle_analysis_preference_dialog with text_to_pass: '{text_to_pass}' (original text: '{text}')")
            self.parameter_collector.handle_analysis_preference_dialog(text_to_pass, thread_ts, channel_id, client, context, run_meta_analysis_wrapper_func, check_analysis_job_func)
        
        elif dialog_type == "waiting_for_file":
            response = client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="CSVファイルをこのスレッドに共有していただければ、メタアナリシスを開始します。")
            context["last_bot_message"] = {"ts": response.get("ts"), "timestamp": time.time(), "content": "CSVファイルをこのスレッドに共有していただければ、メタアナリシスを開始します。"}
        elif dialog_type == "processing_file":
            should_process_as_params = self.analysis_executor.check_processing_status(thread_ts, channel_id, client, context, text)
            if should_process_as_params:
                self.parameter_collector.handle_analysis_preference_dialog(text, thread_ts, channel_id, client, context, run_meta_analysis_wrapper_func, check_analysis_job_func)
        elif dialog_type == "post_analysis":
            self._handle_general_question(text, thread_ts, channel_id, client, context)
        else:
            logger.warning(f"Unknown dialog type: {dialog_type} for text: '{text}'")
            self._handle_general_question(text, thread_ts, channel_id, client, context)

        processed_event_ts_list.append(event_ts)
        context["processed_event_ts"] = processed_event_ts_list
        self.context_manager.save_context(thread_ts, context, channel_id)

    def handle_file_shared(self, event, client):
        logger.info("File shared event received, but handling is delegated to message event or app_mention")
        pass

    def _handle_general_question(self, text, thread_ts, channel_id, client, context):
        analysis_state = context.get("analysis_state", {})
        response = "ご質問ありがとうございます。具体的な内容をお知らせください。"
        
        processing_message_ts = None
        if "result" in analysis_state:
            result = analysis_state["result"]
            preferences = analysis_state.get("preferences", {})
            try:
                processing_response = client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="AI解釈を生成中です。少々お待ちください...")
                processing_message_ts = processing_response.get("ts")
                
                interpretation = interpret_meta_analysis_results(result) if preferences.get("analysis_type") != "regression" else interpret_meta_regression_results(result)
                response = f"解釈します：\n\n{interpretation}" if interpretation else "AI解釈を生成できませんでした。"
                
                if processing_message_ts:
                    try: client.chat_delete(channel=channel_id, ts=processing_message_ts)
                    except Exception as e: logger.error(f"Failed to delete processing message: {e}")
            except Exception as e:
                logger.error(f"Error during general question interpretation: {e}")
                response = "質問応答中にエラーが発生しました。"
                if processing_message_ts:
                    try: client.chat_delete(channel=channel_id, ts=processing_message_ts)
                    except Exception as e_del: logger.error(f"Failed to delete processing message after error: {e_del}")
        
        bot_response_message = client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=response)
        # update_historyを呼び出す前に、botの応答を整形
        if bot_response_message.get("ok"):
            self.context_manager.update_history(
                thread_id=thread_ts,
                user_message_content=text, # ユーザーのメッセージ内容
                bot_response_content=response, # Botの応答内容
                channel_id=channel_id,
                user_message_ts=event_ts, # ユーザーメッセージのts
                bot_response_ts=bot_response_message.get("ts") # Botメッセージのts
            )
        else:
            logger.error(f"Failed to send bot response, not updating history. Error: {bot_response_message.get('error')}")

    def _record_bot_question_to_history(self, thread_ts: str, channel_id: str, question_text: str, question_ts: str, context: dict):
        """Botの質問を会話履歴に記録するヘルパー関数"""
        # ユーザーメッセージは空として記録（Botの質問なので）
        self.context_manager.update_history(
            thread_id=thread_ts,
            user_message_content=None, # Botの質問なのでユーザーメッセージはなし
            bot_response_content=question_text,
            channel_id=channel_id,
            user_message_ts=None, # Botの質問なのでユーザーメッセージtsはなし
            bot_response_ts=question_ts
        )
        # last_bot_messageも更新
        context["last_bot_message"] = {
            "ts": question_ts,
            "timestamp": time.time(),
            "content": question_text
        }
        logger.info(f"Recorded bot question to history and updated last_bot_message: ts={question_ts}")
        # self.context_manager.save_context(thread_ts, context, channel_id) # update_history内で保存されるので不要な場合あり

    def handle_analysis_preference_dialog_wrapper(self, text: str, thread_ts: str, channel_id: str, client, context: dict, run_meta_analysis_wrapper_func, check_analysis_job_func):
        """
        ParameterCollector.handle_analysis_preference_dialogのラッパー。
        Botが質問を送信した際に会話履歴を更新する。
        """
        # ParameterCollectorのメソッドを呼び出す前に、もしBotが質問を生成して送信する場合、
        # その質問を会話履歴に記録する必要がある。
        # ParameterCollector内で質問が生成され送信されるので、ParameterCollector側で対応するか、
        # ここでParameterCollectorの戻り値を見て判断する。
        # 今回はParameterCollectorの _update_collected_params_and_get_next_question が質問を返すので、
        # それが送信された後に記録する。

        # ParameterCollectorの呼び出し
        self.parameter_collector.handle_analysis_preference_dialog(
            text, thread_ts, channel_id, client, context, 
            run_meta_analysis_wrapper_func, check_analysis_job_func
        )

        # ParameterCollectorが質問を送信した場合、その質問を履歴に記録
        # last_bot_message が ParameterCollector によって更新されているはず
        last_bot_msg_details = context.get("last_bot_message")
        if last_bot_msg_details and last_bot_msg_details.get("content") and last_bot_msg_details.get("ts"):
            # ParameterCollectorが送信した質問が last_question と一致するか、
            # または dialog_state が collecting_params のままであれば、それがBotの最新の質問
            dialog_state = context.get("dialog_state", {})
            if dialog_state.get("type") == "analysis_preference" and dialog_state.get("state") == "collecting_params":
                last_question_from_history = context.get("question_history", {}).get("last_question")
                # last_bot_message の内容が last_question と一致する場合、または last_question が None (初回) の場合
                if last_bot_msg_details["content"] == last_question_from_history or not last_question_from_history:
                    # この last_bot_message が ParameterCollector によって送信された質問であると仮定
                    # ただし、この方法ではユーザーの連続投稿と区別が難しい場合がある
                    # より確実なのは、ParameterCollectorが質問を送信する際に明示的に履歴記録をトリガーすること
                    # ここでは、ParameterCollectorがlast_bot_messageを更新したことを信頼する
                    logger.info(f"Assuming last_bot_message (ts: {last_bot_msg_details['ts']}) was a question from ParameterCollector. It should have been recorded there.")
                    # ParameterCollector内で履歴記録とlast_bot_message更新が行われるように修正するのが望ましい
                    # 現状では、ParameterCollectorが送信したメッセージのtsを特定し、ここで記録する
                    # しかし、ParameterCollector.handle_analysis_preference_dialog は直接 client.chat_postMessage を呼ぶ
                    # その戻り値のtsをここで取得するのは難しい。
                    # → ParameterCollector内でlast_bot_messageを更新し、それを元にここで履歴を記録するアプローチは複雑。
                    # → MessageHandlerのhandle_message内で、ParameterCollector呼び出し後に、
                    #   contextのlast_bot_messageが更新されていたら、それを履歴に記録する。
                    #   ただし、ユーザーのメッセージとBotの質問が交互に来ることを前提とする。

                    # MessageHandlerのメインループで、ParameterCollector呼び出し後に、
                    # context.last_bot_message が更新されていれば、それを履歴に記録するロジックを追加する。
                    # ここでは何もしない。
                    pass


    # handle_message 内で ParameterCollector を呼び出す部分を修正
    def handle_message(self, event, client, run_meta_analysis_wrapper_func, check_analysis_job_func):
        try:
            logger.info(f"=== RAW MESSAGE EVENT RECEIVED ===\n{json.dumps(event, indent=2, ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"Error logging raw event: {e}. Event: {event}")
        logger.info(f"=== MESSAGE EVENT START ===")
        subtype = event.get("subtype")
        
        if subtype == "message_changed":
            message_data = event.get("message", {})
            channel_id = event.get("channel")
        else:
            message_data = event
            channel_id = event.get("channel")

        thread_ts = message_data.get("thread_ts")
        user_id = message_data.get("user")
        text = message_data.get("text", "")
        bot_id_field_in_event = message_data.get("bot_id") 
        event_ts = event.get("ts") 

        if bot_id_field_in_event:
            logger.info(f"Ignoring message due to 'bot_id' field ('{bot_id_field_in_event}') present in event. Event: {event}")
            return
        
        if not thread_ts:
            logger.info(f"Ignoring message as it's not in a thread. Event: {event}")
            return

        if self.bot_user_id and user_id == self.bot_user_id:
            logger.info(f"Ignoring message from self (bot_user_id: {self.bot_user_id}, event user_id: {user_id}). Event: {event}")
            return
            
        context = self.context_manager.get_context(thread_ts, channel_id)
        if not context:
            if thread_ts: 
                logger.info(f"No context found for thread {thread_ts} in channel {channel_id}. Creating new context.")
                context = {
                    "thread_active": True, 
                    "thread_ts": thread_ts, 
                    "channel_id": channel_id,
                    "dialog_state": {"type": "waiting_for_file", "state": "initial"},
                    "processed_event_ts": [],
                    "processed_file_ids": [], # ファイルIDの重複チェック用リスト
                    "history": [] # 会話履歴を初期化
                }
            else:
                logger.warning(f"No context and no thread_ts. Ignoring message. User: {user_id}, Text: '{text}'")
                return
        
        processed_event_ts_list = context.get("processed_event_ts", [])
        if event_ts in processed_event_ts_list:
            logger.info(f"Ignoring already processed event_ts: {event_ts}. User: {user_id}, Text: '{text}'")
            return
        
        logger.info(f"Processing user message in thread {thread_ts}. User: {user_id}, Text: '{text}'")
        
        # ユーザーメッセージを履歴に記録
        # この時点ではBotの応答はまだないので、user_message_content のみで記録するか、
        # Botの応答後にまとめて記録する。後者の方が自然。

        event_files = event.get("files", [])
        if subtype == "message_changed" and "files" not in message_data:
             event_files = event.get("files", [])

        csv_files = [f for f in event_files if f.get("name", "").lower().endswith(".csv")]
        current_dialog_type = context.get("dialog_state", {}).get("type")

        bot_response_text_for_history = None # Botの応答を格納する変数
        bot_response_ts_for_history = None

        if csv_files and current_dialog_type == "waiting_for_file":
            file_obj = csv_files[0]
            file_id = file_obj.get("id") # ファイルIDを取得
            if file_id and file_id in context.get("processed_file_ids", []):
                logger.info(f"File {file_id} already processed in message handler (duplicate check), skipping. Event ts: {event_ts}")
                # このイベントは処理済みとしてマーク (応答はしない)
                bot_response_text_for_history = None 
                bot_response_ts_for_history = None
            else:
                bot_response_text_for_history = f"CSVファイル「{file_obj.get('name')}」を受け取りました。分析を開始します。"
                response = client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=bot_response_text_for_history)
                bot_response_ts_for_history = response.get("ts")
                self.csv_processor.process_csv_file(file_obj, thread_ts, channel_id, client, context)
                if file_id:
                    context.setdefault("processed_file_ids", []).append(file_id)
            # CSV処理後は一度returnして、ユーザーの次のアクションを待つ
            # ただし、このロジックは handle_message の最初のifブロックと重複しているため、
            # 実際にはこのelseブロック内のcsv_files処理はあまり実行されない可能性がある。
            # 最初のifブロックでreturnするため。
        else:
            dialog_state = context.get("dialog_state", {})
            dialog_type = dialog_state.get("type")
            
            last_bot_message_details = context.get("last_bot_message", {})
            
            if dialog_type == "analysis_preference":
                text_to_pass = text 
                is_mention_only = False
                if self.bot_user_id: 
                    bot_mention_str = f"<@{self.bot_user_id}>"
                    cleaned_text = text.strip()
                    if cleaned_text == bot_mention_str:
                        is_mention_only = True
                        logger.info(f"Original text was just a mention to the bot: '{text}'.")
                        
                if is_mention_only:
                    logger.info(f"Ignoring mention-only event. Event ts: {event_ts}")
                    # この場合、Botは応答しないので履歴にはユーザーメッセージのみ（あるいは記録しない）
                else:
                    logger.info(f"Calling handle_analysis_preference_dialog with text_to_pass: '{text_to_pass}' (original text: '{text}')")
                    # ParameterCollectorが応答を返す。その応答を履歴に記録する必要がある。
                    # ParameterCollector内で client.chat_postMessage が呼ばれる。
                    # その結果(tsとtext)をどうやってここまで持ってくるか？
                    # → ParameterCollectorが応答メッセージとtsを返すようにするか、
                    #   あるいは、ParameterCollector内で直接履歴を更新する。
                    #   後者の方がシンプルかもしれないが、責務分担の観点からは前者。
                    #   一旦、ParameterCollectorがlast_bot_messageを更新することを期待する。
                    self.parameter_collector.handle_analysis_preference_dialog(text_to_pass, thread_ts, channel_id, client, context, run_meta_analysis_wrapper_func, check_analysis_job_func)
                    # ParameterCollectorがlast_bot_messageを更新したはずなので、それを取得
                    updated_last_bot_msg = context.get("last_bot_message", {})
                    bot_response_text_for_history = updated_last_bot_msg.get("content")
                    bot_response_ts_for_history = updated_last_bot_msg.get("ts")

            elif dialog_type == "waiting_for_file":
                bot_response_text_for_history = "CSVファイルをこのスレッドに共有していただければ、メタアナリシスを開始します。"
                response = client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=bot_response_text_for_history)
                bot_response_ts_for_history = response.get("ts")
                context["last_bot_message"] = {"ts": bot_response_ts_for_history, "timestamp": time.time(), "content": bot_response_text_for_history}
            
            elif dialog_type == "processing_file":
                should_process_as_params = self.analysis_executor.check_processing_status(thread_ts, channel_id, client, context, text)
                if should_process_as_params:
                    self.parameter_collector.handle_analysis_preference_dialog(text, thread_ts, channel_id, client, context, run_meta_analysis_wrapper_func, check_analysis_job_func)
                    updated_last_bot_msg = context.get("last_bot_message", {})
                    bot_response_text_for_history = updated_last_bot_msg.get("content")
                    bot_response_ts_for_history = updated_last_bot_msg.get("ts")
                # else の場合、check_processing_status内でメッセージが送信される。そのメッセージを履歴に。
                # check_processing_status がメッセージ内容とtsを返すようにするか、内部で履歴更新。
                # → ここでは、Botが応答した場合、その内容が last_bot_message に入ることを期待。
                else:
                    # check_processing_status がメッセージを投稿した場合、context.last_bot_message が更新されているはず
                    updated_last_bot_msg = context.get("last_bot_message", {})
                    bot_response_text_for_history = updated_last_bot_msg.get("content")
                    bot_response_ts_for_history = updated_last_bot_msg.get("ts")


            elif dialog_type == "post_analysis":
                # _handle_general_question がメッセージを投稿し、履歴も更新する
                self._handle_general_question(text, thread_ts, channel_id, client, context)
                # _handle_general_question内で履歴更新されるので、ここでは何もしない
                bot_response_text_for_history = None # 既に記録済み
            else:
                logger.warning(f"Unknown dialog type: {dialog_type} for text: '{text}'")
                # _handle_general_question がメッセージを投稿し、履歴も更新する
                self._handle_general_question(text, thread_ts, channel_id, client, context)
                bot_response_text_for_history = None # 既に記録済み

        # ユーザーメッセージと（あれば）Botの応答を履歴に記録
        if not (dialog_type == "post_analysis" or (dialog_type == "unknown" and bot_response_text_for_history is None)): # _handle_general_questionが呼ばれるケースは除く
            if text or bot_response_text_for_history: # どちらかがあれば記録
                 self.context_manager.update_history(
                    thread_id=thread_ts,
                    user_message_content=text if text else None,
                    bot_response_content=bot_response_text_for_history if bot_response_text_for_history else None,
                    channel_id=channel_id,
                    user_message_ts=event_ts if text else None,
                    bot_response_ts=bot_response_ts_for_history if bot_response_text_for_history else None
                )

        processed_event_ts_list.append(event_ts)
        context["processed_event_ts"] = processed_event_ts_list
        self.context_manager.save_context(thread_ts, context, channel_id)

    def handle_file_shared(self, event, client):
        logger.info("File shared event received, but handling is delegated to message event or app_mention")
        pass
