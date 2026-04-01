import math
import hashlib
from decimal import Decimal, getcontext


class NeuralEncoding:
    def __init__(self, ai_model_version="Ray-Neural-v1.2-Final"):
        self.model_version = ai_model_version
        self.block_size = 128
        self.base = 256
        getcontext().prec = 1000
        self.frozen_state = {}

    def AnalyzeEntropy(self, data):
        if not data:
            return 0
        byte_counts = {}
        for byte in data:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1
        entropy = 0
        total_len = len(data)
        for count in byte_counts.values():
            p = count / total_len
            entropy -= p * math.log2(p)
        return entropy

    def GenerateNeuralSeed(self, binary_data, progress_callback=None):
        seeds = []
        total_len = len(binary_data)
        total_blocks = (total_len + self.block_size - 1) // self.block_size if total_len else 0
        report_every = max(1, total_blocks // 200) if total_blocks else 1
        INT_RANGE = Decimal(10) ** 800

        print(f"Seeding bytes={total_len} block_size={self.block_size}")

        block_idx = 0
        for i in range(0, total_len, self.block_size):
            block = binary_data[i : i + self.block_size]

            low = Decimal(0)
            high = INT_RANGE

            for byte in block:
                width = high - low

                if width < self.base:
                    print(f"[WARN] range_too_narrow byte_offset={i}")

                high = low + (width * (byte + 1)) // self.base
                low = low + (width * byte) // self.base

            seeds.append(str(low))

            if progress_callback and (
                block_idx % report_every == 0 or block_idx == total_blocks - 1
            ):
                done = min(i + len(block), total_len)
                progress_callback(done, total_len)
            block_idx += 1

        print(f"Seeding done seeds={len(seeds)}")
        return seeds

    def CaptureDeterministicState(self):
        self.frozen_state = {
            "model": self.model_version,
            "precision": getcontext().prec,
            "block_size": self.block_size,
            "engine": "Integer-Fixed-Range-V6-Strict",
            "state_hash": hashlib.sha256(str(self.model_version).encode()).hexdigest(),
        }
        return self.frozen_state
