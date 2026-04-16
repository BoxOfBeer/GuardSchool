"""Фоновая синхронизация локальной установки с облаком (pull bundle при смене ревизии)."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

_LOG = logging.getLogger(__name__)


def _sync_token(cfg: dict[str, Any]) -> str:
    t = (os.environ.get("GUARDSCHOOL_CLOUD_SYNC_TOKEN") or "").strip()
    if t:
        return t
    return str(cfg.get("cloud_sync_token") or "").strip()


async def run_cloud_sync_once() -> dict[str, Any]:
    """Один цикл: проверка /api/sync/status и при необходимости импорт ZIP."""
    import httpx

    from .gs_data_revision import compute_data_revision
    from .gs_import_bundle import import_bundle_bytes
    from .gs_jsonio import read_json, write_json
    from .gs_paths import CONFIG_PATH, SYNC_STATE_PATH

    cfg = read_json(CONFIG_PATH, {})
    if not cfg.get("cloud_sync_enabled", True):
        return {"skipped": True, "reason": "disabled"}
    base = str(cfg.get("cloud_base_url") or "").strip().rstrip("/")
    if not base:
        return {"skipped": True, "reason": "no cloud_base_url"}
    token = _sync_token(cfg)
    if not token:
        return {"skipped": True, "reason": "no sync token"}

    st = read_json(SYNC_STATE_PATH, {})
    interval_min = max(1, int(cfg.get("cloud_sync_interval_minutes") or 5))
    now = time.time()
    last_attempt = float(st.get("last_attempt_ts") or 0)
    if now - last_attempt < interval_min * 60:
        return {"skipped": True, "reason": "interval"}

    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(90.0)

    st = read_json(SYNC_STATE_PATH, {})
    st["last_attempt_ts"] = now
    write_json(SYNC_STATE_PATH, st)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            sr = await client.get(f"{base}/api/sync/status", headers=headers)
            sr.raise_for_status()
            status = sr.json()
        except Exception as e:
            err = str(e)[:500]
            st = read_json(SYNC_STATE_PATH, {})
            st["last_error"] = err
            st["last_ok_at"] = st.get("last_ok_at")
            write_json(SYNC_STATE_PATH, st)
            return {"ok": False, "error": err}

        remote_rev = str(status.get("data_revision") or status.get("revision") or "").strip()
        if not remote_rev:
            err = "empty revision from cloud"
            st = read_json(SYNC_STATE_PATH, {})
            st["last_error"] = err
            write_json(SYNC_STATE_PATH, st)
            return {"ok": False, "error": err}

        last_imported = str(st.get("last_data_revision") or "").strip()
        if remote_rev == last_imported:
            st = read_json(SYNC_STATE_PATH, {})
            st["last_ok_at"] = now
            st["last_error"] = ""
            st["last_data_revision"] = remote_rev
            write_json(SYNC_STATE_PATH, st)
            return {"ok": True, "unchanged": True}

        try:
            br = await client.get(f"{base}/api/sync/bundle", headers=headers)
            br.raise_for_status()
            raw = br.content
        except Exception as e:
            err = str(e)[:500]
            st = read_json(SYNC_STATE_PATH, {})
            st["last_error"] = err
            write_json(SYNC_STATE_PATH, st)
            return {"ok": False, "error": err}

        try:
            import_bundle_bytes(raw, lang="ru")
        except Exception as e:
            err = f"import: {e}"[:500]
            st = read_json(SYNC_STATE_PATH, {})
            st["last_error"] = err
            write_json(SYNC_STATE_PATH, st)
            return {"ok": False, "error": err}

        st = read_json(SYNC_STATE_PATH, {})
        st["last_ok_at"] = time.time()
        st["last_error"] = ""
        st["last_data_revision"] = remote_rev
        write_json(SYNC_STATE_PATH, st)
        return {"ok": True, "imported": True, "revision": remote_rev, "local_data_revision": compute_data_revision()}


async def _cloud_sync_loop() -> None:
    while True:
        await asyncio.sleep(15)
        try:
            await run_cloud_sync_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _LOG.debug("cloud sync loop: %s", e)


def start_cloud_sync_background() -> Any:
    """Запуск в asyncio-цикле (lifespan). Возвращает функцию отмены задачи."""
    task = asyncio.create_task(_cloud_sync_loop())

    def _cancel() -> None:
        task.cancel()

    return _cancel
