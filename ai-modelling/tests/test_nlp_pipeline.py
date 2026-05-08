import json
import sys
from pathlib import Path
import tempfile
import pandas as pd
import pytest

# Keep import style consistent with your existing tests
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.misinformation import nlp_pipeline as mod  # noqa: E402
from src.models.misinformation.nlp_pipeline import (  # noqa: E402
    CLUSTER_PROMPT_TEMPLATE,
    ClusterConfig,
    NarrativeClusterer,
    _parse_detection_output,
    run_full_pipeline_with_detection,
)


class DummyClient:
    """Simple fake LLM client for clustering and detection calls."""

    def __init__(self, json_queue=None, text_result="raw-ok", raise_on_generate_json=False):
        self.json_queue = list(json_queue or [])
        self.text_result = text_result
        self.raise_on_generate_json = raise_on_generate_json
        self.prompts = []

    def generate_json(self, prompt: str):
        self.prompts.append(prompt)
        if self.raise_on_generate_json:
            raise RuntimeError("forced failure")
        if self.json_queue:
            return self.json_queue.pop(0)
        return {}

    def generate_text(self, prompt: str):
        self.prompts.append(prompt)
        return self.text_result


@pytest.fixture
def raw_posts():
    return [
        {
            "id": "post_001",
            "author_name": "@a",
            "platform": "TWITTER",
            "content": "Fake evacuation order now",
            "share_count": 10,
            "ts": "2026-01-22T06:14:00+11:00",
            "post_url": "https://x.com/1",
        },
        {
            "id": "post_002",
            "author_name": "@b",
            "platform": "FACEBOOK",
            "content": "Road closed rumor",
            "share_count": 5,
            "ts": "2026-01-22T07:14:00+11:00",
            "post_url": "https://fb.com/2",
        },
    ]


def make_clusterer(json_result, strict_json=True, enforce_all=True):
    client = DummyClient(json_queue=[json_result])
    return NarrativeClusterer(
        client=client,
        prompt_template=CLUSTER_PROMPT_TEMPLATE,
        config=ClusterConfig(
            strict_json=strict_json,
            enforce_all_posts_used_once=enforce_all,
        ),
    )


# ---------------------------
# NarrativeClusterer tests
# ---------------------------

def test_normalize_maps_author_ts_share_count(raw_posts):
    c = make_clusterer({"narratives": []}, enforce_all=False)
    normalized = c._normalize_input_posts(raw_posts)

    assert normalized[0]["author"] == "@a"
    assert normalized[0]["timestamp"] == "2026-01-22T06:14:00+11:00"
    assert normalized[0]["share_count"] == 10


def test_validate_input_posts_raises_on_missing_required_field():
    c = make_clusterer({"narratives": []}, enforce_all=False)
    bad_posts = [
        {
            "id": "post_001",
            "author": "a",
            "platform": "TWITTER",
            "content": "x",
            # share_count missing on purpose
            "timestamp": "2026-01-22T06:14:00+11:00",
            "post_url": "https://x.com/1",
        }
    ]
    with pytest.raises(Exception):
        c._validate_input_posts(bad_posts)


def test_run_success_valid_output_and_post_count_corrected(raw_posts):
    model_output = {
        "narratives": [
            {
                "narrative_id": "nar_001",
                "narrative_summary": "False evacuation narrative",
                "severity": "CRITICAL",
                "post_count": 999,  # should be corrected to len(posts)
                "posts": [
                    {"post_id": "post_001", "key_claim": "evacuation ordered", "platform": "TWITTER"},
                    {"post_id": "post_002", "key_claim": "road closed", "platform": "FACEBOOK"},
                ],
                "timestamp_earliest": "2026-01-22T06:14:00+11:00",
                "timestamp_latest": "2026-01-22T07:14:00+11:00",
            }
        ]
    }
    c = make_clusterer(model_output, enforce_all=True)
    out = c.run(raw_posts)

    assert "narratives" in out
    assert out["narratives"][0]["post_count"] == 2


def test_unknown_post_id_raises(raw_posts):
    bad = {
        "narratives": [
            {
                "narrative_id": "nar_001",
                "narrative_summary": "x",
                "severity": "HIGH",
                "post_count": 1,
                "posts": [{"post_id": "post_999", "key_claim": "x", "platform": "TWITTER"}],
                "timestamp_earliest": "2026-01-22T06:14:00+11:00",
                "timestamp_latest": "2026-01-22T07:14:00+11:00",
            }
        ]
    }
    c = make_clusterer(bad)
    with pytest.raises(ValueError, match="Unknown post_id"):
        c.run(raw_posts)


def test_duplicate_post_id_across_narratives_raises(raw_posts):
    bad = {
        "narratives": [
            {
                "narrative_id": "nar_001",
                "narrative_summary": "x",
                "severity": "HIGH",
                "post_count": 1,
                "posts": [{"post_id": "post_001", "key_claim": "x", "platform": "TWITTER"}],
                "timestamp_earliest": "2026-01-22T06:14:00+11:00",
                "timestamp_latest": "2026-01-22T06:14:00+11:00",
            },
            {
                "narrative_id": "nar_002",
                "narrative_summary": "y",
                "severity": "MEDIUM",
                "post_count": 1,
                "posts": [{"post_id": "post_001", "key_claim": "y", "platform": "TWITTER"}],
                "timestamp_earliest": "2026-01-22T07:14:00+11:00",
                "timestamp_latest": "2026-01-22T07:14:00+11:00",
            },
        ]
    }
    c = make_clusterer(bad)
    with pytest.raises(ValueError, match="Duplicate post_id"):
        c.run(raw_posts)


def test_missing_post_assignment_raises(raw_posts):
    bad = {
        "narratives": [
            {
                "narrative_id": "nar_001",
                "narrative_summary": "x",
                "severity": "HIGH",
                "post_count": 1,
                "posts": [{"post_id": "post_001", "key_claim": "x", "platform": "TWITTER"}],
                "timestamp_earliest": "2026-01-22T06:14:00+11:00",
                "timestamp_latest": "2026-01-22T06:14:00+11:00",
            }
        ]
    }
    c = make_clusterer(bad, enforce_all=True)
    with pytest.raises(ValueError, match="not assigned"):
        c.run(raw_posts)


def test_non_strict_json_returns_raw(raw_posts):
    c = NarrativeClusterer(
        client=DummyClient(json_queue=[{}], text_result="hello"),
        prompt_template=CLUSTER_PROMPT_TEMPLATE,
        config=ClusterConfig(strict_json=False, enforce_all_posts_used_once=False),
    )
    out = c.run(raw_posts)
    assert out == {"raw_output": "hello"}


# ---------------------------
# _parse_detection_output tests
# ---------------------------

def test_parse_detection_output_happy_path():
    out = _parse_detection_output(
        {
            "label": "fake",
            "risk_score": 0.91,
            "severity": "CRITICAL",
            "rationale": "dangerous claim",
        },
        "post_001",
    )
    assert out["post_id"] == "post_001"
    assert out["label"] == "fake"
    assert out["risk_score"] == 0.91
    assert out["severity"] == "CRITICAL"
    assert out["needs_human_review"] is True


def test_parse_detection_output_invalid_label_defaults_conservatively():
    out = _parse_detection_output(
        {
            "label": "uncertain",
            "risk_score": 0.2,  # still parse-failed path
            "severity": "LOW",
            "rationale": "bad label",
        },
        "post_001",
    )
    assert out["label"] == "fake"
    assert out["needs_human_review"] is True


def test_parse_detection_output_clamps_risk_and_normalizes_severity():
    out = _parse_detection_output(
        {
            "label": "legit",
            "risk_score": 3.5,  # should clamp to 1.0
            "severity": "unknown",  # should map to LOW for legit
            "rationale": "x",
        },
        "post_002",
    )
    assert out["risk_score"] == 1.0
    assert out["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


# ---------------------------
# End-to-end orchestration tests
# ---------------------------

def test_run_full_pipeline_success_with_mocks(raw_posts, monkeypatch, tmp_path):
    # 1) Make filesystem paths safe under tmp_path by monkeypatching Path in module
    RealPath = Path

    class FakePath(type(RealPath())):
        @classmethod
        def __new__(cls, *args, **kwargs):
            s = args[0] if args else ""
            p = RealPath(s)
            # Keep __file__ path for project_root resolution
            if str(p).endswith("nlp_pipeline.py"):
                return p
            # Redirect "project_root" resolution to tmp_path for writes/reads
            return RealPath(tmp_path / str(p).lstrip("/"))

    # Simpler and safer: monkeypatch only data locations via helper stubs instead of full Path replacement.
    # We'll patch the classes/functions that touch heavy IO and models.

    # 2) Fake clusterer run result
    class FakeNarrativeClusterer:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, posts):
            return {
                "narratives": [
                    {
                        "narrative_id": "nar_001",
                        "narrative_summary": "summary",
                        "severity": "HIGH",
                        "post_count": 2,
                        "posts": [
                            {"post_id": "post_001", "key_claim": "c1", "platform": "TWITTER"},
                            {"post_id": "post_002", "key_claim": "c2", "platform": "FACEBOOK"},
                        ],
                        "timestamp_earliest": "2026-01-22T06:14:00+11:00",
                        "timestamp_latest": "2026-01-22T07:14:00+11:00",
                    }
                ]
            }

    # 3) Fake indexer outputs
    target_csv = tmp_path / "target_posts.csv"
    source_csv = tmp_path / "source_posts.csv"
    pd.DataFrame(
        [
            {"id": "post_001", "text": "t1"},
            {"id": "post_002", "text": "t2"},
        ]
    ).to_csv(target_csv, index=False)
    pd.DataFrame(
        [
            {"id": "src_1", "text": "s1", "label": "fake"},
            {"id": "src_2", "text": "s2", "label": "legit"},
        ]
    ).to_csv(source_csv, index=False)

    class FakeIndexer:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        def run(self, input_path, out_dir, data_name, build_embeddings_for):
            self.calls += 1
            if data_name == "TARGET":
                return {"posts_csv": str(target_csv), "embedding_pth": str(tmp_path / "target_emb.pth")}
            return {"posts_csv": str(source_csv), "embedding_pth": str(tmp_path / "source_emb.pth")}

    # 4) Fake retriever payload
    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, **kwargs):
            return [
                {
                    "target_post_id": "post_001",
                    "retrieved_examples": [
                        {"source_post_id": "src_1", "text": "example fake", "label": "fake", "score": 0.9}
                    ],
                },
                {
                    "target_post_id": "post_002",
                    "retrieved_examples": [
                        {"source_post_id": "src_2", "text": "example legit", "label": "legit", "score": 0.88}
                    ],
                },
            ]

    # 5) Fake instruction builder
    class FakeBuilder:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, target_posts_df, retrieved_payload):
            return [
                {"post_id": "post_001", "instruction": "inst1", "input": "", "output": "", "num_examples": 1},
                {"post_id": "post_002", "instruction": "inst2", "input": "", "output": "", "num_examples": 1},
            ]

    monkeypatch.setattr(mod, "NarrativeClusterer", FakeNarrativeClusterer)
    monkeypatch.setattr(mod, "IndexConstructorPost", FakeIndexer)
    monkeypatch.setattr(mod, "RetrieverPost", FakeRetriever)
    monkeypatch.setattr(mod, "InferenceInstructionBuilderPost", FakeBuilder)

    # 6) LLM detection responses (2 posts)
    client = DummyClient(
        json_queue=[
            {"label": "fake", "risk_score": 0.9, "severity": "HIGH", "rationale": "danger"},
            {"label": "legit", "risk_score": 0.1, "severity": "LOW", "rationale": "benign"},
        ]
    )

    out = run_full_pipeline_with_detection(raw_posts, client)

    assert set(out.keys()) == {"narratives", "detections", "artifacts"}
    assert len(out["narratives"]) == 1
    assert len(out["detections"]) == 2
    assert out["artifacts"]["retrieval_count"] == 2
    assert out["artifacts"]["instruction_count"] == 2

    labels = {d["post_id"]: d["label"] for d in out["detections"]}
    assert labels["post_001"] == "fake"
    assert labels["post_002"] == "legit"


def test_run_full_pipeline_detection_fallback_on_client_error(raw_posts, monkeypatch, tmp_path):
    class FakeNarrativeClusterer:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, posts):
            return {"narratives": []}

    target_csv = tmp_path / "target_posts.csv"
    source_csv = tmp_path / "source_posts.csv"
    pd.DataFrame([{"id": "post_001", "text": "t1"}]).to_csv(target_csv, index=False)
    pd.DataFrame([{"id": "src_1", "text": "s1", "label": "fake"}]).to_csv(source_csv, index=False)

    class FakeIndexer:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, input_path, out_dir, data_name, build_embeddings_for):
            if data_name == "TARGET":
                return {"posts_csv": str(target_csv), "embedding_pth": str(tmp_path / "target_emb.pth")}
            return {"posts_csv": str(source_csv), "embedding_pth": str(tmp_path / "source_emb.pth")}

    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, **kwargs):
            return [{"target_post_id": "post_001", "retrieved_examples": []}]

    class FakeBuilder:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, target_posts_df, retrieved_payload):
            return [{"post_id": "post_001", "instruction": "inst", "input": "", "output": "", "num_examples": 0}]

    monkeypatch.setattr(mod, "NarrativeClusterer", FakeNarrativeClusterer)
    monkeypatch.setattr(mod, "IndexConstructorPost", FakeIndexer)
    monkeypatch.setattr(mod, "RetrieverPost", FakeRetriever)
    monkeypatch.setattr(mod, "InferenceInstructionBuilderPost", FakeBuilder)

    client = DummyClient(raise_on_generate_json=True)
    out = run_full_pipeline_with_detection(raw_posts, client)

    assert len(out["detections"]) == 1
    d = out["detections"][0]
    assert d["post_id"] == "post_001"
    assert d["label"] == "fake"
    assert d["risk_score"] == 0.8
    assert d["severity"] == "HIGH"
    assert d["needs_human_review"] is True
    assert "fallback" in d["rationale"].lower()


def test_run_full_pipeline_calls_detection_prompt_appended(raw_posts, monkeypatch, tmp_path):
    class FakeNarrativeClusterer:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, posts):
            return {"narratives": []}

    target_csv = tmp_path / "target_posts.csv"
    source_csv = tmp_path / "source_posts.csv"
    pd.DataFrame([{"id": "post_001", "text": "t1"}]).to_csv(target_csv, index=False)
    pd.DataFrame([{"id": "src_1", "text": "s1", "label": "fake"}]).to_csv(source_csv, index=False)

    class FakeIndexer:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, input_path, out_dir, data_name, build_embeddings_for):
            if data_name == "TARGET":
                return {"posts_csv": str(target_csv), "embedding_pth": str(tmp_path / "target_emb.pth")}
            return {"posts_csv": str(source_csv), "embedding_pth": str(tmp_path / "source_emb.pth")}

    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, **kwargs):
            return [{"target_post_id": "post_001", "retrieved_examples": []}]

    class FakeBuilder:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, target_posts_df, retrieved_payload):
            return [{"post_id": "post_001", "instruction": "BASE_INSTRUCTION", "input": "", "output": "", "num_examples": 0}]

    monkeypatch.setattr(mod, "NarrativeClusterer", FakeNarrativeClusterer)
    monkeypatch.setattr(mod, "IndexConstructorPost", FakeIndexer)
    monkeypatch.setattr(mod, "RetrieverPost", FakeRetriever)
    monkeypatch.setattr(mod, "InferenceInstructionBuilderPost", FakeBuilder)

    client = DummyClient(json_queue=[{"label": "fake", "risk_score": 0.9, "severity": "HIGH", "rationale": "x"}])
    _ = run_full_pipeline_with_detection(raw_posts, client)

    assert len(client.prompts) >= 1
    sent_prompt = client.prompts[0]
    assert "BASE_INSTRUCTION" in sent_prompt
    assert "Return ONLY valid JSON" in sent_prompt


# -------------------------------------------------
# 1) source CSV missing -> explicit failure
# -------------------------------------------------
def test_run_full_pipeline_raises_if_source_csv_missing(raw_posts, monkeypatch, tmp_path):
    from src.models.misinformation import nlp_pipeline as mod
    class FakeNarrativeClusterer:
        def __init__(self, *args, **kwargs): pass
        def run(self, posts): return {"narratives": []}

    monkeypatch.setattr(mod, "NarrativeClusterer", FakeNarrativeClusterer)

    # Force project_root so hardcoded source path points to non-existent file
    fake_file = tmp_path / "a" / "b" / "c" / "d" / "nlp_pipeline.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_text("# x", encoding="utf-8")
    monkeypatch.setattr(mod, "__file__", str(fake_file))

    client = DummyClient(json_queue=[{"label": "fake", "risk_score": 0.9, "severity": "HIGH", "rationale": "x"}])

    with pytest.raises(FileNotFoundError, match="Source dataset not found"):
        mod.run_full_pipeline_with_detection(raw_posts, client)


# -------------------------------------------------
# 2) empty input list validation
# -------------------------------------------------
def test_run_full_pipeline_rejects_empty_posts(monkeypatch):
    from src.models.misinformation import nlp_pipeline as mod
    client = DummyClient(json_queue=[])

    with pytest.raises(ValueError, match="non-empty list"):
        mod.run_full_pipeline_with_detection([], client)


# -------------------------------------------------
# 3) tempdir mode marker present in artifacts
# -------------------------------------------------
def test_run_full_pipeline_artifacts_mark_temp_storage(raw_posts, monkeypatch, tmp_path):
    from src.models.misinformation import nlp_pipeline as mod
    class FakeNarrativeClusterer:
        def __init__(self, *args, **kwargs): pass
        def run(self, posts): return {"narratives": []}

    target_csv = tmp_path / "target.csv"
    source_csv = tmp_path / "source.csv"
    pd.DataFrame([{"id": "post_001", "text": "t1"}]).to_csv(target_csv, index=False)
    pd.DataFrame([{"id": "src_1", "text": "s1", "label": "fake"}]).to_csv(source_csv, index=False)

    class FakeIndexer:
        def __init__(self, *args, **kwargs): pass
        def run(self, input_path, out_dir, data_name, build_embeddings_for):
            if data_name == "TARGET":
                return {"posts_csv": str(target_csv), "embedding_pth": str(tmp_path / "t.pth")}
            return {"posts_csv": str(source_csv), "embedding_pth": str(tmp_path / "s.pth")}

    class FakeRetriever:
        def __init__(self, *args, **kwargs): pass
        def run(self, **kwargs):
            return [{"target_post_id": "post_001", "retrieved_examples": []}]

    class FakeBuilder:
        def __init__(self, *args, **kwargs): pass
        def run(self, target_posts_df, retrieved_payload):
            return [{"post_id": "post_001", "instruction": "inst", "input": "", "output": "", "num_examples": 0}]

    monkeypatch.setattr(mod, "NarrativeClusterer", FakeNarrativeClusterer)
    monkeypatch.setattr(mod, "IndexConstructorPost", FakeIndexer)
    monkeypatch.setattr(mod, "RetrieverPost", FakeRetriever)
    monkeypatch.setattr(mod, "InferenceInstructionBuilderPost", FakeBuilder)

    # Make source path exist through fake __file__ project root layout
    fake_root = tmp_path / "root"
    src_dataset = fake_root / "ai-modelling" / "src" / "models" / "misinformation" / "datasets"
    src_dataset.mkdir(parents=True, exist_ok=True)
    (src_dataset / "AMTCele.csv").write_text("id,text,label\n1,x,fake\n", encoding="utf-8")

    fake_file = fake_root / "a" / "b" / "c" / "d" / "nlp_pipeline.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_text("# x", encoding="utf-8")
    monkeypatch.setattr(mod, "__file__", str(fake_file))

    client = DummyClient(json_queue=[{"label": "legit", "risk_score": 0.1, "severity": "LOW", "rationale": "ok"}])
    out = mod.run_full_pipeline_with_detection(raw_posts, client)

    assert out["artifacts"]["artifact_storage"] == "temporary_directory"


# -------------------------------------------------
# 4) malformed retrieval payload still handled via instruction builder
# -------------------------------------------------
def test_run_full_pipeline_handles_no_retrieved_examples(raw_posts, monkeypatch, tmp_path):
    from src.models.misinformation import nlp_pipeline as mod

    class FakeNarrativeClusterer:
        def __init__(self, *args, **kwargs): pass
        def run(self, posts): return {"narratives": []}

    target_csv = tmp_path / "target.csv"
    source_csv = tmp_path / "source.csv"
    pd.DataFrame([{"id": "post_001", "text": "t1"}]).to_csv(target_csv, index=False)
    pd.DataFrame([{"id": "src_1", "text": "s1", "label": "fake"}]).to_csv(source_csv, index=False)

    class FakeIndexer:
        def __init__(self, *args, **kwargs): pass
        def run(self, input_path, out_dir, data_name, build_embeddings_for):
            if data_name == "TARGET":
                return {"posts_csv": str(target_csv), "embedding_pth": str(tmp_path / "t.pth")}
            return {"posts_csv": str(source_csv), "embedding_pth": str(tmp_path / "s.pth")}

    class FakeRetriever:
        def __init__(self, *args, **kwargs): pass
        def run(self, **kwargs):
            return [{"target_post_id": "post_001", "retrieved_examples": []}]

    class FakeBuilder:
        def __init__(self, *args, **kwargs): pass
        def run(self, target_posts_df, retrieved_payload):
            assert retrieved_payload[0]["retrieved_examples"] == []
            return [{"post_id": "post_001", "instruction": "fallback_inst", "input": "", "output": "", "num_examples": 0}]

    monkeypatch.setattr(mod, "NarrativeClusterer", FakeNarrativeClusterer)
    monkeypatch.setattr(mod, "IndexConstructorPost", FakeIndexer)
    monkeypatch.setattr(mod, "RetrieverPost", FakeRetriever)
    monkeypatch.setattr(mod, "InferenceInstructionBuilderPost", FakeBuilder)

    fake_root = tmp_path / "root"
    ds = fake_root / "ai-modelling" / "src" / "models" / "misinformation" / "datasets"
    ds.mkdir(parents=True, exist_ok=True)
    (ds / "AMTCele.csv").write_text("id,text,label\n1,x,fake\n", encoding="utf-8")
    fake_file = fake_root / "a" / "b" / "c" / "d" / "nlp_pipeline.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_text("# x", encoding="utf-8")
    monkeypatch.setattr(mod, "__file__", str(fake_file))

    client = DummyClient(json_queue=[{"label": "fake", "risk_score": 0.9, "severity": "HIGH", "rationale": "r"}])
    out = mod.run_full_pipeline_with_detection(raw_posts, client)
    assert len(out["detections"]) == 1


def test_index_and_retrieval_real_components(tmp_path):
    import json
    import numpy as np
    import pandas as pd
    import torch

    from src.models.misinformation.indexconstruct_post import IndexConstructorPost, IndexConstructConfig
    from src.models.misinformation.retrieval_post import RetrieverPost, RetrievalConfig

    # --- Prepare target posts (JSON) ---
    target_posts = [
        {
            "id": "post_001",
            "author": "@a",
            "platform": "TWITTER",
            "content": "Fake evacuation order in Geelong now",
            "share_count": 12,
            "timestamp": "2026-01-22T06:14:00+11:00",
            "post_url": "https://x.com/1",
        },
        {
            "id": "post_002",
            "author": "@b",
            "platform": "FACEBOOK",
            "content": "Fire map says no threat in our suburb",
            "share_count": 3,
            "timestamp": "2026-01-22T07:14:00+11:00",
            "post_url": "https://fb.com/2",
        },
    ]
    target_json = tmp_path / "target_posts.json"
    target_json.write_text(json.dumps(target_posts), encoding="utf-8")

    # --- Prepare source labeled pool (CSV) ---
    source_csv_raw = tmp_path / "source_raw.csv"
    pd.DataFrame(
        [
            {"id": "src_1", "text": "Evacuation order is fake, do not trust.", "label": "fake"},
            {"id": "src_2", "text": "Official CFA warning is legit.", "label": "legit"},
            {"id": "src_3", "text": "Road closure rumor is false.", "label": "fake"},
        ]
    ).to_csv(source_csv_raw, index=False)

    # --- Build index artifacts using real normalizer/saver ---
    indexer = IndexConstructorPost(IndexConstructConfig())

    # Patch heavy embedding step only (keep rest real)
    def fake_build_instruction_embeddings(_csv_path):
        # target has 2 rows for Vreg table, source has 3 rows for Vreg table
        # We'll detect based on filename content:
        if "TARGET" in str(_csv_path):
            return torch.tensor(np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))
        return torch.tensor(np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]], dtype=np.float32))

    indexer.build_instruction_embeddings = fake_build_instruction_embeddings

    target_idx = indexer.run(
        input_path=str(target_json),
        out_dir=str(tmp_path / "index_target"),
        data_name="TARGET",
        build_embeddings_for="Vreg",
    )
    source_idx = indexer.run(
        input_path=str(source_csv_raw),
        out_dir=str(tmp_path / "index_source"),
        data_name="SOURCE",
        build_embeddings_for="Vreg",
    )

    assert Path(target_idx["posts_csv"]).exists()
    assert Path(source_idx["posts_csv"]).exists()
    assert Path(target_idx["embedding_pth"]).exists()
    assert Path(source_idx["embedding_pth"]).exists()

    # --- Real retrieval ---
    retriever = RetrieverPost(
        RetrievalConfig(top_k=2, min_score=0.0, text_col="text", label_col="label", id_col="id")
    )
    payload = retriever.run(
        target_csv=target_idx["posts_csv"],
        source_csv=source_idx["posts_csv"],
        target_emb_path=target_idx["embedding_pth"],
        source_emb_path=source_idx["embedding_pth"],
    )

    assert len(payload) == 2
    assert "target_post_id" in payload[0]
    assert "retrieved_examples" in payload[0]
    assert len(payload[0]["retrieved_examples"]) >= 1
    assert payload[0]["retrieved_examples"][0]["label"] in {"fake", "legit"}


def test_run_full_pipeline_semireal_integration(raw_posts, monkeypatch, tmp_path):
    import numpy as np
    import pandas as pd
    import torch
    from pathlib import Path

    from src.models.misinformation import nlp_pipeline as mod
    from src.models.misinformation.indexconstruct_post import IndexConstructorPost

    # --- Create expected hardcoded source dataset path based on module __file__ logic ---
    fake_root = tmp_path / "proj"
    dataset_dir = fake_root / "ai-modelling" / "src" / "models" / "misinformation" / "datasets"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    source_csv = dataset_dir / "AMTCele.csv"
    pd.DataFrame(
        [
            {"id": "src_1", "text": "Fake evacuation screenshot", "label": "fake"},
            {"id": "src_2", "text": "Official warning update", "label": "legit"},
            {"id": "src_3", "text": "False shelter location rumor", "label": "fake"},
        ]
    ).to_csv(source_csv, index=False)

    # Make project_root resolve into fake_root
    fake_file = fake_root / "a" / "b" / "c" / "d" / "nlp_pipeline.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_text("# stub", encoding="utf-8")
    monkeypatch.setattr(mod, "__file__", str(fake_file))

    # Patch only heavy embedding generation inside IndexConstructorPost
    def fake_embed(self, instruction_csv_path):
        # row count driven by generated Vreg CSV
        n = len(pd.read_csv(instruction_csv_path))
        # deterministic simple embeddings
        arr = np.zeros((n, 4), dtype=np.float32)
        for i in range(n):
            arr[i, i % 4] = 1.0
        return torch.tensor(arr)

    monkeypatch.setattr(IndexConstructorPost, "build_instruction_embeddings", fake_embed, raising=True)

    # Fake client:
    # 1st generate_json call => clustering result
    # Remaining calls => detection outputs
    class QueueClient:
        def __init__(self):
            self.calls = 0

        def generate_json(self, prompt: str):
            self.calls += 1
            if self.calls == 1:
                return {
                    "narratives": [
                        {
                            "narrative_id": "nar_001",
                            "narrative_summary": "evacuation misinformation",
                            "severity": "HIGH",
                            "post_count": 2,
                            "posts": [
                                {"post_id": "post_001", "key_claim": "evacuate now", "platform": "TWITTER"},
                                {"post_id": "post_002", "key_claim": "road closure", "platform": "FACEBOOK"},
                            ],
                            "timestamp_earliest": "2026-01-22T06:14:00+11:00",
                            "timestamp_latest": "2026-01-22T07:14:00+11:00",
                        }
                    ]
                }
            # detection outputs
            return {
                "label": "fake" if self.calls % 2 == 0 else "legit",
                "risk_score": 0.85 if self.calls % 2 == 0 else 0.2,
                "severity": "HIGH" if self.calls % 2 == 0 else "LOW",
                "rationale": "semireal test",
            }

        def generate_text(self, prompt: str):
            return "unused"

    client = QueueClient()

    out = mod.run_full_pipeline_with_detection(raw_posts, client)

    assert "narratives" in out
    assert "detections" in out
    assert "artifacts" in out
    assert len(out["narratives"]) == 1
    assert len(out["detections"]) == len(raw_posts)
    assert out["artifacts"]["retrieval_count"] == len(raw_posts)
    assert out["artifacts"]["instruction_count"] == len(raw_posts)