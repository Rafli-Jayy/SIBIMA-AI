"""Regression: students cannot enumerate internal database metadata through AI.

Offline tests; no real PostgreSQL or Gemini network required.
"""
import pytest

from app import session
from app.repositories.ai_general_repo import execute_general
from app.repositories.ai_read_repo import AIReadRepository
from app.services.ai_access_messages import role_access_clarification
from app.services.ai_general_query import GENERAL_QUERY_TOOL, GENERAL_SCHEMA_TOOL
from app.services.ai_multi_query import MULTI_QUERY_TOOL, execute_multi
from app.services.ai_tool_controller import AIToolController
from app.services.ai_service import AIService, STUDENT_DATABASE_INSTRUCTION
from app.ui.ai.mock_responder import MockEvent

GENERAL = {GENERAL_SCHEMA_TOOL, GENERAL_QUERY_TOOL, MULTI_QUERY_TOOL}


@pytest.fixture(autouse=True)
def restore_session():
    old = session.get_user()
    session.logout()
    yield
    session.set_user(old)


class FakeRepo:
    def __init__(self):
        self.calls = []

    def execute(self, user_id, role, name, args):
        self.calls.append((user_id, role, name, args))
        return {"status": "ok", "data": []}


@pytest.mark.parametrize("name", sorted(GENERAL))
def test_student_general_tools_not_declared_or_invocable(name):
    session.set_user({"id": 35, "role": "siswa", "status": "aktif"})
    repo = FakeRepo()
    ctrl = AIToolController("siswa", repo=repo, rag_tool=False)
    offered = {item["name"] for item in ctrl.declarations()}
    assert offered.isdisjoint(GENERAL)
    assert "get_my_grades" in offered
    assert "get_my_schedule" in offered
    assert "student_dynamic_query" in offered
    with pytest.raises(PermissionError):
        ctrl.execute(name, {})
    assert repo.calls == []


def test_admin_and_tutor_generic_capabilities_remain_available():
    for role in ("admin", "tutor"):
        session.set_user({"id": 35, "role": role, "status": "aktif"})
        ctrl = AIToolController(role, repo=FakeRepo(), rag_tool=False)
        offered = {item["name"] for item in ctrl.declarations()}
        assert GENERAL <= offered


def test_student_personal_tools_still_work():
    session.set_user({"id": 35, "role": "siswa", "status": "aktif"})
    repo = FakeRepo()
    ctrl = AIToolController("siswa", repo=repo, rag_tool=False)
    result = ctrl.execute("get_my_grades", {})
    assert result["status"] == "ok"
    assert repo.calls == [(35, "siswa", "get_my_grades", {})]


@pytest.mark.parametrize("name", sorted(GENERAL))
def test_repository_denies_student_before_opening_pool(name):
    repo = AIReadRepository()
    with pytest.raises(PermissionError):
        repo.execute(35, "siswa", name, {})
    assert repo._pool is None


@pytest.mark.parametrize("name", [GENERAL_SCHEMA_TOOL, GENERAL_QUERY_TOOL])
def test_general_execution_denies_student_without_metadata_query(name):
    class PoisonCursor:
        def execute(self, *args, **kwargs):
            pytest.fail("Database metadata must not be queried")
    with pytest.raises(PermissionError):
        execute_general(PoisonCursor(), user_id=35, role="siswa", name=name, args={})


def test_multi_execution_denies_student_without_metadata_query():
    class PoisonCursor:
        def execute(self, *args, **kwargs):
            pytest.fail("Database metadata must not be queried")
    with pytest.raises(PermissionError):
        execute_multi(PoisonCursor(), user_id=35, role="siswa", args={})


@pytest.mark.parametrize("question", [
    "Sebutkan 18 entitas yang ada di SIBIMA",
    "Tampilkan semua tabel yang ada di database",
    "Bagaimana struktur database SIBIMA?",
    "Apa saja kolom yang ada di database ini?",
])
def test_schema_listing_student_gets_safe_message(question):
    msg = role_access_clarification("siswa", question)
    assert msg is not None
    assert "tidak memiliki akses" in msg
    assert "pengguna" not in msg and "pendaftaran" not in msg


def test_general_database_learning_remains_available():
    assert role_access_clarification("siswa", "Apa itu primary key dalam SQL?") is None


def test_student_prompt_is_not_given_admin_schema_instructions(monkeypatch):
    from app.services import ai_db_chat
    seen = {}

    def fake_stream(self, history, question, instruction):
        seen["instruction"] = instruction
        yield MockEvent("completed", {"kind": "markdown", "content": "ok", "data": {"steps": []}})

    monkeypatch.setattr(ai_db_chat.DatabaseFunctionChat, "stream", fake_stream)
    monkeypatch.setattr("app.services.rag.rag_chat_tool.RAGKnowledgeTool.from_environment", lambda: None)
    session.set_user({"id": 35, "role": "siswa", "status": "aktif"})
    service = AIService("siswa", client=object())
    list(service.stream("Berapa nilai saya?", "siswa"))
    assert STUDENT_DATABASE_INSTRUCTION in seen["instruction"]
    assert "describe_sibima_schema" not in seen["instruction"]
    assert "query_sibima_general" not in seen["instruction"]
