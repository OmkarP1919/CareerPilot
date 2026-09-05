import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.discovery import (
    DiscoveryReport,
    JobFilterRequest,
    SavedSearchCreate,
    SavedSearchResponse,
    SavedSearchRunResponse,
    SavedSearchUpdate,
)
from app.services import discovery_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs/discovery", tags=["discovery"])


@router.post("/filtered", response_model=DiscoveryReport)
def filtered_discovery(
    request: JobFilterRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unified, source-selectable, deduplicated filtered job discovery."""
    try:
        return discovery_service.run_filtered_search(user.id, db, request)
    except Exception:
        logger.exception("Filtered discovery failed for user %s", user.id)
        raise HTTPException(
            status_code=500,
            detail="We couldn't finish finding jobs right now. Please try again.",
        )


@router.get("/sources", response_model=dict)
def list_sources(user: User = Depends(get_current_user)):
    """Return the available job source names for selection."""
    return {"sources": list(discovery_service.ALL_SOURCE_NAMES)}


# ---------------------------------------------------------------------------
# Saved searches
# ---------------------------------------------------------------------------


def _build_saved_search_response(saved) -> SavedSearchResponse:
    """Build a SavedSearchResponse from the ORM row.

    SavedSearch.criteria and SavedSearch.last_seen_keys are stored as JSON text;
    the API contract exposes them as strongly typed fields (criteria dict /
    last_seen_count int). Parse the JSON before constructing the response so
    Pydantic never validates the raw string.
    """
    criteria = discovery_service._safe_json_loads(saved.criteria, {})
    if not isinstance(criteria, dict):
        criteria = {}
    last_seen_keys = discovery_service._safe_json_loads(saved.last_seen_keys, []) or []
    if not isinstance(last_seen_keys, list):
        last_seen_keys = []
    return SavedSearchResponse(
        id=saved.id,
        name=saved.name,
        criteria=criteria,
        last_run_at=saved.last_run_at,
        last_seen_count=len(last_seen_keys),
        created_at=saved.created_at,
        updated_at=saved.updated_at,
    )


@router.get("/saved-searches", response_model=list[SavedSearchResponse])
def list_saved_searches(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    saved = discovery_service.list_saved_searches(user.id, db)
    return [_build_saved_search_response(s) for s in saved]


@router.post("/saved-searches", response_model=SavedSearchResponse, status_code=201)
def create_saved_search(
    data: SavedSearchCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    saved = discovery_service.create_saved_search(user.id, db, data.name, data.criteria)
    return _build_saved_search_response(saved)


@router.post("/saved-searches/{search_id}/run", response_model=SavedSearchRunResponse)
def run_saved_search(
    search_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = discovery_service.run_saved_search(user.id, db, search_id)
    except Exception:
        logger.exception("Saved search run failed for user %s", user.id)
        raise HTTPException(
            status_code=500,
            detail="We couldn't finish running this saved search right now.",
        )
    if result["saved_search"] is None:
        raise HTTPException(status_code=404, detail="Saved search not found")

    saved = result["saved_search"]

    return SavedSearchRunResponse(
        saved_search=_build_saved_search_response(saved),
        report=result["report"],
        new_results=result["new_results"],
    )


@router.put("/saved-searches/{search_id}", response_model=SavedSearchResponse)
def update_saved_search(
    search_id: str,
    data: SavedSearchUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    saved = discovery_service.update_saved_search(
        user.id, db, search_id, data.name, data.criteria
    )
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return _build_saved_search_response(saved)


@router.delete("/saved-searches/{search_id}", status_code=204)
def delete_saved_search(
    search_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = discovery_service.delete_saved_search(user.id, db, search_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Saved search not found")
