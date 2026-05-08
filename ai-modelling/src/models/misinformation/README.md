# Misinformation Pipeline (RAEmoLLM-Style Adaptation)

This folder contains the bushfire misinformation pipeline used by the AI modelling layer.  
It adapts the RAEmoLLM-style workflow (index -> retrieval -> inference) to this project’s post schema and output contract.

---

## What this module does

Given a list of social posts, the pipeline:

1. Clusters posts into misinformation narratives.
2. Builds affective instruction indexes for:
   - target incoming posts
   - source labeled example pool (`AMTCele.csv`)
3. Retrieves top-k similar labeled examples (few-shot context).
4. Constructs inference prompts using retrieved examples.
5. Runs LLM detection and returns structured outputs.

---

## Main files

- `nlp_pipeline.py`  
  End-to-end orchestration and narrative + detection output contract.

- `indexconstruct_post.py`  
  Input normalization, affective instruction table generation, embedding artifact construction.

- `retrieval_post.py`  
  Cosine-similarity retrieval between target and source embeddings.

- `construct_instructs_post.py`  
  Few-shot instruction builder (Template 1/2 style prompts).

- `llm_client.py`  
  LLM provider abstraction and JSON/text generation helpers.

---

## Input schema (pipeline)

`run_full_pipeline_with_detection(raw_posts, client)` expects `raw_posts: list[dict]` where each post can provide:

- `id` (required)
- `content` (required)
- `platform`
- `author` or `author_name`
- `share_count` (defaults to `0`)
- `timestamp` or `ts`
- `post_url`

---

## Output schema

The pipeline returns:

- `narratives`: clustered narrative results
- `detections`: per-post detection results
- `artifacts`: intermediate metadata

### Detection item contract

Each detection item includes:

- `post_id: str`
- `label: "fake" | "legit"`
- `risk_score: float` in `[0, 1]` (probability post is fake)
- `severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"`
- `needs_human_review: bool`
- `rationale: str`

---

## Source example dataset

The retrieval source pool is currently hardcoded to:

`src/models/misinformation/datasets/AMTCele.csv`

Expected key columns:

- `text`
- `label` (`fake` / `legit`)
- optional `id`

---

## Temporary artifacts behavior

The pipeline uses temporary per-run storage for intermediate artifacts (input copy, index outputs, embedding files).  
These temp directories are auto-cleaned after the function returns.

This keeps backend inference runs from permanently storing every request payload.

---

## How to run (local)

You can run the standalone script path from `nlp_pipeline.py` (for local/manual testing), or call the function directly from service/backend code.

Function-level usage pattern:

1. Build `LLMClient`
2. Call `run_full_pipeline_with_detection(raw_posts, client)`
3. Return the resulting dict to caller

---

## Testing status

`tests/test_nlp_pipeline.py` includes:

- clustering validation tests
- detection parser/fallback tests
- orchestration tests with mocks
- semireal integration tests for index/retrieval/pipeline flow

Current status (latest): pipeline tests passing.

---

## Notes for backend integration

- Use the function return payload directly as API response payload.
- Do not rely on fixed `results/` output files for request handling.
- Ensure runtime environment has:
  - model dependencies installed
  - access to `AMTCele.csv`
  - valid LLM provider credentials