from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from app.manager.config import Settings
from app.manager.main import create_app


def executable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]



def acquire_single_instance(root: Path):
    """Keep a second double-click from starting a competing localhost server."""
    if sys.platform != "win32":
        return None
    import msvcrt

    lock_path = root / "HosoManager.lock"
    handle = lock_path.open("a+", encoding="ascii")
    handle.seek(0)
    handle.write("0")
    handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return False
    return handle


def notify_second_instance() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, "Hồ sơ Digitization Manager đang chạy.", "Hồ sơ Digitization Manager", 0x40)
    except Exception:
        pass


def wait_for_server_started(server: uvicorn.Server, timeout: float = 10.0) -> bool:
    """Wait for Uvicorn's bound-server signal without adding a network client."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.started:
            return True
        time.sleep(0.1)
    return bool(server.started)


def write_startup_log(root: Path, message: str) -> None:
    try:
        with (root / "startup.log").open("a", encoding="utf-8") as log_file:
            log_file.write(message + "\n")
    except OSError:
        pass


def main() -> None:
    root = executable_root()
    write_startup_log(root, "starting")
    local_config_path = root / "config.local.json"
    default_config_path = root / "config.json"
    config_path = local_config_path if local_config_path.is_file() else default_config_path
    if config_path.is_file():
        settings = Settings.from_file(config_path)
    else:
        settings = Settings(data_root=root / "input", database_path=root / "data" / "manager.db", config_path=config_path, open_browser_on_start=True)
        settings.save(config_path)
    write_startup_log(root, f"config_loaded: {config_path}")
    settings.validate()
    write_startup_log(root, "config_valid")
    instance_lock = acquire_single_instance(root)
    if instance_lock is False:
        notify_second_instance()
        return
    app = create_app(settings)
    write_startup_log(root, "app_created")
    write_startup_log(root, "server_config_building")
    # Packaged GUI builds have no console streams. Disable Uvicorn's default
    # stdout/stderr logging configuration so startup cannot block on a missing
    # Windows console handle; startup milestones remain in startup.log.
    config = uvicorn.Config(app, host=settings.host, port=settings.port, log_config=None, access_log=False)
    write_startup_log(root, "server_config_built")
    server = uvicorn.Server(config)
    write_startup_log(root, "server_created")
    def run_server() -> None:
        try:
            server.run()
        except BaseException as exc:
            write_startup_log(root, f"server_error: {type(exc).__name__}: {exc}")

    thread = threading.Thread(target=run_server, name="hoso-manager-server", daemon=True)
    write_startup_log(root, "server_thread_starting")
    thread.start()
    write_startup_log(root, "server_thread_started")
    try:
        if not wait_for_server_started(server):
            write_startup_log(root, f"server_not_started: {settings.host}:{settings.port}")
            raise RuntimeError(f"Không thể khởi động máy chủ cục bộ tại {settings.host}:{settings.port}")
        if settings.open_browser_on_start:
            webbrowser.open(f"http://{settings.host}:{settings.port}/")
        thread.join()
    finally:
        server.should_exit = True
        thread.join(timeout=2)
        if instance_lock is not None:
            instance_lock.close()


if __name__ == "__main__":
    main()



