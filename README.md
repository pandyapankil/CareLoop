# CareLoop

> **AI that closes the care coordination gap** — Powered by GLM 5.1

CareLoop is an AI-powered care coordination platform that bridges the communication gap between healthcare providers and patients. Using GLM 5.1's advanced reasoning capabilities, CareLoop analyzes clinical encounters and patient check-ins to produce structured care summaries, actionable tasks, risk assessments, and personalized care plans.

## Demo - Try It Now (No API Key Required!)

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

## ✨ GLM 5.1 Features Demonstrated

CareLoop showcases **6 distinct GLM 5.1 capabilities**:

| Feature | Description | GLM Capability |
|---------|-------------|----------------|
| **Care Analysis** | Analyzes encounters → structured summaries, tasks, risk flags | Function calling + JSON output |
| **Trend Detection** | Compares analyses over time to spot patterns | Long-horizon reasoning |
| **Patient Q&A** | Context-aware answers to patient questions | Conversational AI |
| **Encounter Summarization** | Extracts structured data from free-text notes | Information extraction |
| **Care Plan Generation** | Creates multi-week personalized care plans | Planning + function calling |
| **Real-time Thinking** | Watch GLM reason through the problem | Reasoning content streaming |

### What Makes This Special for GLM 5.1

- **Thinking Display**: Every AI call shows GLM's reasoning in real-time
- **Function Calling**: GLM autonomously creates tasks, schedules reminders, sends messages
- **Transparency Panel**: See the exact prompts sent and responses received
- **Toast Notifications**: Visual feedback as GLM takes actions

## 🚀 Quick Start

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
  --set-env-vars GLM_API_KEY=$GLM_API_KEY,GLM_MODEL=glm-5.1
```

## 📱 Demo Walkthrough

### 1. Dashboard
On the home page, you'll see:
- 3 demo patients with clinical histories
- Stats showing encounters and AI analyses
- Quick access to all GLM features

### 2. Patient Timeline
Click any patient to see:
- Chronological timeline of all encounters
- Provider updates and patient check-ins
- AI analyses with structured outputs

### 3. Run GLM 5.1 Analysis
Click "Run AI Analysis" and watch:
- Loading overlay with thinking indicator
- Real-time reasoning display
- Toast notifications as tasks are created
- Structured summaries, risk flags, and tasks

### 4. Ask GLM Questions
Go to "Ask CareLoop AI" to:
- Type a question or use voice input
- Get context-aware responses
- See previous Q&A history

### 5. Generate Care Plans
Click "Generate Care Plan" for:
- Multi-week personalized plans
- Weekly tasks for patient and provider
- Goals, milestones, and emergency triggers

### 6. Detect Trends
Click "Detect Trends" to:
- Compare multiple analyses over time
- Identify patterns and trajectory
- See directional indicators

### 7. View Transparency
Every AI response includes:
- Expandable transparency panel
- Exact prompts sent to GLM
- Raw AI responses
- Model and timing info

## 📸 Screenshot Ideas for Submission

1. **Home Dashboard** — Show the 3 patients and feature cards
2. **Patient Timeline** — Show encounters with AI analyses
3. **AI Analysis Running** — Capture the thinking display + toasts
4. **Analysis Results** — Show summaries, tasks, risk flags
5. **Patient Q&A** — Show voice input and response
6. **Care Plan** — Show multi-week plan with goals
7. **Trend Detection** — Show pattern analysis
8. **Transparency Panel** — Show prompt + raw response

## ⚙️ Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GLM_API_KEY` | — | No* | Z.ai API key. Without it, app uses realistic mock data |
| `GLM_API_URL` | `https://api.z.ai/api/paas/v4/chat/completions` | No | GLM API endpoint |
| `GLM_MODEL` | `glm-5.1` | No | Model name |
| `PORT` | `8080` | No | Server port |
| `DEBUG` | `true` | No | Enable auto-reload |

*App works in demo mode without an API key — perfect for evaluation.

## 🖥️ Tech Stack

- **Backend**: Python 3.11, FastAPI
- **Frontend**: Jinja2 server-rendered templates
- **Database**: SQLite (zero-config, portable)
- **AI Model**: GLM 5.1 via Z.ai API (OpenAI-compatible)
- **Styling**: Vanilla CSS with dark mode, glassmorphism
- **Container**: Docker

## 📁 Project Structure

```
careloop/
├── app/
│   ├── main.py              # FastAPI app + all routes
│   ├── database.py          # SQLite setup + schema
│   ├── models.py            # Pydantic models
│   ├── services/
│   │   └── glm_service.py   # All 6 GLM call types
│   ├── templates/           # 35+ Jinja2 HTML templates
│   └── static/
│       └── style.css        # Dark-mode premium styles
├── seed.py                  # Demo data seeder (3 patients)
├── requirements.txt
├── Dockerfile
└── README.md
```

## 🧪 Testing

```bash
pip install pytest pytest-asyncio
python3 -m pytest tests/ -v
```

## 🔍 AI Transparency

Every GLM analysis includes a transparency panel showing:
- The exact system prompt sent to GLM 5.1
- The full user context assembled from encounters
- The raw, unmodified GLM response

This demonstrates responsible AI practices and lets evaluators inspect exactly how GLM 5.1 is being used.

---

Built for the [Build with GLM 5.1 Challenge](https://build-with-glm-5-1-challenge.devpost.com/) by Z.AI
