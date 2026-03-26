# Hard 75 Tracker

A multi-user Hard 75 challenge tracking system with email-based progress updates.

## Quick Start

```bash
# Start all services
docker compose up

# Run in development mode (with hot reload)
docker compose up --build

# Run tests
docker compose exec app pytest

# View logs
docker compose logs -f app
```

## Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│   Gmail API     │───▶│ Email Agent  │───▶│  PostgreSQL │
│  (user emails)  │    │   (Claude)   │    │   Database  │
└─────────────────┘    └──────────────┘    └─────────────┘
                              │                    │
                              ▼                    │
                       ┌──────────────┐           │
                       │    MinIO     │           │
                       │  (S3 photos) │           │
                       └──────────────┘           │
                                                  │
┌─────────────────┐    ┌──────────────┐          │
│    Browser      │───▶│   FastAPI    │◀─────────┘
│  (Dashboard)    │◀───│  + Jinja2    │
└─────────────────┘    └──────────────┘
```

## Project Structure

- `src/main.py` - FastAPI app entry point
- `src/config.py` - Environment configuration (pydantic-settings)
- `src/db.py` - Async PostgreSQL client (asyncpg)
- `src/storage.py` - S3/MinIO client for photo uploads
- `src/auth/` - Google OAuth and session management
- `src/api/` - REST API endpoints
- `src/pages/` - Server-rendered page routes
- `src/partials/` - HTMX partial templates
- `src/agent/` - Email processing agent
- `src/scheduler/` - Daily summary email job
- `src/templates/` - Jinja2 templates

## Key Commands

```bash
# Database (from host)
psql -h localhost -p 6432 -U hard75 -d hard75

# Database (from docker)
docker compose exec postgres psql -U hard75 -d hard75

# MinIO Console
open http://localhost:9001  # admin: minioadmin/minioadmin

# Run the email agent manually
docker compose exec app python -m src.agent.runner

# Run daily summary job
docker compose exec app python -m src.scheduler.summary

# Bootstrap admin user
docker compose exec app python -m src.agent.bootstrap
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - OAuth credentials
- `ANTHROPIC_API_KEY` - For Claude extraction
- `ADMIN_EMAIL` / `ADMIN_NAME` - Initial admin user

## Gmail API Setup

1. Create project in Google Cloud Console
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `credentials.json` to project root
5. Run agent once to generate `token.pickle`

## Database Schema

Key tables:
- `users` - User accounts with role (user/admin)
- `hard75_days` - Daily progress tracking (75 days) with nutrition totals
- `workout_sessions` - Workout session details
- `workout_sets` - Individual exercise sets
- `meals` - Meal entries with macros (calories, protein, carbs, fat, fiber)
- `pending_senders` - Unknown email senders awaiting approval

## API Endpoints

### Days
- `GET /api/days` - List user's days
- `GET /api/days/streak` - Get streak info
- `GET /api/days/{day_number}` - Get specific day
- `POST /api/days/{day_number}` - Create/update day
- `PATCH /api/days/{day_number}` - Update day fields

### Workouts
- `GET /api/workouts` - List sessions
- `GET /api/workouts/volume` - Volume over time
- `GET /api/workouts/exercises` - List exercises
- `GET /api/workouts/exercises/{name}/progression` - Exercise progression

### Meals & Nutrition
- `GET /api/meals` - List meals (filterable by type, date range)
- `GET /api/meals/today` - Today's nutrition summary
- `GET /api/meals/daily` - Daily nutrition totals for charts
- `GET /api/meals/trends` - Macro trends over time
- `POST /api/meals` - Create meal entry
- `DELETE /api/meals/{id}` - Delete meal

### Admin
- `GET /api/users` - List all users
- `POST /api/users` - Create user
- `PATCH /api/users/{id}` - Update user
- `GET /api/pending` - List pending senders
- `POST /api/pending/{id}/approve` - Approve sender
- `POST /api/pending/{id}/reject` - Reject sender

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_extractor.py

# Run with coverage
pytest --cov=src

# Run with verbose output
pytest -v
```

## Development Notes

- Templates use Tailwind CSS via CDN (no build step)
- HTMX for dynamic updates without full page reloads
- Chart.js for progress visualization (workouts, steps, calories, macros)
- Email agent polls every 5 minutes by default
- Photos stored in MinIO (S3-compatible) bucket
- Claude extracts meals, macros, and nutrition data from emails
- Supports parsing nutrition screenshots (MyFitnessPal, etc.)

## Email Format Examples

The email agent uses Claude to extract data. Users can send emails like:

```
Day 5 update!

Breakfast: Eggs (3) with oatmeal - 450 cal, 35g protein
Lunch: Grilled chicken salad - 550 cal, 45g protein
Dinner: Salmon with rice - 650 cal, 50g protein

Total: 1950 calories, 160g protein, 150g carbs, 65g fat

Workout 1: Gym - bench press 135x10, 155x8, squat 225x6
Workout 2: 45 min outdoor run

Water: done (128oz)
Reading: 15 pages of Atomic Habits
Photo: attached

Steps: 12,543
```

## Hard 75 Rules

1. Two 45-minute workouts daily (one must be outdoor)
2. Follow a diet (no alcohol, no cheat meals)
3. Drink 1 gallon of water
4. Read 10 pages of non-fiction
5. Take a daily progress photo
