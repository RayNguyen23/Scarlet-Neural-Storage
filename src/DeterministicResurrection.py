import hashlib
from decimal import Decimal, getcontext


class DeterministicResurrection:
    def __init__(self, state_config):
        self.config = state_config
        getcontext().prec = 1000
        self.block_size = state_config.get("block_size", 128)
        self.base = 256
        self.is_ready = False

    def InitializeResurrector(self, seeds):
        print(f"Resurrect init model={self.config['model']} seeds={len(seeds)}")

        current_state_hash = hashlib.sha256(str(self.config["model"]).encode()).hexdigest()
        if current_state_hash == self.config["state_hash"]:
            self.is_ready = True
            print(f"Resurrect ready blocks={len(seeds)}")
        else:
            raise Exception("Resurrect aborted: AI state_hash mismatch")

    def BitPerfectReconstruction(self, seeds, original_size, progress_callback=None):
        if not self.is_ready:
            raise Exception("Resurrector not initialized")

        print(f"Reconstructing bytes={original_size} blocks={len(seeds)}")
        reconstructed_data = bytearray()
        total_seeds = len(seeds)
        report_every = max(1, total_seeds // 200) if total_seeds else 1

        INT_RANGE = Decimal(10) ** 800

        for idx, seed_str in enumerate(seeds):
            low = Decimal(0)
            high = INT_RANGE

            current_value = Decimal(seed_str)

            bytes_to_read = self.block_size
            if (idx + 1) * self.block_size > original_size:
                bytes_to_read = original_size % self.block_size

            for _ in range(bytes_to_read):
                width = high - low

                byte_val = 0
                start, end = 0, 255
                while start <= end:
                    mid = (start + end) // 2
                    threshold = low + (width * mid) // self.base

                    if threshold <= current_value:
                        byte_val = mid
                        start = mid + 1
                    else:
                        end = mid - 1

                reconstructed_data.append(byte_val)

                high = low + (width * (byte_val + 1)) // self.base
                low = low + (width * byte_val) // self.base

            if progress_callback and (
                idx % report_every == 0 or idx == total_seeds - 1
            ):
                progress_callback(idx + 1, total_seeds)

        return bytes(reconstructed_data)

    def IntegrityFinalMatch(self, reconstructed_data, original_hash):
        print(f"Integrity check sha256_expected={original_hash[:16]}...")
        current_hash = hashlib.sha256(reconstructed_data).hexdigest()

        if current_hash == original_hash:
            print(f"Integrity ok hash={current_hash}")
            return True
        else:
            print(f"Integrity fail expected={original_hash} actual={current_hash}")
            return False
