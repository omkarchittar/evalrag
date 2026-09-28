import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_evaluation_api import evaluation_api  # noqa: F401

from evalrag.benchmark import API, BenchmarkError, load_bundle, seed, start_run
from evalrag.config import Settings
from evalrag.runtime import QueryProviders, provider_identity

BUNDLE = Path(__file__).resolve().parents[2] / "benchmarks"


def test_authored_corpus_is_complete_and_consistent():
    name, cases, docs = load_bundle(BUNDLE)
    assert "Meridian" in name
    assert len(cases) == 60 and len(docs) == 8
    assert sum(case["expected_abstention"] is True for case in cases) == 6
    assert sum(case["expected_tool"] == "calculator" for case in cases) == 6
    assert all(
        case["expected_answer"] and case["expected_sources"]
        for case in cases
        if not case["expected_abstention"]
    )
    assert all(b"Fictional benchmark policy" in document for document in docs.values())


def test_bundle_detects_corpus_tampering(tmp_path):
    import shutil

    shutil.copytree(BUNDLE, tmp_path / "bundle")
    (tmp_path / "bundle/corpus/retention.md").write_text("Unrelated content")
    with pytest.raises(BenchmarkError, match="checksum mismatch"):
        load_bundle(tmp_path / "bundle")


def test_provider_identity_is_opaque_and_ignores_rotated_credentials():
    first = provider_identity("https://user:secret@EXAMPLE.com/v1/")
    assert first == provider_identity("https://other:rotated@example.com/v1")
    assert "secret" not in first and "example" not in first
    assert first != provider_identity("https://example.com/v2")
    providers = QueryProviders(Settings(openai_base_url="https://example.com/v1"))
    providers.settings.openai_base_url = "https://changed.example/v1"
    assert providers.identity == first and providers.base_url == "https://example.com/v1"


@pytest.mark.postgres
def test_seed_is_repeatable_and_run_requires_ready_corpus(evaluation_api, tmp_path):  # noqa: F811
    client, _, _, headers = evaluation_api

    class Adapter:
        items = API.items

        def request(self, method, path, **kwargs):
            response = client.request(method, path, headers=headers, **kwargs)
            assert response.is_success, response.text
            return response.json()

    adapter = Adapter()
    args = SimpleNamespace(
        bundle=BUNDLE, state=tmp_path / "state.json", api="http://localhost:8000", index="small"
    )
    seed(adapter, args)
    original = json.loads(args.state.read_text())
    seed(adapter, args)
    assert json.loads(args.state.read_text()) == original
    for kb_id in original["knowledge_bases"].values():
        assert len(adapter.items(f"/api/knowledge-bases/{kb_id}/documents")) == 8
    data = adapter.request("GET", f"/api/datasets/{original['dataset_id']}")
    assert data["version"] == 2 and len(data["cases"]) == 60
    with pytest.raises(BenchmarkError, match="fully indexed"):
        start_run(adapter, args)
    args.api = "http://localhost:8001"
    with pytest.raises(BenchmarkError, match="another API"):
        seed(adapter, args)


def test_runner_queues_valid_agent_configuration_and_checks_dataset(tmp_path):
    import hashlib

    from evalrag.evaluation_api import RunInput

    _, cases, documents = load_bundle(BUNDLE)

    class Adapter:
        changed = False
        body = None

        def items(self, path):
            return [
                {"checksum": hashlib.sha256(content).hexdigest(), "status": "ready"}
                for content in documents.values()
            ]

        def request(self, method, path, **kwargs):
            if method == "GET":
                return {"cases": [] if self.changed else cases}
            self.body = RunInput.model_validate(kwargs["json"])
            return {"id": "run", "status": "queued"}

    args = SimpleNamespace(
        api="http://localhost:8000",
        state=tmp_path / "state.json",
        bundle=BUNDLE,
        index="small",
        top_k=5,
        prompt="grounded-v1",
        model=None,
        evaluator=None,
        no_semantics=False,
        name="Baseline",
        key="benchmark-baseline",
        wait=0,
    )
    args.state.write_text(
        json.dumps(
            {
                "base_url": args.api,
                "knowledge_bases": {"small": "kb"},
                "dataset_id": "dataset",
                "workspace_id": "workspace",
            }
        )
    )
    adapter = Adapter()
    start_run(adapter, args)
    assert adapter.body.query.agent_mode is True
    adapter.changed = True
    with pytest.raises(BenchmarkError, match="Dataset differs"):
        start_run(adapter, args)
