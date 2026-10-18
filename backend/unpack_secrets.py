"""Deploy helper: unpack the Oracle wallet from env vars onto disk before the server starts.

Railway variables are capped at 32768 characters, so the wallet zip (base64) may be split across
ORACLE_WALLET_B64_1, _2, ... Does nothing when no wallet variable is set (local runs)."""
import base64
import io
import os
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def wallet_b64() -> str:
    whole = os.getenv("ORACLE_WALLET_B64", "").strip()
    if whole:
        return whole
    parts, i = [], 1
    while os.getenv(f"ORACLE_WALLET_B64_{i}"):
        parts.append(os.environ[f"ORACLE_WALLET_B64_{i}"].strip())
        i += 1
    return "".join(parts)


def main() -> None:
    data = wallet_b64()
    if not data:
        print("[unpack] no ORACLE_WALLET_B64 set, skipping")
        return
    target = Path(os.getenv("ORACLE_WALLET_DIR", "backend/wallet")).expanduser()
    if not target.is_absolute():
        target = REPO_ROOT / target
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(data))) as zf:
        zf.extractall(target)
    print(f"[unpack] wallet files written to {target}: {sorted(p.name for p in target.iterdir())}")


if __name__ == "__main__":
    main()
