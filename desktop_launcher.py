from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


APP_NAME = "AudioAgent Desktop Full"


def _resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _find_port(preferred: int = 8511) -> int:
    for port in [preferred, *range(8512, 8531)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("Nenhuma porta local disponível entre 8511 e 8530.")


def _open_browser_later(url: str) -> None:
    time.sleep(3)
    webbrowser.open(url)


def main() -> int:
    os.environ.setdefault("AUDIOAGENT_DESKTOP_MODE", "1")
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

    app_path = _resource_root() / "app.py"
    if not app_path.exists():
        raise FileNotFoundError(f"app.py não encontrado em {app_path}")

    sys.path.insert(0, str(_resource_root()))

    port = _find_port()
    url = f"http://127.0.0.1:{port}"
    threading.Thread(target=_open_browser_later, args=(url,), daemon=True).start()

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode",
        "false",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "false",
    ]

    from streamlit.web import cli as streamlit_cli

    return int(streamlit_cli.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
