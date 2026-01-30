"""
Tests for resume and job description parsing functionality.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from index import parse_resume, parse_job_description


class TestParseResume:
    """Tests for parse_resume function."""

    def test_parse_empty_resume(self):
        """Test parsing an empty resume."""
        result = parse_resume("")

        assert result["raw_text"] == ""
        assert result["skills"] == []
        assert result["experience"] == []
        assert result["education"] == []
        assert result["summary"] == ""

    def test_parse_none_resume(self):
        """Test parsing None resume."""
        result = parse_resume(None)

        assert result["raw_text"] is None
        assert result["skills"] == []

    def test_parse_resume_with_skills_section(self):
        """Test parsing resume with skills section."""
        resume = """
Skills:
Python, JavaScript, React, Node.js
Docker, Kubernetes, AWS
"""
        result = parse_resume(resume)

        assert len(result["skills"]) > 0
        assert "Python" in result["skills"]

    def test_parse_resume_with_experience_section(self):
        """Test parsing resume with experience section."""
        resume = """
Experience:
Senior Engineer at Company A (2020-Present)
- Led development team
- Built microservices

Junior Engineer at Company B (2018-2020)
- Wrote Python scripts
"""
        result = parse_resume(resume)

        assert len(result["experience"]) > 0

    def test_parse_resume_with_education_section(self):
        """Test parsing resume with education section."""
        resume = """
Education:
B.S. Computer Science, MIT, 2018
M.S. Data Science, Stanford, 2020
"""
        result = parse_resume(resume)

        assert len(result["education"]) > 0

    def test_parse_resume_with_summary_section(self):
        """Test parsing resume with summary section."""
        resume = """
Summary:
Experienced software engineer with 10 years of experience
in building scalable distributed systems.
"""
        result = parse_resume(resume)

        assert "Experienced software engineer" in result["summary"]

    def test_parse_full_resume(self, sample_resume_text):
        """Test parsing a complete resume."""
        result = parse_resume(sample_resume_text)

        assert len(result["skills"]) > 0
        assert len(result["experience"]) > 0
        assert len(result["education"]) > 0
        assert result["summary"] != ""

    def test_parse_resume_with_bullet_skills(self):
        """Test parsing skills separated by bullets."""
        resume = """
Skills:
• Python • JavaScript • React
• Docker • AWS
"""
        result = parse_resume(resume)

        assert "Python" in result["skills"]
        assert "JavaScript" in result["skills"]

    def test_parse_resume_with_technical_skills_header(self):
        """Test parsing with 'Technical Skills' header variant."""
        resume = """
Technical Skills:
Python, Java, C++
"""
        result = parse_resume(resume)

        assert "Python" in result["skills"]

    def test_parse_resume_with_work_experience_header(self):
        """Test parsing with 'Work Experience' header variant."""
        resume = """
Work Experience:
Manager at Corp (2020-2023)
"""
        result = parse_resume(resume)

        assert len(result["experience"]) > 0

    def test_parse_resume_no_sections_uses_summary(self):
        """Test that text without sections is used as summary."""
        resume = "I am a skilled developer with experience in Python and cloud technologies."
        result = parse_resume(resume)

        assert "skilled developer" in result["summary"]


class TestParseJobDescription:
    """Tests for parse_job_description function."""

    def test_parse_empty_job_description(self):
        """Test parsing an empty job description."""
        result = parse_job_description("")

        assert result["raw_text"] == ""
        assert result["title"] == ""
        assert result["requirements"] == []
        assert result["responsibilities"] == []
        assert result["qualifications"] == []
        assert result["company_info"] == ""

    def test_parse_none_job_description(self):
        """Test parsing None job description."""
        result = parse_job_description(None)

        assert result["raw_text"] is None
        assert result["requirements"] == []

    def test_parse_jd_with_title(self):
        """Test extracting job title from description."""
        jd = """
Senior Software Engineer

Requirements:
- 5 years experience
"""
        result = parse_job_description(jd)

        assert "Senior Software Engineer" in result["title"]

    def test_parse_jd_with_requirements(self):
        """Test parsing job description requirements."""
        jd = """
Requirements:
- 5+ years of experience
- Strong Python skills
- Cloud experience (AWS/GCP)
"""
        result = parse_job_description(jd)

        assert len(result["requirements"]) > 0

    def test_parse_jd_with_responsibilities(self):
        """Test parsing job description responsibilities."""
        jd = """
Responsibilities:
- Lead development team
- Design system architecture
- Conduct code reviews
"""
        result = parse_job_description(jd)

        assert len(result["responsibilities"]) > 0

    def test_parse_jd_with_qualifications(self):
        """Test parsing job description qualifications."""
        jd = """
Qualifications:
- Bachelor's degree in CS
- Experience with agile
- Strong communication
"""
        result = parse_job_description(jd)

        assert len(result["qualifications"]) > 0

    def test_parse_jd_with_about_section(self):
        """Test parsing job description company info."""
        jd = """
About the Company:
We are a leading tech company building innovative solutions.
"""
        result = parse_job_description(jd)

        assert "leading tech company" in result["company_info"]

    def test_parse_full_job_description(self, sample_job_description):
        """Test parsing a complete job description."""
        result = parse_job_description(sample_job_description)

        assert result["title"] != ""
        assert len(result["requirements"]) > 0
        assert len(result["responsibilities"]) > 0

    def test_parse_jd_with_duties_header(self):
        """Test parsing with 'Duties' header variant."""
        jd = """
Job Title

Duties:
- Write code
- Review PRs
"""
        result = parse_job_description(jd)

        assert len(result["responsibilities"]) > 0

    def test_parse_jd_with_required_header(self):
        """Test parsing with 'Required' header variant."""
        jd = """
Required:
- Python experience
- Team leadership
"""
        result = parse_job_description(jd)

        assert len(result["requirements"]) > 0


class TestParsingIntegration:
    """Integration tests for parsing both resume and JD."""

    def test_parse_both_documents(self, sample_resume_text, sample_job_description):
        """Test parsing both resume and job description."""
        resume_result = parse_resume(sample_resume_text)
        jd_result = parse_job_description(sample_job_description)

        # Both should have extracted meaningful data
        assert len(resume_result["skills"]) > 0
        assert len(jd_result["requirements"]) > 0

    def test_skill_matching_scenario(self):
        """Test that skills and requirements can be matched."""
        resume = """
Skills:
Python, AWS, Docker, Kubernetes, React
"""
        jd = """
Requirements:
- Strong Python skills
- AWS experience required
- Docker knowledge preferred
"""
        resume_result = parse_resume(resume)
        jd_result = parse_job_description(jd)

        resume_skills = set(s.lower() for s in resume_result["skills"])

        # At least some skills should match requirements conceptually
        assert "python" in resume_skills
        assert "aws" in resume_skills
