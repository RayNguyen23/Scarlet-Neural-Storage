from __future__ import annotations

import hashlib
import io
import os
import pickle
import sys
import tarfile
import threading
import time
from datetime import datetime
from enum import Enum
from pathlib import Path

from src.AutonomousSeedManagement import AutonomousSeedManagement
from src.DeterministicResurrection import DeterministicResurrection
from src.NeuralEncoding import NeuralEncoding

ROOT = Path(__file__).resolve().parent.parent
SESSION_DIR = ROOT / ".scarlet"
SESSION_FILE = SESSION_DIR / "neural_session.pkl"
SESSION_VERSION = 1

HEAL_ALARM_THRESHOLD_MS = 150
EVENT_LOG_MAX = 400


class Workflow(str, Enum):
    IDLE = "idle"
    ENCODING = "encoding"
    ENCODED = "encoded"
    SUMMONING = "summoning"
    RESTORED = "restored"
    FAILED = "failed"


def build_devices(count: int) -> list:
    count = max(1, int(count))
    devices = []
    for i in range(count):
        latency = 45 + (i * 37 + (i % 4) * 42) % 200
        devices.append({"id": f"Node-{i + 1:02d}", "latency": latency})
    return devices


def _unlink_session_file() -> None:
    try:
        if SESSION_FILE.is_file():
            SESSION_FILE.unlink()
    except OSError:
        pass


class PipelineState:
    def __init__(self):
        self._lock = threading.Lock()
        self._session: dict = {}
        self.reset()

    def reset(self):
        with self._lock:
            self.running = False
            self.pct = 0.0
            self.operation = ""
            self.result_path = None
            self.error = None
            self.done = False
            self.params = {}
            self.devices = []
            self.event_log = []
            self.encoding_complete = False
            self.summon_complete = False
            self.workflow = Workflow.IDLE.value
            self._session = {}
        _unlink_session_file()

    def set_workflow(self, w: str):
        with self._lock:
            self.workflow = w

    def update(
        self,
        pct=None,
        operation=None,
        result_path=None,
        error=None,
        done=None,
    ):
        with self._lock:
            if pct is not None:
                self.pct = float(max(0.0, min(100.0, pct)))
            if operation is not None:
                self.operation = operation
            if result_path is not None:
                self.result_path = result_path
            if error is not None:
                self.error = error
            if done is not None:
                self.done = done

    def set_params(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                if v is None:
                    continue
                if isinstance(v, (dict, list)):
                    self.params[k] = v
                else:
                    self.params[k] = v

    def set_devices(self, devices: list):
        with self._lock:
            self.devices = [dict(d) for d in devices]

    def log(self, message: str, level: str = "info"):
        with self._lock:
            ts = datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}] [{level.upper()}] {message}"
            self.event_log.append(line)
            if len(self.event_log) > EVENT_LOG_MAX:
                self.event_log = self.event_log[-(EVENT_LOG_MAX // 2) :]

    def snapshot(self):
        with self._lock:
            disk = SESSION_FILE.is_file()
            return {
                "running": self.running,
                "pct": self.pct,
                "operation": self.operation,
                "result_path": self.result_path,
                "error": self.error,
                "done": self.done,
                "params": dict(self.params),
                "devices": [dict(d) for d in self.devices],
                "event_log": list(self.event_log),
                "encoding_complete": self.encoding_complete,
                "summon_complete": self.summon_complete,
                "workflow": self.workflow,
                "session_file_exists": disk,
                "session_file_path": str(SESSION_FILE) if disk else "",
            }

    def set_running(self, v: bool):
        with self._lock:
            self.running = v

    def store_session(
        self,
        *,
        seeds,
        state_config,
        original_hash,
        original_size,
        is_folder,
        base_name,
        desc,
    ):
        with self._lock:
            self._session = {
                "seeds": seeds,
                "state_config": state_config,
                "original_hash": original_hash,
                "original_size": original_size,
                "is_folder": is_folder,
                "base_name": base_name,
                "desc": desc,
            }

    def load_session(self):
        with self._lock:
            if not self._session.get("seeds"):
                return None
            return dict(self._session)


pipeline_state = PipelineState()


def persist_session_to_disk(state: PipelineState) -> tuple[bool, str]:
    with state._lock:
        if not state._session.get("seeds"):
            return False, "no_session_in_memory"
        bundle = {
            "v": SESSION_VERSION,
            "session": dict(state._session),
            "devices": [dict(d) for d in state.devices],
            "params": dict(state.params),
        }
    try:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SESSION_FILE.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(SESSION_FILE)
        return True, str(SESSION_FILE.resolve())
    except OSError as e:
        return False, str(e)


def restore_session_from_disk(state: PipelineState) -> tuple[bool, str]:
    if not SESSION_FILE.is_file():
        return False, "session_file_missing"
    try:
        with open(SESSION_FILE, "rb") as f:
            bundle = pickle.load(f)
    except (OSError, pickle.PickleError, EOFError) as e:
        return False, f"load_failed:{e}"
    if not isinstance(bundle, dict) or bundle.get("v") != SESSION_VERSION:
        return False, "unsupported_or_corrupt_session"
    sess = bundle.get("session") or {}
    if not sess.get("seeds"):
        return False, "session_empty"
    with state._lock:
        state._session = sess
        state.devices = [dict(d) for d in (bundle.get("devices") or [])]
        state.params = dict(bundle.get("params") or {})
        state.encoding_complete = True
        state.summon_complete = False
        state.error = None
        state.result_path = None
        state.workflow = Workflow.ENCODED.value
        state.operation = "Session loaded from disk"
        state.pct = 0.0
        state.done = False
    state.log(f"Session restored from {SESSION_FILE}")
    return True, str(SESSION_FILE.resolve())


def _map_encode(done: int, total: int, lo: float, hi: float, state: PipelineState):
    if total <= 0:
        return
    frac = done / total
    state.update(pct=lo + frac * (hi - lo), operation="Encoding — neural seeds")


def _map_decode(done: int, total: int, lo: float, hi: float, state: PipelineState):
    if total <= 0:
        return
    frac = done / total
    state.update(pct=lo + frac * (hi - lo), operation="Summon — reconstruction")


def run_encoding_phase(
    source_path: str, is_folder: bool, num_devices: int, state: PipelineState
):
    restore_dir = ROOT / "restore"
    source_path = os.path.abspath(os.path.expanduser(source_path or ""))
    auto_mgmt = None

    try:
        state.set_workflow(Workflow.ENCODING.value)
        state.encoding_complete = False
        state.summon_complete = False
        state.result_path = None
        state.error = None

        if not source_path.strip():
            state.log("No source path", level="error")
            state.set_workflow(Workflow.FAILED.value)
            state.update(error="Select a file or folder first", done=True, pct=100.0)
            return

        if not os.path.exists(source_path):
            state.log(f"path_not_found: {source_path}", level="error")
            state.set_workflow(Workflow.FAILED.value)
            state.update(error=f"path_not_found: {source_path}", done=True, pct=100.0)
            return

        state.log(
            f"ENCODE start path={source_path} type={'folder' if is_folder else 'file'} devices={num_devices}"
        )
        state.set_params(
            source_path=source_path,
            source_type="folder" if is_folder else "file",
            num_devices_requested=num_devices,
            restore_dir=str(restore_dir.resolve()),
            heal_alarm_threshold_ms=HEAL_ALARM_THRESHOLD_MS,
            int_range="10**800",
        )
        state.update(pct=2.0, operation="Reading payload", done=False, error=None)

        if not is_folder:
            with open(source_path, "rb") as f:
                raw_data = f.read()
        else:
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode="w") as tar:
                tar.add(source_path, arcname=os.path.basename(source_path))
            raw_data = stream.getvalue()

        state.update(pct=8.0, operation="SHA-256 fingerprint")
        original_size = len(raw_data)
        original_hash = hashlib.sha256(raw_data).hexdigest()
        base_name = os.path.basename(source_path.rstrip(os.sep))

        state.set_params(
            original_size_bytes=original_size,
            original_sha256=original_hash,
            payload_basename=base_name,
        )
        state.log(f"Payload sha256={original_hash} bytes={original_size}")

        encoder = NeuralEncoding(ai_model_version="Ray-Neural-v1.2-Final")

        def enc_cb(done, total):
            _map_encode(done, total, 8.0, 72.0, state)

        seeds = encoder.GenerateNeuralSeed(raw_data, progress_callback=enc_cb)
        state_config = encoder.CaptureDeterministicState()

        desc = f"{base_name} — Neural DNA payload"
        manifest = {
            original_hash: {
                "seeds": seeds,
                "description": desc,
                "size": original_size,
            }
        }

        state.set_params(
            seed_block_count=len(seeds),
            encoder_block_size=state_config.get("block_size"),
            decimal_precision=state_config.get("precision"),
            encoder_model=state_config.get("model"),
            encoder_engine=state_config.get("engine"),
            encoder_state_hash=state_config.get("state_hash"),
            manifest_description=desc,
        )
        state.log(f"Seeds={len(seeds)} blocks block_size={state_config.get('block_size')}")

        state.update(pct=74.0, operation="Manifest & device placement")
        auto_mgmt = AutonomousSeedManagement(manifest)
        coord = auto_mgmt.SemanticIndexing(desc)
        state.set_params(semantic_coord=coord or "(no match)")
        state.log(f"Semantic coord={coord}")

        devices = build_devices(num_devices)
        state.set_devices(devices)
        state.log(f"P2P placement simulation: {len(devices)} nodes")
        auto_mgmt.SelfHealingMonitor(devices)
        time.sleep(2)
        state.log(f"Self-heal sample done (alarm>{HEAL_ALARM_THRESHOLD_MS}ms)")

        state.store_session(
            seeds=seeds,
            state_config=state_config,
            original_hash=original_hash,
            original_size=original_size,
            is_folder=is_folder,
            base_name=base_name,
            desc=desc,
        )

        ok, msg = persist_session_to_disk(state)
        if ok:
            state.log(f"Session persisted: {msg}")
        else:
            state.log(f"Session disk write skipped: {msg}", level="warn")

        with state._lock:
            state.encoding_complete = True
        state.set_workflow(Workflow.ENCODED.value)
        state.update(
            pct=100.0,
            operation="Encode complete — ready to summon",
            done=True,
            error=None,
        )
        state.log("ENCODE complete — memory + disk session ready for summon")
    except Exception as e:
        state.log(f"ENCODE error: {e}", level="error")
        state.set_workflow(Workflow.FAILED.value)
        with state._lock:
            state.encoding_complete = False
            state._session = {}
        _unlink_session_file()
        state.update(error=str(e), done=True, pct=100.0, operation="Encode failed")
    finally:
        if auto_mgmt is not None:
            auto_mgmt.StopMonitor()
        state.set_running(False)


def run_summon_phase(state: PipelineState):
    restore_dir = ROOT / "restore"
    sess = state.load_session()
    if not sess:
        state.log("SUMMON blocked: no session", level="error")
        with state._lock:
            corrupt = state.encoding_complete
        state.set_workflow(Workflow.FAILED.value if corrupt else Workflow.IDLE.value)
        state.update(
            error="No session — encode first or load saved session",
            done=True,
            pct=100.0,
            operation="Summon blocked",
        )
        state.set_running(False)
        return

    try:
        state.set_workflow(Workflow.SUMMONING.value)
        state.summon_complete = False
        state.error = None
        state.result_path = None
        state.update(pct=2.0, operation="Summon — initializing", done=False)

        seeds = sess["seeds"]
        state_config = sess["state_config"]
        original_hash = sess["original_hash"]
        original_size = sess["original_size"]
        is_folder = sess["is_folder"]
        base_name = sess["base_name"]

        state.log(
            f"SUMMON bytes={original_size} blocks={len(seeds)} sha256={original_hash[:16]}…"
        )

        resurrect_engine = DeterministicResurrection(state_config)
        resurrect_engine.InitializeResurrector(seeds)

        def dec_cb(done, total):
            _map_decode(done, total, 5.0, 88.0, state)

        reconstructed = resurrect_engine.BitPerfectReconstruction(
            seeds, original_size, progress_callback=dec_cb
        )

        if not resurrect_engine.IntegrityFinalMatch(reconstructed, original_hash):
            state.log("SUMMON integrity FAILED", level="error")
            state.set_workflow(Workflow.ENCODED.value)
            state.update(
                error="integrity_mismatch",
                done=True,
                pct=100.0,
                operation="Summon failed — session unchanged, retry allowed",
            )
            return

        state.set_params(reconstructed_sha256=hashlib.sha256(reconstructed).hexdigest())
        state.log("Integrity OK (bit-perfect)")

        os.makedirs(restore_dir, exist_ok=True)

        if not is_folder:
            final_output = os.path.join(restore_dir, base_name)
            with open(final_output, "wb") as f:
                f.write(reconstructed)
        else:
            bio = io.BytesIO(reconstructed)
            with tarfile.open(fileobj=bio, mode="r") as tar:
                if sys.version_info >= (3, 12):
                    tar.extractall(path=str(restore_dir), filter="data")
                else:
                    tar.extractall(path=str(restore_dir))
            final_output = os.path.join(restore_dir, base_name)

        abs_out = os.path.abspath(final_output)
        state.set_params(output_path=abs_out)
        state.log(f"Written {abs_out}")

        with state._lock:
            state.summon_complete = True
        state.set_workflow(Workflow.RESTORED.value)
        state.update(
            pct=100.0,
            operation="Restore complete",
            result_path=abs_out,
            done=True,
            error=None,
        )
    except Exception as e:
        state.log(f"SUMMON error: {e}", level="error")
        state.set_workflow(Workflow.ENCODED.value)
        state.update(error=str(e), done=True, pct=100.0, operation="Summon error — retry allowed")
    finally:
        state.set_running(False)


def run_pipeline(source_path: str, is_folder: bool, num_devices: int, state: PipelineState):
    state.reset()
    run_encoding_phase(source_path, is_folder, num_devices, state)
    if not state.encoding_complete:
        return
    state.update(done=False, error=None, result_path=None)
    run_summon_phase(state)
