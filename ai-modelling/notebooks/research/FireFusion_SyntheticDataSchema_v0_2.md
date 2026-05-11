# FireFusion — Synthetic Data Schema for NLP Misinformation Model

**AI Modelling Stream · Version 0.2 · May 2026**

---

## 1. Purpose and Context

FireFusion includes an NLP-based misinformation detection pipeline alongside its bushfire risk forecasting model. The NLP model is trained to classify social media posts and online content as misinformation, credible, or unverified in the context of bushfire events. Because labelled real-world training data for this specific task is scarce, the model will be trained on synthetic data generated programmatically to reflect the distribution and themes of real bushfire-related misinformation.

This document defines the schema that every synthetic training sample must conform to. It serves three purposes: (1) it gives the data generator a clear target structure to generate toward; (2) it gives the data validation script a formal specification to validate against; and (3) it gives the NLP model builder a clear picture of what features are available as inputs and what field carries the training label. This schema is the synthetic data equivalent of the GeoJSON Output Schema used for the bushfire forecasting model — a cross-stream contract that must remain stable between generation, validation, and training.

---

## 2. Schema Design Decisions

Several design decisions shaped this schema and are documented here so they can be revisited if requirements change.

- **`narrative_theme` is required, not optional:** The generation script used narrative clustering to identify the dominant themes in bushfire misinformation posts before generating samples. This theme assignment is too valuable to discard — it is both a potential model feature and the primary mechanism by which the validation script can verify that the dataset has adequate thematic coverage. Making it required ensures every sample carries a theme label.

- **`generation_template` is included for auditability:** Different templates produce different quality and distribution characteristics. Recording which template produced each sample enables targeted debugging: if validation reveals a quality problem with a particular theme, the template identifier tells us exactly which generation logic to fix.

- **`source_credibility` is optional and derived, not predicted:** This is a heuristic score assigned at generation time, not a model output. It is marked optional because not all generation templates will assign it, and it should never be used as a training target (that is `label`'s job). It exists as an additional feature that the NLP model builder can choose to use or ignore.

- **`split` is pre-assigned at generation time:** Pre-assigning train/val/test splits at generation ensures stratification by both label and `narrative_theme`. If splits were assigned later, there is a risk of imbalanced splits where some themes appear only in training and not in validation. Pre-assignment at generation time is the safer approach.

- **`label` includes `'unverified'` as a third class:** Real-world posts are often genuinely ambiguous. A strict binary (misinformation / credible) would force the generator to make confident assignments that do not reflect reality. The unverified class preserves this ambiguity and allows the model to learn a three-way classification, with binary evaluation as a fallback by collapsing credible + unverified.

---

## 3. Field Reference

Every field is described with its type, whether it is required, its source category, and operational notes including how it is used by the generator, the validation script, and the model training pipeline.

| Field | Type | Required | Source Category | Description & Operational Notes |
|---|---|---|---|---|
| `post_id` | string | required | Primary key | Unique identifier for each synthetic post. Format: `fp_{uuid4_short}`. Used by validation script to deduplicate and reference records. |
| `text` | string | required | Model input | The post body text. Free-form, 20–300 characters. Primary feature fed to the NLP classifier and narrative clustering model. |
| `label` | string | required | Training target | Ground truth classification: `'misinformation'`, `'credible'`, or `'unverified'`. Binary version (mis / not_mis) also supported for baseline classifier. |
| `platform` | string | required | Feature / context | Simulated source platform: `'twitter'`, `'facebook'`, `'reddit'`, `'news_article'`, `'official_agency'`. Affects tone and length distribution in generation. |
| `narrative_theme` | string | required | Clustering target | High-level theme assigned during generation using narrative clustering technique. Values: `'arson_blame'`, `'govt_inaction'`, `'evacuation_false'`, `'fire_extent_exaggeration'`, `'official_update'`, `'factual_report'`, `'unrelated'`. Used by the validation script to verify theme coverage. |
| `location_mentioned` | string | optional | Feature | Geographic entity extracted or assigned during generation, e.g. `'Gippsland'`, `'East Gippsland'`, `'Victoria'`. Null if no location reference in post. Supports geo-filtering downstream. |
| `timestamp_simulated` | string | required | Feature / context | ISO 8601 datetime string representing the simulated post date. Generated within the 2019–2023 Victorian fire season window to align with training data temporal range. |
| `source_credibility` | float | optional | Derived feature | Numeric credibility score 0.0–1.0. 0.0 = clearly fabricated / extreme misinformation; 1.0 = official verified source. Derived heuristically during generation, not model-predicted. |
| `language` | string | required | Filter / QA | Always `'en'` for this dataset. Included for schema completeness and to support future multilingual extension. |
| `generation_template` | string | internal | QA / audit | Identifier for the generation template used to produce this record, e.g. `'fake_arson_v2'`, `'official_agency_v1'`. Enables tracing which template produced which samples and auditing distribution balance. |
| `split` | string | required | Pipeline control | Dataset split assignment: `'train'`, `'val'`, or `'test'`. Pre-assigned at generation time using stratified split (70/15/15) to ensure label and theme balance across splits. |

---

## 4. Controlled Vocabularies (Enum Fields)

Fields with controlled vocabularies are listed below. The validation script should reject any record where an enum field carries a value not in this list.

| Field | Allowed Values | Notes |
|---|---|---|
| `label` | `misinformation`, `credible`, `unverified` | Binary mapping: credible=0, misinformation=1 for baseline model |
| `platform` | `twitter`, `facebook`, `reddit`, `news_article`, `official_agency` | |
| `narrative_theme` | `arson_blame`, `govt_inaction`, `evacuation_false`, `fire_extent_exaggeration`, `official_update`, `factual_report`, `unrelated` | Must achieve ≥5% coverage per theme in training split |
| `split` | `train`, `val`, `test` | Stratified 70/15/15 by label and `narrative_theme` |
| `language` | `en` | Fixed for v1.0 |

---

## 5. Target Label Distribution

The dataset should be generated with the following approximate label distribution. This is intentionally imbalanced to reflect the real-world dominance of misinformation-type content during fire events.

| Label | Target Share | Rationale |
|---|---|---|
| `misinformation` | ~60% | Reflects real-world dominance of misinformation-type posts on social platforms during fire events |
| `credible` | ~30% | Official agency posts, verified news sources, fact-based content |
| `unverified` | ~10% | Posts that cannot be classified confidently — preserves ambiguity present in real data |

---

## 6. Example Record (JSON)

A valid synthetic record conforming to this schema looks like the following. This example can be used as a test case for the validation script.

```json
{
  "post_id": "fp_a3f8c21b",
  "text": "They're not telling us how bad the fire really is. Saw flames 5km from the highway and there's nothing on the ABC. Classic govt cover-up.",
  "label": "misinformation",
  "platform": "facebook",
  "narrative_theme": "govt_inaction",
  "location_mentioned": "East Gippsland",
  "timestamp_simulated": "2020-01-04T14:32:00+11:00",
  "source_credibility": 0.12,
  "language": "en",
  "generation_template": "fake_govt_inaction_v1",
  "split": "train"
}
```

---

## 7. Validation Requirements

The data validation script should enforce the following checks against this schema. A record fails validation if any required check is not satisfied.

- **Required fields present:** `post_id`, `text`, `label`, `platform`, `narrative_theme`, `timestamp_simulated`, `language`, `generation_template`, `split` must all be non-null and non-empty.

- **`post_id` uniqueness:** No two records may share the same `post_id`. Duplicate detection should be run across the full dataset, not per-split.

- **Enum conformance:** `label`, `platform`, `narrative_theme`, `split`, and `language` must each carry a value from the controlled vocabulary defined in Section 4.

- **Text length:** `text` must be between 20 and 300 characters. Records outside this range should be flagged (not silently dropped) so the generator can be adjusted.

- **`source_credibility` range:** If present, must be a float in [0.0, 1.0]. Values outside this range are invalid.

- **Timestamp format:** `timestamp_simulated` must be a valid ISO 8601 datetime string. Values outside the 2019–2023 window should be flagged as a warning (not an error) since future extension may use other date ranges.

- **Theme coverage:** The training split must contain at least 5% representation for each `narrative_theme` value. Themes below this threshold should be flagged so the generator can top up underrepresented classes.

- **Split distribution:** The overall train/val/test ratio should be approximately 70/15/15 (±5%). Label distribution within each split should be approximately consistent with the target distribution in Section 5.

---

## 8. Version History

| Version | Date | Changes |
|---|---|---|
| v0.1 | April 2026 | Initial schema: `post_id`, `text`, `label`, `platform`, `timestamp_simulated`, `language` |
| v0.2 (current) | May 2026 | Added `narrative_theme` (required) to support clustering task; added `source_credibility` (optional derived feature); added `generation_template` for audit traceability; added `split` field; expanded enum definitions; aligned label values with target distribution; added standalone JSON Schema section |
