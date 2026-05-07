from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

from dotenv import load_dotenv
from openai import OpenAI
from google import genai


LOGGER = logging.getLogger(__name__)
load_dotenv()


Provider = Literal["gemini", "openai"]


@dataclass
class LLMConfig:
    provider: Provider = "gemini"
    model: str = "gemini-3-flash-preview"
    temperature: float = 0.2
    max_retries: int = 3
    retry_backoff_sec: float = 2.0
    request_delay_sec: float = 0.5


class LLMClient:
    """
    Provider-agnostic LLM client for misinformation NLP tasks.

    Supports:
    - prompt-based text generation
    - prompt-based JSON generation (with cleanup + validation)
    - retry + backoff
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = self._build_client(config.provider)

    @staticmethod
    def _build_client(provider: Provider) -> Any:
        if provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise EnvironmentError("Missing GEMINI_API_KEY")
            return genai.Client(api_key=api_key)

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError("Missing OPENAI_API_KEY")
            return OpenAI(api_key=api_key)

        raise ValueError(f"Unsupported provider: {provider}")

    def _call_once(self, prompt: str) -> str:
        if self.config.provider == "gemini":
            response = self._client.models.generate_content(
                model=self.config.model,
                contents=prompt,
            )
            return (response.text or "").strip()

        # openai
        response = self._client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip()

    def generate_text(self, prompt: str) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                output = self._call_once(prompt)
                if not output:
                    raise ValueError("Empty response from LLM")
                if self.config.request_delay_sec > 0:
                    time.sleep(self.config.request_delay_sec)
                return output
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                LOGGER.warning("LLM call failed (attempt %s/%s): %s", attempt, self.config.max_retries, exc)
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_backoff_sec * attempt)

        raise RuntimeError(f"LLM call failed after retries: {last_error}") from last_error

    def generate_json(self, prompt: str) -> dict[str, Any]:
        text = self.generate_text(prompt)
        cleaned = clean_json_content(text)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model output is not valid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Expected top-level JSON object from model output")

        return parsed


def clean_json_content(content: str) -> str:
    """
    Removes markdown code fences and extracts first JSON object block.
    """
    content = content.strip()

    # Strip common markdown fences
    if content.startswith("```json"):
        content = content[7:].strip()
    elif content.startswith("```"):
        content = content[3:].strip()

    if content.endswith("```"):
        content = content[:-3].strip()

    # If model wraps explanations around JSON, try extracting first {...} block.
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    return match.group(0).strip() if match else content


def render_prompt(template: str, variables: dict[str, Any]) -> str:
    """
    Simple placeholder replacement using {key} format.
    """
    prompt = template
    for key, value in variables.items():
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, ensure_ascii=False)
        else:
            value_str = str(value)
        prompt = prompt.replace(f"{{{key}}}", value_str)
    return prompt


def load_prompt_template(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def _ensure_dir(path: str | Path) -> Path:
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def cluster_narratives(
    client: LLMClient,
    posts: Sequence[dict[str, Any]],
    prompt_template: str,
    *,
    strict_json: bool = True,
) -> dict[str, Any]:
    """
    Cluster a batch of posts into misinformation narratives.

    Expected post item format (flexible): {"id": "...", "text": "...", ...}
    Prompt template should reference:
      - {posts_json}
      - optional other variables you include
    """
    prompt = render_prompt(
        prompt_template,
        {
            "posts_json": posts,
            "task": "narrative_clustering",
        },
    )
    return client.generate_json(prompt) if strict_json else {"raw_output": client.generate_text(prompt)}


def generate_augmented_samples(
    client: LLMClient,
    records: Sequence[dict[str, Any]],
    prompt_template: str,
    *,
    strict_json: bool = True,
) -> list[dict[str, Any]]:
    """
    Generate synthetic/augmented misinformation samples from input records.
    """
    outputs: list[dict[str, Any]] = []

    for idx, record in enumerate(records):
        prompt = render_prompt(
            prompt_template,
            {
                "record_json": record,
                "task": "misinformation_data_generation",
            },
        )

        try:
            result = client.generate_json(prompt) if strict_json else {"raw_output": client.generate_text(prompt)}
            outputs.append(result)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Generation failed at index %s: %s", idx, exc)
            outputs.append(
                {
                    "error": str(exc),
                    "input_record": record,
                }
            )

    return outputs


def batch_process_json_files(
    client: LLMClient,
    input_dir: str | Path,
    output_dir: str | Path,
    prompt_template: str,
    *,
    mode: Literal["cluster", "generate"] = "generate",
) -> dict[str, Any]:
    """
    Process each JSON file in a folder and write one output JSON per input file.

    - mode='cluster': expects input file to contain {"posts":[...]} or a list directly
    - mode='generate': sends the full file content as {record_json}
    """
    in_dir = Path(input_dir)
    out_dir = _ensure_dir(output_dir)

    if not in_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {in_dir}")

    json_files = sorted(p for p in in_dir.iterdir() if p.suffix.lower() == ".json")
    if not json_files:
        LOGGER.warning("No JSON files found in %s", in_dir)
        return {"processed": 0, "failed": 0, "outputs": []}

    processed = 0
    failed = 0
    outputs: list[str] = []

    for file_path in json_files:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))

            if mode == "cluster":
                if isinstance(payload, dict) and "posts" in payload:
                    posts = payload["posts"]
                elif isinstance(payload, list):
                    posts = payload
                else:
                    raise ValueError("Cluster mode expects list or {'posts': [...]} JSON")
                result = cluster_narratives(client, posts, prompt_template, strict_json=True)
            else:
                prompt = render_prompt(
                    prompt_template,
                    {
                        "record_json": payload,
                        "task": "misinformation_data_generation",
                    },
                )
                result = client.generate_json(prompt)

            out_file = out_dir / file_path.name
            out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

            outputs.append(str(out_file))
            processed += 1
            LOGGER.info("Processed %s -> %s", file_path.name, out_file.name)

        except Exception as exc:  # noqa: BLE001
            failed += 1
            LOGGER.error("Failed processing %s: %s", file_path.name, exc)

    return {
        "processed": processed,
        "failed": failed,
        "outputs": outputs,
    }