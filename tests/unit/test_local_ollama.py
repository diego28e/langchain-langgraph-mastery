"""Module 14: Ollama status, model checks and the get_model wiring (no server needed)."""
import httpx
import pytest

from mastery.local import ModelMissing, OllamaUnavailable, fits_in_memory, measure, ollama_status, require_model
from mastery.models import get_model, model_string

TAGS = {"models": [{"name": "qwen3:4b", "size": 2_500_000_000, "details": {"family": "qwen3"}},
                   {"name": "nomic-embed-text:latest", "size": 274_000_000, "details": {"family": "nomic-bert"}}]}
SHOW = {"qwen3:4b": {"capabilities": ["completion", "tools", "thinking"], "model_info": {"qwen3.context_length": 40960},
                     "details": {"family": "qwen3", "parameter_size": "4.0B", "quantization_level": "Q4_K_M"}},
        "nomic-embed-text:latest": {"capabilities": ["embedding"], "details": {"family": "nomic-bert"}}}


def fake_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.5"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=TAGS)
        if request.url.path == "/api/show":
            import json
            return httpx.Response(200, json=SHOW[json.loads(request.content)["model"]])
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_status_lists_models_with_capabilities():
    s = ollama_status("http://local:11434", client=fake_client())
    assert s.running and s.version == "0.40.5"
    m = s.get("qwen3:4b")
    assert m.tools and m.context_length == 40960 and m.quantization == "Q4_K_M" and m.size_gb == 2.5
    assert s.get("nomic-embed-text").capabilities == ("embedding",)


def test_server_down_is_reported_not_raised():
    def down(request):
        raise httpx.ConnectError("refused")
    s = ollama_status("http://local:1", client=httpx.Client(transport=httpx.MockTransport(down)))
    assert not s.running and "ConnectError" in s.error
    with pytest.raises(OllamaUnavailable, match="Start the Ollama app"):
        require_model("qwen3:4b", s)


def test_require_model_says_how_to_pull_and_checks_capabilities():
    s = ollama_status("http://local:11434", client=fake_client())
    with pytest.raises(ModelMissing, match="ollama pull llama3.2:3b"):
        require_model("llama3.2:3b", s)
    with pytest.raises(ValueError, match="tools"):
        require_model("nomic-embed-text", s, need=("tools",))
    assert require_model("qwen3:4b", s, need=("tools",)).name == "qwen3:4b"


def test_fits_in_memory_for_a_cpu_only_32gb_laptop():
    assert fits_in_memory(2.5, 31.8) == "cpu"
    assert fits_in_memory(14.0, 31.8) == "cpu"
    assert fits_in_memory(40.0, 31.8) == "no"
    assert fits_in_memory(2.5, 16, vram_gb=8) == "gpu"


def test_measure_uses_ollama_counters():
    from langchain_core.messages import AIMessage

    class M:
        model = "qwen3:4b"
        def invoke(self, prompt):
            return AIMessage("hi", response_metadata={"eval_count": 20, "eval_duration": 2_000_000_000,
                                                      "load_duration": 1_500_000_000, "prompt_eval_count": 9})
    s = measure(M(), "x")
    assert s.tokens_per_s == 10.0 and s.load_s == 1.5 and s.output_tokens == 20 and s.text == "hi"


def test_get_model_ollama_role_and_params(monkeypatch):
    pytest.importorskip("langchain_ollama")
    monkeypatch.setenv("MASTERY_MODEL_LOCAL", "qwen3:4b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/")
    assert model_string("fast", "ollama") == "ollama:qwen3:4b"
    assert model_string("vision", "ollama").startswith("ollama:")
    llm = get_model("fast", "ollama", temperature=0, max_tokens=64)
    assert type(llm).__name__ == "ChatOllama"
    assert llm.model == "qwen3:4b" and llm.num_predict == 64 and llm.reasoning is False
    assert llm.base_url == "http://127.0.0.1:11434" and llm.client_kwargs["timeout"] == 300.0
