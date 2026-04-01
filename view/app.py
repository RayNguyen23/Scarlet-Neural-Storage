import os
import subprocess
import sys
import threading
from pathlib import Path

import eel

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from view.pipeline import (
    persist_session_to_disk,
    pipeline_state,
    restore_session_from_disk,
    run_encoding_phase,
    run_summon_phase,
)

WEB_ROOT = Path(__file__).resolve().parent / "web"
eel.init(str(WEB_ROOT))


def _busy() -> bool:
    return pipeline_state.snapshot()["running"]


@eel.expose
def pick_file():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(title="Select file")
    root.destroy()
    return path or ""


@eel.expose
def pick_folder():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askdirectory(title="Select folder")
    root.destroy()
    return path or ""


@eel.expose
def get_state():
    return pipeline_state.snapshot()


@eel.expose
def reset_workspace():
    if _busy():
        return {"ok": False, "error": "Wait for the current operation to finish."}
    pipeline_state.reset()
    pipeline_state.log("Workspace reset (session cleared)")
    return {"ok": True}


@eel.expose
def load_saved_session():
    if _busy():
        return {"ok": False, "error": "Busy"}
    ok, msg = restore_session_from_disk(pipeline_state)
    if not ok:
        return {"ok": False, "error": msg}
    return {"ok": True, "path": msg}


@eel.expose
def save_session_now():
    if _busy():
        return {"ok": False, "error": "Busy"}
    ok, msg = persist_session_to_disk(pipeline_state)
    if not ok:
        return {"ok": False, "error": msg}
    pipeline_state.log(f"Manual session save → {msg}")
    return {"ok": True, "path": msg}


@eel.expose
def start_encoding(source_path, is_folder, num_devices):
    if _busy():
        return {"ok": False, "error": "Busy"}

    if not (source_path or "").strip():
        return {"ok": False, "error": "Choose a file or folder first"}

    pipeline_state.reset()
    pipeline_state.set_running(True)
    pipeline_state.set_params(
        app_root=str(ROOT.resolve()),
        ui_source=os.path.abspath(os.path.expanduser(source_path.strip())),
        ui_is_folder=bool(is_folder),
        ui_device_count=int(num_devices),
        product="Ray-Neural-v1.2-Final",
    )
    pipeline_state.log(
        f"Queued ENCODE devices={num_devices} folder={bool(is_folder)}"
    )
    pipeline_state.update(
        pct=0,
        operation="Queued — encoding",
        done=False,
        error=None,
        result_path=None,
    )

    def worker():
        run_encoding_phase(source_path, bool(is_folder), int(num_devices), pipeline_state)

    threading.Thread(target=worker, daemon=True).start()
    return {"ok": True}


@eel.expose
def start_summon():
    if _busy():
        return {"ok": False, "error": "Busy"}

    snap = pipeline_state.snapshot()
    if not snap.get("encoding_complete"):
        return {"ok": False, "error": "Encode first, or load a saved session"}

    pipeline_state.set_running(True)
    pipeline_state.log("Queued SUMMON")
    pipeline_state.update(
        pct=0,
        operation="Queued — summon",
        done=False,
        error=None,
        result_path=None,
    )

    def worker():
        run_summon_phase(pipeline_state)

    threading.Thread(target=worker, daemon=True).start()
    return {"ok": True}


@eel.expose
def open_in_finder(path):
    path = os.path.abspath(os.path.expanduser(path))
    if not path or not os.path.exists(path):
        return {"ok": False, "error": "path_not_found"}
    try:
        subprocess.run(
            ["open", "-R", path] if os.path.isfile(path) else ["open", path],
            check=False,
        )
        return {"ok": True}
    except OSError as e:
        return {"ok": False, "error": str(e)}


def start_desktop():
    eel.start("index.html", size=(1180, 780), port=0)


def main():
    start_desktop()


if __name__ == "__main__":
    main()
