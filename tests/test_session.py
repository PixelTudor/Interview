"""
Tests for session management functionality.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from index import (
    SESSIONS,
    create_session,
    get_session,
    QuestionType,
    TrainingStep,
    InterviewerType,
    INTERVIEWER_CONTEXTS,
)


class TestCreateSession:
    """Tests for create_session function."""

    def test_create_session_with_defaults(self):
        """Test creating a session with default values."""
        session = create_session("test-123")

        assert session["session_id"] == "test-123"
        assert session["role"] == "Senior Study Manager"
        assert session["company"] == "Taiho Oncology"
        assert session["question_type"] == "curveball"
        assert session["current_step"] == "identify_principle"
        assert session["current_question"] == ""
        assert session["anchors"] == []
        assert session["principle"] == ""
        assert session["history"] == []
        assert session["resume"] is None
        assert session["job_description"] is None
        assert session["parsed_resume"] is None
        assert session["parsed_job_description"] is None

    def test_create_session_with_custom_role(self):
        """Test creating a session with custom role."""
        session = create_session("test-456", role="Software Engineer")

        assert session["role"] == "Software Engineer"
        assert session["company"] == "Taiho Oncology"

    def test_create_session_with_custom_company(self):
        """Test creating a session with custom company."""
        session = create_session("test-789", company="Google")

        assert session["role"] == "Senior Study Manager"
        assert session["company"] == "Google"

    def test_create_session_with_custom_role_and_company(self):
        """Test creating a session with both custom role and company."""
        session = create_session("test-abc", "Data Scientist", "Meta")

        assert session["role"] == "Data Scientist"
        assert session["company"] == "Meta"

    def test_session_stored_in_sessions_dict(self):
        """Test that created session is stored in SESSIONS dictionary."""
        session_id = "stored-session-123"
        session = create_session(session_id)

        assert session_id in SESSIONS
        assert SESSIONS[session_id] == session

    def test_create_multiple_sessions(self):
        """Test creating multiple independent sessions."""
        session1 = create_session("session-1", "Role 1", "Company 1")
        session2 = create_session("session-2", "Role 2", "Company 2")

        assert len(SESSIONS) == 2
        assert SESSIONS["session-1"]["role"] == "Role 1"
        assert SESSIONS["session-2"]["role"] == "Role 2"


class TestGetSession:
    """Tests for get_session function."""

    def test_get_existing_session(self):
        """Test retrieving an existing session."""
        created = create_session("get-test-123")
        retrieved = get_session("get-test-123")

        assert retrieved is not None
        assert retrieved == created

    def test_get_nonexistent_session(self):
        """Test retrieving a session that doesn't exist."""
        result = get_session("nonexistent-session")

        assert result is None

    def test_get_session_returns_reference(self):
        """Test that get_session returns a reference to the actual session."""
        create_session("ref-test")
        session = get_session("ref-test")
        session["role"] = "Modified Role"

        # Changes should persist
        retrieved_again = get_session("ref-test")
        assert retrieved_again["role"] == "Modified Role"


class TestInterviewerType:
    """Tests for interviewer type functionality."""

    def test_all_interviewer_types_defined(self):
        """Test that all interviewer types have contexts."""
        for int_type in InterviewerType:
            assert int_type in INTERVIEWER_CONTEXTS

    def test_interviewer_context_has_required_fields(self):
        """Test that each interviewer context has required fields."""
        required_fields = ["name", "focus", "style", "tips"]
        for int_type, context in INTERVIEWER_CONTEXTS.items():
            for field in required_fields:
                assert field in context
                assert len(context[field]) > 0

    def test_create_session_with_interviewer_type(self):
        """Test creating a session with custom interviewer type."""
        session = create_session("int-test", interviewer_type="recruiter")
        assert session["interviewer_type"] == "recruiter"

    def test_create_session_default_interviewer_type(self):
        """Test that sessions default to hiring_manager."""
        session = create_session("default-int-test")
        assert session["interviewer_type"] == "hiring_manager"

    def test_interviewer_type_values(self):
        """Test all expected interviewer types exist."""
        expected_types = [
            "hiring_manager",
            "recruiter",
            "skip_level",
            "peer",
            "hr",
            "panel"
        ]
        actual_types = [t.value for t in InterviewerType]
        for expected in expected_types:
            assert expected in actual_types


class TestSessionState:
    """Tests for session state management."""

    def test_update_question_type(self):
        """Test updating session question type."""
        session = create_session("state-test")
        session["question_type"] = QuestionType.BEHAVIORAL.value

        assert session["question_type"] == "behavioral"

    def test_update_current_step(self):
        """Test updating session current step."""
        session = create_session("step-test")
        session["current_step"] = TrainingStep.CREATE_ANCHORS.value

        assert session["current_step"] == "create_anchors"

    def test_update_anchors(self):
        """Test updating session anchors."""
        session = create_session("anchor-test")
        session["anchors"] = ["Moment", "Risk", "Moves", "Win"]

        assert len(session["anchors"]) == 4
        assert "Risk" in session["anchors"]

    def test_update_principle(self):
        """Test updating session principle."""
        session = create_session("principle-test")
        session["principle"] = "Always be honest and direct"

        assert session["principle"] == "Always be honest and direct"

    def test_append_to_history(self):
        """Test appending messages to session history."""
        session = create_session("history-test")
        session["history"].append({"role": "user", "content": "Test message"})
        session["history"].append({"role": "assistant", "content": "Test response"})

        assert len(session["history"]) == 2
        assert session["history"][0]["role"] == "user"
        assert session["history"][1]["role"] == "assistant"

    def test_training_step_progression(self):
        """Test that training steps can be progressed correctly."""
        session = create_session("progression-test")
        steps = [
            "identify_principle",
            "create_anchors",
            "guided_recall",
            "delivery_practice",
            "compression",
            "random_entry"
        ]

        for step in steps:
            session["current_step"] = step
            assert session["current_step"] == step
