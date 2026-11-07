from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class JobText(Exception):
    """Message d’avancement traduit côté navigateur (message_code + repli français)."""

    def __init__(self, code: str, fallback: str, **fields: object) -> None:
        super().__init__(fallback)
        self.code = code
        self.fields = {key: "" if value is None else str(value) for key, value in fields.items()}


def emit(
    progress: Callable[..., None] | None,
    done: int,
    total: int | None,
    code: str,
    fallback: str,
    /,
    **fields: object,
) -> None:
    if progress is None:
        return
    clean = {key: "" if value is None else str(value) for key, value in fields.items()}
    progress(done, total, fallback, code, clean)


class JobRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.state: dict[str, Any] | None = None
        self._queue: list[tuple[str, Callable[..., dict], tuple]] = []

    def snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            snap = None if self.state is None else dict(self.state)
            if snap is not None:
                snap["queued"] = [{"kind": k} for k, _, _ in self._queue]
            return snap

    def busy(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self, kind: str, fn: Callable[..., dict], *args: Any) -> dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                if any(k == kind for k, _, _ in self._queue):
                    snap = dict(self.state or {})
                    snap["status"] = "queued"
                    snap["kind"] = kind
                    snap["message"] = "Déjà en file d’attente"
                    snap["message_code"] = "prog.queued"
                    snap["message_vars"] = {}
                    snap["queued"] = [{"kind": k} for k, _, _ in self._queue]
                    return snap
                self._queue.append((kind, fn, args))
                current = (self.state or {}).get("kind") or "task"
                return {
                    "kind": kind,
                    "status": "queued",
                    "done": 0,
                    "total": None,
                    "message": f"En file, après : {current}",
                    "message_code": "prog.after",
                    "message_vars": {"current": current},
                    "result": None,
                    "error": None,
                    "queued": [{"kind": k} for k, _, _ in self._queue],
                }
            return self._launch(kind, fn, args)

    def _launch(self, kind: str, fn: Callable[..., dict], args: tuple) -> dict[str, Any]:
        self.state = {
            "kind": kind,
            "status": "running",
            "done": 0,
            "total": None,
            "message": "Démarrage…",
            "message_code": "prog.start",
            "message_vars": {},
            "result": None,
            "error": None,
            "mfa_needed": False,
            "started_at": _now(),
            "finished_at": None,
            "queued": [{"kind": k} for k, _, _ in self._queue],
        }
        self._thread = threading.Thread(
            target=self._run, args=(kind, fn, args), daemon=True
        )
        self._thread.start()
        return dict(self.state)

    def progress(
        self,
        done: int,
        total: int | None,
        message: str,
        code: str = "",
        fields: dict | None = None,
    ) -> None:
        with self._lock:
            if not self.state:
                return
            self.state["done"] = done
            self.state["total"] = total
            self.state["message"] = message
            self.state["message_code"] = code or ""
            self.state["message_vars"] = dict(fields or {})

    def patch(self, **fields: Any) -> None:
        with self._lock:
            if not self.state:
                return
            self.state.update(fields)

    def _run(self, kind: str, fn: Callable[..., dict], args: tuple) -> None:
        try:
            result = fn(*args, progress=self.progress)
            with self._lock:
                if self.state:
                    message = self.state.get("message") or "Terminé"
                    code = self.state.get("message_code") or ""
                    if message in {"", "Démarrage…"}:
                        message = "Terminé"
                        code = "prog.done"
                    self.state.update(
                        {
                            "status": "done",
                            "result": result,
                            "message": message,
                            "message_code": code,
                            "finished_at": _now(),
                        }
                    )
        except JobText as exc:
            with self._lock:
                if self.state:
                    self.state.update(
                        {
                            "status": "error",
                            "error": str(exc),
                            "message": str(exc),
                            "message_code": exc.code,
                            "message_vars": dict(exc.fields),
                            "finished_at": _now(),
                        }
                    )
        except Exception as exc:
            with self._lock:
                if self.state:
                    self.state.update(
                        {
                            "status": "error",
                            "error": str(exc),
                            "message": str(exc),
                            "message_code": "",
                            "message_vars": {},
                            "finished_at": _now(),
                        }
                    )
        with self._lock:
            if self._queue:
                nxt = self._queue.pop(0)
                self._launch(*nxt)
