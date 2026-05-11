import psycopg
from psycopg.rows import class_row
from typing import Optional
from ...config.config import environment
from ..models.misinformation_models import NarrativeClusterObject, ActiveIncidentObject, Post


class MisinformationRepository:

    def __init__(self):
        self.db_url = environment.db_url

    def get_all_narrative_cluster_objects(self) -> list[NarrativeClusterObject]:
        with psycopg.connect(self.db_url, row_factory=class_row(NarrativeClusterObject)) as conn:
            return conn.execute("SELECT * FROM narrative_cluster_objects").fetchall()

    def get_narrative_cluster_object_by_id(self, narrative_id: str) -> Optional[NarrativeClusterObject]:
        with psycopg.connect(self.db_url, row_factory=class_row(NarrativeClusterObject)) as conn:
            return conn.execute(
                "SELECT * FROM narrative_cluster_objects WHERE narrative_id = %s",
                (narrative_id,)
            ).fetchone()

    def get_incident_narrative_cluster_objects(self, incident_id: str) -> list[NarrativeClusterObject]:
        with psycopg.connect(self.db_url, row_factory=class_row(NarrativeClusterObject)) as conn:
            return conn.execute(
                "SELECT * FROM narrative_cluster_objects WHERE incident_id = %s",
                (incident_id,)
            ).fetchall()

    def get_all_posts(self) -> list[Post]:
        with psycopg.connect(self.db_url, row_factory=class_row(Post)) as conn:
            return conn.execute("SELECT * FROM posts").fetchall()

    def get_post_by_id(self, post_id: str) -> Optional[Post]:
        with psycopg.connect(self.db_url, row_factory=class_row(Post)) as conn:
            return conn.execute(
                "SELECT * FROM posts WHERE id = %s",(post_id,)
            ).fetchone()

    def get_all_active_incidents(self) -> list[ActiveIncidentObject]:

        with psycopg.connect(self.db_url, row_factory=class_row(ActiveIncidentObject)) as conn:
            return conn.execute("SELECT * FROM active_incident_objects").fetchall()

    def get_active_incident_by_id(self, incident_id: str) -> Optional[ActiveIncidentObject]:
        with psycopg.connect(self.db_url, row_factory=class_row(ActiveIncidentObject)) as conn:
            return conn.execute(
                "SELECT * FROM active_incident_objects WHERE incident_id = %s",(incident_id,)
            ).fetchone()