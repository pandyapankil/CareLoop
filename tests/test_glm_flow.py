"""Comprehensive tests for CareLoop."""

import pytest
import json
import tempfile
import os
from unittest.mock import patch
from datetime import datetime, timezone

_test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DB_PATH"] = _test_db.name

from app.database import init_db, get_db
from app.services.glm_service import (
    extract_json,
    get_mock_analysis,
    get_mock_trend,
    get_mock_qa_answer,
    get_mock_careplan,
    get_mock_encounter_summary_v2,
    get_mock_followups_v2,
    run_care_analysis,
    run_trend_detection,
    run_patient_qa,
    run_careplan_generation,
    run_encounter_summary,
    run_followup_suggestions,
    record_usage,
    get_usage,
    reset_usage,
    _calc_cost,
    Usage,
    TOOLS,
)


class TestJsonExtraction:
    def test_direct_json(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_code_fence_no_lang(self):
        text = '```\n{"key": "value"}\n```'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_embedded_json(self):
        text = 'Here is the analysis:\n{"shared_summary": "test"}\nDone.'
        result = extract_json(text)
        assert result["shared_summary"] == "test"

    def test_nested_json(self):
        data = {"tasks": [{"title": "Test", "owner": "provider"}], "risk_flags": []}
        result = extract_json(json.dumps(data))
        assert result["tasks"][0]["title"] == "Test"

    def test_invalid_json_returns_none(self):
        assert extract_json("this is not json") is None

    def test_empty_returns_none(self):
        assert extract_json("") is None


class TestMockAnalysis:
    def test_mock_has_required_fields(self):
        mock = get_mock_analysis("Test Patient")
        for key in ("shared_summary", "patient_summary", "tasks", "risk_flags"):
            assert key in mock
        assert len(mock["tasks"]) > 0
        assert len(mock["risk_flags"]) > 0

    def test_mock_tasks_have_owners(self):
        for task in get_mock_analysis("X")["tasks"]:
            assert task["owner"] in ("patient", "provider")

    def test_mock_risk_flags_have_severity(self):
        for flag in get_mock_analysis("X")["risk_flags"]:
            assert flag["severity"] in ("high", "medium", "low")

    def test_mock_trend(self):
        trend = get_mock_trend()
        assert trend["direction"] in ("improving", "stable", "declining")

    def test_mock_qa(self):
        assert len(get_mock_qa_answer("How am I?")) > 0

    def test_mock_careplan(self):
        plan = get_mock_careplan("Test", "Condition")
        for key in ("plan_title", "duration_weeks", "goals", "weekly_plan"):
            assert key in plan

    def test_mock_encounter_summary(self):
        summary = get_mock_encounter_summary_v2("note")
        for key in ("chief_complaint", "diagnoses", "urgency"):
            assert key in summary

    def test_mock_followups(self):
        followups = get_mock_followups_v2("Test")
        assert isinstance(followups, list) and len(followups) == 3


class TestTools:
    def test_four_tools_defined(self):
        names = [t["function"]["name"] for t in TOOLS]
        assert set(names) == {
            "create_task",
            "schedule_reminder",
            "send_message",
            "get_patient_history",
        }

    def test_create_task_schema(self):
        tool = next(t for t in TOOLS if t["function"]["name"] == "create_task")
        params = tool["function"]["parameters"]["properties"]
        assert "title" in params
        assert params["owner"]["enum"] == ["patient", "provider", "coordinator"]


class TestUsageTracking:
    def test_record_and_get_usage(self):
        init_db()
        reset_usage()
        record_usage("test", "glm-5.1", 100, 50, 0.15)
        usage = get_usage()
        assert usage["prompt_tokens"] == 100
        assert usage["total_tokens"] == 150

    def test_reset_usage(self):
        init_db()
        reset_usage()
        record_usage("test", "glm-5.1", 100, 50, 0.15)
        reset_usage()
        assert get_usage()["prompt_tokens"] == 0

    def test_cost_calculation(self):
        u = Usage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000)
        assert _calc_cost("glm-5.1", u) > 0


class TestCareAnalysis:
    @pytest.mark.asyncio
    async def test_with_mock_data(self):
        with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
            init_db()
            with get_db() as db:
                db.execute(
                    "INSERT INTO patients (id, name, condition, created_at) VALUES (?, ?, ?, ?)",
                    ("tp1", "Test Patient", "Test condition", "2024-01-01T00:00:00"),
                )
                db.execute(
                    "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "te1",
                        "tp1",
                        "provider",
                        "Dr. Test",
                        "provider_update",
                        "Patient doing well.",
                        "2024-01-01T00:00:00",
                    ),
                )

            result = await run_care_analysis("tp1")
            assert "error" not in result
            assert "analysis_id" in result

            with get_db() as db:
                row = db.execute(
                    "SELECT * FROM glm_analyses WHERE id = ?", (result["analysis_id"],)
                ).fetchone()
                assert row is not None
                assert row["prompt_sent"] is not None
                tasks = db.execute(
                    "SELECT * FROM tasks WHERE analysis_id = ?",
                    (result["analysis_id"],),
                ).fetchall()
                assert len(tasks) > 0

    @pytest.mark.asyncio
    async def test_no_encounters(self):
        with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
            init_db()
            with get_db() as db:
                db.execute(
                    "INSERT INTO patients (id, name, condition, created_at) VALUES (?, ?, ?, ?)",
                    ("tp2", "Empty", "None", "2024-01-01T00:00:00"),
                )
            result = await run_care_analysis("tp2")
            assert result["error"] == "No encounters to analyze"

    @pytest.mark.asyncio
    async def test_patient_not_found(self):
        with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
            init_db()
            result = await run_care_analysis("nonexistent")
            assert result["error"] == "Patient not found"


class TestTrendDetection:
    @pytest.mark.asyncio
    async def test_needs_analysis(self):
        with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
            init_db()
            with get_db() as db:
                db.execute(
                    "INSERT INTO patients (id, name, condition, created_at) VALUES (?, ?, ?, ?)",
                    ("tp3", "Trend", "Test", "2024-01-01T00:00:00"),
                )
            result = await run_trend_detection("tp3")
            assert result["error"] == "Need at least one analysis"


class TestPatientQA:
    @pytest.mark.asyncio
    async def test_qa_with_mock(self):
        with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
            init_db()
            with get_db() as db:
                db.execute(
                    "INSERT INTO patients (id, name, condition, created_at) VALUES (?, ?, ?, ?)",
                    ("tp4", "QA", "Test", "2024-01-01T00:00:00"),
                )
            result = await run_patient_qa("tp4", "How am I doing?")
            assert "qa_id" in result
            assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_qa_patient_not_found(self):
        with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
            init_db()
            assert "error" in await run_patient_qa("nonexistent", "test")


class TestCarePlan:
    @pytest.mark.asyncio
    async def test_careplan_mock(self):
        with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
            init_db()
            with get_db() as db:
                db.execute(
                    "INSERT INTO patients (id, name, condition, created_at) VALUES (?, ?, ?, ?)",
                    ("tp5", "Plan", "Recovery", "2024-01-01T00:00:00"),
                )
                db.execute(
                    "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "pe1",
                        "tp5",
                        "provider",
                        "Dr.",
                        "provider_update",
                        "Recovering.",
                        "2024-01-01T00:00:00",
                    ),
                )
            result = await run_careplan_generation("tp5")
            assert "plan_id" in result
            assert "plan_title" in result["plan"]


class TestEncounterSummary:
    @pytest.mark.asyncio
    async def test_summary_mock(self):
        with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
            init_db()
            with get_db() as db:
                db.execute(
                    "INSERT INTO patients (id, name, condition, created_at) VALUES (?, ?, ?, ?)",
                    ("tp6", "Enc", "Test", "2024-01-01T00:00:00"),
                )
                db.execute(
                    "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "ee1",
                        "tp6",
                        "provider",
                        "Dr.",
                        "provider_update",
                        "Headache. BP 140/90.",
                        "2024-01-01T00:00:00",
                    ),
                )
            result = await run_encounter_summary("ee1")
            assert "summary" in result

    @pytest.mark.asyncio
    async def test_not_found(self):
        with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
            init_db()
            assert "error" in await run_encounter_summary("nonexistent")


class TestFollowupSuggestions:
    @pytest.mark.asyncio
    async def test_followups_mock(self):
        with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
            init_db()
            with get_db() as db:
                db.execute(
                    "INSERT INTO patients (id, name, condition, created_at) VALUES (?, ?, ?, ?)",
                    ("tp7", "FU", "Test", "2024-01-01T00:00:00"),
                )
                db.execute(
                    "INSERT INTO glm_analyses (id, patient_id, shared_summary, patient_summary, risk_flags_json, tasks_json, model, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "fa1",
                        "tp7",
                        "Improving",
                        "Keep going",
                        "[]",
                        "[]",
                        "glm-5.1",
                        "2024-01-01T00:00:00",
                    ),
                )
            result = await run_followup_suggestions("fa1")
            assert "suggestions" in result
            assert isinstance(result["suggestions"], list)


class TestDatabaseSchema:
    def test_all_tables_exist(self):
        init_db()
        with get_db() as db:
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for t in (
                "patients",
                "encounters",
                "glm_analyses",
                "tasks",
                "qa_exchanges",
                "users",
                "sessions",
                "appointments",
                "medications",
                "medication_logs",
                "symptom_entries",
                "messages",
                "notifications",
                "care_team",
                "documents",
                "audit_log",
                "user_settings",
                "care_plans",
                "api_usage",
            ):
                assert t in tables, f"Missing table: {t}"

    def test_no_duplicate_indexes(self):
        init_db()
        with get_db() as db:
            indexes = [
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
                ).fetchall()
            ]
            assert len(indexes) == len(set(indexes))


class TestValidation:
    def test_sanitize_html(self):
        from app.utils.validation import sanitize_html

        assert sanitize_html("<b>bold</b>") == "<b>bold</b>"
        assert sanitize_html("<script>alert(1)</script>") == "alert(1)"
        assert sanitize_html("") == ""

    def test_validate_email(self):
        from app.utils.validation import validate_email

        assert validate_email("test@example.com") is True
        assert validate_email("invalid") is False
        assert validate_email("") is False

    def test_validate_phone(self):
        from app.utils.validation import validate_phone

        assert validate_phone("+1-555-123-4567") is True
        assert validate_phone("") is False

    def test_truncate(self):
        from app.utils.validation import truncate

        assert truncate("hello", 10) == "hello"
        assert truncate("hello world this is long", 15) == "hello world..."

    def test_validate_file_upload(self):
        from app.utils.validation import validate_file_upload

        assert validate_file_upload("test.pdf", 1024)[0] is True
        assert validate_file_upload("test.exe", 1024)[0] is False
        assert validate_file_upload("test.pdf", 20 * 1024 * 1024)[0] is False


class TestAuthMiddleware:
    def test_hash_and_verify_password(self):
        from app.middleware.auth import hash_password, verify_password

        hashed = hash_password("test123")
        assert verify_password("test123", hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_sign_and_verify_token(self):
        from app.middleware.auth import sign_token, verify_signed_token

        signed = sign_token("test-token")
        assert verify_signed_token(signed) == "test-token"
        assert verify_signed_token("invalid") is None

    def test_role_permissions(self):
        from app.middleware.auth import has_permission

        assert has_permission("admin", "anything") is True
        assert has_permission("provider", "run_analyses") is True
        assert has_permission("patient", "run_analyses") is False
        assert has_permission("patient", "view_own_data") is True

    def test_log_audit(self):
        from app.middleware.auth import log_audit

        init_db()
        log_audit("test_action", "patient", "p1", "u1", "detail")
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            assert row["action"] == "test_action"
