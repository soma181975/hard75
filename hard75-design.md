# Hard 75 Tracker — System Design Document

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Database Schema](#3-database-schema)
4. [Agent Design](#4-agent-design)
5. [Email Routing Logic](#5-email-routing-logic)
6. [Input Parsing](#6-input-parsing)
7. [Dashboard Design](#7-dashboard-design)
8. [Authentication](#8-authentication)
9. [Daily Summary Email](#9-daily-summary-email)
10. [Deployment](#10-deployment)

---

## 1. Overview

A multi-user Hard 75 challenge tracking system. Users send progress updates throughout the day as emails to a shared Gmail inbox. An agent reads each email, extracts structured data using Claude, and stores it in a Postgres database. Each user has a personal dashboard. An admin manages users and can view any dashboard.

### Hard 75 Rules Tracked

| Rule | Field |
|------|-------|
| Two workouts per day (at least one outdoor) | `workout_sessions` |
| Follow a diet — no cheat meals, no alcohol | `diet_done` |
| Drink one gallon of water | `water_done` |
| Read 10 pages of a non-fiction book | `reading_done` |
| Take a daily progress photo | `photo_done` |

---

## 2. Architecture

### Components

| Component | Technology | Vendor |
|-----------|-----------|--------|
| Agent (polling + processing) | Python 3.11+ | Digital Ocean Droplet |
| Database | Postgres | Supabase (free tier) |
| Photo storage | S3-compatible object storage | Digital Ocean Spaces |
| Email inbox | Gmail API | Google |
| AI extraction | Claude API (claude-sonnet-4-20250514) | Anthropic |
| Dashboard (web UI) | Python + FastAPI + Jinja2 | Digital Ocean Droplet (same) |
| Authentication | Google OAuth 2.0 | Google |
| Process management | systemd | Digital Ocean Droplet |
| Scheduled jobs | cron (system) | Digital Ocean Droplet |

### Data Flow

```
Users / Admin
    │
    │  email (text, images, strengthlog blocks)
    ▼
Shared Gmail Inbox
    │
    │  Gmail API (poll every 5 min)
    ▼
Agent (Python · Droplet)
    ├── Lookup sender → users table
    ├── Unknown sender → pending queue + auto-reply
    ├── Unapproved sender → ignore + log
    └── Approved user →
            ├── Claude extracts structured JSON
            ├── Smart merge into hard75_days
            ├── Parse workout blocks → workout_sessions + workout_sets
            ├── Upload photos → DO Spaces
            └── Upsert to Supabase

Cron (9pm per user's timezone)
    └── Query Supabase → build summary email → send via Gmail API

Dashboard (FastAPI · same Droplet)
    ├── Google OAuth login
    ├── role = 'user'  → personal dashboard
    └── role = 'admin' → admin dashboard + /dashboard/{user_id} drill-in
```

---

## 3. Database Schema

### 3.1 `users`

One row per registered person. Role drives access across the entire system.

```sql
create table users (
  id                  uuid primary key default gen_random_uuid(),
  email               text unique not null,
  name                text,
  role                text not null default 'user',   -- 'user' | 'admin'
  approved            boolean not null default false,
  approved_at         timestamptz,
  is_active           boolean not null default true,  -- soft delete
  hard75_start_date   date,
  timezone            text not null default 'UTC',    -- e.g. America/New_York
  summary_send_time   time not null default '21:00',  -- local time
  created_at          timestamptz not null default now()
);
```

**Notes:**
- `email` is the natural key — matched against Gmail `From:` address.
- `role = 'admin'` grants access to the admin dashboard and all user views.
- `is_active = false` disables the user without deleting data.
- `hard75_start_date` is set by the admin. Day numbers are calculated relative to this date in the user's timezone.
- Initial admin is bootstrapped from the `ADMIN_EMAIL` environment variable on first agent startup.

---

### 3.2 `hard75_days`

One row per user per calendar day. Unique on `(user_id, day_number)`.

```sql
create table hard75_days (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references users(id),
  day_number          integer not null,               -- 1–75
  date                date not null,
  title               text,                           -- email subject verbatim
  diet_done           boolean,
  diet_notes          text,
  water_done          boolean,
  reading_done        boolean,
  reading_pages       integer,
  reading_book        text,
  photo_done          boolean,
  photo_url           text,                           -- DO Spaces public URL
  steps               integer,                        -- from Apple Health or text
  distance_miles      numeric(6,2),
  active_calories     integer,
  exercise_minutes    integer,
  all_done            boolean,                        -- computed: all 5 tasks complete
  missed_reason       text,                           -- if user explains a missed day
  raw_notes           text,                           -- all email bodies appended
  email_received_at   timestamptz,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),

  unique (user_id, day_number)
);
```

**Smart merge rule:** When a new email arrives for a day that already has a row, only non-null fields from the new extraction overwrite existing values. `raw_notes` is always appended, never replaced.

---

### 3.3 `workout_sessions`

One row per workout session. A day can have up to 2 sessions.

```sql
create table workout_sessions (
  id                  uuid primary key default gen_random_uuid(),
  day_id              uuid not null references hard75_days(id),
  user_id             uuid not null references users(id),  -- denormalized
  workout_type        text not null,                       -- 'strength' | 'cardio' | 'walk' | 'other'
  is_outdoor          boolean,
  started_at          timestamptz,
  duration_minutes    integer,
  total_sets          integer,
  total_reps          integer,
  total_volume_lbs    numeric(10,1),
  notes               text,                               -- raw source text
  created_at          timestamptz not null default now()
);
```

**Notes:**
- `user_id` is denormalized for fast querying across sessions without joining through `hard75_days`.
- `is_outdoor` is used to validate the Hard 75 rule that at least one workout is outdoors per day.

---

### 3.4 `workout_sets`

One row per individual exercise set. Powers PR/YR tracking and progression charts.

```sql
create table workout_sets (
  id              uuid primary key default gen_random_uuid(),
  session_id      uuid not null references workout_sessions(id),
  user_id         uuid not null references users(id),  -- denormalized
  exercise_name   text not null,                       -- normalized to lowercase
  set_number      integer not null,
  reps            integer,
  weight_lbs      numeric(7,2),
  is_pr           boolean not null default false,      -- PR! flag
  is_yr           boolean not null default false,      -- YR! flag
  created_at      timestamptz not null default now()
);
```

**Notes:**
- `exercise_name` is normalized to lowercase on insert (e.g. `"bench press"`).
- PR and YR flags are stored as-reported by the user / strengthlog app.
- To find progression for a given exercise: `select * from workout_sets where user_id = $1 and exercise_name = $2 order by created_at`.

---

### 3.5 `pending_senders`

Temporary queue for unknown senders awaiting admin review.

```sql
create table pending_senders (
  id            uuid primary key default gen_random_uuid(),
  email         text not null,
  first_seen_at timestamptz not null default now(),
  email_subject text,
  email_snippet text,   -- first 300 chars of email body
  resolved      boolean not null default false
);
```

---

### 3.6 Indexes

```sql
create index on hard75_days (user_id, day_number);
create index on hard75_days (user_id, date);
create index on workout_sessions (user_id);
create index on workout_sessions (day_id);
create index on workout_sets (user_id, exercise_name);
create index on workout_sets (session_id);
```

---

### 3.7 Triggers

```sql
-- Auto-update updated_at on hard75_days
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger hard75_days_updated_at
  before update on hard75_days
  for each row execute procedure set_updated_at();
```

---

## 4. Agent Design

### 4.1 Project Structure

```
hard75-agent/
├── agent.py              # main entry point — polling loop
├── config.py             # env vars + constants
├── bootstrap.py          # initial admin seeding on startup
├── gmail.py              # Gmail API client + helpers
├── extractor.py          # Claude extraction logic
├── merger.py             # smart merge into Supabase
├── storage.py            # DO Spaces photo upload
├── scheduler.py          # cron-triggered summary email
├── dashboard/
│   ├── app.py            # FastAPI app
│   ├── auth.py           # Google OAuth flow
│   ├── routes/
│   │   ├── user.py       # personal dashboard routes
│   │   └── admin.py      # admin dashboard routes
│   └── templates/        # Jinja2 HTML templates
├── requirements.txt
├── .env.example
├── hard75.service        # systemd unit file
└── README.md
```

### 4.2 Polling Loop (`agent.py`)

```
startup:
  bootstrap.ensure_admin_exists()

loop every 5 minutes:
  messages = gmail.fetch_unread()
  for each message:
    sender = extract from_address(message)
    user   = supabase.lookup_user_by_email(sender)

    if user is None:
      pending_senders.insert(sender, snippet)
      gmail.send_reply(message, template="unknown_sender")
      continue

    if not user.approved or not user.is_active:
      gmail.send_reply(message, template="not_approved")
      continue

    extracted = extractor.process(message, user)
    merger.merge_day(user, extracted)
    gmail.mark_read(message)
```

### 4.3 Admin Bootstrap (`bootstrap.py`)

On every startup, run:

```python
admin_email = os.environ["ADMIN_EMAIL"]
existing = supabase.table("users").select("id").eq("email", admin_email).execute()
if not existing.data:
    supabase.table("users").insert({
        "email": admin_email,
        "name": "Admin",
        "role": "admin",
        "approved": True,
        "is_active": True,
    }).execute()
```

This is idempotent — safe to run on every restart.

---

## 5. Email Routing Logic

```
Email arrives
    │
    ├─ sender in users table?
    │       │
    │     NO └─ insert into pending_senders
    │            send auto-reply: "contact admin to register"
    │            mark as read → stop
    │
    └─ YES
          │
          ├─ approved = false OR is_active = false?
          │       │
          │     YES └─ log it, ignore silently → stop
          │
          └─ approved = true AND is_active = true
                │
                └─ process email → extract → merge → save
```

---

## 6. Input Parsing

Claude is given the full email (subject, text body, and any image attachments as base64) in a single API call. The system prompt instructs Claude to detect and extract all content types present.

### 6.1 Claude System Prompt (summary)

Claude is instructed to return a single JSON object with three top-level keys:

```json
{
  "day": { ... },           // hard75_days fields
  "sessions": [ ... ],      // array of workout_sessions
  "sets": { ... }           // keyed by session index → array of sets
}
```

Rules given to Claude:
- Use `null` for any field not mentioned — never guess or infer.
- Detect day number from subject (e.g. "Day 12") first; fall back to `null` (agent calculates from start_date).
- Parse strengthlog format: `Exercise Name: reps x weight (PR!|YR!), ...`
- If an image is attached, extract Apple Health stats: steps, distance, active calories, exercise minutes.
- If a strengthlog screenshot is attached instead of text, extract the same set data from the image.
- Normalize exercise names to lowercase.
- `workout_type`: classify as `'strength'` if sets/reps are present, `'cardio'` or `'walk'` for distance/time only workouts, `'other'` otherwise.

### 6.2 Day Number Calculation

```python
from datetime import date
import pytz

def calculate_day_number(user: User, email_date: datetime) -> int:
    tz = pytz.timezone(user.timezone)
    local_date = email_date.astimezone(tz).date()
    delta = local_date - user.hard75_start_date
    return max(1, delta.days + 1)
```

If Claude finds `"Day 12"` in the subject, that value is used directly. Otherwise the agent calculates from the email timestamp in the user's local timezone.

### 6.3 Smart Merge (`merger.py`)

```
1. Determine day_number for this user
2. Fetch existing hard75_days row (user_id, day_number)
3. If no row exists → insert
4. If row exists:
     for each field in extracted["day"]:
       if new value is not null → overwrite existing
     raw_notes → append new email body
     recompute all_done:
       all_done = (
         workout count >= 2 AND
         at least one is_outdoor AND
         diet_done AND water_done AND
         reading_done AND photo_done
       )
5. For each session in extracted["sessions"]:
     check if a session with same started_at already exists
     if not → insert workout_session + its sets
```

---

## 7. Dashboard Design

### 7.1 Routing

| URL | Access | View |
|-----|--------|------|
| `/` | Any authenticated | Redirects based on role |
| `/dashboard` | role = 'user' | Personal dashboard |
| `/admin` | role = 'admin' | Admin dashboard |
| `/admin/users/{id}` | role = 'admin' | View any user's personal dashboard |
| `/admin/users/new` | role = 'admin' | Add new user form |
| `/admin/users/{id}/edit` | role = 'admin' | Edit user form |

### 7.2 Personal Dashboard Widgets

| Widget | Data source |
|--------|-------------|
| 75-day progress bar | `count(*) from hard75_days where user_id = $1` |
| Streak counter | Consecutive `all_done = true` days ending today |
| Daily checklist grid | `hard75_days` — 75 cells, green/red/gray |
| Photo gallery | `photo_url` per day, sorted by day_number |
| Volume per session chart | `total_volume_lbs` from `workout_sessions` |
| Exercise progression chart | `weight_lbs` over time per `exercise_name` from `workout_sets` |
| PR / YR highlight feed | `workout_sets where is_pr = true or is_yr = true` |
| Steps trend chart | `steps` from `hard75_days` |
| Week-at-a-glance | Last 7 `hard75_days` rows — task completion per day |

### 7.3 Admin Dashboard Widgets

| Widget | Description |
|--------|-------------|
| Users table | All users: name, email, role, approved, is_active, current day number, today's all_done status |
| Pending approvals | `pending_senders` where `resolved = false` — approve/reject actions |
| Add user form | Fields: email, name, timezone, hard75_start_date. Creates row with `approved = true` |
| Edit user panel | Edit: name, timezone, hard75_start_date, role, is_active |
| View as user | Link to `/admin/users/{id}` — renders the user's personal dashboard |

---

## 8. Authentication

Google OAuth 2.0 via the `authlib` Python library and FastAPI.

### 8.1 Flow

```
User visits dashboard
    └── Not authenticated → redirect to /login

/login
    └── Redirect to Google OAuth consent screen
            scope: openid, email, profile

Google callback → /auth/callback
    └── Exchange code for tokens
    └── Extract email from id_token
    └── Lookup email in users table
            ├── Not found or not approved or not is_active → show "access denied"
            └── Found + approved + active → set session cookie, redirect to /
```

### 8.2 Session

- Server-side sessions using `itsdangerous` signed cookies.
- Session stores: `user_id`, `email`, `role`.
- Session expiry: 7 days.
- All dashboard routes protected by a `require_login` dependency.
- Admin routes additionally protected by a `require_admin` dependency.

---

## 9. Daily Summary Email

### 9.1 Scheduling

A separate cron job runs every minute on the Droplet and checks which users are due for their summary email at that moment (accounting for each user's timezone and `summary_send_time`).

```bash
# crontab entry
* * * * * /home/hard75/hard75-agent/venv/bin/python /home/hard75/hard75-agent/scheduler.py
```

`scheduler.py` logic:

```
for each active + approved user:
  local_now = now in user.timezone
  if local_now.time() matches user.summary_send_time (within the minute):
    if not already sent today:
      build_and_send_summary(user)
```

### 9.2 Summary Email Contents

| Section | Content |
|---------|---------|
| Streak counter | Current consecutive all_done days |
| Today's checklist | Each of the 5 tasks: done or missed |
| Photo of the day | Inline image from `photo_url` if present |
| Week-at-a-glance | Table: last 7 days × 5 tasks, green/red cells |

Email is sent via the Gmail API using the shared inbox as sender (`From: hard75bot@gmail.com`), addressed to `user.email`.

---

## 10. Deployment

### 10.1 Supabase

**Purpose:** Managed Postgres database.

**Setup steps:**
1. Create a free account at https://supabase.com
2. Create a new project. Choose a region close to your Droplet.
3. Go to **SQL Editor** and run `schema.sql` (all `create table`, index, and trigger statements).
4. Go to **Settings → API** and copy:
   - `Project URL` → `SUPABASE_URL`
   - `service_role` key (not `anon`) → `SUPABASE_SERVICE_KEY`

**Free tier limits:** 500 MB database, 1 GB file storage, 2 GB bandwidth. Sufficient for 75 days × multiple users.

**Environment variables:**
```
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
```

---

### 10.2 Digital Ocean Spaces

**Purpose:** S3-compatible object storage for progress photos.

**Setup steps:**
1. In your Digital Ocean account, go to **Spaces Object Storage → Create Space**.
2. Choose a region (e.g. `nyc3`). Name it `hard75-photos`.
3. Set file listing to **Private** (individual files will be public-read via ACL).
4. Go to **API → Spaces Access Keys → Generate New Key**.
5. Copy the key and secret.

**Photo path convention:** `/{user_id}/day-{NNN}/{original_filename}`

Example: `/a1b2c3d4/day-012/progress.jpg`

**Environment variables:**
```
DO_SPACES_KEY=your_spaces_access_key
DO_SPACES_SECRET=your_spaces_secret_key
DO_SPACES_BUCKET=hard75-photos
DO_SPACES_REGION=nyc3
DO_SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
```

---

### 10.3 Digital Ocean Droplet

**Purpose:** Runs the agent process, dashboard web server, and cron jobs.

**Recommended size:** Basic, 1 vCPU, 1 GB RAM ($6/mo). Sufficient for the polling agent + FastAPI dashboard.

**Setup steps:**

```bash
# 1. Create Droplet (Ubuntu 24.04 LTS) via DO console or CLI

# 2. SSH in as root
ssh root@your-droplet-ip

# 3. Create a dedicated user
adduser hard75
usermod -aG sudo hard75

# 4. Install Python
apt update && apt install -y python3.11 python3.11-venv python3-pip git

# 5. Copy project files
# From your local machine:
scp -r hard75-agent/ hard75@your-droplet-ip:/home/hard75/
scp token.pickle hard75@your-droplet-ip:/home/hard75/hard75-agent/

# 6. Set up Python virtual environment
su - hard75
cd /home/hard75/hard75-agent
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 7. Create .env file
cp .env.example .env
nano .env   # fill in all values

# 8. Install systemd service for the agent
sudo cp hard75.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hard75
sudo systemctl start hard75

# 9. Install systemd service for the dashboard
sudo cp hard75-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hard75-dashboard
sudo systemctl start hard75-dashboard

# 10. Set up cron for summary emails
crontab -e
# Add: * * * * * /home/hard75/hard75-agent/venv/bin/python /home/hard75/hard75-agent/scheduler.py >> /var/log/hard75-scheduler.log 2>&1

# 11. Check logs
journalctl -u hard75 -f
journalctl -u hard75-dashboard -f
```

**Systemd unit — agent (`hard75.service`):**
```ini
[Unit]
Description=Hard 75 Agent
After=network.target

[Service]
Type=simple
User=hard75
WorkingDirectory=/home/hard75/hard75-agent
EnvironmentFile=/home/hard75/hard75-agent/.env
ExecStart=/home/hard75/hard75-agent/venv/bin/python agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Systemd unit — dashboard (`hard75-dashboard.service`):**
```ini
[Unit]
Description=Hard 75 Dashboard
After=network.target

[Service]
Type=simple
User=hard75
WorkingDirectory=/home/hard75/hard75-agent
EnvironmentFile=/home/hard75/hard75-agent/.env
ExecStart=/home/hard75/hard75-agent/venv/bin/uvicorn dashboard.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

### 10.4 Google Cloud Console (Gmail API + OAuth)

**Purpose:** Gmail API access for reading emails and sending summaries. Google OAuth for dashboard login.

**Setup steps:**

1. Go to https://console.cloud.google.com and create a new project (e.g. `Hard75Tracker`).
2. Go to **APIs & Services → Library** and enable:
   - **Gmail API**
3. Go to **APIs & Services → OAuth consent screen**:
   - User type: **External**
   - App name: `Hard 75 Tracker`
   - Add scopes: `gmail.modify`, `openid`, `email`, `profile`
   - Add your email as a test user (while in development)
4. Go to **APIs & Services → Credentials → Create Credentials**:
   - Create an **OAuth 2.0 Client ID** → Desktop app → download as `credentials.json`
   - Create a second **OAuth 2.0 Client ID** → Web application
     - Authorized redirect URI: `http://your-droplet-ip:8000/auth/callback`
     - Download or note the client ID and secret
5. Run the agent once locally to authorize Gmail:
   ```bash
   python agent.py
   # Browser opens → sign in → token.pickle is created
   ```
6. Copy `token.pickle` to the Droplet.

**Environment variables:**
```
GOOGLE_CLIENT_ID=your_web_oauth_client_id
GOOGLE_CLIENT_SECRET=your_web_oauth_client_secret
GOOGLE_REDIRECT_URI=http://your-droplet-ip:8000/auth/callback
SESSION_SECRET_KEY=a_long_random_string
```

---

### 10.5 Anthropic API

**Purpose:** Claude powers all email extraction — free text, strengthlog parsing, Apple Health screenshot OCR.

**Setup steps:**
1. Go to https://console.anthropic.com
2. Create an API key under **API Keys**.
3. Model to use: `claude-sonnet-4-20250514`

**Environment variables:**
```
ANTHROPIC_API_KEY=sk-ant-...
```

---

### 10.6 Complete `.env` Reference

```bash
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Digital Ocean Spaces
DO_SPACES_KEY=your_spaces_access_key
DO_SPACES_SECRET=your_spaces_secret_key
DO_SPACES_BUCKET=hard75-photos
DO_SPACES_REGION=nyc3
DO_SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com

# Google OAuth (dashboard login)
GOOGLE_CLIENT_ID=your_web_oauth_client_id
GOOGLE_CLIENT_SECRET=your_web_oauth_client_secret
GOOGLE_REDIRECT_URI=http://your-droplet-ip:8000/auth/callback
SESSION_SECRET_KEY=replace_with_long_random_string

# Admin bootstrap
ADMIN_EMAIL=your@email.com

# Agent config
POLL_INTERVAL_SECONDS=300
```

---

### 10.7 Deployment Checklist

```
[ ] Supabase project created
[ ] schema.sql executed in Supabase SQL editor
[ ] DO Space created (hard75-photos, private listing)
[ ] DO Spaces access key generated
[ ] Google Cloud project created
[ ] Gmail API enabled
[ ] OAuth consent screen configured
[ ] Desktop OAuth client created → credentials.json downloaded
[ ] Web OAuth client created → client ID + secret noted
[ ] Gmail authorized locally → token.pickle generated
[ ] Anthropic API key created
[ ] Droplet created (Ubuntu 24.04, 1 GB RAM)
[ ] Project files copied to Droplet
[ ] token.pickle copied to Droplet
[ ] .env filled in on Droplet
[ ] Python venv created + requirements installed
[ ] hard75.service installed + started
[ ] hard75-dashboard.service installed + started
[ ] Cron entry added for scheduler.py
[ ] ADMIN_EMAIL user created in DB (auto via bootstrap)
[ ] Admin can log in via Google OAuth
[ ] Test email sent → data appears in Supabase
```

---

*Document version: 1.0 — reflects multi-user design with strength training tracking, Apple Health integration, admin dashboard, and Google OAuth.*
