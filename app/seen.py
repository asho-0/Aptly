_notified: set[str] = set()
_processed: set[str] = set()


def is_new(uid: str) -> bool:
    return uid not in _notified and uid not in _processed


def is_already_notified(uid: str) -> bool:
    return uid in _notified


def mark_notified(uid: str) -> None:
    _notified.add(uid)
    _processed.add(uid)


def mark_processed(uid: str) -> None:
    _processed.add(uid)


def clear_processed() -> int:
    count = len(_processed) - len(_notified)
    _processed.clear()
    _processed.update(_notified)
    return max(0, count)


def reset_notified() -> int:
    count = len(_notified)
    _notified.clear()
    _processed.clear()
    return count


def mark_notified_batch(uids: list[str]) -> None:
    _notified.update(uids)
    _processed.update(uids)


def warm(uids: list[str]) -> int:
    before = len(_notified)
    _notified.update(uids)
    _processed.update(uids)
    return len(_notified) - before


def count() -> int:
    return len(_notified)
