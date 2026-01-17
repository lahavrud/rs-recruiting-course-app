"""Tests for Pydantic schemas validation."""

import pytest
from pydantic import ValidationError

from src.schemas import CandidateProfileCreate, CandidateProfileUpdate


class TestCandidateProfileCreateValidation:
    """Test CandidateProfileCreate schema validation."""

    def test_valid_resume_path(self):
        """Test that valid paths within uploads/resumes/ are accepted."""
        schema = CandidateProfileCreate(
            full_name="Test User",
            email="test@example.com",
            resume_path="uploads/resumes/test_resume.pdf",
        )
        assert schema.resume_path == "uploads/resumes/test_resume.pdf"

    def test_none_resume_path(self):
        """Test that None is allowed for optional resume_path field."""
        schema = CandidateProfileCreate(
            full_name="Test User",
            email="test@example.com",
            resume_path=None,
        )
        assert schema.resume_path is None

    def test_path_traversal_parent_directory(self):
        """Test that paths with '..' are rejected (path traversal attack)."""
        with pytest.raises(ValidationError, match="Path cannot contain '..'"):
            CandidateProfileCreate(
                full_name="Malicious User",
                email="malicious@example.com",
                resume_path="../../../../etc/passwd",
            )

    def test_path_traversal_relative_parent(self):
        """Test that relative parent paths are rejected."""
        with pytest.raises(ValidationError, match="Path cannot contain '..'"):
            CandidateProfileCreate(
                full_name="Malicious User",
                email="malicious@example.com",
                resume_path="../config.py",
            )

    def test_absolute_path_rejected(self):
        """Test that absolute paths are rejected."""
        with pytest.raises(ValidationError, match="Path cannot be absolute"):
            CandidateProfileCreate(
                full_name="Malicious User",
                email="malicious@example.com",
                resume_path="/root/sensitive_file",
            )

    def test_path_outside_uploads_directory(self):
        """Test that paths outside uploads/resumes/ are rejected."""
        error_msg = "Path must be within 'uploads/resumes/'"
        with pytest.raises(ValidationError, match=error_msg):
            CandidateProfileCreate(
                full_name="Malicious User",
                email="malicious@example.com",
                resume_path="config/secrets.env",
            )

    def test_nested_valid_path(self):
        """Test that nested paths within uploads/resumes/ are accepted."""
        schema = CandidateProfileCreate(
            full_name="Test User",
            email="test@example.com",
            resume_path="uploads/resumes/2026/01/resume.pdf",
        )
        assert schema.resume_path == "uploads/resumes/2026/01/resume.pdf"


class TestCandidateProfileUpdateValidation:
    """Test CandidateProfileUpdate schema validation."""

    def test_valid_resume_path(self):
        """Test that valid paths within uploads/resumes/ are accepted."""
        schema = CandidateProfileUpdate(
            resume_path="uploads/resumes/updated_resume.pdf",
        )
        assert schema.resume_path == "uploads/resumes/updated_resume.pdf"

    def test_none_resume_path(self):
        """Test that None is allowed for optional resume_path field."""
        schema = CandidateProfileUpdate(resume_path=None)
        assert schema.resume_path is None

    def test_path_traversal_parent_directory(self):
        """Test that paths with '..' are rejected (path traversal attack)."""
        with pytest.raises(ValidationError, match="Path cannot contain '..'"):
            CandidateProfileUpdate(resume_path="../../../../etc/passwd")

    def test_path_traversal_relative_parent(self):
        """Test that relative parent paths are rejected."""
        with pytest.raises(ValidationError, match="Path cannot contain '..'"):
            CandidateProfileUpdate(resume_path="../config.py")

    def test_absolute_path_rejected(self):
        """Test that absolute paths are rejected."""
        with pytest.raises(ValidationError, match="Path cannot be absolute"):
            CandidateProfileUpdate(resume_path="/root/sensitive_file")

    def test_path_outside_uploads_directory(self):
        """Test that paths outside uploads/resumes/ are rejected."""
        error_msg = "Path must be within 'uploads/resumes/'"
        with pytest.raises(ValidationError, match=error_msg):
            CandidateProfileUpdate(resume_path="config/secrets.env")

    def test_nested_valid_path(self):
        """Test that nested paths within uploads/resumes/ are accepted."""
        schema = CandidateProfileUpdate(
            resume_path="uploads/resumes/2026/01/updated.pdf",
        )
        assert schema.resume_path == "uploads/resumes/2026/01/updated.pdf"
