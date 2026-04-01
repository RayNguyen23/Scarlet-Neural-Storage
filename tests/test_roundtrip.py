import hashlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from view.pipeline import pipeline_state, run_pipeline


def main():
    data = os.urandom(2048)
    expected_hash = hashlib.sha256(data).hexdigest()

    f = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    try:
        f.write(data)
        f.close()

        pipeline_state.reset()
        run_pipeline(f.name, False, 3, pipeline_state)
        snap = pipeline_state.snapshot()

        assert not snap.get("error"), snap.get("error")
        assert snap.get("workflow") == "restored", snap.get("workflow")
        assert snap.get("result_path")

        out_path = snap["result_path"]
        with open(out_path, "rb") as rf:
            got = rf.read()
        assert got == data, "byte mismatch"
        assert hashlib.sha256(got).hexdigest() == expected_hash
        print("OK round-trip", len(got), "bytes")
        return 0
    finally:
        try:
            os.unlink(f.name)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
