from typing import Optional

from ..models.misinformation_models import NarrativeClusterObject, Post, ActiveIncidentObject
from ..repositories.misinformation_repository import MisinformationRepository

class MisinformationService:

    def __init__(self):
        self.misinformation_repository: MisinformationRepository = MisinformationRepository()

    def get_all_narrative_cluster_objects(self) -> list[NarrativeClusterObject]:
        try:
            return self.misinformation_repository.get_all_narrative_cluster_objects()
        except Exception as e:
            print(e)
            return []

    def get_narrative_cluster_object_by_id(self, narrative_id: str) -> Optional[NarrativeClusterObject]:
        try:
            return self.misinformation_repository.get_narrative_cluster_object_by_id(narrative_id)
        except Exception as e:
            print(e)
            return None

    def get_incident_narrative_cluster_objects(self, incident_id: str) -> list[NarrativeClusterObject]:
        try:
            return self.misinformation_repository.get_incident_narrative_cluster_objects(incident_id)
        except Exception as e:
            print(e)
            return []

    def get_all_posts(self) -> list[Post]:
        try:
            return self.misinformation_repository.get_all_posts()
        except Exception as e:
            print(e)
            return []

    def get_post_by_id(self, post_id: str) -> Optional[Post]:
        try:
            return self.misinformation_repository.get_post_by_id(post_id)
        except Exception as e:
            print(e)
            return None

    def get_all_active_incidents(self) -> list[ActiveIncidentObject]:
        try:
            return self.misinformation_repository.get_all_active_incidents()
        except Exception as e:
            print(e)
            return []

    def get_active_incident_by_id(self, incident_id: str) -> Optional[ActiveIncidentObject]:
        try:
            return self.misinformation_repository.get_active_incident_by_id(incident_id)
        except Exception as e:
            print(e)
            return None