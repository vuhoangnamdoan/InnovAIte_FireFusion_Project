from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import pandas as pd


@dataclass
class ConstructInstructsConfig:
    # Paper-style task prompt
    task_prompt: str = (
        "Determine whether the target text is fake or legit using the retrieved examples."
    )
    include_affective_info: bool = False  # Template 2 if True
    top_k: int = 4
    # For strict AMTCele-aligned retrieval supervision
    allowed_labels: tuple[str, ...] = ("fake", "legit")
    drop_unlabeled_examples: bool = True
    require_min_examples: int = 1


class InferenceInstructionBuilderPost:
    """
    RAEmoLLM inference instruction construction adapted for post schema.

    Inputs:
      - target posts DataFrame
      - retrieved payload from RetrieverPost:
          [{"target_post_id": ..., "retrieved_examples": [...]}]

    Output:
      - records for LLM generation:
          [{"post_id", "instruction", "input", "output", "num_examples"}]
    """

    def __init__(self, config: ConstructInstructsConfig | None = None) -> None:
        self.config = config or ConstructInstructsConfig()

    @staticmethod
    def _safe_str(v: Any) -> str:
        return "" if v is None else str(v)

    def _normalize_label(self, label: Any) -> str:
        lbl = self._safe_str(label).strip().lower()
        return lbl

    def _is_allowed_label(self, label: str) -> bool:
        return label in self.config.allowed_labels

    def _format_example_template1(self, ex: dict[str, Any]) -> str:
        # Paper template: Text + Label
        text = self._safe_str(ex.get("text"))
        label = self._normalize_label(ex.get("label", ""))
        return f"Text: {text}. The label of text: {label}."

    def _format_example_template2(self, ex: dict[str, Any]) -> str:
        # Paper template 2: Text + Affective info + Label
        text = self._safe_str(ex.get("text"))
        label = self._normalize_label(ex.get("label", ""))
        aff = self._safe_str(ex.get("affective_info", ex.get("Vreg", "unknown")))
        return f"Text: {text}. Affective info: {aff}. The label of text: {label}."

    def _filter_examples(self, retrieved_examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # keep top-k first
        exs = retrieved_examples[: self.config.top_k]

        filtered: list[dict[str, Any]] = []
        for ex in exs:
            lbl = self._normalize_label(ex.get("label", ""))
            if self.config.drop_unlabeled_examples:
                if not self._is_allowed_label(lbl):
                    continue
            # write back normalized label for consistent formatting
            ex2 = dict(ex)
            ex2["label"] = lbl
            filtered.append(ex2)
        return filtered

    def build_instruction(
        self,
        target_post: dict[str, Any],
        retrieved_examples: list[dict[str, Any]],
    ) -> tuple[str, int]:
        target_text = self._safe_str(target_post.get("text", target_post.get("content", "")))
        exs = self._filter_examples(retrieved_examples)

        # If no usable retrieved examples, fallback to "few-shot empty" form
        if len(exs) < self.config.require_min_examples:
            fallback_instruction = (
                f"Task: {self.config.task_prompt}\n"
                f"Target text: {target_text}\n"
                f"Here are a few examples:\n"
                f"(no valid retrieved labeled examples available)\n"
                f"According to the above information, the label of target text:"
            )
            return fallback_instruction, 0

        if self.config.include_affective_info:
            formatted_examples = "\n".join(self._format_example_template2(ex) for ex in exs)
            target_aff = self._safe_str(target_post.get("Vreg", target_post.get("affective_info", "unknown")))

            # Template 2 (paper style)
            instruction = (
                f"Task: {self.config.task_prompt}\n"
                f"Target text: {target_text}. Affective info: {target_aff}\n"
                f"Here are a few examples retrieved by affective info:\n"
                f"{formatted_examples}\n"
                f"According to the above information, the label of target text:"
            )
            return instruction, len(exs)

        # Template 1 (paper style)
        formatted_examples = "\n".join(self._format_example_template1(ex) for ex in exs)
        instruction = (
            f"Task: {self.config.task_prompt}\n"
            f"Target text: {target_text}\n"
            f"Here are a few examples:\n"
            f"{formatted_examples}\n"
            f"According to the above information, the label of target text:"
        )
        return instruction, len(exs)

    def run(
        self,
        target_posts_df: pd.DataFrame,
        retrieved_payload: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        # Index retrieval results by target_post_id for fast lookup
        by_target = {
            str(item.get("target_post_id")): item.get("retrieved_examples", [])
            for item in retrieved_payload
        }

        records: list[dict[str, Any]] = []
        for _, row in target_posts_df.iterrows():
            post_id = str(row.get("id", ""))
            target_post = row.to_dict()
            retrieved_examples = by_target.get(post_id, [])

            instruction, used_n = self.build_instruction(target_post, retrieved_examples)

            # same output format expected by your inference stage
            records.append(
                {
                    "post_id": post_id,
                    "instruction": instruction,
                    "input": "",
                    "output": "",  # placeholder for model generation
                    "num_examples": used_n,
                }
            )

        return records

    @staticmethod
    def save_jsonl(records: list[dict[str, Any]], output_path: str | Path) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return str(output_path)

    @staticmethod
    def save_csv(records: list[dict[str, Any]], output_path: str | Path) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(records).to_csv(output_path, index=False)
        return str(output_path)