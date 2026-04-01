# Scarlet Neural Storage (Neural DNA Engine)

**Author / maintainer:** [RayNguyen23](https://github.com/RayNguyen23) — see `AUTHORS`  
**Version:** 1.2-Final (Integer-Strict Edition)  
**License:** [MIT](LICENSE)

Deterministic **arithmetic coding** pipeline that maps binary payloads to large-integer **neural seeds** and reconstructs them with **bit-perfect** fidelity (verified by SHA-256). Includes a **desktop UI** (Eel), a **two-phase production workflow** (encode → summon), optional **session persistence** on disk, and a **simulated** P2P/self-healing layer for demos.

---

## What this project does

1. **Neural encoding (Step 1)**  
   Reads a file or packs a folder as TAR bytes, fingerprints with SHA-256, runs **integer-only arithmetic coding** (`Decimal` with floor division, no floats on the critical path) to produce a list of **seed strings** per fixed-size block (`block_size` 128). Builds a **manifest**, runs **semantic indexing** (hash-based coordinate from description), registers **simulated devices**, and runs a short **self-healing monitor** (latency jitter + fake replication).  
   The full session (seeds + codec metadata + sizes + paths) is kept **in memory** and also written to **`.scarlet/neural_session.pkl`** after a successful encode (atomic write via temp file).

2. **Summon (Step 2)**  
   Reconstructs bytes from the in-memory session (or after **Load session** from disk), runs **binary search** per byte in the integer range to invert the encoder, checks **SHA-256** against the original fingerprint, and writes output under **`restore/`** (single file or extracted TAR for folders). Python 3.12+ uses `tarfile.extractall(..., filter="data")` for safer extraction.

3. **Workflow state machine**  
   `idle` → `encoding` → `encoded` → `summoning` → `restored`. Encode failure → `failed` and session cleared. Summon failure (e.g. integrity) returns to `encoded` so you can **retry summon** without re-encoding.

---

## Repository layout

| Path | Role |
|------|------|
| `main.py` | Entry: GUI by default, `--cli` for one-shot encode+summon |
| `src/NeuralEncoding.py` | Encoder: `GenerateNeuralSeed`, `CaptureDeterministicState`, optional progress callback |
| `src/DeterministicResurrection.py` | Decoder: `BitPerfectReconstruction`, `IntegrityFinalMatch` |
| `src/AutonomousSeedManagement.py` | Manifest semantic index + threaded self-healing demo |
| `view/pipeline.py` | `PipelineState`, encode/summon phases, pickle session I/O, CLI `run_pipeline` |
| `view/app.py` | Eel server: `get_state`, `start_encoding`, `start_summon`, reset/load/save session, Finder |
| `view/web/` | `index.html`, `style.css`, `app.js` — UI |
| `tests/test_roundtrip.py` | Automated round-trip check |
| `.scarlet/` | Created at runtime; `neural_session.pkl` (gitignored) |
| `restore/` | Restored output (you may gitignore locally) |

---

## Requirements

- **Python 3.10+** (3.12+ recommended for safer `tarfile` extraction)
- **Dependencies:** `eel` (see `requirements.txt`)
- **GUI:** Tk (usually bundled with Python) for file/folder dialogs; **Chrome/Chromium** for Eel’s window
- **`open_in_finder`** in `view/app.py` is **macOS-specific**; on Linux/Windows replace with `xdg-open` / `explorer` if you port the helper

---

## Installation

```bash
git clone <your-fork-or-upstream-url>
cd "Decentralized data center"
pip install -r requirements.txt
```

---

## How to use

### Desktop application (default)

```bash
python3 main.py
```

1. **Step 1 — Encode:** Choose **File** or **Folder**, set **Simulated P2P nodes**, click **Run encoding**. Wait until the badge shows **Session ready**.  
2. **Step 2 — Summon:** Click **Run summon & restore**. On success, use **Open in Finder** (macOS) for the restored path under `restore/`.  
3. **Footer:**  
   - **Load session** — reads `.scarlet/neural_session.pkl` into RAM (e.g. after restarting the app).  
   - **Save session** — writes pickle again (redundant if encode already persisted).  
   - **Reset workspace** — clears memory session, log context, and deletes the pickle file.

### Headless CLI

Edit `PATH` and `DEVICES` in `main.py`, then:

```bash
python3 main.py --cli
```

Runs `run_pipeline`: full reset → encode → summon in one process, using `len(DEVICES)` as the device count.

### Programmatic use

```python
from view.pipeline import pipeline_state, run_encoding_phase, run_summon_phase

pipeline_state.reset()
run_encoding_phase("/path/to/file", False, 3, pipeline_state)
if pipeline_state.encoding_complete:
    run_summon_phase(pipeline_state)
```

---

## How to test

**Quick automated test** (creates a temp file, round-trips through encode+summon, asserts bytes and hash):

```bash
cd /path/to/repo
python3 tests/test_roundtrip.py
```

Expect: `OK round-trip 2048 bytes` and exit code `0`.

**Manual UI test:** Run `python3 main.py`, encode a small file, summon, compare source and `restore/<basename>` with `shasum -a 256`.

**Large payload:** Encoding is CPU-heavy (`Decimal` per byte per block); start with small files, then scale.

---

## Security and operations notes

- **`.scarlet/neural_session.pkl` is equivalent to your payload** for anyone who can read it. Treat like a secret; add `.scarlet/` to `.gitignore` (already in this repo).  
- **Do not extract untrusted TARs** in production without path checks; Python 3.12+ `filter="data"` reduces some traversal risk.  
- **Semantic indexing** here is a **demonstration** (SHA-256 prefix of description), not a real embedding model.  
- **Self-healing** is **simulated** (prints + sleep), not real P2P.

---

## Algorithm constraints (for contributors)

- Keep **integer floor division (`//`)** in encode/decode width updates. Introducing `float` or `round()` in those paths can **break SHA-256 parity**.  
- Encoder and decoder must share the same **`INT_RANGE`** (`10**800`), **`block_size`**, and **`base`** (256).

---

## Roadmap (from original design intent)

- Rust / **libp2p** transport for real decentralized shards  
- External metadata store (e.g. Cassandra)  
- FFI boundary around the integer codec core

---

## Contributing

Issues and PRs are welcome. Please keep changes focused and preserve deterministic round-trips. By contributing, you agree your contributions are licensed under the **MIT License** as in `LICENSE`.

---

## Credit

**Scarlet Neural Storage** — created and maintained by **RayNguyen23**. If you use this project, preserving the copyright line in `LICENSE` and a link or mention of the author is appreciated.
