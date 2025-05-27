"""
非同期処理モジュール

Slackの3秒ルールに対応するための非同期処理機能を提供します。
"""

import os
import asyncio
import threading
import logging
import time
import json
from typing import Dict, Any, Callable, Awaitable, Optional, Union, List
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class AsyncJobManager:
    """非同期ジョブマネージャー"""
    
    def __init__(self, max_workers: int = 5):
        """
        初期化
        
        Args:
            max_workers: 同時実行可能なワーカー数
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.jobs = {}
        self.lock = threading.Lock()
    
    def submit_job(self, job_id: str, func: Callable, *args, **kwargs) -> str:
        """
        ジョブを登録して非同期実行する
        
        Args:
            job_id: ジョブID（Noneの場合は自動生成）
            func: 実行する関数
            *args, **kwargs: 関数に渡す引数
            
        Returns:
            str: ジョブID
        """
        if job_id is None:
            job_id = f"job_{int(time.time())}_{id(func)}"
        
        with self.lock:
            self.jobs[job_id] = {
                "status": "pending",
                "submitted_at": time.time(),
                "result": None,
                "error": None
            }
        
        future = self.executor.submit(self._run_job, job_id, func, *args, **kwargs)
        future.add_done_callback(lambda f: self._handle_job_completion(job_id, f))
        
        return job_id
    
    def _run_job(self, job_id: str, func: Callable, *args, **kwargs) -> Any:
        """
        ジョブを実行する
        
        Args:
            job_id: ジョブID
            func: 実行する関数
            *args, **kwargs: 関数に渡す引数
            
        Returns:
            Any: 関数の戻り値
        """
        with self.lock:
            self.jobs[job_id]["status"] = "running"
            self.jobs[job_id]["started_at"] = time.time()
        
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            logger.exception(f"ジョブ {job_id} の実行中にエラーが発生しました: {e}")
            raise
    
    def _handle_job_completion(self, job_id: str, future) -> None:
        """
        ジョブ完了時の処理
        
        Args:
            job_id: ジョブID
            future: Future オブジェクト
        """
        with self.lock:
            try:
                result = future.result()
                self.jobs[job_id]["status"] = "completed"
                self.jobs[job_id]["result"] = result
            except Exception as e:
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["error"] = str(e)
            
            self.jobs[job_id]["completed_at"] = time.time()
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        ジョブのステータスを取得する
        
        Args:
            job_id: ジョブID
            
        Returns:
            Dict: ジョブのステータス情報
        """
        with self.lock:
            if job_id not in self.jobs:
                return {"status": "not_found"}
            
            return self.jobs[job_id].copy()
    
    def wait_for_job(self, job_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        ジョブの完了を待機する
        
        Args:
            job_id: ジョブID
            timeout: タイムアウト（秒）
            
        Returns:
            Dict: ジョブのステータス情報
        """
        start_time = time.time()
        
        while True:
            status = self.get_job_status(job_id)
            
            if status["status"] in ["completed", "failed"]:
                return status
            
            if timeout is not None and time.time() - start_time > timeout:
                return {"status": "timeout", "job_id": job_id}
            
            time.sleep(0.1)
    
    def cancel_job(self, job_id: str) -> bool:
        """
        ジョブをキャンセルする
        
        Args:
            job_id: ジョブID
            
        Returns:
            bool: キャンセルに成功したかどうか
        """
        with self.lock:
            if job_id not in self.jobs:
                return False
            
            if self.jobs[job_id]["status"] in ["completed", "failed"]:
                return False
            
            self.jobs[job_id]["status"] = "cancelled"
            return True
    
    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """
        古いジョブを削除する
        
        Args:
            max_age_hours: 保持する最大時間（時間）
            
        Returns:
            int: 削除されたジョブ数
        """
        max_age_seconds = max_age_hours * 3600
        current_time = time.time()
        jobs_to_remove = []
        
        with self.lock:
            for job_id, job_info in self.jobs.items():
                if job_info["status"] in ["completed", "failed", "cancelled"]:
                    job_time = job_info.get("completed_at", job_info.get("submitted_at", 0))
                    if current_time - job_time > max_age_seconds:
                        jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self.jobs[job_id]
        
        return len(jobs_to_remove)


class AsyncAnalysisRunner:
    """メタ解析の非同期実行クラス"""
    
    def __init__(self):
        """初期化"""
        self.job_manager = AsyncJobManager()
    
    def run_analysis_async(self, analysis_func: Callable, analysis_params: Dict[str, Any], 
                          callback_url: Optional[str] = None) -> str:
        """
        メタ解析を非同期で実行する
        
        Args:
            analysis_func: 分析関数
            analysis_params: 分析パラメータ
            callback_url: コールバックURL（オプション）
            
        Returns:
            str: ジョブID
        """
        job_id = self.job_manager.submit_job(
            None, 
            self._run_analysis_with_callback, 
            analysis_func, 
            analysis_params, 
            callback_url
        )
        
        return job_id
    
    def _run_analysis_with_callback(self, analysis_func: Callable, 
                                   analysis_params: Dict[str, Any], 
                                   callback_url: Optional[str] = None) -> Dict[str, Any]:
        """
        コールバック付きで分析を実行する
        
        Args:
            analysis_func: 分析関数
            analysis_params: 分析パラメータ
            callback_url: コールバックURL（オプション）
            
        Returns:
            Dict: 分析結果
        """
        try:
            result = analysis_func(**analysis_params)
            
            if callback_url:
                self._send_callback(callback_url, {
                    "status": "completed",
                    "result": result
                })
            
            return result
        except Exception as e:
            logger.exception(f"分析実行中にエラーが発生しました: {e}")
            
            if callback_url:
                self._send_callback(callback_url, {
                    "status": "failed",
                    "error": str(e)
                })
            
            raise
    
    def _send_callback(self, url: str, data: Dict[str, Any]) -> None:
        """
        コールバックを送信する
        
        Args:
            url: コールバックURL
            data: 送信データ
        """
        import requests
        
        try:
            requests.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"}
            )
        except Exception as e:
            logger.error(f"コールバック送信中にエラーが発生しました: {e}")
    
    def get_analysis_status(self, job_id: str) -> Dict[str, Any]:
        """
        分析ステータスを取得する
        
        Args:
            job_id: ジョブID
            
        Returns:
            Dict: 分析ステータス
        """
        return self.job_manager.get_job_status(job_id)
    
    def wait_for_analysis(self, job_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        分析完了を待機する
        
        Args:
            job_id: ジョブID
            timeout: タイムアウト（秒）
            
        Returns:
            Dict: 分析結果
        """
        return self.job_manager.wait_for_job(job_id, timeout)


if __name__ == "__main__":
    def test_function(sleep_time, fail=False):
        """テスト関数"""
        time.sleep(sleep_time)
        if fail:
            raise ValueError("テストエラー")
        return {"result": f"Slept for {sleep_time} seconds"}
    
    job_manager = AsyncJobManager()
    
    job_id1 = job_manager.submit_job(None, test_function, 2)
    print(f"Job 1 submitted with ID: {job_id1}")
    
    job_id2 = job_manager.submit_job(None, test_function, 1, fail=True)
    print(f"Job 2 submitted with ID: {job_id2}")
    
    result1 = job_manager.wait_for_job(job_id1)
    print(f"Job 1 result: {result1}")
    
    result2 = job_manager.wait_for_job(job_id2)
    print(f"Job 2 result: {result2}")
