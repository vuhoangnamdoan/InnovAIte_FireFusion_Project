import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.models.misinformation.llm_client import (
    LLMClient, LLMConfig, clean_json_content, render_prompt
)

def test_clean_json_content_removes_fence():
    raw = "```json\n{\"a\":1}\n```"
    assert clean_json_content(raw) == '{"a":1}'

def test_render_prompt_replaces_json_values():
    tpl = "Task: {task}\nData: {record_json}"
    out = render_prompt(tpl, {"task": "x", "record_json": {"id": 1}})
    assert "Task: x" in out
    assert '"id": 1' in out

def test_generate_json_invalid_top_level(monkeypatch):
    cfg = LLMConfig(provider="gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    monkeypatch.setattr(LLMClient, "_build_client", staticmethod(lambda _: object()))
    c = LLMClient(cfg)
    monkeypatch.setattr(c, "generate_text", lambda _: '["not-object"]')
    with pytest.raises(ValueError, match="top-level JSON object"):
        c.generate_json("prompt")