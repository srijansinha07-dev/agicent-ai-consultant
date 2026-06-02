from __future__ import annotations

from fastapi import APIRouter, Header

from config import CONSULTATION_ADMIN_KEY
from models import ConsultationCreateRequest, ConsultationCreateResponse
from services.consultations_service import create_consultation_request, list_consultations

router = APIRouter(prefix="/api/consultations", tags=["consultations"])


@router.post("", response_model=ConsultationCreateResponse)
async def create_consultation(
    req: ConsultationCreateRequest,
    x_user_id: str = Header(None),
):
    try:
        consultation_id, summary = create_consultation_request(
            user_id=x_user_id,
            name=req.name,
            email=req.email,
            company=req.company,
            project_description=req.project_description,
            budget=req.budget,
            timeline=req.timeline,
            conversation_history=req.conversation_history,
            session_id=req.session_id,
        )

        return ConsultationCreateResponse(
            ok=True,
            consultation_id=consultation_id,
            summary=summary,
            error=None,
        )
    except Exception as e:
        return ConsultationCreateResponse(ok=False, error=str(e))


@router.get("", response_model=list[dict])
async def list_consultations_for_staff(
    x_admin_key: str = Header(None),
):
    if CONSULTATION_ADMIN_KEY and x_admin_key != CONSULTATION_ADMIN_KEY:
        # Avoid leaking stored intakes.
        return []
    return list_consultations()

