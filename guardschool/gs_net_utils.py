"""Network/string helpers for config sanitization."""
from __future__ import annotations

import re
from urllib.parse import urlparse


def normalize_stream_host(raw: str) -> str:
    """
    Из поля «IP приёмника» часто вставляют URL (http://192.168.1.1/) — ping и TCP ждут голый хост.
    Убираем схему, путь, лишние слэши; при виде 192.168.1.1:порт оставляем только IP (порт задаётся отдельно).
    """
    s = str(raw or "").strip()
    if not s:
        return ""
    if re.match(r"^https?://", s, re.IGNORECASE):
        try:
            p = urlparse(s)
            h = (p.hostname or "").strip()
            if h:
                return h[:253]
        except Exception:
            pass
    s = s.split("/")[0].split("?")[0].strip()
    if s.count(":") == 1 and not s.startswith("["):
        left, _, right = s.partition(":")
        if right.isdigit():
            s = left.strip()
    return s[:253]
