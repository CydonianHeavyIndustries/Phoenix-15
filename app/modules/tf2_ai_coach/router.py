from fastapi import APIRouter, Body
from .telemetry import latest_telemetry, read_advice, handle_post_telemetry

router = APIRouter(prefix="/tf2/coach", tags=["tf2_coach"])


@router.get("/advice")
def get_advice():
    return {
        "telemetry": latest_telemetry() or {},
        "coach": read_advice(),
    }


@router.get("/telemetry")
def get_telemetry():
    return latest_telemetry() or {}


@router.post("/telemetry")
def post_telemetry(payload: dict = Body(...)):
    return handle_post_telemetry(payload)
