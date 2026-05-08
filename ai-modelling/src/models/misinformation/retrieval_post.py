from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch


@dataclass
class RetrievalConfig:
    top_k: int = 4
    min_score: float = 0.2
    text_col: str = "text"
    label_col: str = "label"
    id_col: str = "id"
    exclude_same_id: bool = True
    require_labeled_source: bool = True


class RetrieverPost:
    """
    RAEmoLLM-style retrieval:
      - target embeddings ET
      - source embeddings ES
      - cosine similarity
      - top-K source text-label examples per target

    This version is fixed for:
      - labeled source pools (e.g., AMTCele)
      - target/source separation
      - optional self-id exclusion
      - strict shape/column checks
    """

    def __init__(self, config: RetrievalConfig | None = None) -> None:
        self.config = config or RetrievalConfig()

    @staticmethod
    def _load_embeddings(path: str | Path) -> np.ndarray:
        arr = torch.load(path, map_location="cpu", weights_only=False)
        if isinstance(arr, np.ndarray):
            return arr
        return np.array(arr)

    @staticmethod
    def _cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
        b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-12)
        return a_norm @ b_norm.T

    def _validate_frames(
        self,
        target_df: pd.DataFrame,
        source_df: pd.DataFrame,
        target_emb: np.ndarray,
        source_emb: np.ndarray,
    ) -> None:
        if len(target_df) != target_emb.shape[0]:
            raise ValueError(
                f"target_df length ({len(target_df)}) and target_emb rows ({target_emb.shape[0]}) mismatch"
            )
        if len(source_df) != source_emb.shape[0]:
            raise ValueError(
                f"source_df length ({len(source_df)}) and source_emb rows ({source_emb.shape[0]}) mismatch"
            )

        for col in [self.config.id_col, self.config.text_col]:
            if col not in target_df.columns:
                raise ValueError(f"Missing target column: {col}")
            if col not in source_df.columns:
                raise ValueError(f"Missing source column: {col}")

        if self.config.require_labeled_source:
            if self.config.label_col not in source_df.columns:
                raise ValueError(f"Missing source label column: {self.config.label_col}")
            if source_df[self.config.label_col].isna().any():
                raise ValueError("Source label column contains missing values.")

    def retrieve(
        self,
        target_df: pd.DataFrame,
        source_df: pd.DataFrame,
        target_emb: np.ndarray,
        source_emb: np.ndarray,
    ) -> list[dict[str, Any]]:
        self._validate_frames(target_df, source_df, target_emb, source_emb)

        scores = self._cosine_sim(target_emb, source_emb)  # [N_target, N_source]
        out: list[dict[str, Any]] = []

        # speed: local arrays for repeated access
        src_ids = source_df[self.config.id_col].astype(str).to_numpy()
        src_texts = source_df[self.config.text_col].astype(str).to_numpy()
        src_labels = (
            source_df[self.config.label_col].astype(str).str.strip().str.lower().to_numpy()
            if self.config.label_col in source_df.columns
            else np.array([""] * len(source_df))
        )

        for i in range(scores.shape[0]):
            row_scores = scores[i]
            target_id = str(target_df.iloc[i][self.config.id_col])

            # sort descending by similarity
            ranked_idx = np.argsort(-row_scores)

            examples: list[dict[str, Any]] = []
            for j in ranked_idx:
                s = float(row_scores[j])

                # threshold
                if s < self.config.min_score:
                    break  # ranked desc, safe early stop

                # exclude same-id retrieval if requested
                if self.config.exclude_same_id and src_ids[j] == target_id:
                    continue

                # require valid label if strict
                label = src_labels[j]
                if self.config.require_labeled_source and (label == "" or label == "nan"):
                    continue

                examples.append(
                    {
                        "source_post_id": src_ids[j],
                        "text": src_texts[j],
                        "label": label if label else None,
                        "score": s,
                    }
                )

                if len(examples) >= self.config.top_k:
                    break

            out.append(
                {
                    "target_post_id": target_id,
                    "target_text": str(target_df.iloc[i][self.config.text_col]),
                    "retrieved_examples": examples,
                }
            )

        return out

    def run(
        self,
        target_csv: str | Path,
        source_csv: str | Path,
        target_emb_path: str | Path,
        source_emb_path: str | Path,
    ) -> list[dict[str, Any]]:
        target_df = pd.read_csv(target_csv)
        source_df = pd.read_csv(source_csv)

        target_emb = self._load_embeddings(target_emb_path)
        source_emb = self._load_embeddings(source_emb_path)

        return self.retrieve(target_df, source_df, target_emb, source_emb)