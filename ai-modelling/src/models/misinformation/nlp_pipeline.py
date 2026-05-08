"""
End-to-end NLP pipeline for narrative clustering and misinformation detection.

This module orchestrates:
1) narrative clustering,
2) affective index construction,
3) retrieval of labeled few-shot examples,
4) instruction construction,
5) LLM-based detection output parsing.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import tempfile
from .llm_client import LLMClient,  LLMConfig, render_prompt
from .indexconstruct_post import IndexConstructorPost, IndexConstructConfig
from .retrieval_post import RetrieverPost, RetrievalConfig
from .construct_instructs_post import InferenceInstructionBuilderPost, ConstructInstructsConfig
from typing import Literal
from pydantic import BaseModel, Field
import json
from pathlib import Path
import pandas as pd

# ---------- Input schemas ----------
class InputPost(BaseModel):
    id: str
    author: str
    platform: str
    content: str
    share_count: int
    timestamp: datetime
    post_url: str


# ---------- Narrative output schemas ----------
Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]

class NarrativePost(BaseModel):
    post_id: str
    key_claim: str
    platform: str

class Narrative(BaseModel):
    narrative_id: str
    narrative_summary: str
    severity: Severity
    post_count: int = Field(ge=0)
    posts: list[NarrativePost]
    timestamp_earliest: datetime
    timestamp_latest: datetime

class NarrativeResult(BaseModel):
    narratives: list[Narrative]


# ---------- Narrative Clustering ----------
CLUSTER_PROMPT_TEMPLATE = """
You are a wildfire misinformation analyst supporting emergency risk triage.

Goal:
Cluster social posts into coherent misinformation narratives for bushfire operations.
Prioritize life-safety harm and decision-impact during active fire events.

Input:
You will receive a JSON array named posts_json.
Each post has:
- id (string)
- author (string)
- platform (string)
- content (string)
- share_count (integer)
- timestamp (ISO-8601 string)
- post_url (string)

Output format (required):
Return ONLY one valid JSON object with this top-level shape:
{
  "narratives": [
    {
      "narrative_id": "nar_001",
      "narrative_summary": "string",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "post_count": 0,
      "posts": [
        {
          "post_id": "post_001",
          "key_claim": "string",
          "platform": "TWITTER"
        }
      ],
      "timestamp_earliest": "2026-01-22T06:14:00+11:00",
      "timestamp_latest": "2026-01-22T07:48:00+11:00"
    }
  ]
}

Severity rules:
- CRITICAL: immediate life-safety harm if believed (fake evacuation/safety directions/scams).
- HIGH: materially false claims likely to alter public decisions/trust.
- MEDIUM: unverified/speculative claims with moderate harm.
- LOW: weak/low-impact misleading content.

Strict constraints:
- JSON only, no markdown.
- Do not invent post IDs.
- Every post_id must exist in input.
- A post can belong to only one narrative.
- post_count must equal len(posts).
- timestamp_earliest/latest must be min/max timestamps from member posts.

Now process this input:
{posts_json}
""".strip()


@dataclass
class ClusterConfig:
    strict_json: bool = True
    enforce_all_posts_used_once: bool = True

class NarrativeClusterer:
    def __init__(
        self,
        client: LLMClient,
        *,
        prompt_template: str,
        config: ClusterConfig | None = None,
    ) -> None:
        self.client = client
        self.prompt_template = prompt_template
        self.config = config or ClusterConfig()

    @staticmethod
    def _normalize_input_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # unify incoming backend field variants
        return [
            {
                "id": p.get("id"),
                "author": p.get("author", p.get("author_name")),
                "platform": p.get("platform"),
                "content": p.get("content"),
                "share_count": p.get("share_count", 0),
                "timestamp": p.get("timestamp", p.get("ts")),
                "post_url": p.get("post_url"),
            }
            for p in posts
        ]

    @staticmethod
    def _validate_input_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        validated = [InputPost.model_validate(p) for p in posts]
        return [v.model_dump(mode="json") for v in validated]

    def _validate_output(
        self,
        result: dict[str, Any],
        input_posts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        parsed = NarrativeResult.model_validate(result)
        input_ids = {str(p["id"]) for p in input_posts}
        used_ids: set[str] = set()

        for nar in parsed.narratives:
            # enforce post_count consistency even if model got it wrong
            nar.post_count = len(nar.posts)

            for item in nar.posts:
                pid = str(item.post_id)
                if pid not in input_ids:
                    raise ValueError(f"Unknown post_id in output: {pid}")
                if pid in used_ids:
                    raise ValueError(f"Duplicate post_id across narratives: {pid}")
                used_ids.add(pid)

        if self.config.enforce_all_posts_used_once and used_ids != input_ids:
            missing = sorted(input_ids - used_ids)
            raise ValueError(f"Some input posts were not assigned: {missing}")

        return parsed.model_dump(mode="json")

    def run(self, posts: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = self._normalize_input_posts(posts)
        posts_for_prompt = self._validate_input_posts(normalized)
        prompt = render_prompt(self.prompt_template, {"posts_json": posts_for_prompt})

        result = (
            self.client.generate_json(prompt)
            if self.config.strict_json
            else {"raw_output": self.client.generate_text(prompt)}
        )

        if not self.config.strict_json:
            return result

        return self._validate_output(result, posts_for_prompt)


# ---------- Misinformation Detection and Flag ----------
DETECTION_PROMPT_TEMPLATE = """
You are a wildfire misinformation detector.

Return ONLY valid JSON:
{
  "label": "fake|legit",
  "risk_score": 0.0,
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "rationale": "short reason"
}

Rules:
- label must be exactly "fake" or "legit" (lowercase)
- risk_score must be in [0,1] and means probability the post is fake
- severity is impact if the claim is false:
  - CRITICAL: immediate life-safety harm (evacuation/shelter/route directives, emergency scams)
  - HIGH: materially harmful misinformation affecting decisions/trust
  - MEDIUM: moderate confusion/speculation
  - LOW: low operational impact
""".strip()

def _parse_detection_output(output: dict[str, Any], post_id: str) -> dict[str, Any]:
    label = str(output.get("label", "fake")).strip().lower()
    if label not in {"fake", "legit"}:
        label = "fake"
        parse_failed = True
    else:
        parse_failed = False

    try:
        risk = float(output.get("risk_score", 0.8 if label == "fake" else 0.2))
    except Exception:
        risk = 0.8
        parse_failed = True

    risk = max(0.0, min(1.0, risk))

    sev = str(output.get("severity", "HIGH" if label == "fake" else "LOW")).upper()
    if sev not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
        sev = "HIGH" if label == "fake" else "LOW"
        parse_failed = True

    review = bool(output.get("needs_human_review", False))
    if parse_failed or label == "fake" or risk >= 0.8 or sev in {"CRITICAL", "HIGH"}:
        review = True

    return {
        "post_id": post_id,
        "label": label,
        "risk_score": risk,
        "severity": sev,
        "needs_human_review": review,
        "rationale": str(output.get("rationale", "")),
    }

def run_full_pipeline_with_detection(raw_posts: list[dict[str, Any]], client: LLMClient) -> dict[str, Any]:
    """
    End-to-end pipeline:
      A) narrative clustering
      B) index construction (target + source)
      C) retrieval
      D) instruction construction
      E) LLM detection

    Uses per-request temporary storage for intermediate artifacts so incoming
    payloads are not persisted in a fixed project folder.
    """
    if not isinstance(raw_posts, list) or len(raw_posts) == 0:
        raise ValueError("raw_posts must be a non-empty list of post dicts.")

    # Step A: narrative clustering
    clusterer = NarrativeClusterer(
        client=client,
        prompt_template=CLUSTER_PROMPT_TEMPLATE,
        config=ClusterConfig(strict_json=True, enforce_all_posts_used_once=True),
    )
    narratives = clusterer.run(raw_posts)

    project_root = Path(__file__).resolve().parents[4]
    source_csv_path = (
        project_root
        / "ai-modelling"
        / "src"
        / "models"
        / "misinformation"
        / "datasets"
        / "AMTCele.csv"
    )
    if not source_csv_path.exists():
        raise FileNotFoundError(f"Source dataset not found: {source_csv_path}")

    indexer = IndexConstructorPost(IndexConstructConfig())

    # Use temp dir to avoid persisting per-request inputs/artifacts
    with tempfile.TemporaryDirectory(prefix="misinfo_pipeline_") as tmp_dir:
        pipeline_work_dir = Path(tmp_dir)

        # Persist input only inside temp workspace for index stage
        posts_json_path = pipeline_work_dir / "posts_input.json"
        posts_json_path.write_text(
            json.dumps(raw_posts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Step B: target/source indexing
        target_idx = indexer.run(
            input_path=str(posts_json_path),
            out_dir=str(pipeline_work_dir / "index_target"),
            data_name="TARGET",
            build_embeddings_for="Vreg",
        )
        source_idx = indexer.run(
            input_path=str(source_csv_path),
            out_dir=str(pipeline_work_dir / "index_source"),
            data_name="SOURCE",
            build_embeddings_for="Vreg",
        )

        # Step C: retrieval
        retriever = RetrieverPost(
            RetrievalConfig(top_k=4, min_score=0.2, text_col="text", label_col="label", id_col="id")
        )
        retrieved_payload = retriever.run(
            target_csv=target_idx["posts_csv"],
            source_csv=source_idx["posts_csv"],
            target_emb_path=target_idx["embedding_pth"],
            source_emb_path=source_idx["embedding_pth"],
        )

        # Step D: instruction construction
        target_posts_df = pd.read_csv(target_idx["posts_csv"])
        builder = InferenceInstructionBuilderPost(
            ConstructInstructsConfig(
                task_prompt="Determine whether the target text is fake or legit using the retrieved examples.",
                include_affective_info=True,
                top_k=4,
            )
        )
        instructions = builder.run(target_posts_df, retrieved_payload)

        # Step E: detection
        detections: list[dict[str, Any]] = []
        for rec in instructions:
            prompt = rec["instruction"] + "\n\n" + DETECTION_PROMPT_TEMPLATE
            try:
                out = client.generate_json(prompt)
                detections.append(_parse_detection_output(out, rec["post_id"]))
            except Exception:
                detections.append(
                    {
                        "post_id": rec["post_id"],
                        "label": "fake",
                        "risk_score": 0.8,
                        "severity": "HIGH",
                        "needs_human_review": True,
                        "rationale": "LLM output parsing failed; conservative fallback",
                    }
                )

        return {
            "narratives": narratives["narratives"],
            "detections": detections,
            "artifacts": {
                # Keep useful metadata; paths are temp and ephemeral by design
                "index_target": target_idx,
                "index_source": source_idx,
                "retrieval_count": len(retrieved_payload),
                "instruction_count": len(instructions),
                "artifact_storage": "temporary_directory",
            },
        }

# ---------- NLP Pipeline (Narrative Clustering + Misinformation Detection) ----------
def main() -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[4]
    posts_path = project_root / "posts.json"

    raw_posts = json.loads(posts_path.read_text(encoding="utf-8"))

    client = LLMClient(
        LLMConfig(
            provider="gemini",
            model="gemini-3-flash-preview",
            temperature=0.2,
            max_retries=3,
        )
    )

    result = run_full_pipeline_with_detection(raw_posts, client)

    # save full artifact
    out_dir = project_root / "ai-modelling" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "misinformation_pipeline_output.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # short summary logs
    print(f"Narratives: {len(result.get('narratives', []))}")
    print(f"Detections: {len(result.get('detections', []))}")
    print(f"Saved: {out_file}")

    return result

if __name__ == "__main__":
    _ = main()