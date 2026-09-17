import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{64}\.(pdf|png|json)", key):
            raise ValueError("Invalid storage key")
        return self.root / key

    def put(self, data: bytes, suffix: str) -> str:
        key = f"{digest(data)}.{suffix}"
        target = self.path(key)
        if target.exists():
            if digest(target.read_bytes()) != digest(data):
                raise OSError("Artifact hash mismatch")
            return key
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".pending-")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return key
