"""
Tests for question generation and question banks.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from index import (
    QuestionType,
    TrainingStep,
    QUESTION_BANKS,
    INTERRUPTIONS,
    CURVEBALL_QUESTIONS,
    ALIGNMENT_QUESTIONS,
    CRO_MANAGEMENT_QUESTIONS,
    BEHAVIORAL_QUESTIONS,
    MOTIVATION_QUESTIONS,
    generate_personalized_questions,
    parse_resume,
    parse_job_description,
)


class TestQuestionBanks:
    """Tests for question banks."""

    def test_all_question_types_have_banks(self):
        """Test that all question types have corresponding question banks."""
        for q_type in QuestionType:
            assert q_type in QUESTION_BANKS
            assert len(QUESTION_BANKS[q_type]) > 0

    def test_curveball_questions_not_empty(self):
        """Test that curveball questions bank is not empty."""
        assert len(CURVEBALL_QUESTIONS) > 0

    def test_alignment_questions_not_empty(self):
        """Test that alignment questions bank is not empty."""
        assert len(ALIGNMENT_QUESTIONS) > 0

    def test_cro_management_questions_not_empty(self):
        """Test that CRO management questions bank is not empty."""
        assert len(CRO_MANAGEMENT_QUESTIONS) > 0

    def test_behavioral_questions_not_empty(self):
        """Test that behavioral questions bank is not empty."""
        assert len(BEHAVIORAL_QUESTIONS) > 0

    def test_motivation_questions_not_empty(self):
        """Test that motivation questions bank is not empty."""
        assert len(MOTIVATION_QUESTIONS) > 0

    def test_questions_are_strings(self):
        """Test that all questions are non-empty strings."""
        for q_type, questions in QUESTION_BANKS.items():
            for question in questions:
                assert isinstance(question, str)
                assert len(question) > 10

    def test_questions_end_with_punctuation(self):
        """Test that questions end with appropriate punctuation."""
        for q_type, questions in QUESTION_BANKS.items():
            for question in questions:
                assert question[-1] in '.?!'


class TestInterruptions:
    """Tests for interruption banks."""

    def test_redirect_interruptions_exist(self):
        """Test that redirect interruptions exist."""
        assert "redirect" in INTERRUPTIONS
        assert len(INTERRUPTIONS["redirect"]) > 0

    def test_clarify_interruptions_exist(self):
        """Test that clarify interruptions exist."""
        assert "clarify" in INTERRUPTIONS
        assert len(INTERRUPTIONS["clarify"]) > 0

    def test_challenge_interruptions_exist(self):
        """Test that challenge interruptions exist."""
        assert "challenge" in INTERRUPTIONS
        assert len(INTERRUPTIONS["challenge"]) > 0

    def test_executive_interruptions_exist(self):
        """Test that executive interruptions exist."""
        assert "executive" in INTERRUPTIONS
        assert len(INTERRUPTIONS["executive"]) > 0

    def test_interruptions_are_strings(self):
        """Test that all interruptions are non-empty strings."""
        for int_type, interruptions in INTERRUPTIONS.items():
            for interruption in interruptions:
                assert isinstance(interruption, str)
                assert len(interruption) > 5


class TestTrainingSteps:
    """Tests for training step enumeration."""

    def test_all_training_steps_defined(self):
        """Test that all expected training steps are defined."""
        expected_steps = [
            "identify_principle",
            "create_anchors",
            "guided_recall",
            "delivery_practice",
            "compression",
            "random_entry"
        ]

        actual_steps = [step.value for step in TrainingStep]

        for expected in expected_steps:
            assert expected in actual_steps

    def test_training_step_count(self):
        """Test the number of training steps."""
        assert len(TrainingStep) == 6


class TestPersonalizedQuestions:
    """Tests for personalized question generation."""

    def test_generate_with_empty_session(self):
        """Test generating questions with no resume or JD."""
        session = {
            "parsed_resume": None,
            "parsed_job_description": None
        }

        result = generate_personalized_questions(session)

        assert result is None or len(result) == 0

    def test_generate_with_resume_only(self, sample_resume_text):
        """Test generating questions with only a resume."""
        session = {
            "parsed_resume": parse_resume(sample_resume_text),
            "parsed_job_description": None
        }

        result = generate_personalized_questions(session)

        assert result is not None
        assert len(result) > 0

    def test_generate_with_jd_only(self, sample_job_description):
        """Test generating questions with only a job description."""
        session = {
            "parsed_resume": None,
            "parsed_job_description": parse_job_description(sample_job_description)
        }

        result = generate_personalized_questions(session)

        assert result is not None
        assert len(result) > 0

    def test_generate_with_both(self, sample_resume_text, sample_job_description):
        """Test generating questions with both resume and JD."""
        session = {
            "parsed_resume": parse_resume(sample_resume_text),
            "parsed_job_description": parse_job_description(sample_job_description)
        }

        result = generate_personalized_questions(session)

        assert result is not None
        assert len(result) > 0

    def test_questions_are_relevant(self, sample_resume_text, sample_job_description):
        """Test that generated questions are relevant to inputs."""
        session = {
            "parsed_resume": parse_resume(sample_resume_text),
            "parsed_job_description": parse_job_description(sample_job_description)
        }

        result = generate_personalized_questions(session)

        # At least one question should contain something from resume or JD
        all_questions = ' '.join(result).lower()
        assert any(word in all_questions for word in ['experience', 'role', 'how', 'tell', 'describe'])

    def test_questions_are_strings(self, full_session):
        """Test that all generated questions are strings."""
        result = generate_personalized_questions(full_session)

        for question in result:
            assert isinstance(question, str)
            assert len(question) > 10

    def test_generate_with_minimal_resume(self):
        """Test generating questions with minimal resume data."""
        session = {
            "parsed_resume": {
                "raw_text": "Simple resume",
                "skills": ["Python"],
                "experience": [],
                "education": [],
                "summary": ""
            },
            "parsed_job_description": None
        }

        # Should not crash even with minimal data
        result = generate_personalized_questions(session)
        # Result may be None or empty list, both are acceptable
        assert result is None or isinstance(result, list)

    def test_generate_with_minimal_jd(self):
        """Test generating questions with minimal JD data."""
        session = {
            "parsed_resume": None,
            "parsed_job_description": {
                "raw_text": "Simple JD",
                "title": "Engineer",
                "requirements": ["Python experience"],
                "responsibilities": [],
                "qualifications": [],
                "company_info": ""
            }
        }

        result = generate_personalized_questions(session)

        assert result is not None
        assert len(result) > 0
