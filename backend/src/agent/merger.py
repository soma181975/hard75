"""Smart merge of extracted data into the database."""

import logging
from datetime import date, timedelta
from typing import Optional

from src.db import db
from src.agent.extractor import ExtractionResult, ExtractedWorkout, ExtractedMeal

logger = logging.getLogger(__name__)


class Merger:
    """Merge extracted Hard 75 data into the database."""

    async def merge(
        self,
        user_id: int,
        extraction: ExtractionResult,
        photo_urls: list[str] = None,
    ) -> dict:
        """
        Merge extraction result into the database.

        Returns a summary of what was created/updated.
        """
        results = {
            "day_created": False,
            "day_updated": False,
            "workouts_created": 0,
            "sets_created": 0,
            "meals_created": 0,
        }

        # Get user's start date
        user = await db.fetchrow(
            "SELECT start_date FROM users WHERE id = $1",
            user_id,
        )

        if not user or not user["start_date"]:
            logger.warning(f"User {user_id} has no start date set")
            return results

        # Determine day number and date
        day_number = extraction.day.day_number
        day_date = extraction.day.date

        if day_number and not day_date:
            # Calculate date from day number
            day_date = user["start_date"] + timedelta(days=day_number - 1)
        elif day_date and not day_number:
            # Calculate day number from date
            delta = (day_date - user["start_date"]).days
            if 0 <= delta < 75:
                day_number = delta + 1
            else:
                logger.warning(f"Date {day_date} is outside Hard 75 range for user {user_id}")
                return results
        elif not day_number and not day_date:
            # Default to today
            day_date = date.today()
            delta = (day_date - user["start_date"]).days
            if 0 <= delta < 75:
                day_number = delta + 1
            else:
                logger.warning("Cannot determine day number")
                return results

        # Validate day number
        if day_number < 1 or day_number > 75:
            logger.warning(f"Invalid day number: {day_number}")
            return results

        # Merge day data
        day_id = await self._merge_day(
            user_id=user_id,
            day_number=day_number,
            day_date=day_date,
            extraction=extraction,
            photo_url=photo_urls[0] if photo_urls else None,
        )

        if day_id:
            results["day_created"] = True

            # Merge workouts
            for workout in extraction.workouts:
                session_id = await self._merge_workout(
                    user_id=user_id,
                    day_id=day_id,
                    day_date=day_date,
                    workout=workout,
                )
                if session_id:
                    results["workouts_created"] += 1

                    # Merge sets
                    sets_created = await self._merge_sets(session_id, workout)
                    results["sets_created"] += sets_created

            # Merge meals
            for meal in extraction.meals:
                meal_id = await self._merge_meal(
                    user_id=user_id,
                    day_id=day_id,
                    day_date=day_date,
                    meal=meal,
                )
                if meal_id:
                    results["meals_created"] += 1

        return results

    async def _merge_day(
        self,
        user_id: int,
        day_number: int,
        day_date: date,
        extraction: ExtractionResult,
        photo_url: Optional[str] = None,
    ) -> Optional[int]:
        """Upsert day data."""
        day = extraction.day

        # Build notes with timestamp
        new_notes = day.raw_notes
        if new_notes:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_notes = f"[{timestamp}]\n{new_notes}"

        row = await db.fetchrow(
            """
            INSERT INTO hard75_days (
                user_id, day_number, date,
                workout1_done, workout2_done, diet_done,
                water_done, reading_done, photo_done,
                steps, water_oz, reading_minutes,
                calories, protein_g, carbs_g, fat_g, fiber_g,
                photo_url, raw_notes
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
            ON CONFLICT (user_id, day_number)
            DO UPDATE SET
                workout1_done = hard75_days.workout1_done OR EXCLUDED.workout1_done,
                workout2_done = hard75_days.workout2_done OR EXCLUDED.workout2_done,
                diet_done = hard75_days.diet_done OR EXCLUDED.diet_done,
                water_done = hard75_days.water_done OR EXCLUDED.water_done,
                reading_done = hard75_days.reading_done OR EXCLUDED.reading_done,
                photo_done = hard75_days.photo_done OR EXCLUDED.photo_done,
                steps = COALESCE(EXCLUDED.steps, hard75_days.steps),
                water_oz = COALESCE(EXCLUDED.water_oz, hard75_days.water_oz),
                reading_minutes = COALESCE(EXCLUDED.reading_minutes, hard75_days.reading_minutes),
                calories = COALESCE(EXCLUDED.calories, hard75_days.calories),
                protein_g = COALESCE(EXCLUDED.protein_g, hard75_days.protein_g),
                carbs_g = COALESCE(EXCLUDED.carbs_g, hard75_days.carbs_g),
                fat_g = COALESCE(EXCLUDED.fat_g, hard75_days.fat_g),
                fiber_g = COALESCE(EXCLUDED.fiber_g, hard75_days.fiber_g),
                photo_url = COALESCE(EXCLUDED.photo_url, hard75_days.photo_url),
                raw_notes = CASE
                    WHEN EXCLUDED.raw_notes IS NOT NULL
                    THEN COALESCE(hard75_days.raw_notes || E'\\n\\n', '') || EXCLUDED.raw_notes
                    ELSE hard75_days.raw_notes
                END
            RETURNING id
            """,
            user_id,
            day_number,
            day_date,
            day.workout1_done,
            day.workout2_done,
            day.diet_done,
            day.water_done,
            day.reading_done,
            day.photo_done,
            day.steps,
            day.water_oz,
            day.reading_minutes,
            day.calories,
            day.protein_g,
            day.carbs_g,
            day.fat_g,
            day.fiber_g,
            photo_url,
            new_notes,
        )

        return row["id"] if row else None

    async def _merge_workout(
        self,
        user_id: int,
        day_id: int,
        day_date: date,
        workout: ExtractedWorkout,
    ) -> Optional[int]:
        """Create a workout session."""
        row = await db.fetchrow(
            """
            INSERT INTO workout_sessions (
                user_id, hard75_day_id, date, workout_number,
                workout_type, duration_minutes, location, is_outdoor
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            user_id,
            day_id,
            day_date,
            workout.workout_number,
            workout.workout_type,
            workout.duration_minutes,
            workout.location,
            workout.is_outdoor,
        )

        return row["id"] if row else None

    async def _merge_sets(
        self,
        session_id: int,
        workout: ExtractedWorkout,
    ) -> int:
        """Create workout sets from exercises."""
        sets_created = 0

        for exercise in workout.exercises:
            exercise_name = exercise.get("name", "Unknown")
            for set_data in exercise.get("sets", []):
                await db.execute(
                    """
                    INSERT INTO workout_sets (
                        session_id, exercise_name, set_number,
                        weight_lbs, reps, rpe
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    session_id,
                    exercise_name,
                    set_data.get("set_number"),
                    set_data.get("weight_lbs"),
                    set_data.get("reps"),
                    set_data.get("rpe"),
                )
                sets_created += 1

        return sets_created

    async def _merge_meal(
        self,
        user_id: int,
        day_id: int,
        day_date: date,
        meal: ExtractedMeal,
    ) -> Optional[int]:
        """Create a meal record."""
        import json

        # Convert food_items to JSON
        food_items_json = json.dumps(meal.food_items) if meal.food_items else None

        row = await db.fetchrow(
            """
            INSERT INTO meals (
                user_id, hard75_day_id, date, meal_type,
                description, calories, protein_g, carbs_g,
                fat_g, fiber_g, sugar_g, food_items
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
            """,
            user_id,
            day_id,
            day_date,
            meal.meal_type,
            meal.description,
            meal.calories,
            meal.protein_g,
            meal.carbs_g,
            meal.fat_g,
            meal.fiber_g,
            meal.sugar_g,
            food_items_json,
        )

        return row["id"] if row else None


# Global merger instance
merger = Merger()
