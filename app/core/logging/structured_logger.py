import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

class StructuredJSONLogger:
    def __init__(self, log_name: str, logs_directory: str = "app/logs") -> None:
        self.log_name = log_name
        self.logs_directory = Path(logs_directory)
        self.logs_directory.mkdir(exist_ok=True)
        self._current_file: Optional[Path] = None
        self._file_handle: Any = None

    def _get_file_handle(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.logs_directory / f"{today}_{self.log_name}.jsonl"
        
        if self._current_file != log_file:
            if self._file_handle:
                self._file_handle.close()
            self._current_file = log_file
            self._file_handle = open(log_file, "a", encoding="utf-8", buffering=1) # Line buffered
        return self._file_handle

    def log(self, data: dict[str, Any]) -> None:
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

        try:
            f = self._get_file_handle()
            json.dump(data, f, ensure_ascii=False)
            f.write("\n")
        except IOError as exc:
            logging.error(f"Failed to write to JSON log: {exc}")

    def log_notification_sent(
        self,
        apartment_id: str,
        source_name: str,
        chat_id: str,
        title: str,
        success: bool,
        error_msg: Optional[str] = None,
    ) -> None:
        self.log(
            {
                "event": "notification_sent",
                "apartment_id": apartment_id,
                "source_name": source_name,
                "chat_id": chat_id,
                "title": title,
                "success": success,
                "error": error_msg,
            }
        )

    def log_scrape_run_finished(
        self,
        source_slug: str,
        source_name: str,
        duration_seconds: float,
        listings_found: int,
        listings_new: int,
        error: Optional[str] = None,
    ) -> None:
        self.log(
            {
                "event": "scrape_run_finished",
                "source_slug": source_slug,
                "source_name": source_name,
                "duration_seconds": round(duration_seconds, 2),
                "listings_found": listings_found,
                "listings_new": listings_new,
                "success": error is None,
                "error": error,
            }
        )

    def log_filter_updated(
        self,
        chat_id: str,
        changed_fields: dict[str, tuple[Any, Any]],
    ) -> None:
        self.log(
            {
                "event": "filter_updated",
                "chat_id": chat_id,
                "changes": {
                    field: {
                        "old": old_val,
                        "new": new_val,
                    }
                    for field, (old_val, new_val) in changed_fields.items()
                },
            }
        )


notification_logger = StructuredJSONLogger("notifications")
scrape_logger = StructuredJSONLogger("scrape_runs")

def setup_daily_logging(
    logs_directory: str = "app/logs",
    level: str = "INFO",
) -> logging.Logger:
    logs_path = Path(logs_directory)
    logs_path.mkdir(exist_ok=True)

    logger = logging.getLogger() 
    logger.setLevel(level)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    timestamp = datetime.now().strftime("%d_%m_%Y")
    log_file = logs_path / f"{timestamp}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger