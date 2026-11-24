"""
ai/model_manager.py
===================
Pausable and Resumable Model Downloader for Troko-Desk.
Downloads Llama 3.2 3B GGUF (~2.02 GB) into models/ with HTTP Range headers
so downloads can be safely interrupted and resumed without losing progress.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

import httpx

from config.settings import settings
from core.event_bus import bus

logger = logging.getLogger(__name__)


class ModelDownloadManager:
    """
    Manages local model assets for Troko (Llama 3.2 3B GGUF, Kokoro, etc.).
    Supports pausing, resuming and progress callbacks.
    """

    def __init__(self) -> None:
        self.dest_path = Path(settings.llama_model_path)
        self.url = settings.llama_download_url
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self.total_bytes: int = 0
        self.downloaded_bytes: int = 0
        self.is_downloading: bool = False

    def is_model_ready(self) -> bool:
        """Returns True if the GGUF model exists and has reasonable size (>100MB)."""
        return self.dest_path.exists() and self.dest_path.stat().st_size > 100 * 1024 * 1024

    def start_download(self, on_progress: Optional[Callable[[float, int, int], None]] = None) -> None:
        if self.is_model_ready():
            logger.info("Model already downloaded at %s", self.dest_path)
            return

        if self._thread and self._thread.is_alive():
            logger.warning("Download already in progress")
            return

        self._pause_event.clear()
        self._stop_event.clear()
        self.is_downloading = True

        self._thread = threading.Thread(
            target=self._download_worker,
            args=(on_progress,),
            daemon=True,
            name="model-downloader",
        )
        self._thread.start()

    def pause_download(self) -> None:
        self._pause_event.set()
        self.is_downloading = False
        logger.info("Model download paused")

    def resume_download(self) -> None:
        self._pause_event.clear()
        self.is_downloading = True
        logger.info("Model download resumed")

    def cancel_download(self) -> None:
        self._stop_event.set()
        self.is_downloading = False
        logger.info("Model download cancelled")

    def _download_worker(self, on_progress: Optional[Callable[[float, int, int], None]]) -> None:
        self.dest_path.parent.mkdir(parents=True, exist_ok=True)
        part_path = self.dest_path.with_suffix(".gguf.part")

        # Resume support: check existing bytes
        initial_bytes = part_path.stat().st_size if part_path.exists() else 0
        self.downloaded_bytes = initial_bytes

        headers = {}
        if initial_bytes > 0:
            headers["Range"] = f"bytes={initial_bytes}-"
            logger.info("Resuming download from byte offset %d", initial_bytes)

        try:
            with httpx.stream("GET", self.url, headers=headers, follow_redirects=True, timeout=60.0) as resp:
                if resp.status_code not in (200, 206):
                    logger.error("Download failed with HTTP %d", resp.status_code)
                    self.is_downloading = False
                    return

                content_len = resp.headers.get("content-length")
                if content_len:
                    self.total_bytes = initial_bytes + int(content_len)
                else:
                    self.total_bytes = 2020 * 1024 * 1024  # ~2.02 GB fallback estimate

                mode = "ab" if initial_bytes > 0 else "wb"
                with open(part_path, mode) as f:
                    for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                        if self._stop_event.is_set():
                            break

                        while self._pause_event.is_set():
                            threading.Event().wait(0.5)
                            if self._stop_event.is_set():
                                break

                        if chunk:
                            f.write(chunk)
                            self.downloaded_bytes += len(chunk)

                            pct = (self.downloaded_bytes / self.total_bytes) * 100 if self.total_bytes else 0.0
                            if on_progress:
                                on_progress(pct, self.downloaded_bytes, self.total_bytes)

            if not self._stop_event.is_set() and part_path.exists():
                part_path.rename(self.dest_path)
                logger.info("Model download complete: %s", self.dest_path)
                bus.emit("on_model_download_done", path=str(self.dest_path))

        except Exception as exc:
            logger.exception("Error during model download: %s", exc)
        finally:
            self.is_downloading = False


model_manager = ModelDownloadManager()
