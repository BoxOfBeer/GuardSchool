from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "guardschool" / "app.py"
lines = APP.read_text(encoding="utf-8").splitlines(keepends=True)
del lines[1030:1173]  # uploads through screens (1-based 1031-1173)
del lines[1010:1028]  # _tenant_upload_local_file (1011-1028)
text = "".join(lines)
if "register_page_routes" not in text:
    text = text.replace(
        "register_auth_routes(app)\n",
        "register_auth_routes(app)\nfrom .routes_pages import register_page_routes\nregister_page_routes(app)\n",
    )
APP.write_text(text, encoding="utf-8")
print("app lines", text.count("\n"))
