"""Tests for the CareLoop GLM analysis flow."""
import pytest
import json
import sqlite3
import tempfile
from unittest.mock import patch, AsyncMock

# Setup test database using temp file (not :memory: — each connection needs same DB)
import os
_test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DB_PATH"] = _test_db.name

from app.database import init_db, get_db
from app.services.glm_service import (
    extract_json,
    get_mock_analysis,
    run_care_analysis,
)


class TestJsonExtraction:
    """Test robust JSON extraction from GLM responses."""

    def test_direct_json(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_embedded_json(self):
        text = 'Here is the analysis:\n{"shared_summary": "test"}\nDone.'
        result = extract_json(text)
        assert result["shared_summary"] == "test"

    def test_invalid_json_returns_none(self):
        result = extract_json("this is not json")
        assert result is None

    def test_empty_returns_none(self):
        result = extract_json("")
        assert result is None


class TestMockAnalysis:
    """Test mock analysis generation."""

    def test_mock_has_required_fields(self):
        mock = get_mock_analysis("Test Patient", "some encounters")
        assert "shared_summary" in mock
        assert "patient_summary" in mock
        assert "tasks" in mock
        assert "risk_flags" in mock
        assert len(mock["tasks"]) > 0
        assert len(mock["risk_flags"]) > 0

    def test_mock_tasks_have_owners(self):
        mock = get_mock_analysis("Test Patient", "some encounters")
        for task in mock["tasks"]:
            assert task["owner"] in ("patient", "provider")


@pytest.mark.asyncio
async def test_care_analysis_with_mock_data():
    """Test the full care analysis flow using mock data (no API key)."""
    # Ensure no API key
    with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
        init_db()

        # Create test patient and encounter
        with get_db() as db:
            db.execute(
                "INSERT INTO patients (id, name, condition, created_at) VALUES (?, ?, ?, ?)",
                ("test-patient-1", "Test Patient", "Test condition", "2024-01-01T00:00:00")
            )
            db.execute(
                "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("test-enc-1", "test-patient-1", "provider", "Dr. Test",
                 "provider_update", "Patient is doing well.", "2024-01-01T00:00:00")
            )

        # Run analysis
        result = await run_care_analysis("test-patient-1")

        assert "error" not in result
        assert "analysis_id" in result
        assert "result" in result

        # Verify analysis was stored
        with get_db() as db:
            analysis = db.execute(
                "SELECT * FROM glm_analyses WHERE id = ?",
                (result["analysis_id"],)
            ).fetchone()
            assert analysis is not None
            assert analysis["shared_summary"] != ""
            assert analysis["patient_summary"] != ""

            # Verify tasks were created
            tasks = db.execute(
                "SELECT * FROM tasks WHERE analysis_id = ?",
                (result["analysis_id"],)
            ).fetchall()
            assert len(tasks) > 0


@pytest.mark.asyncio
async def test_care_analysis_no_encounters():
    """Test analysis fails gracefully with no encounters."""
    with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
        init_db()

        with get_db() as db:
            db.execute(
                "INSERT INTO patients (id, name, condition, created_at) VALUES (?, ?, ?, ?)",
                ("test-patient-empty", "Empty Patient", "None", "2024-01-01T00:00:00")
            )

        result = await run_care_analysis("test-patient-empty")
        assert "error" in result
        assert result["error"] == "No encounters to analyze"


@pytest.mark.asyncio
async def test_care_analysis_patient_not_found():
    """Test analysis fails gracefully with invalid patient."""
    with patch.dict(os.environ, {"GLM_API_KEY": ""}, clear=False):
        init_db()
        result = await run_care_analysis("nonexistent-patient")
        assert "error" in result
        assert result["error"] == "Patient not found"
