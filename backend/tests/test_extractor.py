"""Tests for the Claude extractor."""

import pytest
from unittest.mock import MagicMock, patch

from src.agent.extractor import Extractor, ExtractionResult, ExtractedDay


class TestExtractor:
    """Tests for the Extractor class."""

    @pytest.fixture
    def extractor(self):
        """Create an extractor instance with mocked client."""
        with patch("src.agent.extractor.anthropic.Anthropic") as mock_client:
            ext = Extractor()
            ext._client = mock_client.return_value
            return ext

    def test_parse_response_valid_json(self, extractor):
        """Test parsing a valid JSON response."""
        response_text = """
        ```json
        {
            "day": {
                "day_number": 5,
                "date": "2024-03-15",
                "workout1_done": true,
                "workout2_done": true,
                "diet_done": true,
                "water_done": true,
                "reading_done": true,
                "photo_done": true,
                "steps": 12543,
                "water_oz": 128,
                "reading_minutes": 15
            },
            "workouts": [
                {
                    "workout_number": 1,
                    "workout_type": "strength",
                    "duration_minutes": 45,
                    "is_outdoor": false,
                    "location": "gym",
                    "exercises": [
                        {
                            "name": "Bench Press",
                            "sets": [
                                {"set_number": 1, "weight_lbs": 135, "reps": 10}
                            ]
                        }
                    ]
                }
            ],
            "confidence": 0.9
        }
        ```
        """

        result = extractor._parse_response(response_text, "Raw email content")

        assert isinstance(result, ExtractionResult)
        assert result.day.day_number == 5
        assert result.day.workout1_done is True
        assert result.day.steps == 12543
        assert len(result.workouts) == 1
        assert result.workouts[0].workout_type == "strength"
        assert result.confidence == 0.9

    def test_parse_response_invalid_json(self, extractor):
        """Test parsing an invalid JSON response."""
        response_text = "This is not valid JSON"

        result = extractor._parse_response(response_text, "Raw email content")

        assert isinstance(result, ExtractionResult)
        assert result.confidence == 0.0
        assert result.day.raw_notes == "Raw email content"

    def test_parse_response_partial_data(self, extractor):
        """Test parsing a response with partial data."""
        response_text = """
        {
            "day": {
                "day_number": 3,
                "workout1_done": true,
                "workout2_done": false
            },
            "workouts": [],
            "confidence": 0.5
        }
        """

        result = extractor._parse_response(response_text, "Partial update")

        assert result.day.day_number == 3
        assert result.day.workout1_done is True
        assert result.day.workout2_done is False
        assert result.day.diet_done is False  # Default value
        assert len(result.workouts) == 0


class TestExtractedDay:
    """Tests for ExtractedDay dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        day = ExtractedDay()

        assert day.day_number is None
        assert day.date is None
        assert day.workout1_done is False
        assert day.workout2_done is False
        assert day.diet_done is False
        assert day.water_done is False
        assert day.reading_done is False
        assert day.photo_done is False
        assert day.steps is None
        assert day.water_oz is None
        assert day.reading_minutes is None
        assert day.raw_notes is None

    def test_custom_values(self):
        """Test creating a day with custom values."""
        from datetime import date

        day = ExtractedDay(
            day_number=10,
            date=date(2024, 3, 15),
            workout1_done=True,
            steps=15000,
        )

        assert day.day_number == 10
        assert day.date == date(2024, 3, 15)
        assert day.workout1_done is True
        assert day.steps == 15000
        assert day.workout2_done is False  # Still default
