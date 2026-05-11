from fastapi import APIRouter, Depends, HTTPException

from ..internal.models.misinformation_models import (
    ActiveIncidentObject,
    NarrativeClusterObject,
    Post,
)
from ..internal.services.misinformation_service import MisinformationService

# tags used for categorising endpoints in Swagger documentation
router = APIRouter(prefix="/api/misinformation", tags=["misinformation"])


@router.get("/narratives", response_model=list[NarrativeClusterObject])
async def get_all_narrative_cluster_objects(
    service: MisinformationService = Depends(MisinformationService),
):
    return service.get_all_narrative_cluster_objects()


@router.get(
    "/narratives/{narrative_id}",
    response_model=NarrativeClusterObject,
)
async def get_narrative_cluster_object_by_id(
    narrative_id: str,
    service: MisinformationService = Depends(MisinformationService),
):
    result = service.get_narrative_cluster_object_by_id(narrative_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Narrative cluster {narrative_id} not found")
    return result


@router.get(
    "/incidents/{incident_id}/narrative-cluster-objects",
    response_model=list[NarrativeClusterObject],
)
async def get_incident_narrative_cluster_objects(
    incident_id: str,
    service: MisinformationService = Depends(MisinformationService),
):
    return service.get_incident_narrative_cluster_objects(incident_id)


@router.get("/posts", response_model=list[Post])
async def get_all_posts(
    service: MisinformationService = Depends(MisinformationService),
):
    return service.get_all_posts()


@router.get("/posts/{post_id}", response_model=Post)
async def get_post_by_id(
    post_id: str,
    service: MisinformationService = Depends(MisinformationService),
):
    result = service.get_post_by_id(post_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found")
    return result


@router.get("/incidents", response_model=list[ActiveIncidentObject])
async def get_all_active_incidents(
    service: MisinformationService = Depends(MisinformationService),
):
    return service.get_all_active_incidents()


@router.get("/incidents/{incident_id}", response_model=ActiveIncidentObject)
async def get_active_incident_by_id(
    incident_id: str,
    service: MisinformationService = Depends(MisinformationService),
):
    result = service.get_active_incident_by_id(incident_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return result