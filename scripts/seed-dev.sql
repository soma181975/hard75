-- Development seed data

-- Insert admin user
INSERT INTO users (email, name, role, start_date)
VALUES ('admin@example.com', 'Admin User', 'admin', CURRENT_DATE - INTERVAL '10 days')
ON CONFLICT (email) DO NOTHING;

-- Insert test user
INSERT INTO users (email, name, role, start_date)
VALUES ('test@example.com', 'Test User', 'user', CURRENT_DATE - INTERVAL '10 days')
ON CONFLICT (email) DO NOTHING;

-- Get user IDs
DO $$
DECLARE
    test_user_id INTEGER;
    session_id INTEGER;
BEGIN
    SELECT id INTO test_user_id FROM users WHERE email = 'test@example.com';

    -- Insert sample days for test user
    FOR i IN 1..10 LOOP
        INSERT INTO hard75_days (
            user_id, day_number, date,
            workout1_done, workout2_done, diet_done,
            water_done, reading_done, photo_done,
            steps, water_oz, reading_minutes,
            calories, protein_g, carbs_g, fat_g, fiber_g,
            raw_notes
        ) VALUES (
            test_user_id,
            i,
            CURRENT_DATE - (10 - i) * INTERVAL '1 day',
            TRUE, TRUE, TRUE,
            TRUE, TRUE, TRUE,
            8000 + (random() * 4000)::int,
            128,
            30,
            1800 + (random() * 400)::int,
            150 + (random() * 50)::int,
            150 + (random() * 100)::int,
            60 + (random() * 30)::int,
            25 + (random() * 15)::int,
            'Day ' || i || ' completed via seed data'
        )
        ON CONFLICT (user_id, day_number) DO NOTHING;

        -- Insert workout sessions for each day
        INSERT INTO workout_sessions (
            user_id, date, workout_number,
            workout_type, duration_minutes, location, is_outdoor
        ) VALUES (
            test_user_id,
            CURRENT_DATE - (10 - i) * INTERVAL '1 day',
            1,
            'strength',
            45,
            'gym',
            FALSE
        ) RETURNING id INTO session_id;

        -- Insert some sets for the session
        INSERT INTO workout_sets (session_id, exercise_name, set_number, weight_lbs, reps)
        VALUES
            (session_id, 'Bench Press', 1, 135, 10),
            (session_id, 'Bench Press', 2, 155, 8),
            (session_id, 'Bench Press', 3, 175, 6),
            (session_id, 'Squat', 1, 185, 10),
            (session_id, 'Squat', 2, 205, 8),
            (session_id, 'Squat', 3, 225, 6);

        -- Second workout (outdoor)
        INSERT INTO workout_sessions (
            user_id, date, workout_number,
            workout_type, duration_minutes, location, is_outdoor
        ) VALUES (
            test_user_id,
            CURRENT_DATE - (10 - i) * INTERVAL '1 day',
            2,
            'cardio',
            45,
            'outdoor',
            TRUE
        );
    END LOOP;

    -- Link workout sessions to hard75_days
    UPDATE workout_sessions ws
    SET hard75_day_id = hd.id
    FROM hard75_days hd
    WHERE ws.user_id = hd.user_id
    AND ws.date = hd.date;

    -- Insert sample meals for each day
    FOR i IN 1..10 LOOP
        -- Breakfast
        INSERT INTO meals (
            user_id, date, meal_type, description,
            calories, protein_g, carbs_g, fat_g, fiber_g,
            food_items
        ) VALUES (
            test_user_id,
            CURRENT_DATE - (10 - i) * INTERVAL '1 day',
            'breakfast',
            'Eggs and oatmeal',
            450,
            35,
            45,
            15,
            5,
            '[{"name": "Eggs", "quantity": "3 whole", "calories": 210, "protein_g": 18, "carbs_g": 0, "fat_g": 15}, {"name": "Oatmeal", "quantity": "1 cup", "calories": 150, "protein_g": 5, "carbs_g": 27, "fat_g": 3}, {"name": "Banana", "quantity": "1 medium", "calories": 90, "protein_g": 1, "carbs_g": 23, "fat_g": 0}]'::jsonb
        );

        -- Lunch
        INSERT INTO meals (
            user_id, date, meal_type, description,
            calories, protein_g, carbs_g, fat_g, fiber_g
        ) VALUES (
            test_user_id,
            CURRENT_DATE - (10 - i) * INTERVAL '1 day',
            'lunch',
            'Grilled chicken salad',
            550,
            45,
            25,
            30,
            8
        );

        -- Dinner
        INSERT INTO meals (
            user_id, date, meal_type, description,
            calories, protein_g, carbs_g, fat_g, fiber_g
        ) VALUES (
            test_user_id,
            CURRENT_DATE - (10 - i) * INTERVAL '1 day',
            'dinner',
            'Salmon with rice and vegetables',
            650,
            50,
            55,
            20,
            6
        );

        -- Snack
        INSERT INTO meals (
            user_id, date, meal_type, description,
            calories, protein_g, carbs_g, fat_g, fiber_g
        ) VALUES (
            test_user_id,
            CURRENT_DATE - (10 - i) * INTERVAL '1 day',
            'snack',
            'Protein shake with almonds',
            300,
            30,
            15,
            12,
            3
        );
    END LOOP;

    -- Link meals to hard75_days
    UPDATE meals m
    SET hard75_day_id = hd.id
    FROM hard75_days hd
    WHERE m.user_id = hd.user_id
    AND m.date = hd.date;

END $$;
