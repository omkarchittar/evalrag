import pytest
from sqlalchemy import select
from test_auth import PASSWORD
from test_retrieval import populate

from evalrag.models import EvaluationDataset, Job, KnowledgeBase, Membership, Workspace

pytestmark = pytest.mark.postgres


@pytest.fixture
def evaluation_api(api, db):
    client, user, admin = api
    workspace = Workspace(name="Evaluation workspace")
    db.add(workspace)
    db.flush()
    db.add(Membership(workspace_id=workspace.id, user_id=user.id, role="owner"))
    kb = KnowledgeBase(
        workspace_id=workspace.id,
        name="Policies",
        embedding_model="text-embedding-3-small",
        embedding_dimension=3,
    )
    db.add(kb)
    db.flush()
    populate(db, kb, [1, 0, 0])
    headers = {
        "Authorization": "Bearer "
        + client.post("/api/auth/token", json={"email": user.email, "password": PASSWORD}).json()[
            "access_token"
        ]
    }
    return client, workspace, kb, headers


def test_dataset_replace_uses_version_and_run_submission_is_idempotent(evaluation_api, db):
    client, workspace, kb, headers = evaluation_api
    created = client.post(
        f"/api/workspaces/{workspace.id}/datasets", headers=headers, json={"name": "Policy suite"}
    )
    assert created.status_code == 201, created.text
    data = created.json()
    case = {
        "question": "Retention?",
        "expected_answer": "30 days",
        "expected_sources": ["a" * 64],
        "expected_abstention": False,
        "tags": ["policy"],
    }
    update = client.put(
        f"/api/datasets/{data['id']}/cases", headers=headers, json={"version": 1, "cases": [case]}
    )
    assert update.status_code == 200 and update.json()["version"] == 2
    stale = client.put(
        f"/api/datasets/{data['id']}/cases", headers=headers, json={"version": 1, "cases": []}
    )
    assert stale.status_code == 409
    body = {
        "dataset_id": data["id"],
        "knowledge_base_id": kb.id,
        "name": "Baseline",
        "evaluate_semantics": False,
    }
    request_headers = {**headers, "Idempotency-Key": "start-evaluation-1"}
    first = client.post(
        f"/api/workspaces/{workspace.id}/evaluation-runs", headers=request_headers, json=body
    )
    assert first.status_code == 201, first.text
    repeat = client.post(
        f"/api/workspaces/{workspace.id}/evaluation-runs", headers=request_headers, json=body
    )
    assert repeat.json()["id"] == first.json()["id"]
    changed = client.post(
        f"/api/workspaces/{workspace.id}/evaluation-runs",
        headers=request_headers,
        json={**body, "name": "Different"},
    )
    assert changed.status_code == 409
    assert (
        db.scalar(select(Job).where(Job.kind == "evaluate_run")).resource_id == first.json()["id"]
    )
    exported = client.get(f"/api/datasets/{data['id']}/export", headers=headers).json()
    assert exported["cases"][0]["expected_sources"] == ["a" * 64]
    assert "id" not in exported["cases"][0]


def test_other_workspace_datasets_cannot_be_read_or_scheduled(evaluation_api, db):
    client, workspace, kb, headers = evaluation_api
    other = Workspace(name="Other")
    db.add(other)
    db.flush()
    data = EvaluationDataset(workspace_id=other.id, name="Private")
    db.add(data)
    db.flush()
    assert client.get("/api/datasets/" + data.id, headers=headers).status_code == 404
    response = client.post(
        f"/api/workspaces/{workspace.id}/evaluation-runs",
        headers={**headers, "Idempotency-Key": "forbidden-run"},
        json={"dataset_id": data.id, "knowledge_base_id": kb.id, "name": "Attack"},
    )
    assert response.status_code == 404


def test_viewer_can_read_but_cannot_edit_or_run_evaluations(evaluation_api, db):
    client, workspace, kb, headers = evaluation_api
    member = db.scalar(select(Membership).where(Membership.workspace_id == workspace.id))
    member.role = "viewer"
    db.flush()
    assert (
        client.get(f"/api/workspaces/{workspace.id}/datasets", headers=headers).status_code == 200
    )
    assert (
        client.post(
            f"/api/workspaces/{workspace.id}/datasets",
            headers=headers,
            json={"name": "Not allowed"},
        ).status_code
        == 403
    )
