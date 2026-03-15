import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class StructuredJSONLogger:
    def __init__(self, log_name: str, logs_directory: str = "logs") -> None:
        self.log_name = log_name
        self.logs_directory = Path(logs_directory)
        self.logs_directory.mkdir(exist_ok=True)

    def log(self, data: dict[str, Any]) -> None:
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.logs_directory / f"{today}_{self.log_name}.jsonl"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
                f.write("\n")
        except IOError as exc:
            logging.error(f"Failed to write to {log_file}: {exc}")

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
    log_name: str = "notifier",
    logs_directory: str = "logs",
    level: str = "INFO",
) -> logging.Logger:
    import logging.handlers

    logs_path = Path(logs_directory)
    logs_path.mkdir(exist_ok=True)

    logger = logging.getLogger(log_name)
    logger.setLevel(level)

    # Format
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_file = logs_path / f"{log_name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        mode="a",
        maxBytes=50 * 1024 * 1024,  # 50 MB
        backupCount=7,  # Keep 7 backups
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
