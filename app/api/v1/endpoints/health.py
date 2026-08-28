# ruff: noqa: B008  - FastAPI Depends() in argument defaults is the documented idiom
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db

router = APIRouter()


@router.get("")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail="database unreachable") from e
    return {"status": "ok"}
