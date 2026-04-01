# Scarlet Neural Storage (Neural DNA Engine)

**Author / maintainer:** [RayNguyen23](https://github.com/RayNguyen23) — see `AUTHORS`  
**Version:** 1.2-Final (Integer-Strict Edition)  
**License:** [MIT](LICENSE)

Deterministic **integer arithmetic coding** pipeline: binary payloads are mapped to large-integer **seeds** per block and reconstructed with **bit-perfect** fidelity (SHA-256 check). Ships with a **desktop UI** (Eel), a **two-phase workflow** (encode → summon), optional **session persistence** under `.scarlet/`, and a **simulated** P2P/self-healing layer for experiments.

---

## Mathematics and core algorithms

Notation below uses plain text and code so it renders the same in GitHub, editors, and terminals (no LaTeX required).

### 1. Fixed-range integer arithmetic coding

The codec treats the payload as a sequence of bytes: alphabet **A** is all byte values **0 .. 255**, alphabet size **q = 256**.

An **integer half-open interval** `[L, H)` is maintained with **exact integer arithmetic** (via `decimal.Decimal` and floor division `//` on the encode/decode path only—no `float` or `round()` there, so behavior is stable across platforms).

**Initial range.** Before each block of up to **B = 128** bytes:

```text
L := 0
H := R
R := 10**800   (same as 10^800; a huge integer range)
```

A very large **R** keeps the interval width from collapsing to zero after **B** refinement steps.

**Refinement for one byte** `b` in `0 .. 255`. Let `w = H - L`. The encoder updates:

```text
H := L + (w * (b + 1)) // q
L := L + (w * b) // q
```

(`//` is integer floor division, matching the Python implementation.)

This **partitions `[L, H)` into 256 subintervals** with integer endpoints; the decoder applies the same recurrence, so each step is **reversible**.

**Pure-low seed.** After all bytes in the block, the stored **seed** is the **lower endpoint** `L` (as a decimal string). Using the low bound avoids ambiguity from midpoint-style rounding.

### 2. Decoding (summon): binary search per byte

The decoder starts with `[L, H) = [0, R)`. The target value **V** is the encoder’s final `L` for the block; each output byte is recovered by matching subintervals.

For current `[L, H)` with `w = H - L`, the left edge of the subinterval for symbol **m** is:

```text
T(m) = L + (w * m) // q
```

The emitted byte is the **largest** `m` in `0 .. 255` such that `T(m) <= V`. The code uses **binary search** on `m` (about 8 to 9 steps per byte), then applies the same `(L, H)` update as the encoder for that `m`. Repeating for the whole block recovers the original bytes **exactly** when **V** is the true seed.

### 3. Block structure

- **`block_size` B = 128** bytes per seed (last block may be shorter).
- **`INT_RANGE` R = 10^800** must match in encoder and decoder.
- **`base` q = 256** (one symbol per byte).

### 4. Integrity: SHA-256

For payload bytes **X**:

```text
h = SHA256(X)
```

After reconstruction **X'**, require **SHA256(X') = h**. On mismatch, summon aborts (session can stay in `encoded` for retry).

### 5. Codec fingerprint (`state_hash`)

`CaptureDeterministicState` records `model` (engine version string), `block_size`, `precision`, and a **SHA-256 hash of the version string** so the resurrector agrees with the encoder configuration before decode.

### 6. Shannon entropy (utility)

For empirical byte frequencies **p_i** (proportion of byte value *i*):

```text
H = -sum_i(p_i * log2(p_i))    (bits per symbol; 0*log2(0) treated as 0)
```

This is **informational** only; it does not change the coding intervals.

### 7. Semantic index (simulation)

For description string **d**, a 16-hex “coordinate” is the first 16 hex digits of **SHA256**(lowercase **d**):

```text
coord = hex(SHA256(d_lower))[0:16]
```

This is a **deterministic hash tag**, not a learned embedding.

### 8. Self-healing loop (simulation)

Device records carry a baseline latency; a background thread adds jitter, compares to a fixed **150 ms** threshold, and prints a **simulated** migration to the lowest-latency peer. No network I/O.

---

## What this project does (operational)

1. **Encode:** Read file or TAR-pack folder → SHA-256 → integer-strict block encoding → manifest + semantic tag + device table + short monitor → session in RAM + `.scarlet/neural_session.pkl`.  
2. **Summon:** Read session → decode blocks → SHA-256 check → write `restore/` (file or extracted TAR; Python 3.12+ uses `tarfile.extractall(..., filter="data")`).  
3. **Workflow:** `idle` → `encoding` → `encoded` → `summoning` → `restored`; encode failure → `failed`; summon failure → stay `encoded` for retry.

---

## Repository layout

| Path | Role |
|------|------|
| `main.py` | Entry: GUI by default, `--cli` for one-shot encode+summon |
| `src/NeuralEncoding.py` | Encoder: `GenerateNeuralSeed`, `CaptureDeterministicState`, optional progress callback |
| `src/DeterministicResurrection.py` | Decoder: `BitPerfectReconstruction`, `IntegrityFinalMatch` |
| `src/AutonomousSeedManagement.py` | Manifest semantic index + threaded self-healing simulation |
| `view/pipeline.py` | `PipelineState`, encode/summon phases, pickle session I/O, `run_pipeline` |
| `view/app.py` | Eel server: `get_state`, `start_encoding`, `start_summon`, reset/load/save session, Finder |
| `view/web/` | `index.html`, `style.css`, `app.js` |
| `tests/test_roundtrip.py` | Automated round-trip check |
| `.scarlet/` | Runtime session pickle (gitignored) |
| `restore/` | Restored output |

---

## Requirements

- **Python 3.10+** (3.12+ recommended for safer `tarfile` extraction)
- **Dependencies:** `eel` (`requirements.txt`)
- **GUI:** Tk for dialogs; Chrome/Chromium for Eel
- **`open_in_finder`** is **macOS-specific**; port with `xdg-open` / `explorer` on other OSes

---

## Installation

```bash
git clone <repository-url>
cd <your-clone-directory>
pip install -r requirements.txt
```

---

## How to use

### Desktop application

```bash
python3 main.py
```

1. **Encode:** Pick file/folder, set node count, **Run encoding** until **Session ready**.  
2. **Summon:** **Run summon & restore**; **Open in Finder** (macOS) for output under `restore/`.  
3. **Footer:** **Load session** (after restart), **Save session**, **Reset workspace**.

### Headless CLI

Set `PATH` and `DEVICES` in `main.py`, then:

```bash
python3 main.py --cli
```

### Programmatic

```python
from view.pipeline import pipeline_state, run_encoding_phase, run_summon_phase

pipeline_state.reset()
run_encoding_phase("/path/to/file", False, 3, pipeline_state)
if pipeline_state.encoding_complete:
    run_summon_phase(pipeline_state)
```

---

## How to test

```bash
python3 tests/test_roundtrip.py
```

Expect `OK round-trip 2048 bytes` and exit code `0`. For UI runs, compare `shasum -a 256` on source vs `restore/<basename>`.

---

## Security and operations

- **`.scarlet/neural_session.pkl` equals your payload** to anyone who can read it—protect like a key.  
- **Untrusted archives:** validate paths before extract in production.  
- **Semantic index / self-heal:** illustrative only, not production P2P.

---

## Contributor rules (codec)

- Keep **integer floor division** in interval updates; floats/`round()` there can **break** bit-identical decode.  
- Encoder and decoder must share the same **R**, **B**, and **q** (`INT_RANGE`, `block_size`, alphabet size 256).

---

## Roadmap

- Rust / libp2p transport  
- External metadata store  
- FFI around the integer codec core

---

## Contributing

Issues and PRs welcome. Contributions are licensed under the **MIT License** (`LICENSE`).

---

## Credit

**Scarlet Neural Storage** — **RayNguyen23**. Preserving the `LICENSE` copyright notice and author attribution is appreciated.
