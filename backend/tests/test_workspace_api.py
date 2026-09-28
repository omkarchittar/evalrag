import pytest
from test_auth import PASSWORD

from evalrag.models import Membership, User, Workspace
from evalrag.security import hash_password

pytestmark = pytest.mark.postgres


def token(client, email="member@example.com"):
    result = client.post("/api/auth/token", json={"email": email, "password": PASSWORD})
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def test_create_workspace_kb_upload_and_duplicate_are_scoped(api):
    client, _, _ = api
    headers = token(client)
    response = client.post("/api/workspaces", json={"name": "Engineering"}, headers=headers)
    assert response.status_code == 201
    workspace = response.json()
    response = client.post(
        f"/api/workspaces/{workspace['id']}/knowledge-bases",
        headers=headers,
        json={"name": "Handbook"},
    )
    assert response.status_code == 201
    kb = response.json()
    assert kb["embedding_model"] == "text-embedding-3-small"
    url = f"/api/knowledge-bases/{kb['id']}/documents"
    first = client.post(
        url, headers=headers, files={"file": ("policy.md", b"Retention is 30 days.")}
    )
    second = client.post(
        url, headers=headers, files={"file": ("renamed.md", b"Retention is 30 days.")}
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert "content" not in first.json()
    listed = client.get(url, headers=headers).json()
    assert len(listed["items"]) == 1
    assert listed["items"][0]["status"] == "queued"


def test_other_users_cannot_read_or_mutate_workspace(api, db):
    client, _, _ = api
    first_headers = token(client)
    workspace = client.post(
        "/api/workspaces", json={"name": "Private"}, headers=first_headers
    ).json()
    db.add(
        User(
            email="other@example.com",
            name="Other",
            password_hash=hash_password(PASSWORD),
            role="member",
        )
    )
    db.flush()
    other = token(client, "other@example.com")
    assert client.get("/api/workspaces", headers=other).json() == []
    assert (
        client.get(f"/api/workspaces/{workspace['id']}/knowledge-bases", headers=other).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/workspaces/{workspace['id']}/knowledge-bases",
            headers=other,
            json={"name": "Attack"},
        ).status_code
        == 404
    )


def test_viewer_cannot_upload_or_create_knowledge_base(api, db):
    client, member, admin = api
    workspace = Workspace(name="Shared")
    db.add(workspace)
    db.flush()
    db.add_all(
        [
            Membership(workspace_id=workspace.id, user_id=admin.id, role="owner"),
            Membership(workspace_id=workspace.id, user_id=member.id, role="viewer"),
        ]
    )
    db.flush()
    headers = token(client)
    assert (
        client.get(f"/api/workspaces/{workspace.id}/knowledge-bases", headers=headers).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/workspaces/{workspace.id}/knowledge-bases",
            headers=headers,
            json={"name": "Write"},
        ).status_code
        == 403
    )


def test_owner_can_add_member_but_editor_cannot_change_permissions(api):
    client, _, admin = api
    owner = token(client)
    ws = client.post("/api/workspaces", json={"name": "Team"}, headers=owner).json()
    response = client.put(
        f"/api/workspaces/{ws['id']}/members",
        headers=owner,
        json={"email": admin.email, "role": "editor"},
    )
    assert response.status_code == 200
    editor = token(client, admin.email)
    response = client.put(
        f"/api/workspaces/{ws['id']}/members",
        headers=editor,
        json={"email": admin.email, "role": "owner"},
    )
    assert response.status_code == 403  # global admin is not workspace owner


def test_invalid_chunk_settings_and_embedding_models_rejected(api):
    client, _, _ = api
    headers = token(client)
    ws = client.post("/api/workspaces", json={"name": "Team"}, headers=headers).json()
    for settings in [{"chunk_size": 32, "chunk_overlap": 32}, {"embedding_model": "fake-model"}]:
        response = client.post(
            f"/api/workspaces/{ws['id']}/knowledge-bases",
            headers=headers,
            json={"name": "Broken", **settings},
        )
        assert response.status_code == 422
