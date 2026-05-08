import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from transformers import AutoTokenizer, LlamaModel


@dataclass
class IndexConstructConfig:
    embedding_model_name: str = "lzw1008/Emollama-chat-7b"
    device: str = "auto"


class IndexConstructorPost:
    """
    RAEmoLLM-style index construction adapted for:
      1) target post stream schema
      2) AMTCele-style labeled source schema
    """

    def __init__(self, config: IndexConstructConfig | None = None) -> None:
        self.config = config or IndexConstructConfig()

    # -----------------------------
    # Input normalization
    # -----------------------------
    def normalize_posts(self, input_path: str | Path) -> pd.DataFrame:
        p = Path(input_path)
        if p.suffix.lower() == ".json":
            payload = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload = payload.get("posts", [])
            df = pd.DataFrame(payload)
        elif p.suffix.lower() == ".csv":
            df = pd.read_csv(p)
        else:
            raise ValueError(f"Unsupported input format: {p.suffix}")

        cols = set(df.columns)

        # Case A: AMTCele-like source pool (domain,label,text)
        if {"label", "text"}.issubset(cols):
            out = pd.DataFrame()
            # Build stable id if missing
            out["id"] = df["id"] if "id" in df.columns else [f"src_{i}" for i in range(len(df))]
            out["text"] = df["text"].astype(str).str.replace("\n", " ", regex=False)
            out["label"] = df["label"].astype(str).str.strip().str.lower()
            out["author"] = ""
            out["platform"] = ""
            out["ts"] = ""
            out["post_url"] = ""
            out["share_count"] = 0
            out["domain"] = df["domain"].astype(str) if "domain" in df.columns else ""
        else:
            # Case B: your incoming posts schema
            out = pd.DataFrame()
            out["id"] = df["id"]
            out["text"] = df["content"].astype(str).str.replace("\n", " ", regex=False)
            out["label"] = None  # unlabeled target stream
            out["author"] = df.get("author", df.get("author_name", "")).fillna("").astype(str)
            out["platform"] = df.get("platform", "").fillna("").astype(str)
            out["ts"] = df.get("timestamp", df.get("ts", "")).fillna("").astype(str)
            out["post_url"] = df.get("post_url", "").fillna("").astype(str)
            out["share_count"] = pd.to_numeric(df.get("share_count", 0), errors="coerce").fillna(0).astype(int)
            out["domain"] = ""

        if out["id"].isna().any():
            raise ValueError("Missing 'id' in some rows.")
        if out["text"].isna().any() or (out["text"].str.strip() == "").any():
            raise ValueError("Missing/empty text content in some rows.")

        return out[
            ["id", "text", "label", "author", "platform", "ts", "post_url", "share_count", "domain"]
        ].copy()

    # -----------------------------
    # Prompt builders (paper style)
    # -----------------------------
    @staticmethod
    def _end(text: str) -> str:
        t = text.strip()
        if not t:
            return ""
        return t if t[-1] in ".!?" else t + "."

    def _construct_eireg(self, x: str, emo: str) -> str:
        pre = (
            "Calculate the intensity of emotion E in the tweet as a decimal value ranging from 0 to 1, "
            "with 0 representing the lowest intensity and 1 representing the highest intensity."
        )
        return f"Task: {pre} Tweet: {self._end(x)} Emotion E: {emo}. Intensity Score:"

    def _construct_eioc(self, x: str, emo: str) -> str:
        pre = (
            "Classify the tweet into one of four ordinal classes of intensity of emotion E that best represents "
            "the mental state of the tweeter. 0: no E can be inferred. 1: low amount of E can be inferred. "
            "2: moderate amount of E can be inferred. 3: high amount of E can be inferred."
        )
        return f"Task: {pre} Tweet: {self._end(x)} Emotion E: {emo}. Intensity Class:"

    def _construct_vreg(self, x: str) -> str:
        pre = (
            "Calculate the sentiment intensity or valence score of the tweet, "
            "which should be a real number between 0 (extremely negative) and 1 (extremely positive)."
        )
        return f"Task: {pre} Tweet: {self._end(x)} Intensity Score:"

    def _construct_voc(self, x: str) -> str:
        pre = (
            "Classify the tweet into one of seven ordinal classes, corresponding to various levels of positive and "
            "negative sentiment intensity, that best represents the mental state of the tweeter. "
            "3: very positive mental state can be inferred. 2: moderately positive mental state can be inferred. "
            "1: slightly positive mental state can be inferred. 0: neutral or mixed mental state can be inferred. "
            "-1: slightly negative mental state can be inferred. -2: moderately negative mental state can be inferred. "
            "-3: very negative mental state can be inferred."
        )
        return f"Task: {pre} Tweet: {self._end(x)} Intensity Class:"

    def _construct_ec(self, x: str) -> str:
        pre = (
            "Categorize the tweet's emotional tone as either 'neutral or no emotion' or identify the presence of one "
            "or more of the given emotions (anger, anticipation, disgust, fear, joy, love, optimism, pessimism, "
            "sadness, surprise, trust)."
        )
        return f"Task: {pre} Tweet: {self._end(x)} This tweet contains emotions:"

    # -----------------------------
    # Build instruction tables
    # -----------------------------
    def build_affective_instruction_tables(self, posts_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        emotions = ["anger", "fear", "joy", "sadness"]
        n = len(posts_df)

        eireg = []
        for emo in emotions:
            eireg.append(
                pd.DataFrame(
                    {"Instruction": posts_df["text"].apply(lambda x: self._construct_eireg(x, emo)), "Answer": [9999] * n}
                )
            )
        df_eireg = pd.concat(eireg, ignore_index=True)

        eioc = []
        for emo in emotions:
            eioc.append(
                pd.DataFrame(
                    {"Instruction": posts_df["text"].apply(lambda x: self._construct_eioc(x, emo)), "Answer": [9999] * n}
                )
            )
        df_eioc = pd.concat(eioc, ignore_index=True)

        df_vreg = pd.DataFrame({"Instruction": posts_df["text"].apply(self._construct_vreg), "Answer": [9999] * n})
        df_voc = pd.DataFrame({"Instruction": posts_df["text"].apply(self._construct_voc), "Answer": [9999] * n})
        df_ec = pd.DataFrame({"Instruction": posts_df["text"].apply(self._construct_ec), "Answer": [9999] * n})

        df_all = pd.concat([df_eireg, df_eioc, df_vreg, df_voc, df_ec], ignore_index=True)

        return {"EIreg": df_eireg, "EIoc": df_eioc, "Vreg": df_vreg, "Voc": df_voc, "Ec": df_ec, "ALL": df_all}

    @staticmethod
    def _save_jsonl(df: pd.DataFrame, path: Path) -> None:
        with path.open("w", encoding="utf-8") as f:
            for _, row in df.iterrows():
                f.write(
                    json.dumps(
                        {"instruction": row["Instruction"], "input": "", "output": row["Answer"]},
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    def save_affective_artifacts(
        self,
        out_dir: str | Path,
        data_name: str,
        posts_df: pd.DataFrame,
        tables: dict[str, pd.DataFrame],
    ) -> dict[str, str]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        paths: dict[str, str] = {}

        # IMPORTANT: includes label column for source retrieval pool
        posts_csv = out / f"{data_name}-posts-normalized.csv"
        posts_df.to_csv(posts_csv, index=False)
        paths["posts_csv"] = str(posts_csv)

        for key in ["EIreg", "EIoc", "Vreg", "Voc", "Ec", "ALL"]:
            fname = f"{data_name}-affective-all.csv" if key == "ALL" else f"{data_name}-{key}.csv"
            p = out / fname
            tables[key].to_csv(p, index=False)
            paths[f"{key.lower()}_csv"] = str(p)

        all_jsonl = out / f"{data_name}-affective-all.jsonl"
        self._save_jsonl(tables["ALL"], all_jsonl)
        paths["all_jsonl"] = str(all_jsonl)

        return paths

    # -----------------------------
    # Embeddings (paper-style)
    # -----------------------------
    def build_instruction_embeddings(self, instruction_csv_path: str | Path) -> torch.Tensor:
        df = pd.read_csv(instruction_csv_path)
        prompts = [f"Human: \n{x}\n\nAssistant:\n" for x in df["Instruction"].astype(str).tolist()]

        tokenizer = AutoTokenizer.from_pretrained(self.config.embedding_model_name)
        model = LlamaModel.from_pretrained(self.config.embedding_model_name, device_map="auto")
        tokenizer.pad_token_id = 0
        tokenizer.padding_side = "left"

        device = torch.device(0) if torch.cuda.is_available() else torch.device("cpu")
        vectors = []

        with torch.no_grad():
            for prompt in prompts:
                inputs = tokenizer(prompt, padding=True, return_tensors="pt")
                outputs = model(
                    input_ids=inputs["input_ids"].to(device),
                    attention_mask=inputs["attention_mask"].to(device),
                    output_hidden_states=True,
                )
                vec = torch.mean(outputs.last_hidden_state, dim=1).squeeze(0).cpu()
                vectors.append(vec)

        return torch.stack(vectors)

    # -----------------------------
    # End-to-end
    # -----------------------------
    def run(
        self,
        input_path: str | Path,
        out_dir: str | Path,
        data_name: str = "POSTS",
        build_embeddings_for: str = "Vreg",
    ) -> dict[str, str]:
        posts_df = self.normalize_posts(input_path)
        tables = self.build_affective_instruction_tables(posts_df)
        paths = self.save_affective_artifacts(out_dir, data_name, posts_df, tables)

        emb_csv = Path(out_dir) / f"{data_name}-{build_embeddings_for}.csv"
        emb = self.build_instruction_embeddings(emb_csv)
        emb_path = Path(out_dir) / f"{data_name}-{build_embeddings_for}-embeddings.pth"
        torch.save(emb.numpy(), emb_path)
        paths["embedding_pth"] = str(emb_path)

        return paths