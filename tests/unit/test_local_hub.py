"""mastery.local.hub: licence verdicts, quant parsing and the snapshot round trip, all offline."""
from pathlib import Path
from types import SimpleNamespace

from mastery.local.hub import (HubModel, license_verdict, load_snapshot, model_details, ollama_hf_tag, quant_files,
                               save_snapshot, search_models, to_hub_model)

SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "samples" / "local" / "hub-snapshot.json"


def test_license_verdicts():
    assert license_verdict("apache-2.0") == "permissive"
    assert license_verdict("MIT") == "permissive"
    assert license_verdict("cc-by-nc-4.0") == "non-commercial"
    assert license_verdict("llama3.2") == "read the terms"
    assert license_verdict(None) == "unknown"


def test_to_hub_model_reads_model_info_like_objects():
    info = SimpleNamespace(id="org/m", card_data={"license": "mit"}, gated="manual", pipeline_tag="text-generation",
                           downloads=10, likes=2, siblings=[SimpleNamespace(rfilename="model.safetensors", size=2 * 1024**3),
                                                            SimpleNamespace(rfilename="README.md", size=10)])
    m = to_hub_model(info)
    assert (m.license, m.verdict, m.needs_token, m.size_gb()) == ("mit", "permissive", True, 2.0)


def test_quant_files_sorted_and_parsed():
    m = HubModel("o/r-GGUF", files=(("r-Q8_0.gguf", 4 * 1024**3), ("r-Q4_K_M.gguf", 2 * 1024**3),
                                    ("r-UD-IQ1_S.gguf", 1024**3), ("README.md", 5)))
    assert quant_files(m) == [("IQ1_S", 1.0), ("Q4_K_M", 2.0), ("Q8_0", 4.0)]
    assert ollama_hf_tag("o/r-GGUF", "Q4_K_M") == "hf.co/o/r-GGUF:Q4_K_M"


def test_search_and_details_use_the_given_api():
    calls = {}

    class FakeApi:
        def list_models(self, **kw):
            calls["list"] = kw
            return [SimpleNamespace(id="a/b", card_data=None, gated=False, pipeline_tag=None, downloads=1, likes=0, siblings=None)]

        def model_info(self, repo_id, files_metadata):
            calls["info"] = (repo_id, files_metadata)
            return SimpleNamespace(id=repo_id, card_data={"license": "apache-2.0"}, siblings=[])

    assert [m.id for m in search_models("qwen3", task="text-generation", api=FakeApi())] == ["a/b"]
    assert calls["list"]["sort"] == "downloads" and calls["list"]["filter"] == "text-generation"
    assert model_details("x/y", api=FakeApi()).license == "apache-2.0" and calls["info"] == ("x/y", True)


def test_snapshot_round_trip(tmp_path):
    m = HubModel("o/r", license="mit", files=(("a.gguf", 3),))
    loaded = load_snapshot(save_snapshot([m], tmp_path / "s.json", recorded="2026-10-16"))
    assert loaded["o/r"] == m


def test_course_snapshot_has_what_lesson_14_02_reads():
    snap = load_snapshot(SNAPSHOT)
    assert snap["Qwen/Qwen3-4B-GGUF"].verdict == "permissive"
    assert ("Q4_K_M", 2.33) in quant_files(snap["Qwen/Qwen3-4B-GGUF"])
    assert snap["meta-llama/Llama-3.2-1B-Instruct"].needs_token
    assert snap["CohereLabs/c4ai-command-r7b-12-2024"].verdict == "non-commercial"
