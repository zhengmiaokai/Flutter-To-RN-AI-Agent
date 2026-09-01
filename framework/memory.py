"""framework/memory — cross-run persistent memory for the conversion pipeline.

Stores four memory types in a JSON file (target_dir/.memory.json) using the
same atomic-write + thread-lock pattern as StateManager:

  ① conversion few-shots  : high-score (>= 90) dart→ts pairs per category
  ② fix memos             : error_code → fix snippet (for verify_fix)
  ③ score memory          : source_hash → reflect score (skip-if-unchanged)
  ④ project digest        : converted modules + key type signatures

Correctness guard: memory is advisory only — it hints or skips, never forces.
Score-memory skip must be paired with a dependency check by the caller, so a
changed dependency (e.g. a modified model file) still triggers re-review.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_CURRENT_VERSION = 1

# Cap on few-shots per category; oldest entries are evicted on overflow.
_MAX_FEW_SHOTS_PER_CATEGORY = 50
_MAX_FIX_MEMOS_PER_CODE = 5
_MIN_FEW_SHOT_SCORE = 90


class MemoryStore:
    """Persists and loads conversion memory via a JSON file."""

    def __init__(self, target_dir: str):
        self._path = Path(target_dir) / ".memory.json"
        # RLock: record_*() holds the lock and calls save(), which re-acquires
        # it — a plain Lock() would self-deadlock on the same thread.
        self._lock = threading.RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()

    # ---- load / save --------------------------------------------------------

    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return self._fresh()
        if not isinstance(data, dict) or data.get("version", 0) != _CURRENT_VERSION:
            return self._fresh()
        return data

    def _fresh(self) -> dict:
        return {
            "version": _CURRENT_VERSION,
            "few_shots": {},
            "fix_memos": {},
            "score_memory": {},
            "project_digest": {},
        }

    def save(self):
        with self._lock:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ---- ① conversion few-shots --------------------------------------------

    def record_few_shot(
        self,
        category: str,
        dart_snippet: str,
        ts_snippet: str,
        score: int,
    ) -> None:
        """Record a high-score conversion pair (dart hash → ts snippet)."""
        if score < _MIN_FEW_SHOT_SCORE or not dart_snippet.strip() or not ts_snippet.strip():
            return
        dart_hash = _hash_snippet(dart_snippet)
        with self._lock:
            bucket = self._data["few_shots"].setdefault(category, {})
            if dart_hash in bucket:
                # Refresh with the latest/better example
                bucket[dart_hash].update({
                    "ts": ts_snippet,
                    "score": score,
                    "created_at": self._now(),
                })
            else:
                bucket[dart_hash] = {
                    "dart": dart_snippet[:_snippet_cap(dart_snippet)],
                    "ts": ts_snippet[:_snippet_cap(ts_snippet)],
                    "score": score,
                    "created_at": self._now(),
                }
                self._evict_oldest(bucket, _MAX_FEW_SHOTS_PER_CATEGORY)
            self.save()

    def query_few_shots(self, category: str, top_k: int = 2) -> str:
        """Return top-k few-shots for a category as a prompt block (or '')."""
        bucket = self._data["few_shots"].get(category, {})
        if not bucket:
            return ""
        ranked = sorted(
            bucket.values(), key=lambda v: v.get("score", 0), reverse=True
        )[:top_k]
        lines = ["## Past conversion examples (from previous runs — mirror their patterns):"]
        for i, v in enumerate(ranked, 1):
            lines.append(
                f"\n--- Example {i} (quality score {v.get('score')}) ---\n"
                f"```dart\n{v['dart']}\n```\n→\n```typescript\n{v['ts']}\n```"
            )
        lines.append(
            "\nNOTE: Use these only as style reference. Preserve ALL business logic "
            "of the current source file."
        )
        return "\n".join(lines)

    # ---- ② fix memos --------------------------------------------------------

    def record_fix_memo(
        self,
        error_code: str,
        category: str,
        error_message: str,
        fix_snippet: str,
    ) -> None:
        """Record a successful fix for an error code (tsc passed after fix)."""
        if not error_code or not fix_snippet.strip():
            return
        err_hash = _hash_snippet(error_message)
        with self._lock:
            memos = self._data["fix_memos"].setdefault(error_code, [])
            # Replace same-error memo, else append (capped)
            for m in memos:
                if m.get("error_message_hash") == err_hash:
                    m.update({
                        "fix": fix_snippet[:_snippet_cap(fix_snippet)],
                        "category": category,
                        "created_at": self._now(),
                    })
                    self.save()
                    return
            memos.insert(0, {
                "category": category,
                "error_message_hash": err_hash,
                "fix": fix_snippet[:_snippet_cap(fix_snippet)],
                "created_at": self._now(),
            })
            del memos[_MAX_FIX_MEMOS_PER_CODE:]
            self.save()

    def query_fix_memos(self, error_codes: list[str], top_k: int = 3) -> str:
        """Return known fixes for the given error codes as a prompt block."""
        blocks = []
        for code in error_codes:
            for m in self._data["fix_memos"].get(code, [])[:top_k]:
                blocks.append(
                    f"[{code} fix from previous run] (category: {m.get('category')})\n"
                    f"```typescript\n{m['fix']}\n```"
                )
        if not blocks:
            return ""
        header = (
            "## Known fixes for these error codes from previous runs — reuse the "
            "pattern if it applies, but verify it fits the current file:\n"
        )
        return header + "\n\n".join(blocks[:top_k])

    # ---- ③ score memory -----------------------------------------------------

    def record_score_memory(
        self,
        source_hash: str,
        score: int,
        pass_: bool,
        deps_hash: str = "",
    ) -> None:
        with self._lock:
            self._data["score_memory"][source_hash] = {
                "score": score,
                "pass": bool(pass_),
                "deps_hash": deps_hash,
                "updated_at": self._now(),
            }
            self.save()

    def get_score_memory(self, source_hash: str) -> Optional[dict]:
        entry = self._data["score_memory"].get(source_hash)
        return dict(entry) if entry else None

    def should_skip_reflect(self, source_hash: str, deps_hash: str) -> bool:
        """True if this exact source (and its deps) already passed reflect."""
        entry = self.get_score_memory(source_hash)
        if not entry:
            return False
        if not entry.get("pass"):
            return False
        if deps_hash and entry.get("deps_hash") and entry.get("deps_hash") != deps_hash:
            return False
        return True

    # ---- ④ project digest ---------------------------------------------------

    def set_project_digest(self, content: str) -> None:
        if not content.strip():
            return
        with self._lock:
            self._data["project_digest"] = {
                "content": content[:4000],
                "updated_at": self._now(),
            }
            self.save()

    def get_project_digest(self) -> str:
        return self._data.get("project_digest", {}).get("content", "")

    # ---- helpers ------------------------------------------------------------

    @staticmethod
    def _evict_oldest(bucket: dict, cap: int):
        if len(bucket) <= cap:
            return
        overflow = sorted(
            bucket.items(), key=lambda kv: kv[1].get("created_at", "")
        )[: len(bucket) - cap]
        for key, _ in overflow:
            bucket.pop(key, None)


def _hash_snippet(snippet: str) -> str:
    import hashlib
    return hashlib.md5(snippet.encode("utf-8")).hexdigest()[:16]


def _snippet_cap(snippet: str) -> int:
    """Cap stored snippets so the memory file stays small (~400 tokens)."""
    return 1200
