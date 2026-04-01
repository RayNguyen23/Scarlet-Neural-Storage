# Scarlet Neural Storage (Neural DNA Engine)

**Author / maintainer:** [RayNguyen23](https://github.com/RayNguyen23) — see `AUTHORS`  
**Version:** 1.2-Final (Integer-Strict Edition)  
**License:** [MIT](LICENSE)

Deterministic **integer arithmetic coding** pipeline: binary payloads are mapped to large-integer **seeds** per block and reconstructed with **bit-perfect** fidelity (SHA-256 check). Ships with a **desktop UI** (Eel), a **two-phase workflow** (encode → summon), optional **session persistence** under `.scarlet/`, and a **simulated** P2P/self-healing layer for experiments.

---

## Mathematics and core algorithms

### 1. Fixed-range integer arithmetic coding

The codec treats the payload as a sequence of bytes (symbols in alphabet \(\mathcal{A} = \{0,\ldots,255\}\), so \(|\mathcal{A}| = q = 256\)).

An **integer interval** \([L, H)\) is maintained with **exact integer arithmetic** (implemented with `decimal.Decimal` and **floor division** `//` only on the encode/decode path—no `float` or `round()` in those updates, so behavior is stable across platforms).

**Initial range.** Before each block of up to \(B = 128\) bytes:

\[
L_0 = 0,\quad H_0 = R,\quad R = 10^{800}.
\]

Using a huge \(R\) keeps the subinterval width from collapsing to zero under \(B\) successive refinements.

**Refinement for one byte** \(b \in \{0,\ldots,255\}\). Let \(w = H - L\). The encoder narrows the interval with:

\[
H \leftarrow L + \left\lfloor \frac{w \cdot (b+1)}{q} \right\rfloor,\qquad
L \leftarrow L + \left\lfloor \frac{w \cdot b}{q} \right\rfloor.
\]

This is the standard **partition of \([L,H)\) into 256 subintervals** using integer endpoints, so every step is **reversible** when the decoder applies the same recurrence.

**Pure-low seed.** After processing all bytes in the block, the **seed** stored for that block is the **lower endpoint** \(L\) (as a decimal string). Storing the low bound avoids ambiguity from midpoint rounding strategies.

### 2. Decoding (summon): binary search per byte

The decoder holds the same \([L_0,H_0) = [0,R)\). For each output byte it knows the target value \(V\) equals the encoder’s stored \(L\) at the end of the block, but **incrementally** it must recover each byte by matching subintervals.

For current \([L,H)\) with width \(w = H-L\), the smallest threshold for symbol \(m\) is:

\[
T(m) = L + \left\lfloor \frac{w \cdot m}{q} \right\rfloor.
\]

The correct byte is the **largest** \(m \in \{0,\ldots,255\}\) such that \(T(m) \le V\). The implementation finds this with **binary search** on \(m\) (8–9 steps per byte), then applies the same \((L,H)\) update as the encoder for that \(m\). Repeating for each byte in the block reproduces the original byte string **exactly** when \(V\) is the true seed.

### 3. Block structure

- **`block_size` \(B = 128\)** bytes per seed (last block may be shorter).
- **`INT_RANGE` \(R = 10^{800}\)** is shared by encoder and decoder and must not diverge.
- **`base` \(q = 256\)** matches byte alphabet size.

### 4. Integrity: SHA-256

Before encoding, the raw payload bytes \(X\) are fingerprinted:

\[
h = \mathrm{SHA256}(X).
\]

After reconstruction \(X'\), acceptance requires \( \mathrm{SHA256}(X') = h \). Mismatch aborts summon with an error (session left in `encoded` state for retry).

### 5. Codec fingerprint (`state_hash`)

`CaptureDeterministicState` records `model` (engine version string), `block_size`, `precision`, and a **SHA-256 hash of the version string** used to ensure the resurrector agrees with the encoder configuration before decode.

### 6. Shannon entropy (utility)

`AnalyzeEntropy` computes, for empirical byte frequencies \(p_i\):

\[
H = -\sum_i p_i \log_2 p_i
\]

(in bits per symbol). It is **informational** in this codebase and does not change the coding intervals.

### 7. Semantic index (simulation)

For a description string \(d\), a 16-hex “coordinate” is:

\[
\text{coord} = \mathrm{hex}\big(\mathrm{SHA256}(d_{\text{lower}})\big)_{0..15}.
\]

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
- Encoder and decoder must share **\(R\)**, **\(B\)**, and **\(q\)**.

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
