"""
Pytest configuration and fixtures for Interview Coach tests.
"""

import pytest
import sys
import os

# Add the api directory to the path so we can import index
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from index import (
    SESSIONS,
    create_session,
    get_session,
    parse_resume,
    parse_job_description,
    generate_personalized_questions,
    QuestionType,
    TrainingStep,
    InterviewerType,
    QUESTION_BANKS,
    INTERRUPTIONS,
    INTERVIEWER_CONTEXTS,
)


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear sessions before each test."""
    SESSIONS.clear()
    yield
    SESSIONS.clear()


@pytest.fixture
def sample_session():
    """Create a sample session for testing."""
    return create_session("test-session-123", "Software Engineer", "Acme Corp")


@pytest.fixture
def sample_resume_text():
    """Sample resume text for testing."""
    return """
John Doe
Software Engineer

Summary:
Experienced software engineer with 5+ years in full-stack development.
Passionate about building scalable applications and mentoring junior developers.

Skills:
Python, JavaScript, React, Node.js, PostgreSQL, AWS, Docker, Kubernetes

Experience:
Senior Software Engineer at Tech Corp (2020-Present)
- Led development of microservices architecture serving 1M+ users
- Mentored team of 4 junior developers
- Reduced API response time by 40%

Software Engineer at Startup Inc (2018-2020)
- Built React frontend for e-commerce platform
- Implemented CI/CD pipeline using GitHub Actions
- Collaborated with product team on feature specifications

Education:
B.S. Computer Science, State University, 2018
"""


@pytest.fixture
def sample_job_description():
    """Sample job description for testing."""
    return """
Senior Software Engineer

About the Company:
Acme Corp is a leading technology company building innovative solutions.

Responsibilities:
- Design and implement scalable backend services
- Lead technical discussions and code reviews
- Mentor junior team members
- Collaborate with product and design teams

Requirements:
- 5+ years of software development experience
- Strong proficiency in Python or Java
- Experience with cloud platforms (AWS, GCP, or Azure)
- Excellent communication skills

Qualifications:
- Bachelor's degree in Computer Science or related field
- Experience with microservices architecture
- Familiarity with agile methodologies
"""


@pytest.fixture
def session_with_resume(sample_session, sample_resume_text):
    """Session with parsed resume."""
    sample_session["resume"] = sample_resume_text
    sample_session["parsed_resume"] = parse_resume(sample_resume_text)
    return sample_session


@pytest.fixture
def session_with_jd(sample_session, sample_job_description):
    """Session with parsed job description."""
    sample_session["job_description"] = sample_job_description
    sample_session["parsed_job_description"] = parse_job_description(sample_job_description)
    return sample_session


@pytest.fixture
def full_session(sample_session, sample_resume_text, sample_job_description):
    """Session with both resume and job description."""
    sample_session["resume"] = sample_resume_text
    sample_session["parsed_resume"] = parse_resume(sample_resume_text)
    sample_session["job_description"] = sample_job_description
    sample_session["parsed_job_description"] = parse_job_description(sample_job_description)
    return sample_session
