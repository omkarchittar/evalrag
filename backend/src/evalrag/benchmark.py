"""Reproducible benchmark commands against the same authenticated API as the UI."""

import argparse
import getpass
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from evalrag.evaluation_api import CaseInput


class BenchmarkError(Exception):
    pass


def load_bundle(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    dataset = json.loads((directory / "dataset.json").read_text())
    if manifest["schema_version"] != 1 or dataset["schema_version"] != 1:
        raise BenchmarkError("Unsupported benchmark schema")
    documents = {}
    for entry in manifest["documents"]:
        filename = entry["filename"]
        if Path(filename).name != filename or filename in documents:
            raise BenchmarkError("Invalid or duplicate corpus filename")
        content = (directory / "corpus" / filename).read_bytes()
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise BenchmarkError(f"Corpus checksum mismatch: {filename}")
        documents[filename] = content
    cases = [CaseInput.model_validate(case).model_dump() for case in dataset["cases"]]
    if not 50 <= len(cases) <= 100 or len(cases) != manifest["cases"]:
        raise BenchmarkError("Benchmark must contain 50–100 cases matching its manifest")
    if len({case["question"] for case in cases}) != len(cases):
        raise BenchmarkError("Duplicate benchmark questions")
    hashes = {entry["sha256"] for entry in manifest["documents"]}
    if any(not set(case["expected_sources"]) <= hashes for case in cases):
        raise BenchmarkError("Expected source is absent from the corpus")
    return dataset["name"], cases, documents


def case_fingerprint(cases):
    canonical = sorted(json.dumps(case, sort_keys=True, ensure_ascii=False) for case in cases)
    return hashlib.sha256(json.dumps(canonical).encode()).hexdigest()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


class API:
    def __init__(self, base_url, email, password):
        url = urlsplit(base_url)
        if (
            url.scheme not in {"https", "http"}
            or (url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"})
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise BenchmarkError("Use HTTPS (or loopback HTTP) without URL credentials or query")
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=60)
        try:
            token = self.request(
                "POST", "/api/auth/token", json={"email": email, "password": password}
            )
            self.client.headers["Authorization"] = "Bearer " + token["access_token"]
        except BaseException:
            self.client.close()
            raise

    def request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        if response.is_error:
            # Do not echo provider messages, request bodies, tokens or credentials.
            raise BenchmarkError(f"API {method} {path}: HTTP {response.status_code}")
        return response.json()

    def items(self, path):
        result = []
        while True:
            page = self.request("GET", path, params={"limit": 100, "offset": len(result)})
            result.extend(page["items"])
            if len(result) >= page["total"] or not page["items"]:
                return result

    def close(self):
        self.client.close()


def seed(api, args):
    name, cases, documents = load_bundle(args.bundle)
    state_path = Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    bundle_hash = case_fingerprint(cases)
    identity = {"base_url": args.api.rstrip("/"), "bundle_hash": bundle_hash}
    if state and any(state.get(key) != value for key, value in identity.items()):
        raise BenchmarkError("State belongs to another API or corpus; use a new --state path")
    state.update(identity)
    if "workspace_id" not in state:
        workspace = api.request("POST", "/api/workspaces", json={"name": name})
        state["workspace_id"] = workspace["id"]
        save(state_path, state)
    prefix = f"/api/workspaces/{state['workspace_id']}"
    state.setdefault("knowledge_bases", {})
    for variant, model, dimension in [
        ("small", "text-embedding-3-small", 1536),
        ("large", "text-embedding-3-large", 3072),
    ]:
        if variant not in state["knowledge_bases"]:
            kb = api.request(
                "POST",
                prefix + "/knowledge-bases",
                json={
                    "name": f"Meridian / {variant}",
                    "embedding_model": model,
                    "embedding_dimension": dimension,
                    "chunk_strategy": "recursive",
                    "chunk_size": 400,
                    "chunk_overlap": 60,
                },
            )
            state["knowledge_bases"][variant] = kb["id"]
            save(state_path, state)
        for filename, content in documents.items():
            api.request(
                "POST",
                f"/api/knowledge-bases/{state['knowledge_bases'][variant]}/documents",
                files={"file": (filename, content, "text/markdown")},
            )
    if "dataset_id" not in state:
        dataset = api.request("POST", prefix + "/datasets", json={"name": name})
        state["dataset_id"] = dataset["id"]
        save(state_path, state)
    path = f"/api/datasets/{state['dataset_id']}"
    current = api.request("GET", path)
    existing = [
        {key: value for key, value in case.items() if key != "id"} for case in current["cases"]
    ]
    if case_fingerprint(existing) != case_fingerprint(cases):
        if current["version"] != 1 or existing:
            raise BenchmarkError("Seeded dataset was edited; use a new --state path")
        api.request("PUT", path + "/cases", json={"version": current["version"], "cases": cases})
    print(json.dumps(state, indent=2))
    print(
        f"Seeded {len(cases)} authored cases. Wait for both corpora to finish indexing before running."
    )


def load_state(args):
    state = json.loads(Path(args.state).read_text())
    if state["base_url"] != args.api.rstrip("/"):
        raise BenchmarkError("State belongs to another API")
    return state


def wait_for_run(api, run_id, timeout):
    deadline = time.monotonic() + timeout
    while True:
        run = api.request("GET", f"/api/evaluation-runs/{run_id}")
        if run["status"] in {"completed", "failed"}:
            return run
        if time.monotonic() >= deadline:
            raise BenchmarkError(
                f"Wait timed out; run {run_id} continues in the worker. Use report later."
            )
        time.sleep(min(2, max(0, deadline - time.monotonic())))


def start_run(api, args):
    state = load_state(args)
    kb_id = state["knowledge_bases"][args.index]
    _, cases, corpus = load_bundle(args.bundle)
    documents = api.items(f"/api/knowledge-bases/{kb_id}/documents")
    expected = {hashlib.sha256(content).hexdigest() for content in corpus.values()}
    available = {doc["checksum"] for doc in documents if doc["status"] == "ready"}
    if available != expected or len(documents) != len(expected):
        raise BenchmarkError("Benchmark corpus must be fully indexed with no additional documents")
    current = api.request("GET", f"/api/datasets/{state['dataset_id']}")
    actual_cases = [{k: v for k, v in case.items() if k != "id"} for case in current["cases"]]
    if case_fingerprint(actual_cases) != case_fingerprint(cases):
        raise BenchmarkError("Dataset differs from the benchmark bundle; seed a new dataset")
    query = {"top_k": args.top_k, "prompt_version": args.prompt, "agent_mode": True}
    if args.model:
        query["model"] = args.model
    body = {
        "dataset_id": state["dataset_id"],
        "knowledge_base_id": kb_id,
        "name": args.name,
        "query": query,
        "evaluate_semantics": not args.no_semantics,
    }
    if args.evaluator:
        body["evaluator_model"] = args.evaluator
    run = api.request(
        "POST",
        f"/api/workspaces/{state['workspace_id']}/evaluation-runs",
        headers={"Idempotency-Key": args.key},
        json=body,
    )
    print(f"Run {run['id']} ({run['status']})", flush=True)
    if args.wait:
        run = wait_for_run(api, run["id"], args.wait)
        print(
            json.dumps(
                {"id": run["id"], "status": run["status"], "metrics": run["metrics"]}, indent=2
            )
        )
        if run["status"] != "completed":
            raise BenchmarkError(f"Evaluation failed: {run['error_code']}")


def report(api, args):
    run = api.request("GET", f"/api/evaluation-runs/{args.run_id}")
    results = api.items(f"/api/evaluation-runs/{args.run_id}/results")
    output = {
        "schema_version": 1,
        "evidence": "persisted API observations; provider authenticity is not independently verified",
        "run": run,
        "results": results,
    }
    if args.traces:
        output["traces"] = [
            api.request("GET", f"/api/query-traces/{row['trace_id']}") for row in results
        ]
    save(args.output, output)
    print(
        f"Saved {len(results)}/{run['total_cases']} results to {args.output}; status={run['status']}"
    )


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--api", default="http://127.0.0.1:8000")
    root.add_argument("--email", required=True)
    root.add_argument("--state", default=".data/meridian.json")
    root.add_argument("--bundle", default="benchmarks")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="Import both embedding configurations and authored cases")
    run = commands.add_parser(
        "run", help="Queue a durable experiment (incurs configured provider usage)"
    )
    run.add_argument("--index", choices=["small", "large"], default="small")
    run.add_argument("--name", required=True)
    run.add_argument(
        "--key", required=True, help="Stable idempotency key; reuse for retry of the same request"
    )
    run.add_argument("--top-k", type=int, choices=range(1, 21), default=5)
    run.add_argument("--prompt", choices=["grounded-v1", "concise-v1"], default="grounded-v1")
    run.add_argument("--model")
    run.add_argument("--evaluator")
    run.add_argument("--no-semantics", action="store_true")
    run.add_argument(
        "--wait", type=int, default=0, help="Maximum seconds to wait; zero returns immediately"
    )
    export = commands.add_parser(
        "report", help="Export persisted results, optionally with full traces"
    )
    export.add_argument("run_id")
    export.add_argument("--output", required=True)
    export.add_argument("--traces", action="store_true")
    comparison = commands.add_parser(
        "compare", help="Exit 1 on regression or inconclusive comparison"
    )
    comparison.add_argument("baseline")
    comparison.add_argument("candidate")
    comparison.add_argument("--output", required=True)
    comparison.add_argument("--quality-tolerance", type=float, default=0.05)
    comparison.add_argument("--operational-tolerance", type=float, default=0.2)
    return root


def main():
    args = parser().parse_args()
    api = None
    try:
        password = os.environ.get("EVALRAG_BENCHMARK_PASSWORD") or getpass.getpass("Password: ")
        api = API(args.api, args.email, password)
        if args.command == "seed":
            seed(api, args)
        elif args.command == "run":
            start_run(api, args)
        elif args.command == "report":
            report(api, args)
        else:
            result = api.request(
                "GET",
                f"/api/evaluation-runs/{args.candidate}/compare/{args.baseline}",
                params={
                    "quality_tolerance": args.quality_tolerance,
                    "operational_tolerance": args.operational_tolerance,
                },
            )
            save(args.output, result)
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 1
    except (BenchmarkError, OSError, ValueError, KeyError, httpx.HTTPError) as exc:
        # Unexpected HTTP/parser errors can contain sensitive values; only our own errors are printable.
        print(
            str(exc)
            if isinstance(exc, BenchmarkError)
            else f"Benchmark command failed ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 2
    finally:
        if api:
            api.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
