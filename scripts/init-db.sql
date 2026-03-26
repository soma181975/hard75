-- Hard 75 Tracker Database Schema

-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    google_id VARCHAR(255) UNIQUE,
    avatar_url TEXT,
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    start_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on email for lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);

-- Hard75 Days tracking
CREATE TABLE hard75_days (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL CHECK (day_number >= 1 AND day_number <= 75),
    date DATE NOT NULL,

    -- Daily tasks
    workout1_done BOOLEAN DEFAULT FALSE,
    workout2_done BOOLEAN DEFAULT FALSE,
    diet_done BOOLEAN DEFAULT FALSE,
    water_done BOOLEAN DEFAULT FALSE,
    reading_done BOOLEAN DEFAULT FALSE,
    photo_done BOOLEAN DEFAULT FALSE,

    -- All tasks complete?
    all_done BOOLEAN GENERATED ALWAYS AS (
        workout1_done AND workout2_done AND diet_done AND
        water_done AND reading_done AND photo_done
    ) STORED,

    -- Additional tracking
    steps INTEGER,
    water_oz INTEGER,
    reading_minutes INTEGER,

    -- Daily nutrition totals (aggregated from meals or reported directly)
    calories INTEGER,
    protein_g INTEGER,
    carbs_g INTEGER,
    fat_g INTEGER,
    fiber_g INTEGER,

    -- Photo URLs (stored in S3/MinIO)
    photo_url TEXT,

    -- Raw notes from email
    raw_notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint: one entry per user per day
    UNIQUE(user_id, day_number)
);

CREATE INDEX idx_hard75_days_user_date ON hard75_days(user_id, date);
CREATE INDEX idx_hard75_days_user_day ON hard75_days(user_id, day_number);

-- Workout sessions
CREATE TABLE workout_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hard75_day_id INTEGER REFERENCES hard75_days(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    workout_number INTEGER CHECK (workout_number IN (1, 2)),

    -- Workout metadata
    workout_type VARCHAR(100), -- e.g., 'strength', 'cardio', 'outdoor'
    duration_minutes INTEGER,
    location VARCHAR(100), -- e.g., 'gym', 'outdoor', 'home'

    -- For outdoor workouts
    is_outdoor BOOLEAN DEFAULT FALSE,

    -- Notes
    notes TEXT,

    -- Screenshot URL (e.g., from Strengthlog)
    screenshot_url TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_workout_sessions_user_date ON workout_sessions(user_id, date);
CREATE INDEX idx_workout_sessions_day ON workout_sessions(hard75_day_id);

-- Workout sets (individual exercises)
CREATE TABLE workout_sets (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,

    -- Exercise info
    exercise_name VARCHAR(255) NOT NULL,
    set_number INTEGER,

    -- Set data
    weight_lbs DECIMAL(6,2),
    reps INTEGER,
    duration_seconds INTEGER, -- for timed exercises
    distance_miles DECIMAL(6,2), -- for cardio

    -- RPE (Rate of Perceived Exertion)
    rpe DECIMAL(3,1) CHECK (rpe >= 1 AND rpe <= 10),

    notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_workout_sets_session ON workout_sets(session_id);
CREATE INDEX idx_workout_sets_exercise ON workout_sets(exercise_name);

-- Meals tracking
CREATE TABLE meals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hard75_day_id INTEGER REFERENCES hard75_days(id) ON DELETE CASCADE,
    date DATE NOT NULL,

    -- Meal info
    meal_type VARCHAR(50), -- 'breakfast', 'lunch', 'dinner', 'snack', 'pre-workout', 'post-workout'
    meal_time TIME,
    description TEXT,

    -- Nutrition data
    calories INTEGER,
    protein_g INTEGER,
    carbs_g INTEGER,
    fat_g INTEGER,
    fiber_g INTEGER,
    sugar_g INTEGER,
    sodium_mg INTEGER,

    -- Optional: specific food items as JSON array
    food_items JSONB,

    -- Notes
    notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_meals_user_date ON meals(user_id, date);
CREATE INDEX idx_meals_day ON meals(hard75_day_id);
CREATE INDEX idx_meals_type ON meals(meal_type);

-- Pending senders (emails not yet approved)
CREATE TABLE pending_senders (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    message_count INTEGER DEFAULT 1,
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    approved_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_pending_senders_email ON pending_senders(email);
CREATE INDEX idx_pending_senders_status ON pending_senders(status);

-- Processed emails (to avoid reprocessing)
CREATE TABLE processed_emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'success' CHECK (status IN ('success', 'failed', 'skipped')),
    error_message TEXT
);

CREATE INDEX idx_processed_emails_message_id ON processed_emails(message_id);

-- Function to calculate current streak
CREATE OR REPLACE FUNCTION calculate_streak(p_user_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    streak INTEGER := 0;
    check_day INTEGER;
BEGIN
    -- Get the highest completed day
    SELECT MAX(day_number) INTO check_day
    FROM hard75_days
    WHERE user_id = p_user_id AND all_done = TRUE;

    IF check_day IS NULL THEN
        RETURN 0;
    END IF;

    -- Count consecutive days backwards from the highest
    WHILE check_day > 0 LOOP
        IF EXISTS (
            SELECT 1 FROM hard75_days
            WHERE user_id = p_user_id
            AND day_number = check_day
            AND all_done = TRUE
        ) THEN
            streak := streak + 1;
            check_day := check_day - 1;
        ELSE
            EXIT;
        END IF;
    END LOOP;

    RETURN streak;
END;
$$ LANGUAGE plpgsql;
