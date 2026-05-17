from fastapi import APIRouter, Body, HTTPException

from app.services import sites

router = APIRouter(prefix="/api/sites", tags=["sites"])


@router.get("")
def list_all():
    return {"sites": sites.list_sites()}


@router.post("")
def create(payload: dict = Body(...)):
    if "name" not in payload or "lat" not in payload or "lon" not in payload:
        raise HTTPException(400, "name, lat, lon are required")
    return sites.create_site(payload)


@router.get("/{site_id}")
def get(site_id: str):
    site = sites.get_site(site_id)
    if not site:
        raise HTTPException(404, "site not found")
    return site


@router.put("/{site_id}")
def update(site_id: str, payload: dict = Body(...)):
    site = sites.update_site(site_id, payload)
    if not site:
        raise HTTPException(404, "site not found")
    return site


@router.delete("/{site_id}")
def delete(site_id: str):
    if not sites.delete_site(site_id):
        raise HTTPException(404, "site not found")
    return {"ok": True}
