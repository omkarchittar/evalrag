import pytest
from sqlalchemy import select
from test_auth import PASSWORD
from test_generation import provider, response_payload
from test_persistence import knowledge_base
from test_rag import Embeddings, Transactions
from test_retrieval import populate

from evalrag.models import Membership, QueryTrace
from evalrag.query_api import get_query_database, get_query_providers

pytestmark = pytest.mark.postgres


@pytest.fixture
def query_api(api, db):
    client, user, _ = api
    database = Transactions(db)
    kb = knowledge_base(db)
    _, chunk = populate(db, kb, [1, 0, 0])
    db.add(Membership(workspace_id=kb.workspace_id, user_id=user.id, role="viewer"))
    db.flush()
    payload = response_payload()
    import json

    answer = json.loads(payload["choices"][0]["message"]["content"])
    answer["claims"][0]["citations"][0]["chunk_id"] = chunk.id
    payload["choices"][0]["message"]["content"] = json.dumps(answer)

    class Providers:
        standard_openai = True

        def embedding(self, index):
            return Embeddings(database)

        def generation(self, model):
            return provider(payload)

    client.app.dependency_overrides[get_query_database] = lambda: database
    client.app.dependency_overrides[get_query_providers] = lambda: Providers()
    token = client.post("/api/auth/token", json={"email": user.email, "password": PASSWORD}).json()[
        "access_token"
    ]
    return client, kb, {"Authorization": "Bearer " + token}


def test_query_api_returns_and_lists_persisted_cited_trace(query_api, db):
    client, kb, headers = query_api
    result = client.post(
        f"/api/knowledge-bases/{kb.id}/queries",
        headers=headers,
        json={"question": "What is the retention policy?"},
    )
    assert result.status_code == 201, result.text
    data = result.json()
    assert data["answer"] == "Retention is 30 days."
    assert data["outcome"] == "answered"
    assert client.get("/api/query-traces/" + data["id"], headers=headers).json()["id"] == data["id"]
    history = client.get(f"/api/knowledge-bases/{kb.id}/queries", headers=headers).json()
    assert history["total"] == 1
    assert db.scalar(select(QueryTrace.id)) == data["id"]


def test_query_api_rejects_unconfigured_model_and_cross_workspace(query_api, db):
    client, kb, headers = query_api
    other = knowledge_base(db)
    response = client.post(
        f"/api/knowledge-bases/{other.id}/queries", headers=headers, json={"question": "private?"}
    )
    assert response.status_code == 404
    bad = client.post(
        f"/api/knowledge-bases/{kb.id}/queries",
        headers=headers,
        json={"question": "question", "config": {"model": "unexpected-expensive-model"}},
    )
    assert bad.status_code == 422
    assert db.scalar(select(QueryTrace.id)) is None


def test_partial_config_uses_deployment_default_model(query_api):
    client, kb, headers = query_api
    client.app.state.settings.generation_model = "configured-model"
    response = client.post(
        f"/api/knowledge-bases/{kb.id}/queries",
        headers=headers,
        json={"question": "Retention?", "config": {"top_k": 10}},
    )
    assert response.status_code == 201, response.text
    assert response.json()["config"]["model"] == "configured-model"
