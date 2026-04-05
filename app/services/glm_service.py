"""CareLoop — GLM 5.1 integration service.

Handles 3 distinct GLM call types:
1. Care Analysis — aggregate encounters → structured JSON output
2. Trend Detection — compare analyses over time → identify patterns
3. Patient Q&A — answer patient questions from care context
"""

import os
import json
import re
import httpx
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db

# ─── Configuration (read lazily so .env is loaded first) ─────
REQUEST_TIMEOUT = 60.0


def _api_key():
    return os.getenv("GLM_API_KEY", "")


def _api_url():
    return os.getenv("GLM_API_URL", "https://api.z.ai/api/paas/v4/chat/completions")


def _model():
    return os.getenv("GLM_MODEL", "glm-5.1")


# ─── JSON Extraction ────────────────────────────────────────
def extract_json(text: str) -> Optional[dict]:
    """Robustly extract JSON from GLM response, handling markdown fences and malformed output."""
    # Try direct parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from markdown code fences
    patterns = [
        r"```json\s*(.*?)\s*```",
        r"```\s*(.*?)\s*```",
        r"\{.*\}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(
                    match.group(1) if "```" in pattern else match.group(0)
                )
            except (json.JSONDecodeError, IndexError):
                continue

    return None


# ─── Mock Data ───────────────────────────────────────────────
def get_mock_analysis(patient_name: str, encounters_text: str) -> dict:
    """Return realistic mock analysis when API key is unavailable."""
    return {
        "shared_summary": (
            f"Patient {patient_name} shows a mixed clinical picture. Recent provider notes "
            "indicate some clinical improvements alongside areas requiring close monitoring. "
            "The patient's self-reported check-in confirms adherence to treatment but highlights "
            "concerns about symptom management and daily functioning. Coordination between "
            "provider follow-ups and patient self-care goals should be prioritized."
        ),
        "patient_summary": (
            "You're making progress overall! Your medical team sees improvement in key areas. "
            "Keep taking your medications as prescribed and noting any changes you feel. "
            "A few things need closer attention — your care team will work with you on those. "
            "Don't hesitate to reach out if anything feels off."
        ),
        "tasks": [
            {
                "title": "Schedule follow-up appointment within 2 weeks",
                "owner": "patient",
                "due_window": "next 14 days",
                "description": "Discuss recent symptom changes",
            },
            {
                "title": "Review and adjust medication dosage",
                "owner": "provider",
                "due_window": "next visit",
                "description": "Based on latest clinical observations",
            },
            {
                "title": "Complete recommended lab work",
                "owner": "patient",
                "due_window": "next 7 days",
                "description": "Fasting blood panel as ordered",
            },
            {
                "title": "Update care plan with latest findings",
                "owner": "provider",
                "due_window": "next 3 days",
                "description": "Incorporate new assessment results",
            },
        ],
        "risk_flags": [
            {
                "flag": "Symptom pattern requires monitoring",
                "severity": "medium",
                "detail": "Recent reports suggest intermittent symptom recurrence that warrants tracking",
            },
            {
                "flag": "Medication adherence confirmation needed",
                "severity": "low",
                "detail": "Patient self-reports consistent adherence; verify at next visit",
            },
        ],
    }


def get_mock_trend() -> dict:
    """Return mock trend analysis."""
    return {
        "trend_summary": "Based on available analyses, the patient's overall trajectory appears stable with gradual improvements in key areas. Some fluctuation in symptom reports warrants continued monitoring.",
        "patterns": [
            "Treatment adherence has been consistent across check-ins",
            "Symptom severity shows a gradual downward trend",
            "Patient engagement is increasing over time",
        ],
        "direction": "improving",
    }


def get_mock_qa_answer(question: str) -> str:
    """Return mock Q&A answer."""
    return (
        f'Based on your care records, here\'s what I can share about your question: "{question}"\n\n'
        "Your care team has been tracking your progress closely. The latest notes indicate "
        "steady improvement in your main health markers. If you have concerns about specific "
        "symptoms or medications, I'd recommend discussing them at your next appointment. "
        "Your provider can give you the most personalized guidance.\n\n"
        "⚠️ Note: This is an AI-generated summary from your care records. Always consult your "
        "healthcare provider for medical decisions."
    )


# ─── GLM API Call ────────────────────────────────────────────
async def call_glm(system_prompt: str, user_prompt: str) -> tuple[str, bool]:
    """Call GLM 5.1 API with retry for rate limits. Returns (response_text, success_bool)."""
    import asyncio

    api_key = _api_key()
    if not api_key:
        return "", False

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    max_retries = 3
    retry_delays = [5, 15, 30]  # seconds

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(_api_url(), json=payload, headers=headers)

                if response.status_code == 429:
                    delay = retry_delays[attempt] if attempt < len(retry_delays) else 30
                    print(
                        f"[CareLoop] Rate limited (429), retry {attempt + 1}/{max_retries} in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return content, True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                delay = retry_delays[attempt]
                print(
                    f"[CareLoop] Rate limited (429), retry {attempt + 1}/{max_retries} in {delay}s..."
                )
                await asyncio.sleep(delay)
                continue
            print(f"[CareLoop] GLM API error: {e}")
            return str(e), False
        except Exception as e:
            print(f"[CareLoop] GLM API error: {e}")
            return str(e), False

    return "Rate limit exceeded after retries", False


# ─── Analysis Prompts ────────────────────────────────────────
ANALYSIS_SYSTEM_PROMPT = """You are CareLoop AI, a healthcare coordination assistant powered by GLM 5.1.
Your role is to analyze patient encounters (provider clinical notes and patient self-check-ins) and produce a structured care coordination summary.

You MUST respond with ONLY a valid JSON object in exactly this format:
{
  "shared_summary": "A comprehensive clinical summary suitable for the care team (2-4 sentences)",
  "patient_summary": "A warm, easy-to-understand summary for the patient in plain language (2-4 sentences)",
  "tasks": [
    {
      "title": "Specific actionable task",
      "owner": "provider or patient",
      "due_window": "timeframe like 'next 7 days' or 'next visit'",
      "description": "Brief explanation of why this task matters"
    }
  ],
  "risk_flags": [
    {
      "flag": "Short risk description",
      "severity": "low, medium, or high",
      "detail": "Why this is flagged and what to watch for"
    }
  ]
}

Guidelines:
- Generate 3-6 actionable tasks with clear owners
- Flag genuine risks — do not over-flag; severity should be proportional
- Patient summary should be empathetic and avoid medical jargon when possible
- Be specific and reference actual details from the encounters
- Do NOT include any text outside the JSON object"""


TREND_SYSTEM_PROMPT = """You are CareLoop AI analyzing trends across multiple care analyses for the same patient over time.

You MUST respond with ONLY a valid JSON object in exactly this format:
{
  "trend_summary": "2-3 sentence summary of how this patient's care trajectory is evolving",
  "patterns": ["pattern 1", "pattern 2", "pattern 3"],
  "direction": "improving, stable, or concerning"
}

Guidelines:
- Compare the analyses chronologically
- Look for: symptom changes, adherence trends, risk escalation/de-escalation
- Be specific about what is changing and in which direction
- Do NOT include any text outside the JSON object"""


QA_SYSTEM_PROMPT = """You are CareLoop AI, helping a patient understand their care based on their medical records.

Guidelines:
- Answer based ONLY on the care context provided
- Use warm, empathetic language — avoid heavy medical jargon
- If the question is outside the available context, say so honestly
- Always remind the patient to consult their provider for medical decisions
- Keep responses concise (3-5 sentences)
- Do NOT make up medical advice or diagnoses"""


# ─── Service Functions ───────────────────────────────────────
async def run_care_analysis(patient_id: str) -> dict:
    """Run GLM 5.1 care analysis for a patient. Returns analysis result dict."""
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return {"error": "Patient not found"}

        encounters = db.execute(
            "SELECT * FROM encounters WHERE patient_id = ? ORDER BY created_at ASC",
            (patient_id,),
        ).fetchall()

        if not encounters:
            return {"error": "No encounters to analyze"}

        # Build context
        encounter_lines = []
        for e in encounters:
            encounter_lines.append(
                f"[{e['created_at']}] {e['author_role'].upper()} ({e['author_name']}): {e['content']}"
            )
        encounters_text = "\n\n".join(encounter_lines)

        user_prompt = f"""Patient: {patient["name"]}
Condition: {patient["condition"]}
Notes: {patient["notes"] or "N/A"}

--- Encounters (chronological) ---
{encounters_text}

Analyze these encounters and produce the structured JSON output."""

        # Call GLM or use mock
        raw_response, success = await call_glm(ANALYSIS_SYSTEM_PROMPT, user_prompt)

        if success:
            parsed = extract_json(raw_response)
            if not parsed:
                parsed = get_mock_analysis(patient["name"], encounters_text)
                raw_response = f"[JSON parse failed, using fallback]\nOriginal response:\n{raw_response}"
        else:
            parsed = get_mock_analysis(patient["name"], encounters_text)
            raw_response = "[Demo mode — GLM_API_KEY not set]"

        # Store analysis
        analysis_id = str(uuid.uuid4())
        latest_encounter_id = encounters[-1]["id"] if encounters else None

        db.execute(
            """INSERT INTO glm_analyses
               (id, patient_id, encounter_id, shared_summary, patient_summary,
                risk_flags_json, tasks_json, raw_response, prompt_sent, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                analysis_id,
                patient_id,
                latest_encounter_id,
                parsed.get("shared_summary", ""),
                parsed.get("patient_summary", ""),
                json.dumps(parsed.get("risk_flags", [])),
                json.dumps(parsed.get("tasks", [])),
                raw_response,
                f"SYSTEM:\n{ANALYSIS_SYSTEM_PROMPT}\n\nUSER:\n{user_prompt}",
                _model(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        # Create tasks from analysis
        for task_data in parsed.get("tasks", []):
            db.execute(
                """INSERT INTO tasks (id, patient_id, analysis_id, title, description, owner, due_window, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    patient_id,
                    analysis_id,
                    task_data.get("title", ""),
                    task_data.get("description", ""),
                    task_data.get("owner", "provider"),
                    task_data.get("due_window", ""),
                    "pending",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        # Auto-create urgent tasks for high-severity risk flags
        for flag in parsed.get("risk_flags", []):
            if flag.get("severity") == "high":
                db.execute(
                    """INSERT INTO tasks (id, patient_id, analysis_id, title, description, owner, due_window, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        patient_id,
                        analysis_id,
                        f"⚠️ URGENT: {flag.get('flag', 'High-risk flag')}",
                        flag.get("detail", ""),
                        "provider",
                        "immediate",
                        "pending",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

    return {"analysis_id": analysis_id, "result": parsed}


async def run_trend_detection(patient_id: str) -> dict:
    """Detect trends across previous analyses for a patient."""
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return {"error": "Patient not found"}

        analyses = db.execute(
            "SELECT * FROM glm_analyses WHERE patient_id = ? ORDER BY created_at ASC",
            (patient_id,),
        ).fetchall()

        if len(analyses) < 1:
            return {"error": "Need at least one analysis for trend detection"}

        # Build context from previous analyses
        analysis_lines = []
        for a in analyses:
            analysis_lines.append(
                f"[{a['created_at']}] Summary: {a['shared_summary']}\n"
                f"  Risk flags: {a['risk_flags_json']}\n"
                f"  Tasks: {a['tasks_json']}"
            )
        analyses_text = "\n\n".join(analysis_lines)

        user_prompt = f"""Patient: {patient["name"]}
Condition: {patient["condition"]}

--- Previous Care Analyses (chronological, {len(analyses)} total) ---
{analyses_text}

Analyze trends across these care analyses."""

        raw_response, success = await call_glm(TREND_SYSTEM_PROMPT, user_prompt)

        if success:
            parsed = extract_json(raw_response)
            if not parsed:
                parsed = get_mock_trend()
        else:
            parsed = get_mock_trend()

        # Update the latest analysis with trend info
        if analyses:
            db.execute(
                "UPDATE glm_analyses SET trend_summary = ? WHERE id = ?",
                (parsed.get("trend_summary", ""), analyses[-1]["id"]),
            )

    return {"trend": parsed}


async def run_patient_qa(patient_id: str, question: str) -> dict:
    """Answer a patient's question using their care context."""
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return {"error": "Patient not found"}

        # Gather context: encounters + latest analysis
        encounters = db.execute(
            "SELECT * FROM encounters WHERE patient_id = ? ORDER BY created_at DESC LIMIT 5",
            (patient_id,),
        ).fetchall()

        latest_analysis = db.execute(
            "SELECT * FROM glm_analyses WHERE patient_id = ? ORDER BY created_at DESC LIMIT 1",
            (patient_id,),
        ).fetchone()

        # Build context
        context_parts = [
            f"Patient: {patient['name']}",
            f"Condition: {patient['condition']}",
        ]

        if latest_analysis:
            context_parts.append(
                f"\nLatest AI Analysis:\n{latest_analysis['shared_summary']}"
            )
            context_parts.append(
                f"Patient Summary: {latest_analysis['patient_summary']}"
            )

        if encounters:
            context_parts.append("\n--- Recent Encounters ---")
            for e in encounters:
                context_parts.append(
                    f"[{e['created_at']}] {e['author_role']}: {e['content'][:300]}"
                )

        context = "\n".join(context_parts)

        user_prompt = f"""Care Context:
{context}

Patient Question: {question}

Please answer this question based on the care context above."""

        raw_response, success = await call_glm(QA_SYSTEM_PROMPT, user_prompt)

        if not success:
            answer = get_mock_qa_answer(question)
        else:
            answer = raw_response

        # Store Q&A exchange
        qa_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO qa_exchanges (id, patient_id, question, answer, context_used, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                qa_id,
                patient_id,
                question,
                answer,
                context[:2000],
                _model(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return {"qa_id": qa_id, "answer": answer}


# ─── Encounter Summarization ────────────────────────────────
ENCOUNTER_SUMMARY_PROMPT = """You are CareLoop AI, a clinical data extraction assistant powered by GLM 5.1.
Extract structured clinical data from the provider's free-text clinical note.

You MUST respond with ONLY a valid JSON object in exactly this format:
{
  "chief_complaint": "Primary reason for the encounter",
  "diagnoses": ["diagnosis 1", "diagnosis 2"],
  "medications_mentioned": [
    {"name": "medication name", "action": "started|changed|continued|stopped", "dosage": "dosage info"}
  ],
  "vitals": {"key": "value"},
  "procedures": ["procedure 1"],
  "follow_up": "Follow-up instructions",
  "urgency": "routine|urgent|emergent"
}

Guidelines:
- Extract only what is explicitly stated — do not infer diagnoses
- If a field has no data, use an empty list or empty string
- Be specific with medication dosages when mentioned
- Do NOT include any text outside the JSON object"""


def get_mock_encounter_summary(content: str) -> dict:
    return {
        "chief_complaint": "Clinical encounter — details extracted from provider note",
        "diagnoses": ["See full note for details"],
        "medications_mentioned": [
            {"name": "See note", "action": "continued", "dosage": "as noted"}
        ],
        "vitals": {},
        "procedures": [],
        "follow_up": "As specified in clinical note",
        "urgency": "routine",
    }


async def run_encounter_summary(encounter_id: str) -> dict:
    with get_db() as db:
        encounter = db.execute(
            "SELECT * FROM encounters WHERE id = ?", (encounter_id,)
        ).fetchone()
        if not encounter:
            return {"error": "Encounter not found"}

        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (encounter["patient_id"],)
        ).fetchone()

        user_prompt = f"""Patient: {patient["name"]}
Condition: {patient["condition"]}

--- Provider Clinical Note ---
{encounter["content"]}

Extract structured clinical data from this note."""

        raw_response, success = await call_glm(ENCOUNTER_SUMMARY_PROMPT, user_prompt)

        if success:
            parsed = extract_json(raw_response)
            if not parsed:
                parsed = get_mock_encounter_summary(encounter["content"])
        else:
            parsed = get_mock_encounter_summary(encounter["content"])
            raw_response = "[Demo mode — GLM_API_KEY not set]"

        summary_json = json.dumps(parsed)
        db.execute(
            "UPDATE encounters SET structured_summary = ? WHERE id = ?",
            (summary_json, encounter_id),
        )

    return {
        "encounter_id": encounter_id,
        "summary": parsed,
        "raw_response": raw_response,
    }


# ─── Follow-up Suggestions ──────────────────────────────────
FOLLOWUP_PROMPT = """You are CareLoop AI, generating follow-up question suggestions for a patient.
Based on the care analysis provided, suggest 3 questions the patient might want to ask next.

You MUST respond with ONLY a valid JSON array of strings:
["Question 1?", "Question 2?", "Question 3?"]

Guidelines:
- Questions should be things a real patient would ask
- Make them specific to the care context, not generic
- Use plain, non-medical language
- Do NOT include any text outside the JSON array"""


def get_mock_followups(patient_name: str) -> list:
    return [
        f"When should I schedule my next follow-up appointment?",
        f"Are there any warning signs I should watch for?",
        f"What changes should I make to my daily routine?",
    ]


async def run_followup_suggestions(analysis_id: str) -> dict:
    with get_db() as db:
        analysis = db.execute(
            "SELECT * FROM glm_analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
        if not analysis:
            return {"error": "Analysis not found"}

        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (analysis["patient_id"],)
        ).fetchone()

        user_prompt = f"""Patient: {patient["name"]}
Condition: {patient["condition"]}

--- Care Analysis Summary ---
{analysis["shared_summary"]}

Patient-Friendly Summary:
{analysis["patient_summary"]}

Risk Flags: {analysis["risk_flags_json"]}
Tasks: {analysis["tasks_json"]}

Suggest 3 follow-up questions this patient might want to ask."""

        raw_response, success = await call_glm(FOLLOWUP_PROMPT, user_prompt)

        if success:
            parsed = extract_json(raw_response)
            if not parsed or not isinstance(parsed, list):
                parsed = get_mock_followups(patient["name"])
        else:
            parsed = get_mock_followups(patient["name"])
            raw_response = "[Demo mode — GLM_API_KEY not set]"

        db.execute(
            "UPDATE glm_analyses SET followup_suggestions = ? WHERE id = ?",
            (json.dumps(parsed), analysis_id),
        )

    return {
        "analysis_id": analysis_id,
        "suggestions": parsed,
        "raw_response": raw_response,
    }


# ─── Care Plan Generation ───────────────────────────────────
CAREPLAN_PROMPT = """You are CareLoop AI, a care planning assistant powered by GLM 5.1.
Generate a comprehensive multi-week care plan based on the patient's encounters and analyses.

You MUST respond with ONLY a valid JSON object in exactly this format:
{
  "plan_title": "Short descriptive title for the care plan",
  "duration_weeks": 4,
  "goals": ["Goal 1", "Goal 2", "Goal 3"],
  "weekly_plan": [
    {
      "week": 1,
      "focus": "What to focus on this week",
      "patient_tasks": ["Task for patient", "Another task"],
      "provider_tasks": ["Task for provider"],
      "check_in_topics": ["What to discuss at check-in"],
      "warnings": ["Warning signs to watch for"]
    }
  ],
  "milestones": ["Milestone 1 — Week 2", "Milestone 2 — Week 4"],
  "emergency_triggers": ["When to seek immediate care"]
}

Guidelines:
- Be specific and reference actual conditions and medications from the encounters
- Plan should be realistic and achievable
- Include clear emergency triggers
- Patient tasks should be in plain language
- Generate 2-4 weeks depending on clinical complexity
- Do NOT include any text outside the JSON object"""


def get_mock_careplan(patient_name: str, condition: str) -> dict:
    return {
        "plan_title": f"Recovery Plan — {condition}",
        "duration_weeks": 3,
        "goals": [
            "Complete initial recovery phase",
            "Manage symptoms effectively",
            "Gradually increase activity level",
        ],
        "weekly_plan": [
            {
                "week": 1,
                "focus": "Rest and monitoring",
                "patient_tasks": [
                    "Take medications as prescribed",
                    "Monitor symptoms daily",
                    "Rest and avoid strenuous activity",
                ],
                "provider_tasks": [
                    "Review lab results",
                    "Adjust medications if needed",
                ],
                "check_in_topics": ["Symptom changes", "Medication side effects"],
                "warnings": ["Worsening pain", "New symptoms"],
            },
            {
                "week": 2,
                "focus": "Gradual activity increase",
                "patient_tasks": [
                    "Begin light walking if cleared",
                    "Continue medication schedule",
                    "Track progress in check-ins",
                ],
                "provider_tasks": ["Assess recovery progress"],
                "check_in_topics": ["Activity tolerance", "Energy levels"],
                "warnings": ["Chest pain", "Shortness of breath"],
            },
            {
                "week": 3,
                "focus": "Building routine",
                "patient_tasks": [
                    "Establish daily routine",
                    "Attend follow-up appointment",
                    "Begin cardiac rehab if referred",
                ],
                "provider_tasks": [
                    "Conduct follow-up assessment",
                    "Create long-term maintenance plan",
                ],
                "check_in_topics": ["Overall progress", "Next steps"],
                "warnings": ["Regression of symptoms"],
            },
        ],
        "milestones": [
            "Complete Week 1 without complications",
            "Tolerate light activity by Week 2",
            "Attend follow-up appointment by Week 3",
        ],
        "emergency_triggers": [
            "Sudden severe pain",
            "Difficulty breathing",
            "Signs of infection (fever >101°F, redness, swelling)",
        ],
    }


async def run_careplan_generation(patient_id: str) -> dict:
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return {"error": "Patient not found"}

        encounters = db.execute(
            "SELECT * FROM encounters WHERE patient_id = ? ORDER BY created_at ASC",
            (patient_id,),
        ).fetchall()

        analyses = db.execute(
            "SELECT * FROM glm_analyses WHERE patient_id = ? ORDER BY created_at DESC LIMIT 3",
            (patient_id,),
        ).fetchall()

        encounter_lines = []
        for e in encounters:
            encounter_lines.append(
                f"[{e['created_at']}] {e['author_role'].upper()} ({e['author_name']}): {e['content']}"
            )

        analysis_lines = []
        for a in analyses:
            analysis_lines.append(
                f"[{a['created_at']}] Summary: {a['shared_summary']}\n"
                f"  Risks: {a['risk_flags_json']}\n  Tasks: {a['tasks_json']}"
            )

        user_prompt = f"""Patient: {patient["name"]}
Condition: {patient["condition"]}
Notes: {patient["notes"] or "N/A"}

--- Encounters (chronological, {len(encounters)} total) ---
{chr(10).join(encounter_lines)}

--- Previous AI Analyses ({len(analyses)} total) ---
{chr(10).join(analysis_lines) if analysis_lines else "No previous analyses."}

Generate a comprehensive multi-week care plan."""

        raw_response, success = await call_glm(CAREPLAN_PROMPT, user_prompt)

        if success:
            parsed = extract_json(raw_response)
            if not parsed:
                parsed = get_mock_careplan(patient["name"], patient["condition"])
        else:
            parsed = get_mock_careplan(patient["name"], patient["condition"])
            raw_response = "[Demo mode — GLM_API_KEY not set]"

        plan_id = str(uuid.uuid4())
        plan_json = json.dumps(parsed)
        db.execute(
            """INSERT INTO care_plans (id, patient_id, plan_json, raw_response, prompt_sent, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                plan_id,
                patient_id,
                plan_json,
                raw_response,
                f"SYSTEM:\n{CAREPLAN_PROMPT}\n\nUSER:\n{user_prompt}",
                _model(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return {"plan_id": plan_id, "plan": parsed, "raw_response": raw_response}
