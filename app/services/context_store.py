from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from app.models.contexts import (
    CategoryContext,
    CustomerContext,
    MerchantContext,
    TriggerContext,
)


class StaleVersionError(Exception):
    def __init__(self, current_version: int):
        self.current_version = current_version
        super().__init__(f"Stale version provided. Current version is {current_version}")


class ContextStore:
    """
    Thread-safe in-memory store for versioned contexts.
    Key: (scope, context_id)
    """

    def __init__(self):
        self._lock = threading.RLock()
        # Storage: (scope, context_id) -> {"version": int, "payload": dict, "stored_at": str}
        self._store: Dict[Tuple[str, str], Dict[str, Any]] = {}
        # Parsed cache for high performance
        self._parsed_cache: Dict[Tuple[str, str, int], Any] = {}

    def put(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: Dict[str, Any],
        delivered_at: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Pushes a context into the store according to versioning rules:
        - If never seen: store it.
        - If same version: idempotent, accept.
        - If higher version: replace atomically.
        - If older version: reject as stale.

        Returns: (accepted, stored_at_or_reason, current_version_if_stale)
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        key = (scope, context_id)

        with self._lock:
            existing = self._store.get(key)
            if existing is not None:
                current_ver = existing["version"]
                if version < current_ver:
                    return False, "stale_version", current_ver
                elif version == current_ver:
                    # Idempotent: return stored_at
                    return True, existing["stored_at"], None
                else:
                    # Higher version: replace atomically
                    self._store[key] = {
                        "version": version,
                        "payload": payload,
                        "stored_at": now_iso,
                        "delivered_at": delivered_at,
                    }
                    # Invalidate cached parsed model
                    self._parsed_cache.pop((scope, context_id, current_ver), None)
                    return True, now_iso, None
            else:
                # Never seen
                self._store[key] = {
                    "version": version,
                    "payload": payload,
                    "stored_at": now_iso,
                    "delivered_at": delivered_at,
                }
                return True, now_iso, None

    def get_raw(self, scope: str, context_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._store.get((scope, context_id))
            if entry is None:
                return None
            return entry["payload"]

    def get_version(self, scope: str, context_id: str) -> Optional[int]:
        with self._lock:
            entry = self._store.get((scope, context_id))
            if entry is None:
                return None
            return entry["version"]

    def get_category(self, slug: str) -> Optional[CategoryContext]:
        key = ("category", slug)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ver = entry["version"]
            cache_key = ("category", slug, ver)
            if cache_key in self._parsed_cache:
                return self._parsed_cache[cache_key]

            try:
                cat = CategoryContext(**entry["payload"])
                self._parsed_cache[cache_key] = cat
                return cat
            except Exception:
                return None

    def get_merchant(self, merchant_id: str) -> Optional[MerchantContext]:
        key = ("merchant", merchant_id)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ver = entry["version"]
            cache_key = ("merchant", merchant_id, ver)
            if cache_key in self._parsed_cache:
                return self._parsed_cache[cache_key]

            try:
                m = MerchantContext(**entry["payload"])
                self._parsed_cache[cache_key] = m
                return m
            except Exception:
                return None

    def get_customer(self, customer_id: str) -> Optional[CustomerContext]:
        key = ("customer", customer_id)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ver = entry["version"]
            cache_key = ("customer", customer_id, ver)
            if cache_key in self._parsed_cache:
                return self._parsed_cache[cache_key]

            try:
                c = CustomerContext(**entry["payload"])
                self._parsed_cache[cache_key] = c
                return c
            except Exception:
                return None

    def get_trigger(self, trigger_id: str) -> Optional[TriggerContext]:
        key = ("trigger", trigger_id)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ver = entry["version"]
            cache_key = ("trigger", trigger_id, ver)
            if cache_key in self._parsed_cache:
                return self._parsed_cache[cache_key]

            try:
                t = TriggerContext(**entry["payload"])
                self._parsed_cache[cache_key] = t
                return t
            except Exception:
                return None

    def get_counts_by_scope(self) -> Dict[str, int]:
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        with self._lock:
            for scope, _ in self._store.keys():
                if scope in counts:
                    counts[scope] += 1
        return counts

    def clear(self):
        with self._lock:
            self._store.clear()
            self._parsed_cache.clear()


# Global singleton instance
context_store = ContextStore()
