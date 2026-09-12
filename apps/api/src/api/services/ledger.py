import hashlib
import json
from datetime import UTC, datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# SIMULATED-by-design: ephemeral keypair generated at process startup.
# Signatures cannot be verified across server restarts.
# Replace by loading a persistent key from env/secrets (HSM/KMS) when production-ready.
_private_key: Ed25519PrivateKey = Ed25519PrivateKey.generate()

GENESIS_HASH = "0" * 64
# Advisory lock key — prevents concurrent writes from forking the hash-chain.
_LOCK_KEY = 3826459712


async def append_event(
    db: AsyncSession,
    event_type: str,
    payload: dict,  # type: ignore[type-arg]
    data_class: str = "SIMULATED-by-design",
) -> str:
    """Append event to the hash-chain. Returns the hash of the new entry.

    Serialised with a pg_advisory_xact_lock so concurrent transactions
    cannot produce two entries with the same prev_hash.
    data_class must be one of: REAL | SIMULATED-by-design | PENDING-WIRE.
    """
    await db.execute(text(f"SELECT pg_advisory_xact_lock({_LOCK_KEY})"))

    prev_result = await db.execute(
        text("SELECT hash FROM ledger_entry ORDER BY id DESC LIMIT 1")
    )
    prev_row = prev_result.first()
    prev_hash = str(prev_row[0]) if prev_row else GENESIS_HASH

    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    raw = f"{event_type}|{payload_json}|{prev_hash}"
    entry_hash = hashlib.sha256(raw.encode()).hexdigest()
    signature = _private_key.sign(entry_hash.encode()).hex()

    await db.execute(
        text("""
            INSERT INTO ledger_entry
                (event_type, payload, prev_hash, hash, signature, data_class, created_at)
            VALUES
                (:event_type, :payload, :prev_hash, :hash, :signature, :data_class, :created_at)
        """),
        {
            "event_type": event_type,
            "payload": payload_json,
            "prev_hash": prev_hash,
            "hash": entry_hash,
            "signature": signature,
            "data_class": data_class,
            "created_at": datetime.now(UTC),
        },
    )
    return entry_hash
