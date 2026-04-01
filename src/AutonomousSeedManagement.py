import time
import hashlib
import threading
import random


class AutonomousSeedManagement:
    def __init__(self, master_manifest):
        self.manifest = master_manifest
        self.semantic_index = {}
        self.device_health = {}
        self.running_monitor = False

    def SemanticIndexing(self, file_content_desc):
        semantic_vector = hashlib.sha256(file_content_desc.lower().encode()).hexdigest()[:16]

        for file_hash in self.manifest:
            if self.manifest[file_hash].get("description") == file_content_desc:
                self.semantic_index[semantic_vector] = file_hash
                print(f"Semantic index coord={semantic_vector} desc_len={len(file_content_desc)}")
                return semantic_vector

        return None

    def SelfHealingMonitor(self, devices):
        self.device_health = {d["id"]: d["latency"] for d in devices}
        self.running_monitor = True

        def monitor_loop():
            print("SelfHealing monitor active")
            while self.running_monitor:
                for dev_id, latency in self.device_health.items():
                    current_latency = latency + random.uniform(-10, 50)

                    if current_latency > 150:
                        print(f"[ALARM] device={dev_id} latency_ms={current_latency:.2f}")
                        self._trigger_replication(dev_id)

                time.sleep(5)

        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()

    def _trigger_replication(self, weak_device_id):
        target_device = min(self.device_health, key=self.device_health.get)

        if target_device != weak_device_id:
            print(f"Healing migrate from={weak_device_id} to={target_device}")
            time.sleep(1)
            print("Healing done")

    def StopMonitor(self):
        self.running_monitor = False
