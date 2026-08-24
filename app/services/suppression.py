from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Set, Tuple


class SuppressionEngine:
    """
    Suppression Engine to prevent spam, duplicate proactive triggers,
    and repeated identical bodies per merchant or conversation.
    """

    def __init__(self):
        self._lock = threading.RLock()
        # suppression_key -> last_sent_iso
        self._suppression_keys: Dict[str, str] = {}
        # (merchant_id, body_hash) -> last_sent_iso
        self._sent_bodies: Dict[Tuple[str, str], str] = {}
        # (conversation_id, body_hash)
        self._conversation_bodies: Set[Tuple[str, str]] = set()

    def is_suppressed(
        self,
        suppression_key: Optional[str],
        merchant_id: str,
        body: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        with self._lock:
            if suppression_key and suppression_key in self._suppression_keys:
                return True, f"suppression_key '{suppression_key}' already triggered"

            if body:
                b_hash = hashlib.sha256(body.strip().encode("utf-8")).hexdigest()
                if (merchant_id, b_hash) in self._sent_bodies:
                    return True, "duplicate body already sent to merchant"

                if conversation_id and (conversation_id, b_hash) in self._conversation_bodies:
                    return True, "duplicate body already sent in conversation"

            return False, "ok"

    def record_sent(
        self,
        suppression_key: Optional[str],
        merchant_id: str,
        body: str,
        conversation_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ):
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with self._lock:
            if suppression_key:
                self._suppression_keys[suppression_key] = ts
            b_hash = hashlib.sha256(body.strip().encode("utf-8")).hexdigest()
            self._sent_bodies[(merchant_id, b_hash)] = ts
            if conversation_id:
                self._conversation_bodies.add((conversation_id, b_hash))

    def clear(self):
        with self._lock:
            self._suppression_keys.clear()
            self._sent_bodies.clear()
            self._conversation_bodies.clear()


suppression_engine = SuppressionEngine()
