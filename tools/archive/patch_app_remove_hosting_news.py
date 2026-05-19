from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "guardschool" / "app.py"
lines = APP.read_text(encoding="utf-8").splitlines(keepends=True)

for s, e in sorted(
    [
        (990, 1008),
        (918, 977),
        (674, 893),
        (535, 670),
        (406, 495),
        (302, 336),
    ],
    reverse=True,
):
    del lines[s - 1 : e]

text = "".join(lines)

imp = """from .gs_school_news import (
    load_school_news,
    safe_unlink_school_news_upload_url,
    sanitize_school_news_item,
    save_school_news_image_bytes,
)
from .gs_checkin_screen import (
    checkin_board_payload,
    checkin_period_normalize,
    checkin_events_screen_slug_for_monitor,
    device_widget_types_for_tv_device_panel,
    find_monitor_widget,
    find_submit_widget,
    resolve_checkin_submit_places,
    screen_config_by_slug,
    screen_widgets_ordered_with_carousel_children,
)
from .gs_admin_upload import (
    read_upload_capped,
    reject_if_saas_upload,
    saas_check_json_payload_size,
    saas_check_quota_for_path,
    saas_enforce_user_data_quota_after_multi_write,
)
from .app_hosting import register_hosting_middleware

# Back-compat
_screen_config_by_slug = screen_config_by_slug
_find_submit_widget = find_submit_widget
_find_monitor_widget = find_monitor_widget
_checkin_events_screen_slug_for_monitor = checkin_events_screen_slug_for_monitor
_resolve_checkin_submit_places = resolve_checkin_submit_places
_checkin_board_payload = checkin_board_payload
_reject_if_saas_upload = reject_if_saas_upload
_read_upload_capped = read_upload_capped
"""

if "from .gs_school_news import" not in text:
    text = text.replace("from .routes_pages import register_page_routes\n", "from .routes_pages import register_page_routes\n" + imp)

reg = "register_page_routes(app)\n"
if "register_hosting_middleware" not in text:
    text = text.replace(reg, reg + "register_hosting_middleware(app)\n")

APP.write_text(text, encoding="utf-8")
print("lines", text.count("\n"))
