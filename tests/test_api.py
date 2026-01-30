"""
Tests for API endpoints and handler functionality.
"""

import pytest
import json
import sys
import os
from io import BytesIO
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from index import (
    handler,
    SESSIONS,
    create_session,
    get_session,
    QUESTION_BANKS,
    INTERRUPTIONS,
    QuestionType,
)


class MockRequest:
    """Mock HTTP request for testing."""

    def __init__(self, method, path, body=None, headers=None):
        self.command = method
        self.path = path
        self.headers = headers or {'Content-Length': len(body) if body else 0}
        self._body = body.encode() if body else b''

    def read(self, length):
        return self._body[:length]


class MockHandler(handler):
    """Mock handler that captures responses."""

    def __init__(self, method, path, body=None):
        self.path = path
        self.headers = {'Content-Length': str(len(body) if body else 0)}
        self.rfile = BytesIO(body.encode() if body else b'')
        self.wfile = BytesIO()
        self._response_code = None
        self._response_headers = {}
        self._response_data = None

    def send_response(self, code):
        self._response_code = code

    def send_header(self, name, value):
        self._response_headers[name] = value

    def end_headers(self):
        pass

    def get_response(self):
        """Get the response data as dict."""
        self.wfile.seek(0)
        data = self.wfile.read().decode()
        return json.loads(data) if data else {}


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_returns_200(self):
        """Test that health check returns 200 status."""
        h = MockHandler('GET', '/api')
        h.do_GET()

        assert h._response_code == 200

    def test_health_check_returns_status(self):
        """Test that health check returns status info."""
        h = MockHandler('GET', '/api')
        h.do_GET()

        response = h.get_response()
        assert response["status"] == "healthy"
        assert response["service"] == "Interview Coach"

    def test_health_check_lists_endpoints(self):
        """Test that health check lists available endpoints."""
        h = MockHandler('GET', '/api')
        h.do_GET()

        response = h.get_response()
        assert "endpoints" in response
        assert len(response["endpoints"]) > 0

    def test_health_check_with_trailing_slash(self):
        """Test health check with trailing slash."""
        h = MockHandler('GET', '/api/')
        h.do_GET()

        assert h._response_code == 200

    def test_unknown_get_returns_404(self):
        """Test that unknown GET path returns 404."""
        h = MockHandler('GET', '/api/unknown')
        h.do_GET()

        assert h._response_code == 404


class TestSessionsEndpoint:
    """Tests for sessions endpoint."""

    def test_create_session_returns_200(self):
        """Test creating a session returns 200."""
        h = MockHandler('POST', '/api/sessions', '{}')
        h.do_POST()

        assert h._response_code == 200

    def test_create_session_returns_session_id(self):
        """Test that creating session returns session ID."""
        h = MockHandler('POST', '/api/sessions', '{}')
        h.do_POST()

        response = h.get_response()
        assert "session_id" in response

    def test_create_session_with_custom_role(self):
        """Test creating session with custom role."""
        body = json.dumps({"role": "Data Scientist"})
        h = MockHandler('POST', '/api/sessions', body)
        h.do_POST()

        response = h.get_response()
        assert response["session"]["role"] == "Data Scientist"

    def test_create_session_with_custom_company(self):
        """Test creating session with custom company."""
        body = json.dumps({"company": "Google"})
        h = MockHandler('POST', '/api/sessions', body)
        h.do_POST()

        response = h.get_response()
        assert response["session"]["company"] == "Google"


class TestQuestionEndpoint:
    """Tests for question endpoint."""

    def test_get_question_without_session_returns_400(self):
        """Test getting question without session returns 400."""
        h = MockHandler('POST', '/api/question', '{}')
        h.do_POST()

        assert h._response_code == 400

    def test_get_question_with_valid_session(self):
        """Test getting question with valid session."""
        session = create_session("test-session")

        body = json.dumps({"session_id": "test-session"})
        h = MockHandler('POST', '/api/question', body)
        h.do_POST()

        assert h._response_code == 200
        response = h.get_response()
        assert "question" in response

    def test_get_question_updates_session_state(self):
        """Test that getting question updates session state."""
        session = create_session("state-test")

        body = json.dumps({
            "session_id": "state-test",
            "question_type": "behavioral"
        })
        h = MockHandler('POST', '/api/question', body)
        h.do_POST()

        updated_session = get_session("state-test")
        assert updated_session["question_type"] == "behavioral"
        assert updated_session["current_question"] != ""

    def test_get_question_returns_instruction(self):
        """Test that getting question returns instruction."""
        session = create_session("instruction-test")

        body = json.dumps({"session_id": "instruction-test"})
        h = MockHandler('POST', '/api/question', body)
        h.do_POST()

        response = h.get_response()
        assert "instruction" in response


class TestRespondEndpoint:
    """Tests for respond endpoint."""

    def test_respond_without_session_returns_400(self):
        """Test responding without session returns 400."""
        body = json.dumps({"response": "test"})
        h = MockHandler('POST', '/api/respond', body)
        h.do_POST()

        assert h._response_code == 400

    def test_respond_without_response_returns_400(self):
        """Test responding without response text returns 400."""
        session = create_session("respond-test")

        body = json.dumps({"session_id": "respond-test", "response": ""})
        h = MockHandler('POST', '/api/respond', body)
        h.do_POST()

        assert h._response_code == 400


class TestConfirmEndpoint:
    """Tests for confirm endpoint."""

    def test_confirm_without_session_returns_400(self):
        """Test confirming without session returns 400."""
        h = MockHandler('POST', '/api/confirm', '{}')
        h.do_POST()

        assert h._response_code == 400

    def test_confirm_advances_step(self):
        """Test that confirming advances to next step."""
        session = create_session("confirm-test")
        session["current_step"] = "identify_principle"

        body = json.dumps({"session_id": "confirm-test"})
        h = MockHandler('POST', '/api/confirm', body)
        h.do_POST()

        assert h._response_code == 200
        response = h.get_response()
        assert response["current_step"] == "create_anchors"

    def test_confirm_at_last_step(self):
        """Test confirming at last step shows completion."""
        session = create_session("complete-test")
        session["current_step"] = "random_entry"

        body = json.dumps({"session_id": "complete-test"})
        h = MockHandler('POST', '/api/confirm', body)
        h.do_POST()

        response = h.get_response()
        assert "complete" in response["current_step"]


class TestInterruptEndpoint:
    """Tests for interrupt endpoint."""

    def test_interrupt_without_session_returns_400(self):
        """Test interrupting without session returns 400."""
        h = MockHandler('POST', '/api/interrupt', '{}')
        h.do_POST()

        assert h._response_code == 400

    def test_interrupt_returns_interruption(self):
        """Test that interrupt returns an interruption."""
        session = create_session("interrupt-test")

        body = json.dumps({"session_id": "interrupt-test"})
        h = MockHandler('POST', '/api/interrupt', body)
        h.do_POST()

        assert h._response_code == 200
        response = h.get_response()
        assert "interruption" in response

    def test_interrupt_respects_type(self):
        """Test that interrupt respects the type parameter."""
        session = create_session("type-test")

        body = json.dumps({
            "session_id": "type-test",
            "type": "challenge"
        })
        h = MockHandler('POST', '/api/interrupt', body)
        h.do_POST()

        response = h.get_response()
        assert response["type"] == "challenge"


class TestAnchorsEndpoint:
    """Tests for anchors endpoint."""

    def test_set_anchors_without_session_returns_400(self):
        """Test setting anchors without session returns 400."""
        h = MockHandler('POST', '/api/anchors', '{}')
        h.do_POST()

        assert h._response_code == 400

    def test_set_anchors_updates_session(self):
        """Test that setting anchors updates session."""
        session = create_session("anchors-test")

        body = json.dumps({
            "session_id": "anchors-test",
            "anchors": ["Moment", "Risk", "Win"]
        })
        h = MockHandler('POST', '/api/anchors', body)
        h.do_POST()

        assert h._response_code == 200
        updated_session = get_session("anchors-test")
        assert updated_session["anchors"] == ["Moment", "Risk", "Win"]


class TestPrincipleEndpoint:
    """Tests for principle endpoint."""

    def test_set_principle_without_session_returns_400(self):
        """Test setting principle without session returns 400."""
        h = MockHandler('POST', '/api/principle', '{}')
        h.do_POST()

        assert h._response_code == 400

    def test_set_principle_updates_session(self):
        """Test that setting principle updates session."""
        session = create_session("principle-test")

        body = json.dumps({
            "session_id": "principle-test",
            "principle": "Always be honest"
        })
        h = MockHandler('POST', '/api/principle', body)
        h.do_POST()

        assert h._response_code == 200
        updated_session = get_session("principle-test")
        assert updated_session["principle"] == "Always be honest"


class TestResumeEndpoint:
    """Tests for resume upload endpoint."""

    def test_upload_resume_without_session_returns_400(self):
        """Test uploading resume without session returns 400."""
        body = json.dumps({"resume_text": "My resume"})
        h = MockHandler('POST', '/api/resume', body)
        h.do_POST()

        assert h._response_code == 400

    def test_upload_resume_without_text_returns_400(self):
        """Test uploading empty resume returns 400."""
        session = create_session("resume-test")

        body = json.dumps({"session_id": "resume-test", "resume_text": ""})
        h = MockHandler('POST', '/api/resume', body)
        h.do_POST()

        assert h._response_code == 400

    def test_upload_resume_success(self):
        """Test successful resume upload."""
        session = create_session("resume-success")

        body = json.dumps({
            "session_id": "resume-success",
            "resume_text": "Skills: Python, JavaScript"
        })
        h = MockHandler('POST', '/api/resume', body)
        h.do_POST()

        assert h._response_code == 200
        response = h.get_response()
        assert "parsed" in response

    def test_upload_resume_stores_in_session(self):
        """Test that uploaded resume is stored in session."""
        session = create_session("resume-store")

        body = json.dumps({
            "session_id": "resume-store",
            "resume_text": "My resume content"
        })
        h = MockHandler('POST', '/api/resume', body)
        h.do_POST()

        updated_session = get_session("resume-store")
        assert updated_session["resume"] == "My resume content"
        assert updated_session["parsed_resume"] is not None


class TestJobDescriptionEndpoint:
    """Tests for job description upload endpoint."""

    def test_upload_jd_without_session_returns_400(self):
        """Test uploading JD without session returns 400."""
        body = json.dumps({"job_description": "JD text"})
        h = MockHandler('POST', '/api/job-description', body)
        h.do_POST()

        assert h._response_code == 400

    def test_upload_jd_without_text_returns_400(self):
        """Test uploading empty JD returns 400."""
        session = create_session("jd-test")

        body = json.dumps({"session_id": "jd-test", "job_description": ""})
        h = MockHandler('POST', '/api/job-description', body)
        h.do_POST()

        assert h._response_code == 400

    def test_upload_jd_success(self):
        """Test successful JD upload."""
        session = create_session("jd-success")

        body = json.dumps({
            "session_id": "jd-success",
            "job_description": "Requirements: Python experience"
        })
        h = MockHandler('POST', '/api/job-description', body)
        h.do_POST()

        assert h._response_code == 200
        response = h.get_response()
        assert "parsed" in response


class TestPersonalizedQuestionEndpoint:
    """Tests for personalized question endpoint."""

    def test_personalized_without_session_returns_400(self):
        """Test personalized question without session returns 400."""
        h = MockHandler('POST', '/api/personalized-question', '{}')
        h.do_POST()

        assert h._response_code == 400

    def test_personalized_without_data_returns_400(self):
        """Test personalized question without resume/JD returns 400."""
        session = create_session("personal-test")

        body = json.dumps({"session_id": "personal-test"})
        h = MockHandler('POST', '/api/personalized-question', body)
        h.do_POST()

        assert h._response_code == 400


class TestCORSHeaders:
    """Tests for CORS header handling."""

    def test_options_returns_200(self):
        """Test OPTIONS request returns 200."""
        h = MockHandler('OPTIONS', '/api/sessions')
        h.do_OPTIONS()

        assert h._response_code == 200

    def test_response_includes_cors_headers(self):
        """Test that responses include CORS headers."""
        h = MockHandler('GET', '/api')
        h.do_GET()

        assert 'Access-Control-Allow-Origin' in h._response_headers
        assert h._response_headers['Access-Control-Allow-Origin'] == '*'


class TestInterviewerTypesEndpoint:
    """Tests for interviewer types endpoint."""

    def test_get_interviewer_types_returns_200(self):
        """Test that interviewer types endpoint returns 200."""
        h = MockHandler('GET', '/api/interviewer-types')
        h.do_GET()

        assert h._response_code == 200

    def test_get_interviewer_types_returns_list(self):
        """Test that interviewer types returns a list."""
        h = MockHandler('GET', '/api/interviewer-types')
        h.do_GET()

        response = h.get_response()
        assert "interviewer_types" in response
        assert len(response["interviewer_types"]) > 0

    def test_interviewer_types_have_required_fields(self):
        """Test that each interviewer type has required fields."""
        h = MockHandler('GET', '/api/interviewer-types')
        h.do_GET()

        response = h.get_response()
        for int_type in response["interviewer_types"]:
            assert "value" in int_type
            assert "name" in int_type
            assert "focus" in int_type
            assert "tips" in int_type


class TestSessionWithInterviewerType:
    """Tests for session creation with interviewer type."""

    def test_create_session_with_interviewer_type(self):
        """Test creating session with interviewer type."""
        body = json.dumps({"interviewer_type": "recruiter"})
        h = MockHandler('POST', '/api/sessions', body)
        h.do_POST()

        assert h._response_code == 200
        response = h.get_response()
        assert response["session"]["interviewer_type"] == "recruiter"

    def test_create_session_default_interviewer_type(self):
        """Test session defaults to hiring_manager."""
        h = MockHandler('POST', '/api/sessions', '{}')
        h.do_POST()

        response = h.get_response()
        assert response["session"]["interviewer_type"] == "hiring_manager"

    def test_session_response_includes_tips(self):
        """Test that session response includes interviewer tips."""
        h = MockHandler('POST', '/api/sessions', '{}')
        h.do_POST()

        response = h.get_response()
        assert "interviewer_tips" in response


class TestUnknownEndpoint:
    """Tests for unknown endpoint handling."""

    def test_unknown_post_returns_404(self):
        """Test unknown POST endpoint returns 404."""
        h = MockHandler('POST', '/api/unknown', '{}')
        h.do_POST()

        assert h._response_code == 404
        response = h.get_response()
        assert "error" in response
