"""Claude-powered extraction of Hard 75 progress from emails."""

import base64
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

import anthropic

from src.config import get_settings


@dataclass
class ExtractedDay:
    """Extracted Hard 75 day data."""

    day_number: Optional[int] = None
    date: Optional[date] = None
    workout1_done: bool = False
    workout2_done: bool = False
    diet_done: bool = False
    water_done: bool = False
    reading_done: bool = False
    photo_done: bool = False
    steps: Optional[int] = None
    water_oz: Optional[int] = None
    reading_minutes: Optional[int] = None
    # Daily nutrition totals
    calories: Optional[int] = None
    protein_g: Optional[int] = None
    carbs_g: Optional[int] = None
    fat_g: Optional[int] = None
    fiber_g: Optional[int] = None
    raw_notes: Optional[str] = None


@dataclass
class ExtractedWorkout:
    """Extracted workout session data."""

    workout_number: int  # 1 or 2
    workout_type: Optional[str] = None
    duration_minutes: Optional[int] = None
    is_outdoor: bool = False
    location: Optional[str] = None
    exercises: list[dict] = None

    def __post_init__(self):
        if self.exercises is None:
            self.exercises = []


@dataclass
class ExtractedMeal:
    """Extracted meal data."""

    meal_type: str  # 'breakfast', 'lunch', 'dinner', 'snack', 'pre-workout', 'post-workout'
    description: Optional[str] = None
    calories: Optional[int] = None
    protein_g: Optional[int] = None
    carbs_g: Optional[int] = None
    fat_g: Optional[int] = None
    fiber_g: Optional[int] = None
    sugar_g: Optional[int] = None
    food_items: list[dict] = None

    def __post_init__(self):
        if self.food_items is None:
            self.food_items = []


@dataclass
class ExtractionResult:
    """Complete extraction result from an email."""

    day: ExtractedDay
    workouts: list[ExtractedWorkout]
    meals: list[ExtractedMeal]
    confidence: float
    raw_response: str


EXTRACTION_PROMPT = """You are analyzing an email containing a Hard 75 challenge daily update. Extract the following information:

1. **Day Information:**
   - Day number (1-75)
   - Date (if mentioned)
   - Which tasks were completed:
     - Workout 1 (45+ min)
     - Workout 2 (45+ min, one must be outdoor)
     - Diet (following the diet plan, no cheat meals, no alcohol)
     - Water (1 gallon / 128oz)
     - Reading (10+ pages of non-fiction)
     - Progress photo taken
   - Daily nutrition totals (if mentioned):
     - Total calories
     - Protein (grams)
     - Carbs (grams)
     - Fat (grams)
     - Fiber (grams)

2. **Workout Details (for each workout):**
   - Workout number (1 or 2)
   - Type (strength, cardio, HIIT, yoga, etc.)
   - Duration in minutes
   - Whether it was outdoor
   - Location (gym, home, park, etc.)
   - Exercises performed with sets, reps, and weight

3. **Meals (for each meal mentioned):**
   - Meal type: 'breakfast', 'lunch', 'dinner', 'snack', 'pre-workout', 'post-workout'
   - Description of the meal
   - Calories
   - Protein (grams)
   - Carbs (grams)
   - Fat (grams)
   - Fiber (grams)
   - Sugar (grams)
   - Individual food items with their macros (if detailed)

4. **Additional Metrics:**
   - Steps count (if mentioned)
   - Water intake in oz (if specific amount mentioned)
   - Reading time in minutes (if mentioned)

Respond with a JSON object in this exact format:
```json
{
  "day": {
    "day_number": <int or null>,
    "date": "<YYYY-MM-DD or null>",
    "workout1_done": <bool>,
    "workout2_done": <bool>,
    "diet_done": <bool>,
    "water_done": <bool>,
    "reading_done": <bool>,
    "photo_done": <bool>,
    "steps": <int or null>,
    "water_oz": <int or null>,
    "reading_minutes": <int or null>,
    "calories": <int or null>,
    "protein_g": <int or null>,
    "carbs_g": <int or null>,
    "fat_g": <int or null>,
    "fiber_g": <int or null>
  },
  "workouts": [
    {
      "workout_number": <1 or 2>,
      "workout_type": "<string or null>",
      "duration_minutes": <int or null>,
      "is_outdoor": <bool>,
      "location": "<string or null>",
      "exercises": [
        {
          "name": "<exercise name>",
          "sets": [
            {"set_number": 1, "weight_lbs": <float>, "reps": <int>},
            ...
          ]
        }
      ]
    }
  ],
  "meals": [
    {
      "meal_type": "<breakfast|lunch|dinner|snack|pre-workout|post-workout>",
      "description": "<brief description of the meal>",
      "calories": <int or null>,
      "protein_g": <int or null>,
      "carbs_g": <int or null>,
      "fat_g": <int or null>,
      "fiber_g": <int or null>,
      "sugar_g": <int or null>,
      "food_items": [
        {
          "name": "<food item>",
          "quantity": "<amount, e.g., '200g', '1 cup'>",
          "calories": <int or null>,
          "protein_g": <int or null>,
          "carbs_g": <int or null>,
          "fat_g": <int or null>
        }
      ]
    }
  ],
  "confidence": <0.0-1.0>
}
```

If any information is not mentioned or unclear, use null or false as appropriate.
Set confidence based on how clear and complete the information is."""


class Extractor:
    """Extract Hard 75 progress data from email content using Claude."""

    def __init__(self):
        settings = get_settings()
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def extract_from_email(
        self,
        body_text: str,
        body_html: str = "",
        images: list[tuple[bytes, str]] = None,  # (data, mime_type)
    ) -> ExtractionResult:
        """Extract Hard 75 progress from email content."""
        # Build content blocks
        content = []

        # Add email text
        email_content = body_text or body_html
        content.append({
            "type": "text",
            "text": f"Email content:\n\n{email_content}"
        })

        # Add images if provided (screenshots from Apple Health, Strengthlog, etc.)
        if images:
            for img_data, mime_type in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64.standard_b64encode(img_data).decode("utf-8"),
                    },
                })

        # Call Claude
        response = self._client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=EXTRACTION_PROMPT,
            messages=[
                {"role": "user", "content": content},
            ],
        )

        # Parse response
        response_text = response.content[0].text
        return self._parse_response(response_text, email_content)

    def _parse_response(self, response_text: str, raw_notes: str) -> ExtractionResult:
        """Parse Claude's JSON response."""
        # Extract JSON from response (might be wrapped in markdown code blocks)
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_str = response_text

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Return minimal result on parse failure
            return ExtractionResult(
                day=ExtractedDay(raw_notes=raw_notes),
                workouts=[],
                meals=[],
                confidence=0.0,
                raw_response=response_text,
            )

        # Parse day data
        day_data = data.get("day", {})
        day = ExtractedDay(
            day_number=day_data.get("day_number"),
            date=date.fromisoformat(day_data["date"]) if day_data.get("date") else None,
            workout1_done=day_data.get("workout1_done", False),
            workout2_done=day_data.get("workout2_done", False),
            diet_done=day_data.get("diet_done", False),
            water_done=day_data.get("water_done", False),
            reading_done=day_data.get("reading_done", False),
            photo_done=day_data.get("photo_done", False),
            steps=day_data.get("steps"),
            water_oz=day_data.get("water_oz"),
            reading_minutes=day_data.get("reading_minutes"),
            calories=day_data.get("calories"),
            protein_g=day_data.get("protein_g"),
            carbs_g=day_data.get("carbs_g"),
            fat_g=day_data.get("fat_g"),
            fiber_g=day_data.get("fiber_g"),
            raw_notes=raw_notes,
        )

        # Parse workouts
        workouts = []
        for w_data in data.get("workouts", []):
            workout = ExtractedWorkout(
                workout_number=w_data.get("workout_number", 1),
                workout_type=w_data.get("workout_type"),
                duration_minutes=w_data.get("duration_minutes"),
                is_outdoor=w_data.get("is_outdoor", False),
                location=w_data.get("location"),
                exercises=w_data.get("exercises", []),
            )
            workouts.append(workout)

        # Parse meals
        meals = []
        for m_data in data.get("meals", []):
            meal = ExtractedMeal(
                meal_type=m_data.get("meal_type", "snack"),
                description=m_data.get("description"),
                calories=m_data.get("calories"),
                protein_g=m_data.get("protein_g"),
                carbs_g=m_data.get("carbs_g"),
                fat_g=m_data.get("fat_g"),
                fiber_g=m_data.get("fiber_g"),
                sugar_g=m_data.get("sugar_g"),
                food_items=m_data.get("food_items", []),
            )
            meals.append(meal)

        return ExtractionResult(
            day=day,
            workouts=workouts,
            meals=meals,
            confidence=data.get("confidence", 0.5),
            raw_response=response_text,
        )


# Global extractor instance
extractor = Extractor()
