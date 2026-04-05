# CareLoop

> **AI that closes the care coordination gap** — Powered by GLM 5.1

CareLoop is an AI-powered care coordination platform that bridges the communication gap between healthcare providers and patients. Using GLM 5.1's advanced reasoning capabilities, CareLoop analyzes clinical encounters and patient check-ins to produce structured care summaries, actionable tasks, and risk assessments.

## 🎯 What It Does

1. **Provider submits** a clinical update about a patient
2. **Patient submits** a self-check-in describing how they feel
3. **GLM 5.1 analyzes** all encounters and produces:
   - A clinical summary for the care team
   - A patient-friendly summary in plain language
   - Actionable follow-up tasks with owners and due windows
   - Risk flags with severity levels
4. **Timeline displays** everything in a unified, easy-to-scan view
5. **Patient can ask** GLM 5.1 follow-up questions about their care
6. **Trend detection** compares analyses over time to spot patterns

## 🤖 GLM 5.1 Usage (3 Distinct Call Types)

CareLoop demonstrates deep GLM 5.1 integration with three separate AI workflows:

| Call Type | Purpose | What GLM Does |
|-----------|---------|---------------|
| **Care Analysis** | Aggregate encounters → structured output | Produces JSON with summaries, tasks, and risk flags |
| **Trend Detection** | Compare analyses over time | Identifies patterns, trajectory direction, and changes |
| **Patient Q&A** | Answer patient questions from context | Provides empathetic, context-aware answers |

## 🖥️ Tech Stack

- **Backend**: Python 3.11, FastAPI
- **Frontend**: Jinja2 server-rendered templates
- **Database**: SQLite (zero-config, portable)
- **AI Model**: GLM 5.1 via Z.ai API (OpenAI-compatible)
- **Styling**: Vanilla CSS with dark mode, glassmorphism
- **Container**: Docker

## 🚀 Quick Start

### Local Development

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/careloop.git
cd careloop

# Install dependencies
pip install -r requirements.txt

# Set up environment (optional — works without API key in demo mode)
cp .env.example .env
# Edit .env and add your GLM_API_KEY

# Seed demo data
python3 seed.py

# Run
python3 -m uvicorn app.main:app --reload --port 8080
```

Visit http://localhost:8080

### Docker

```bash
docker build -t careloop .
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

## ⚙️ Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GLM_API_KEY` | — | No* | Z.ai API key. Without it, app uses realistic mock data |
| `GLM_API_URL` | `https://api.z.ai/api/paas/v4/chat/completions` | No | GLM API endpoint |
| `GLM_MODEL` | `glm-5.1` | No | Model name |
| `PORT` | `8080` | No | Server port |
| `DEBUG` | `true` | No | Enable auto-reload |

*App works in demo mode without an API key — perfect for evaluation.

## 🔍 AI Transparency

Every GLM analysis includes a transparency panel showing:
- The exact system prompt sent to GLM 5.1
- The full user context assembled from encounters
- The raw, unmodified GLM response

This demonstrates responsible AI practices and lets evaluators inspect exactly how GLM 5.1 is being used.

## 📁 Project Structure

```
careloop/
├── app/
│   ├── main.py              # FastAPI app + all routes
│   ├── database.py          # SQLite setup + schema
│   ├── models.py            # Pydantic models
│   ├── services/
│   │   └── glm_service.py   # All 3 GLM call types
│   ├── templates/           # Jinja2 HTML templates
│   └── static/
│       └── style.css        # Dark-mode premium styles
├── tests/
│   └── test_glm_flow.py     # Integration tests
├── seed.py                  # Demo data seeder
├── Dockerfile
├── requirements.txt
└── README.md
```

## 🧪 Testing

```bash
pip install pytest pytest-asyncio
python3 -m pytest tests/ -v
```

## 📄 License

MIT

---

Built for the [Build with GLM 5.1 Challenge](https://build-with-glm-5-1-challenge.devpost.com/) by Z.AI
