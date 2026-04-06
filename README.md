# CareLoop

> **AI that closes the care coordination gap** — Powered by GLM 5.1

CareLoop is an AI-powered care coordination platform that bridges the communication gap between healthcare providers and patients. Using GLM 5.1's advanced reasoning capabilities — including visible thinking, function calling, and multi-modal analysis — CareLoop transforms clinical encounters into structured care summaries, actionable tasks, risk assessments, and personalized care plans.

---

## Why CareLoop?

Healthcare coordination fails when communication breaks down. Patients forget follow-up instructions, providers lack real-time visibility into patient progress, and critical signals get lost in unstructured notes. CareLoop uses GLM 5.1 to:

- **Analyze** clinical encounters into structured summaries with risk flags
- **Act** autonomously via function calling — creating tasks, sending reminders, scheduling follow-ups
- **Reason** transparently — every AI decision shows its chain-of-thought
- **Plan** personalized multi-week care plans based on patient history

---

## Demo — Try It Now (No API Key Required!)

CareLoop works **out of the box without any API key** — it includes a sophisticated demo mode with realistic mock AI responses:

```bash
# Quick start
git clone https://github.com/your-repo/careloop.git
cd careloop
pip install -r requirements.txt
python3 seed.py
python3 -m uvicorn app.main:app --reload --port 8080
```

Then open **http://localhost:8080** — you'll see 3 demo patients with rich clinical histories ready for analysis.

---

## GLM 5.1 Capabilities Demonstrated

CareLoop showcases **6 distinct GLM 5.1 capabilities**, each mapped to a real clinical workflow:

| Feature | Clinical Use Case | GLM 5.1 Capability |
|---------|-------------------|---------------------|
| **Care Analysis** | Encounters → structured summaries, tasks, risk flags | Function calling + JSON output |
| **Trend Detection** | Compare analyses over time to spot patterns | Long-horizon reasoning |
| **Patient Q&A** | Context-aware answers to patient questions | Conversational AI + empathy |
| **Encounter Summarization** | Extract structured data from free-text notes | Information extraction |
| **Care Plan Generation** | Multi-week personalized care plans | Planning + function calling |
| **Real-time Thinking** | Watch GLM reason through clinical problems | Reasoning content streaming |

### What Makes This Special for GLM 5.1

- **Visible Thinking**: Every AI call displays GLM's reasoning chain in real-time via SSE streaming
- **Autonomous Function Calling**: GLM creates tasks, schedules reminders, and sends messages without human intervention
- **4 Tool Definitions**: `create_task`, `schedule_reminder`, `send_message`, `get_patient_history` — all executed server-side
- **Transparency Panel**: See the exact prompts sent and responses received — responsible AI in action
- **Toast Notifications**: Real-time visual feedback as GLM takes autonomous actions
- **Multi-modal Vision**: Document analysis pipeline ready for image-based clinical document processing

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser (Jinja2 SSR)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ Dashboard │  │ Timeline │  │ Analysis │  │ Care Plans │ │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬──────┘ │
│        └──────────────┴─────────────┴─────────────┘         │
│                          │ SSE Stream                        │
└──────────────────────────┼──────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                    FastAPI (Python 3.11)                     │
│  ┌──────────────┐  ┌─────┴──────┐  ┌──────────────────────┐ │
│  │ 10 Routers   │  │ GLM Service │  │ Auth Middleware      │ │
│  │ (60+ routes) │  │ (6 AI flows)│  │ (RBAC + Sessions)    │ │
│  └──────┬───────┘  └──────┬──────┘  └──────────────────────┘ │
│         │                  │                                   │
│  ┌──────┴───────┐   ┌─────┴──────────────────────────────┐  │
│  │   SQLite     │   │  Z.ai API (OpenAI-compatible)       │  │
│  │  (17 tables) │   │  ┌─────────────────────────────┐   │  │
│  └──────────────┘   │  │  GLM 5.1                    │   │  │
│                      │  │  • Streaming + Thinking      │   │  │
│                      │  │  • Function Calling (4 tools)│   │  │
│                      │  │  • Vision (multi-modal)      │   │  │
│                      │  └─────────────────────────────┘   │  │
│                      └────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Local Development

```bash
# Clone and enter directory
git clone https://github.com/YOUR_USERNAME/careloop.git
cd careloop

# Install dependencies
pip install -r requirements.txt

# (Optional) Add your GLM API key for real AI
cp .env.example .env
# Edit .env and add: GLM_API_KEY=your_z.ai_api_key

# Seed demo data (3 patients with rich clinical histories)
python3 seed.py

# Run the application
python3 -m uvicorn app.main:app --reload --port 8080
```

Visit **http://localhost:8080**

### Docker

```bash
# Build
docker build -t careloop .

# Run without API key (demo mode)
docker run -p 8080:8080 careloop

# Or with your GLM API key
docker run -p 8080:8080 -e GLM_API_KEY=your-key careloop
```

### Deploy to Google Cloud Run

```bash
export PROJECT_ID=your-project-id
gcloud builds submit --tag gcr.io/$PROJECT_ID/careloop
gcloud run deploy careloop \
  --image gcr.io/$PROJECT_ID/careloop \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars GLM_API_KEY=$GLM_API_KEY,GLM_MODEL=glm-4-alltools
```

---

## Demo Walkthrough

### 1. Dashboard
On the home page, you'll see:
- 3 demo patients with detailed clinical histories
- Stats showing encounters and AI analyses per patient
- Quick access to all GLM features

### 2. Patient Timeline
Click any patient to see:
- Chronological timeline of all encounters (provider updates + patient check-ins)
- AI analyses with structured outputs (summaries, risk flags, tasks)
- Care plans and Q&A exchanges
- Task management with complete/skip actions

### 3. Run GLM 5.1 Analysis
Click "Run AI Analysis" and watch:
- Loading overlay with thinking indicator
- Real-time reasoning display via Server-Sent Events
- Toast notifications as tasks are created autonomously
- Structured summaries, risk flags, and prioritized tasks

### 4. Ask GLM Questions
Go to "Ask CareLoop AI" to:
- Type a question or use voice input (Web Speech API)
- Get context-aware, empathetic responses referencing patient history
- See previous Q&A history
- Text-to-speech for responses

### 5. Generate Care Plans
Click "Generate Care Plan" for:
- Multi-week personalized plans based on full encounter history
- Weekly tasks for patient and provider
- Goals, milestones, and emergency triggers
- Autonomous task creation via function calling

### 6. Detect Trends
Click "Detect Trends" to:
- Compare multiple analyses over time
- Identify patterns and trajectory direction
- See recommendations based on trend analysis

### 7. View Transparency
Every AI response includes:
- Expandable transparency panel
- Exact prompts sent to GLM 5.1 (including system + user context)
- Raw, unmodified GLM responses
- Model name and timing info

### 8. Role-Based Dashboards
Switch between demo personas to see:
- **Provider Dashboard**: Overdue tasks, upcoming appointments, patient snapshots
- **Coordinator Dashboard**: Escalation queue, outreach needs, missing documents
- **Patient Dashboard**: Medication schedule, symptom trends, countdown to next appointment
- **Admin Dashboard**: System stats, user management, audit log

---

## Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GLM_API_KEY` | — | No* | Z.ai API key. Without it, app uses realistic mock data |
| `GLM_API_URL` | `https://api.z.ai/api/paas/v4/chat/completions` | No | GLM API endpoint |
| `GLM_MODEL` | `glm-4-alltools` | No | Model name |
| `PORT` | `8080` | No | Server port |
| `HOST` | `0.0.0.0` | No | Server host |
| `DEBUG` | `true` | No | Enable auto-reload |
| `DB_PATH` | `careloop.db` | No | SQLite database path |
| `SECRET_KEY` | *(built-in demo key)* | No | Session signing key |
| `DEMO_MODE` | `false` | No | Enable demo persona switching |

*App works fully in demo mode without an API key — perfect for evaluation.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Python 3.11, FastAPI | Async-native, auto-docs, type-safe |
| **Frontend** | Jinja2 SSR, vanilla CSS | Zero build step, fast load, accessible |
| **Database** | SQLite | Zero-config, portable, WAL mode |
| **AI** | GLM 5.1 via Z.ai API | OpenAI-compatible, thinking, function calling |
| **Styling** | Dark mode, glassmorphism | Premium healthcare aesthetic |
| **Container** | Docker + Cloud Run | One-command deploy |

---

## Project Structure

```
careloop/
├── app/
│   ├── main.py                 # FastAPI app + core routes
│   ├── database.py             # SQLite schema (17 tables)
│   ├── models.py               # Pydantic models
│   ├── services/
│   │   ├── glm_service.py      # 6 GLM workflows + streaming + tools
│   │   └── logging.py          # Structured logging (structlog)
│   ├── routers/
│   │   ├── auth.py             # Login, register, demo personas
│   │   ├── dashboard.py        # 4 role-based dashboards
│   │   ├── appointments.py     # Scheduling + prep checklists
│   │   ├── medications.py      # Med tracking + adherence + refills
│   │   ├── documents.py        # Upload + review + download
│   │   ├── messages.py         # Secure messaging with threads
│   │   ├── symptoms.py         # Symptom tracking + trends
│   │   ├── careteam.py         # Care team management
│   │   ├── notifications.py    # Notification system
│   │   ├── analytics.py        # Care coordination metrics
│   │   └── settings.py         # User preferences
│   ├── middleware/
│   │   ├── auth.py             # RBAC, sessions, bcrypt, audit
│   │   └── csrf.py             # CSRF protection
│   ├── utils/
│   │   ├── validation.py       # Input sanitization + validation
│   │   └── countdown.py        # Appointment countdown timers
│   ├── templates/              # 34 Jinja2 HTML templates
│   └── static/
│       └── style.css           # Dark-mode premium styles (1400+ lines)
├── tests/
│   └── test_glm_flow.py        # Integration + unit tests
├── seed.py                     # Demo data (3 patients, 10 encounters)
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Testing

```bash
pip install pytest pytest-asyncio
python3 -m pytest tests/ -v
```

Tests cover:
- JSON extraction from various GLM response formats
- Mock analysis generation with required fields
- Full care analysis flow with database persistence
- Edge cases (no encounters, invalid patients)
- Encounter summarization
- Care plan generation
- Trend detection
- Patient Q&A

---

## AI Transparency & Responsible AI

Every GLM analysis includes a transparency panel showing:
- The exact system prompt sent to GLM 5.1
- The full user context assembled from encounters
- The raw, unmodified GLM response
- Token usage and estimated cost

This demonstrates responsible AI practices and lets evaluators inspect exactly how GLM 5.1 is being used.

---

## GLM 5.1 Integration Deep Dive

### Streaming with Thinking
```python
async for chunk in stream_glm(messages, system_prompt, tools=True):
    if chunk.event == StreamEventType.THINKING:
        # Display GLM's chain-of-thought in real-time
    elif chunk.event == StreamEventType.CONTENT:
        # Stream structured output
    elif chunk.event == StreamEventType.TOOL_CALL:
        # Execute function calls autonomously
```

### Function Calling (4 Tools)
1. **create_task** — Creates real tasks in the database
2. **schedule_reminder** — Schedules patient/provider notifications
3. **send_message** — Sends messages between care team members
4. **get_patient_history** — Retrieves full context for informed decisions

### Usage Tracking
Every API call records prompt/completion tokens and estimated cost for monitoring.

---

## Key Design Decisions

- **Server-rendered (Jinja2)** over SPA: Faster load, better accessibility, no build step
- **SQLite** over PostgreSQL: Zero-config, portable demo, WAL for concurrency
- **Raw SQL** over ORM: Maximum control, transparent queries, easier to audit
- **SSE streaming** over WebSocket: Simpler, works with proxies, auto-reconnect
- **Cookie sessions** over JWT: Better security for server-rendered apps

---

Built for the [Build with GLM 5.1 Challenge](https://build-with-glm-5-1-challenge.devpost.com/) by Z.AI
