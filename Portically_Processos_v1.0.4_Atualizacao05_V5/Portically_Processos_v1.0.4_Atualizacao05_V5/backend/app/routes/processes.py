from fastapi import APIRouter, HTTPException
router = APIRouter()

@router.get("/processes")
def processes():
    raise HTTPException(410, "Archived demonstration retired; use the protected current application")
