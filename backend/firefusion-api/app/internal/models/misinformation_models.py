from pydantic import BaseModel, field_validator
from enum import Enum
from datetime import datetime

class SeverityValue(Enum):
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class SeverityBreakdown(BaseModel):
    critical: int
    high: int
    medium: int

class SpreadVelocityIndicatorValue(Enum):
    STEADY = "STEADY"
    GROWING= "GROWING"
    SPREADING_FAST = "SPREADING_FAST"

class SocialMediaPlatformValue(Enum):
    TWITTER = "TWITTER"
    FACEBOOK = "FACEBOOK"
    TIKTOK = "TIKTOK"
    REDDIT = "REDDIT"

class ReviewStatusValue(Enum):
    NEEDS_REVIEW = "NEEDS_REVIEW"
    DISMISSED = "DISMISSED"
    CONFIRMED_MISINFORMATION = "CONFIRMED_MISINFORMATION"
    CORRECTION_PUBLISHED = "CORRECTION_PUBLISHED"

class Incident(BaseModel):
    id: str
    name: str
    is_active: bool

class NarrativeCluster(BaseModel):
    id: str
    summary: str
    incident_id: str
    spread_status: SpreadVelocityIndicatorValue
    review_status: ReviewStatusValue

class Post(BaseModel):
    id: str
    author_name: str
    platform: SocialMediaPlatformValue
    content: str
    ts: datetime
    share_count: int
    post_url: str
    misinformation_risk_score: float
    severity: SeverityValue

class Fact(BaseModel):
    source: str
    timestamp: datetime
    content: str

class NarrativeClusterObject(BaseModel):
    narrative_id: str
    narrative_summary: str
    incident_id: str
    incident_name: str
    severity: SeverityValue
    post_ids: list[str] = []
    post_count: int
    combined_shares: int
    spread_status: SpreadVelocityIndicatorValue
    key_claims: list[str]
    matched_facts: list[Fact] = []
    timestamp_earliest: datetime
    timestamp_latest: datetime
    platforms: list[SocialMediaPlatformValue]
    review_status: ReviewStatusValue

    @field_validator('platforms', mode='before')
    @classmethod
    def parse_platforms(cls, v):
        if isinstance(v, str):
            # remove the psql array syntax: '{TWITTER,FACEBOOK,REDDIT}' -> ['TWITTER', 'FACEBOOK', 'REDDIT']
            v = v.strip('{}').split(',')
        return v

class ActiveIncidentObject(BaseModel):
    incident_id: str
    incident_name: str
    total_flags: int
    severity_breakdown: SeverityBreakdown
    top_threat: str | None