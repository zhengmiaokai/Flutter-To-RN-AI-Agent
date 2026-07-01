"""framework/state — JSON file backed checkpoint/resume state persistence.

Provides per-file tracking via structured per-phase state (convert, reflect,
verify) stored in a JSON file. Version 4 removes the redundant top-level
completed/failed/skipped lists since the same information is tracked at
individual-file granularity within each phase's metadata.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_CURRENT_VERSION = 4


class StateManager:
    """Persists and loads conversion progress state via a JSON file.

    Tracks per-file state within each pipeline phase (convert, reflect,
    verify) at individual-file granularity — storing rich metadata such
    as status, scores, issues, categories, and timestamps.
    """

    def __init__(self, state_path: Path):
        self._path = state_path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()

    # ---- Load / save -------------------------------------------------------

    def _load(self) -> dict:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version", 1) < _CURRENT_VERSION:
                self._migrate(data)
            return data
        except (FileNotFoundError, json.JSONDecodeError):
            return self._fresh_state()

    @staticmethod
    def _fresh_state() -> dict:
        return {
            "version": _CURRENT_VERSION,
            "phases": {},
            "phase_data": {},
        }

    def _migrate(self, data: dict):
        """Migrate from older versions to the current format."""
        ver = data.get("version", 1)
        if ver < 3:
            # v1/v2 → v3: add files containers under phase_data
            for phase in ("convert", "reflect", "verify"):
                pd = data.setdefault("phase_data", {}).setdefault(phase, {})
                pd.setdefault("files", {})
        if ver < 4:
            # v3 → v4: migrate flat lists into phase_data, then remove them
            files_store = (
                data.setdefault("phase_data", {})
                .setdefault("convert", {})
                .setdefault("files", {})
            )
            for key in data.get("completed", []):
                if key not in files_store:
                    files_store[key] = {"status": "completed"}
            for entry in data.get("failed", []):
                if isinstance(entry, dict):
                    fkey = entry.get("file", "")
                    if fkey and fkey not in files_store:
                        files_store[fkey] = {"status": "failed", "error": entry.get("error", "")}
            for key in data.get("skipped", []):
                if key not in files_store:
                    files_store[key] = {"status": "skipped"}
            data.pop("completed", None)
            data.pop("failed", None)
            data.pop("skipped", None)
        data["version"] = _CURRENT_VERSION

    def save(self):
        """Atomically write state to JSON file (write tmp, then rename)."""
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    # ---- Per-file tracking (structured, via phase_data) -------------------

    def is_completed(self, file_key: str) -> bool:
        return self.get_file_state("convert", file_key).get("status") == "completed"

    def is_failed(self, file_key: str) -> bool:
        return self.get_file_state("convert", file_key).get("status") == "failed"

    def mark_completed(self, file_key: str, extra: dict | None = None):
        with self._lock:
            data = {"status": "completed"}
            if extra:
                data.update(extra)
            self._set_file_state_unsafe("convert", file_key, data)
            self.save()

    def mark_failed(self, file_key: str, error: str, extra: dict | None = None):
        with self._lock:
            data = {"status": "failed", "error": str(error)}
            if extra:
                data.update(extra)
            self._set_file_state_unsafe("convert", file_key, data)
            self.save()

    # ---- Phase-level tracking (persists across pipeline restarts) ----------

    def is_phase_completed(self, phase: str) -> bool:
        """Check if a pipeline phase was completed in a previous run."""
        return self._data.setdefault("phases", {}).get(phase, False)

    def mark_phase_completed(self, phase: str):
        """Mark a pipeline phase as completed and persist."""
        with self._lock:
            self._data.setdefault("phases", {})[phase] = True
            self.save()

    def mark_phase_incomplete(self, phase: str):
        """Reset a pipeline phase completion flag so the phase runs again.

        Preserves per-file checkpoint data (phase_data[phase].files) so
        individual-file resume still works on the next run.
        """
        with self._lock:
            self._data.setdefault("phases", {})[phase] = False
            self.save()

    def get_phase_data(self, phase: str) -> dict:
        """Retrieve persisted data for a phase (e.g. file_groups for scan)."""
        return self._data.setdefault("phase_data", {}).get(phase, {})

    def set_phase_data(self, phase: str, data: dict):
        """Persist arbitrary data for a phase (merges with existing, preserving
        keys like 'files' that may have been set via set_file_state)."""
        with self._lock:
            pd = self._data.setdefault("phase_data", {}).setdefault(phase, {})
            for k, v in data.items():
                pd[k] = v
            self.save()

    # ---- Structured per-file state (rich data per phase) -------------------

    def _get_files_store(self, phase: str) -> dict:
        """Get or create the per-file state dict for a phase.

        Stored under phase_data[phase]["files"] as a dict of
        file_key → {status, category, source, output, error, ...}
        """
        pd = self._data.setdefault("phase_data", {})
        pd.setdefault(phase, {})
        return pd[phase].setdefault("files", {})

    def _set_file_state_unsafe(self, phase: str, file_key: str, data: dict):
        """Set per-file state without acquiring the lock (caller must hold lock)."""
        store = self._get_files_store(phase)
        existing = store.get(file_key, {})
        existing.update(data)
        # Always ensure timestamp
        if "timestamp" not in existing:
            existing["timestamp"] = datetime.now(timezone.utc).isoformat()
        store[file_key] = existing

    def set_file_state(self, phase: str, file_key: str, data: dict):
        """Store structured per-file state for a pipeline phase.

        Args:
            phase: One of "convert", "reflect", "verify".
            file_key: Unique identifier (e.g. "screens:LoginPage.dart").
            data: Dict with phase-specific fields (status, score, issues, ...).
        """
        with self._lock:
            self._set_file_state_unsafe(phase, file_key, data)
            self.save()

    def clear_phase_files(self, phase: str):
        """Clear per-file state for a pipeline phase.

        Used to clean up stale error data from previous runs on a fresh
        verification cycle — ensuring no contradictory state (errors listed
        alongside a successful build verdict).
        """
        with self._lock:
            pd = self._data.setdefault("phase_data", {}).setdefault(phase, {})
            pd["files"] = {}
            self.save()

    def get_file_state(self, phase: str, file_key: str) -> dict:
        """Get structured per-file state. Returns empty dict if not found."""
        return self._get_files_store(phase).get(file_key, {})

    def get_all_file_states(self, phase: str) -> dict[str, dict]:
        """Get all per-file states for a phase as {file_key: data, ...}."""
        return dict(self._get_files_store(phase))

    def get_file_status_summary(self, phase: str) -> dict[str, int]:
        """Aggregate per-file status counts for a phase.

        Returns e.g. {"completed": 4, "failed": 1, "reviewed": 3, ...}
        """
        counts: dict[str, int] = {}
        for data in self._get_files_store(phase).values():
            status = data.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    # ---- Utility -----------------------------------------------------------

    def reset(self):
        with self._lock:
            self._data = self._fresh_state()
            self.save()

    def summary(self) -> str:
        parts = []
        for phase in ("convert", "reflect", "verify"):
            counts = self.get_file_status_summary(phase)
            if counts:
                detail = ", ".join(f"{k}: {v}" for k, v in counts.items())
                parts.append(f"{phase}: {detail}")
        return " | ".join(parts) if parts else "(no data)"

    def close(self):
        pass  # no-op; kept for API compatibility
