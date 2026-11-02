import json
from decimal import Decimal

import pytest

from internships_project import career_agent, llm_usage, state_store


def test_usage_is_attributed_and_priced_with_cached_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    response = {"id": "resp-test", "model": "gpt-4o", "usage": {
        "input_tokens": 1000, "input_tokens_details": {"cached_tokens": 200},
        "output_tokens": 100}}
    with llm_usage.llm_user("alice"):
        llm_usage.record_response("profile", "gpt-4o", response)
    assert llm_usage.usage_report()["by_user"]["alice"]["cost"] == Decimal("0.00325")
    with state_store._connect() as connection:
        row = connection.execute("SELECT username,action,model,response_id FROM llm_usage").fetchone()
    assert row == ("alice", "profile", "gpt-4o", "resp-test")
    assert "resp-test" in llm_usage.render_usage_report()


def test_unknown_price_or_missing_usage_is_not_reported_as_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    with llm_usage.llm_user("bob"):
        llm_usage.record_response("briefs", "unknown-model", {"model": "unknown-model", "usage": {
            "input_tokens": 50, "output_tokens": 10}})
        llm_usage.record_response("letter", "gpt-4o", {"model": "gpt-4o"})
    report = llm_usage.usage_report()
    assert report["unknown"] == 2
    assert report["by_user"]["bob"]["cost"] == 0
    assert "2 sans coût calculable" in llm_usage.render_usage_report()


def test_openai_response_usage_is_logged_without_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("INTERNSHIPS_AI_MODEL", "gpt-4o")

    class Response:
        status_code = 200

        def json(self):
            return {"id": "resp-123", "model": "gpt-4o",
                    "usage": {"input_tokens": 80, "input_tokens_details": {"cached_tokens": 0},
                              "output_tokens": 20},
                    "output": [{"content": [{"type": "output_text", "text": json.dumps({"ok": True})}]}]}

    monkeypatch.setattr(career_agent.requests, "post", lambda *args, **kwargs: Response())
    with llm_usage.llm_user("alice"):
        assert career_agent._openai_json("candidate_profile", {"type": "object"}, "rules", {"private": "CV text"}) == {"ok": True}
    with state_store._connect() as connection:
        columns = connection.execute("SELECT username,action,model,input_tokens,output_tokens FROM llm_usage").fetchone()
        schema = connection.execute("SELECT sql FROM sqlite_master WHERE name='llm_usage'").fetchone()[0]
    assert columns == ("alice", "candidate_profile", "gpt-4o", 80, 20)
    assert "CV text" not in schema


def test_generation_slot_prevents_parallel_and_excess_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    with llm_usage.llm_user("alice"):
        with llm_usage.generation_slot(max_per_hour=1):
            with pytest.raises(llm_usage.GenerationLimitError, match="déjà en cours"):
                with llm_usage.generation_slot(max_per_hour=1):
                    pass
        with pytest.raises(llm_usage.GenerationLimitError, match="limite"):
            with llm_usage.generation_slot(max_per_hour=1):
                pass
