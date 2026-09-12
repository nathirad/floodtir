from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.verification import LedgerEntryOut, VerificationCreate, VerificationOut
from api.services import verify as verify_svc

router = APIRouter(tags=["verification"])

DBDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/work-orders/{wo_id}/verify", response_model=VerificationOut, status_code=201)
async def verify_work_order(
    wo_id: int, body: VerificationCreate, db: DBDep
) -> VerificationOut:
    v_id, created_at, new_wo_id = await verify_svc.create_verification(
        db,
        wo_id=wo_id,
        outcome=body.outcome,
        verified_by=body.verified_by,
        photo_ref=body.photo_ref,
    )
    return VerificationOut(
        id=v_id,
        work_order_id=wo_id,
        outcome=body.outcome,
        verified_by=body.verified_by,
        photo_ref=body.photo_ref,
        created_at=created_at,
        new_work_order_id=new_wo_id,
    )


@router.get("/ledger", response_model=list[LedgerEntryOut])
async def list_ledger(db: DBDep) -> list[LedgerEntryOut]:
    result = await db.execute(
        text(
            "SELECT id, event_type, payload, prev_hash, hash, data_class, created_at "
            "FROM ledger_entry ORDER BY id ASC"
        )
    )
    return [
        LedgerEntryOut(
            id=int(row[0]),
            event_type=str(row[1]),
            payload=str(row[2]),
            prev_hash=str(row[3]),
            hash=str(row[4]),
            data_class=str(row[5]),
            created_at=row[6],
        )
        for row in result.all()
    ]
