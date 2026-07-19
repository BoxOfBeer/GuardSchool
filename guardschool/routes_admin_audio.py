"""Admin API: PC audio, audio-stream (ffplay), break music."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from . import bell_rupor_worker
from .gs_app_config import load_config, sanitize_audio_stream
from .gs_auth import require_auth
from .gs_ensure_dirs import ensure_dirs
from .gs_paths import BELL_SOUNDS_DIR, BREAK_MUSIC_DIR, UPLOADS_DIR
from .gs_schedule_bells import first_bell_sound_path

router = APIRouter(tags=["admin"])


async def _handle_pc_audio_test_play(request: Request) -> dict[str, str]:
    """Тест колонок с ПК: первый файл из uploads/bells или явный filename в JSON."""
    require_auth(request)
    body: dict[str, Any] = {}
    raw = await request.body()
    if raw.strip():
        try:
            parsed = json.loads(raw.decode("utf-8-sig"))
            if isinstance(parsed, dict):
                body = parsed
        except (json.JSONDecodeError, UnicodeError, TypeError):
            body = {}
    use_first = request.query_params.get("use_first") in ("1", "true", "yes")
    raw_fn = body.get("filename")
    if raw_fn in (None, "", False):
        raw_fn = body.get("file")
    if use_first or raw_fn in (None, "", False):
        fn = ""
    else:
        fn = str(raw_fn).strip()
    if fn:
        safe = Path(fn).name
        path = BELL_SOUNDS_DIR / safe
        if not path.is_file():
            path = UPLOADS_DIR / safe
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Файл не найден в каталогах uploads/bells или uploads.")
    else:
        first = first_bell_sound_path()
        if not first:
            raise HTTPException(
                status_code=400,
                detail="В uploads/bells нет файлов. Загрузите звук в разделе «Сигналы».",
            )
        path = first
        safe = path.name
    audio = dict(sanitize_audio_stream(load_config().get("audio_stream")))
    vol = body.get("volume_percent")
    if vol is not None:
        try:
            audio["volume_percent"] = max(0, min(100, int(vol)))
        except (TypeError, ValueError):
            pass
    ok, err = bell_rupor_worker.stream_file_to_rupor(path, audio)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Не удалось запустить отправку.")
    return {
        "status": "ok",
        "detail": f"Файл «{safe}»: воспроизведение на ПК в фоне (если ffmpeg с muxer wasapi — через него; иначе ffplay в той же папке). Ниже — stderr.",
    }


@router.post("/api/admin/audio-stream-test-send")
async def post_audio_stream_test_send(request: Request) -> dict[str, str]:
    """Совместимость со старыми клиентами; предпочтительно /api/admin/pc-audio-test-play."""
    return await _handle_pc_audio_test_play(request)


@router.post("/api/admin/pc-audio-test-play")
async def post_pc_audio_test_play(request: Request) -> dict[str, str]:
    """Тест Рупор из сайдбара (есть только в актуальном сервере — иначе в браузере будет 404)."""
    return await _handle_pc_audio_test_play(request)


@router.get("/api/admin/audio-stream-last-send")
def get_audio_stream_last_send(request: Request) -> dict[str, Any]:
    """Последний сеанс ffplay (команда и stderr)."""
    require_auth(request)
    return {"last": bell_rupor_worker.get_last_ffmpeg_send()}


@router.get("/api/admin/audio-stream-status")
def get_audio_stream_status(request: Request) -> dict[str, Any]:
    """Процесс ffplay и последний результат — для панели админки."""
    require_auth(request)
    return bell_rupor_worker.get_ffmpeg_status()


@router.post("/api/admin/audio-stream-stop")
def post_audio_stream_stop(request: Request) -> dict[str, Any]:
    """Остановить текущее воспроизведение (ffplay)."""
    require_auth(request)
    return bell_rupor_worker.stop_current_stream()


@router.get("/api/admin/break-music-files")
def list_break_music_files(request: Request) -> dict[str, Any]:
    """Файлы в data/break_music + порядок воспроизведения и громкости для админки."""
    require_auth(request)
    ensure_dirs()
    files = []
    if BREAK_MUSIC_DIR.exists():
        for p in sorted(BREAK_MUSIC_DIR.iterdir()):
            if p.is_file():
                files.append({"filename": p.name})
    from . import local_audio_worker

    return {
        "files": files,
        "directory": str(BREAK_MUSIC_DIR),
        "playback": local_audio_worker.get_break_music_playback_info(),
    }


@router.post("/api/admin/break-music-preview")
async def post_break_music_preview(request: Request) -> dict[str, str]:
    """Прослушать файл из data/break_music на ПК с громкостью «перемена» (как в оркестрации)."""
    require_auth(request)
    body: dict[str, Any] = {}
    raw = await request.body()
    if raw.strip():
        try:
            parsed = json.loads(raw.decode("utf-8-sig"))
            if isinstance(parsed, dict):
                body = parsed
        except (json.JSONDecodeError, UnicodeError, TypeError):
            body = {}
    fn = Path(str(body.get("filename") or "")).name
    if not fn:
        raise HTTPException(status_code=400, detail="Укажите filename (имя файла в data/break_music).")
    path = BREAK_MUSIC_DIR / fn
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден в data/break_music.")
    from . import local_audio_worker

    audio = sanitize_audio_stream(load_config().get("audio_stream"))
    vol = body.get("volume_percent")
    if vol is not None:
        try:
            audio = {**audio, "break_music_volume_percent": max(0, min(100, int(vol)))}
        except (TypeError, ValueError):
            pass
    local_audio_worker.stop_playback_hard()
    time.sleep(0.08)
    ok, err = local_audio_worker.play_break_music_preview(path, audio)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Не удалось воспроизвести.")
    v = int(audio.get("break_music_volume_percent") or 40)
    return {
        "status": "ok",
        "detail": f"«{fn}» — громкость перемены {v}% (ffmpeg af volume={v/100.0:.2f}).",
    }
