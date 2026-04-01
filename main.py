import argparse
import os
import sys
from pathlib import Path

PATH = "./original/ex.jpg"
DEVICES = [
    {"id": "Hanoi-Node-01", "latency": 45},
    {"id": "Hanoi-Node-02", "latency": 180},
    {"id": "HCM-Cloud-01", "latency": 60},
]


def run_cli():
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from view.pipeline import pipeline_state, run_pipeline

    if not os.path.exists(PATH):
        print(f"[ERROR] path_not_found path={PATH}")
        print("\n=== Done ===")
        return

    print("=== CLI: Neural encoding → Summon (restore) ===")
    is_folder = os.path.isdir(PATH)
    run_pipeline(PATH, is_folder, len(DEVICES), pipeline_state)
    snap = pipeline_state.snapshot()
    if snap.get("error"):
        print(f"\n[ERROR] {snap['error']}")
    elif snap.get("result_path"):
        print(f"\n[OK] restore_path={snap['result_path']}")
    print("\n=== Done ===")


def run_gui():
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from view.app import start_desktop

    start_desktop()


def main():
    parser = argparse.ArgumentParser(description="Scarlet Neural Storage")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run headless encode+summon using PATH and device count in main.py",
    )
    args = parser.parse_args()

    if args.cli:
        run_cli()
    else:
        run_gui()


if __name__ == "__main__":
    main()
