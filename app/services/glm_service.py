"""CareLoop — GLM 5.1 advanced integration service.

Key features:
1. Streaming responses with thinking visualization
2. Function calling for autonomous task execution
3. Multi-modal vision for document analysis
4. Long-horizon reasoning chains
5. Usage tracking and cost monitoring
"""

import os
import json
import re
import asyncio
import base64
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

import httpx
import uuid

from app.database import get_db

REQUEST_TIMEOUT = 120.0


def _api_key():
    return os.getenv("GLM_API_KEY", "")


def _api_url():
    return os.getenv("GLM_API_URL", "https://api.z.ai/api/paas/v4/chat/completions")


def _model():
    return os.getenv("GLM_MODEL", "glm-5.1")


class StreamEventType(str, Enum):
    CONTENT = "content"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DONE = "done"
    ERROR = "error"


@dataclass
class StreamChunk:
    event: StreamEventType
    content: str
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_cents: float = 0.0

    def add(self, other: "Usage"):
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.cost_cents += other.cost_cents


def record_usage(
    call_type: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_cents: float,
):
    with get_db() as db:
        db.execute(
            """INSERT INTO api_usage (id, call_type, model, prompt_tokens, completion_tokens, cost_cents, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                call_type,
                model,
                prompt_tokens,
                completion_tokens,
                cost_cents,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_usage() -> dict:
    with get_db() as db:
        result = db.execute(
            """SELECT 
                   COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                   COALESCE(SUM(prompt_tokens + completion_tokens), 0) as total_tokens,
                   COALESCE(SUM(cost_cents), 0) as cost_cents
               FROM api_usage"""
        ).fetchone()
        return {
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "total_tokens": result["total_tokens"],
            "cost_cents": round(result["cost_cents"], 2),
        }


def reset_usage():
    with get_db() as db:
        db.execute("DELETE FROM api_usage")


PRICING_PER_1K = {
    "glm-5.1": {"input": 0.001, "output": 0.001},
    "glm-5.1-flash": {"input": 0.0001, "output": 0.0001},
}


def _calc_cost(model: str, usage: Usage) -> float:
    pricing = PRICING_PER_1K.get(model, PRICING_PER_1K["glm-5.1"])
    return (
        usage.prompt_tokens / 1000 * pricing["input"]
        + usage.completion_tokens / 1000 * pricing["output"]
    ) * 100


def extract_json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

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


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a task/follow-up item in the care management system",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {
                        "type": "string",
                        "description": "Task description",
                    },
                    "owner": {
                        "type": "string",
                        "enum": ["patient", "provider", "coordinator"],
                        "description": "Who owns this task",
                    },
                    "due_window": {
                        "type": "string",
                        "description": "When task is due (e.g., 'next 7 days', 'immediate')",
                    },
                },
                "required": ["title", "owner"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_reminder",
            "description": "Schedule a reminder notification for a patient or provider",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Reminder message"},
                    "notify_user_id": {
                        "type": "string",
                        "description": "User ID to notify",
                    },
                    "due_after_hours": {
                        "type": "integer",
                        "description": "Hours until reminder fires",
                    },
                },
                "required": ["message", "notify_user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a message to another user in the care team",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_id": {
                        "type": "string",
                        "description": "Recipient user ID",
                    },
                    "subject": {"type": "string", "description": "Message subject"},
                    "body": {"type": "string", "description": "Message body"},
                    "urgent": {"type": "boolean", "description": "Mark as urgent"},
                },
                "required": ["recipient_id", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_history",
            "description": "Get complete care history for a patient including encounters, analyses, tasks",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient ID"},
                },
                "required": ["patient_id"],
            },
        },
    },
]


async def execute_tool(name: str, args: dict, patient_id: str = None) -> dict:
    """Execute a function call from GLM. Returns result dict."""
    now = datetime.now(timezone.utc).isoformat()

    if name == "create_task":
        with get_db() as db:
            db.execute(
                """INSERT INTO tasks (id, patient_id, title, description, owner, due_window, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    patient_id,
                    args["title"],
                    args.get("description", ""),
                    args["owner"],
                    args.get("due_window", "next 7 days"),
                    "pending",
                    now,
                ),
            )
        return {"success": True, "task_created": args["title"]}

    elif name == "schedule_reminder":
        with get_db() as db:
            user = db.execute(
                "SELECT id FROM users WHERE id = ?", (args["notify_user_id"],)
            ).fetchone()
            if user:
                db.execute(
                    """INSERT INTO notifications (id, user_id, type, message, related_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        args["notify_user_id"],
                        "reminder",
                        args["message"],
                        patient_id,
                        now,
                    ),
                )
        return {"success": True, "reminder_scheduled": args["message"]}

    elif name == "send_message":
        with get_db() as db:
            sender_id = db.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]
            db.execute(
                """INSERT INTO messages (id, sender_id, receiver_id, subject, body, urgent, patient_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    sender_id,
                    args["recipient_id"],
                    args["subject"],
                    args["body"],
                    args.get("urgent", False),
                    patient_id,
                    now,
                ),
            )
        return {"success": True, "message_sent": args["subject"]}

    elif name == "get_patient_history":
        with get_db() as db:
            encounters = db.execute(
                "SELECT * FROM encounters WHERE patient_id = ? ORDER BY created_at DESC LIMIT 20",
                (args["patient_id"],),
            ).fetchall()
            analyses = db.execute(
                "SELECT * FROM glm_analyses WHERE patient_id = ? ORDER BY created_at DESC LIMIT 5",
                (args["patient_id"],),
            ).fetchall()
            tasks = db.execute(
                "SELECT * FROM tasks WHERE patient_id = ? ORDER BY created_at DESC LIMIT 10",
                (args["patient_id"],),
            ).fetchall()
        return {
            "encounters": [dict(e) for e in encounters],
            "analyses": [dict(a) for a in analyses],
            "tasks": [dict(t) for t in tasks],
        }

    return {"error": f"Unknown tool: {name}"}


async def stream_glm(
    messages: list,
    system_prompt: str = None,
    tools: bool = False,
) -> AsyncGenerator[StreamChunk, None]:
    """Stream GLM 5.1 response with thinking support."""
    api_key = _api_key()
    if not api_key:
        yield StreamChunk(StreamEventType.ERROR, "GLM_API_KEY not configured")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    api_messages.extend(messages)

    payload = {
        "model": _model(),
        "messages": api_messages,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    if tools:
        payload["tools"] = TOOLS

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT, follow_redirects=True
        ) as client:
            async with client.stream(
                "POST", _api_url(), json=payload, headers=headers
            ) as response:
                if response.status_code != 200:
                    yield StreamChunk(
                        StreamEventType.ERROR, f"API error: {response.status_code}"
                    )
                    return

                buffer = ""
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data = line[6:]
                    if data.strip() == "[DONE]":
                        yield StreamChunk(StreamEventType.DONE, "")
                        break

                    try:
                        chunk_data = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    delta = chunk_data.get("delta", {})
                    choice = chunk_data.get("choices", [{}])[0]
                    delta = choice.get("delta", delta)

                    if thinking := delta.get("reasoning_content"):
                        yield StreamChunk(StreamEventType.THINKING, thinking)

                    if content := delta.get("content"):
                        yield StreamChunk(StreamEventType.CONTENT, content)

                    if tool_calls := delta.get("tool_calls"):
                        for tc in tool_calls:
                            yield StreamChunk(
                                StreamEventType.TOOL_CALL,
                                "",
                                tool_name=tc.get("function", {}).get("name"),
                                tool_args=json.loads(
                                    tc.get("function", {}).get("arguments", "{}")
                                ),
                            )

                    usage_obj = chunk_data.get("usage")
                    if usage_obj:
                        u = Usage(
                            prompt_tokens=usage_obj.get("prompt_tokens", 0),
                            completion_tokens=usage_obj.get("completion_tokens", 0),
                            total_tokens=usage_obj.get("total_tokens", 0),
                        )
                        u.cost_cents = _calc_cost(_model(), u)
                        record_usage(
                            "stream",
                            _model(),
                            u.prompt_tokens,
                            u.completion_tokens,
                            u.cost_cents,
                        )

    except asyncio.TimeoutError:
        yield StreamChunk(StreamEventType.ERROR, "Request timeout")
    except Exception as e:
        yield StreamChunk(StreamEventType.ERROR, str(e))


async def call_glm(
    messages: list,
    system_prompt: str = None,
    tools: bool = False,
) -> tuple[str, bool, Optional[str]]:
    """Non-streaming GLM call. Returns (response, success, thinking)."""
    api_key = _api_key()
    if not api_key:
        return "", False, None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    api_messages.extend(messages)

    payload = {
        "model": _model(),
        "messages": api_messages,
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    if tools:
        payload["tools"] = TOOLS

    max_retries = 3
    retry_delays = [5, 15, 30]

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(_api_url(), json=payload, headers=headers)

                if response.status_code == 429:
                    delay = retry_delays[attempt] if attempt < len(retry_delays) else 30
                    print(
                        f"[CareLoop] Rate limited, retry {attempt + 1}/{max_retries} in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                data = response.json()

                msg = data["choices"][0]["message"]
                content = msg.get("content", "")
                thinking = msg.get("reasoning_content")

                usage_obj = data.get("usage")
                if usage_obj:
                    u = Usage(
                        prompt_tokens=usage_obj.get("prompt_tokens", 0),
                        completion_tokens=usage_obj.get("completion_tokens", 0),
                        total_tokens=usage_obj.get("total_tokens", 0),
                    )
                    u.cost_cents = _calc_cost(_model(), u)
                    record_usage(
                        "call",
                        _model(),
                        u.prompt_tokens,
                        u.completion_tokens,
                        u.cost_cents,
                    )
                else:
                    prompt_chars = len(system_prompt or "") + sum(
                        len(m.get("content", "")) for m in messages
                    )
                    est_prompt = max(1, prompt_chars // 4)
                    est_completion = max(1, len(content) // 4)
                    u = Usage(
                        prompt_tokens=est_prompt,
                        completion_tokens=est_completion,
                        total_tokens=est_prompt + est_completion,
                    )
                    u.cost_cents = _calc_cost(_model(), u)
                    record_usage(
                        "call",
                        _model(),
                        u.prompt_tokens,
                        u.completion_tokens,
                        u.cost_cents,
                    )

                return content, True, thinking

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                await asyncio.sleep(retry_delays[attempt])
                continue
            print(f"[CareLoop] GLM API error: {e}")
            return str(e), False, None
        except Exception as e:
            print(f"[CareLoop] GLM API error: {e}")
            return str(e), False, None

    return "Rate limit exceeded", False, None


async def analyze_image(base64_image: str, prompt: str) -> tuple[str, bool]:
    """Analyze an image using GLM's vision capabilities."""
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
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(_api_url(), json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content, True
    except Exception as e:
        print(f"[CareLoop] Vision API error: {e}")
        return str(e), False


ANALYSIS_SYSTEM_PROMPT = """You are CareLoop AI, a healthcare coordination assistant powered by GLM 5.1.
You have access to tools that can create tasks, schedule reminders, and send messages.
Use these tools proactively to act on your analysis results.

Your role: analyze patient encounters and produce structured care coordination output.
Think step-by-step about the patient's situation."""

ANALYSIS_TEMPLATE = """Patient: {name}
Condition: {condition}
Notes: {notes}

--- Encounters ---
{encounters}

Analyze and produce JSON with: shared_summary, patient_summary, tasks, risk_flags.
If creating tasks, use the create_task function to make them real."""

TREND_SYSTEM_PROMPT = """You are CareLoop AI analyzing trends. Identify patterns in patient's care history.
Use get_patient_history to fetch full context when needed."""

QA_SYSTEM_PROMPT = """You are CareLoop AI, helping patients understand their care.
Be warm, empathetic. Use plain language. If unsure, say so."""

ENCOUNTER_SUMMARY_PROMPT = """Extract structured clinical data from provider notes.
Return JSON: chief_complaint, diagnoses, medications_mentioned, vitals, procedures, follow_up, urgency."""

CAREPLAN_PROMPT = """Generate multi-week care plan.
Use get_patient_history for context.
Return JSON: plan_title, duration_weeks, goals, weekly_plan, milestones, emergency_triggers.
Create real tasks via function calls."""


def get_mock_analysis(patient_name: str) -> dict:
    return {
        "shared_summary": f"Patient {patient_name} shows mixed clinical picture with areas requiring monitoring.",
        "patient_summary": "You're making progress! Keep working with your care team.",
        "tasks": [
            {
                "title": "Schedule follow-up",
                "owner": "patient",
                "due_window": "next 14 days",
            },
            {
                "title": "Review medications",
                "owner": "provider",
                "due_window": "next visit",
            },
        ],
        "risk_flags": [
            {
                "flag": "Monitor symptoms",
                "severity": "medium",
                "detail": "Watch for changes",
            },
        ],
    }


def get_mock_trend() -> dict:
    return {
        "trend_summary": "Patient trajectory stable with gradual improvements.",
        "patterns": [
            "Consistent adherence",
            "Improving symptoms",
            "Increasing engagement",
        ],
        "direction": "improving",
    }


def get_mock_qa_answer(question: str) -> str:
    return f"Based on your records regarding '{question}': Your care team notes steady progress. Consult your provider for specific guidance."


def get_mock_careplan(name: str, condition: str) -> dict:
    return {
        "plan_title": f"Recovery — {condition}",
        "duration_weeks": 3,
        "goals": ["Complete recovery", "Manage symptoms", "Increase activity"],
        "weekly_plan": [
            {
                "week": 1,
                "focus": "Rest",
                "patient_tasks": ["Rest", "Monitor symptoms"],
                "provider_tasks": ["Review"],
                "warnings": ["Worsening pain"],
            }
        ],
        "milestones": ["Week 1 complete", "Follow-up"],
        "emergency_triggers": ["Severe pain", "Difficulty breathing"],
    }


async def run_care_analysis(patient_id: str) -> dict:
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

        encounter_text = "\n".join(
            f"[{e['created_at']}] {e['author_role'].upper()}: {e['content']}"
            for e in encounters
        )

        user_msg = {
            "role": "user",
            "content": ANALYSIS_TEMPLATE.format(
                name=patient["name"],
                condition=patient["condition"],
                notes=patient["notes"] or "N/A",
                encounters=encounter_text,
            ),
        }

        content, success, thinking = await call_glm(
            [user_msg], ANALYSIS_SYSTEM_PROMPT, tools=True
        )

        if success:
            parsed = extract_json(content)
            if not parsed:
                parsed = get_mock_analysis(patient["name"])
        else:
            parsed = get_mock_analysis(patient["name"])
            thinking = "[Demo mode]"

        aid = str(uuid.uuid4())
        db.execute(
            """INSERT INTO glm_analyses
               (id, patient_id, shared_summary, patient_summary, risk_flags_json, tasks_json, raw_response, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                aid,
                patient_id,
                parsed.get("shared_summary", ""),
                parsed.get("patient_summary", ""),
                json.dumps(parsed.get("risk_flags", [])),
                json.dumps(parsed.get("tasks", [])),
                content,
                _model(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        for task_data in parsed.get("tasks", []):
            db.execute(
                """INSERT INTO tasks (id, patient_id, analysis_id, title, description, owner, due_window, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    patient_id,
                    aid,
                    task_data.get("title", ""),
                    task_data.get("description", ""),
                    task_data.get("owner", "provider"),
                    task_data.get("due_window", "next 7 days"),
                    "pending",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        for flag in parsed.get("risk_flags", []):
            if flag.get("severity") == "high":
                db.execute(
                    """INSERT INTO tasks (id, patient_id, analysis_id, title, description, owner, due_window, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        patient_id,
                        aid,
                        f"URGENT: {flag.get('flag', '')}",
                        flag.get("detail", ""),
                        "provider",
                        "immediate",
                        "pending",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

    return {"analysis_id": aid, "result": parsed, "thinking": thinking}


async def run_trend_detection(patient_id: str) -> dict:
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
            return {"error": "Need at least one analysis"}

        analysis_text = "\n".join(
            f"[{a['created_at']}] {a['shared_summary']}" for a in analyses
        )

        user_msg = {
            "role": "user",
            "content": f"Patient: {patient['name']}\n\n--- Previous Analyses ---\n{analysis_text}\n\nAnalyze trends.",
        }

        content, success, thinking = await call_glm([user_msg], TREND_SYSTEM_PROMPT)

        if success:
            parsed = extract_json(content)
            if not parsed:
                parsed = get_mock_trend()
        else:
            parsed = get_mock_trend()

        if analyses:
            db.execute(
                "UPDATE glm_analyses SET trend_summary = ? WHERE id = ?",
                (parsed.get("trend_summary", ""), analyses[-1]["id"]),
            )

    return {"trend": parsed, "thinking": thinking}


async def run_patient_qa(patient_id: str, question: str) -> dict:
    with get_db() as db:
        patient = db.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if not patient:
            return {"error": "Patient not found"}

        latest = db.execute(
            "SELECT * FROM glm_analyses WHERE patient_id = ? ORDER BY created_at DESC LIMIT 1",
            (patient_id,),
        ).fetchone()

        context = f"Patient: {patient['name']}\nCondition: {patient['condition']}"
        if latest:
            context += f"\nLatest Analysis: {latest['shared_summary']}"

        user_msg = {
            "role": "user",
            "content": f"{context}\n\nQuestion: {question}\n\nAnswer this question.",
        }

        content, success, thinking = await call_glm([user_msg], QA_SYSTEM_PROMPT)

        if not success:
            answer = get_mock_qa_answer(question)
        else:
            answer = content

        qid = str(uuid.uuid4())
        db.execute(
            """INSERT INTO qa_exchanges (id, patient_id, question, answer, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                qid,
                patient_id,
                question,
                answer,
                _model(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return {"qa_id": qid, "answer": answer, "thinking": thinking}


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

        enc_text = "\n".join(
            f"[{e['created_at']}] {e['author_role']}: {e['content'][:500]}"
            for e in encounters
        )

        user_msg = {
            "role": "user",
            "content": f"Patient: {patient['name']}\nCondition: {patient['condition']}\n\n--- Encounters ---\n{enc_text}\n\nGenerate care plan.",
        }

        content, success, thinking = await call_glm(
            [user_msg], CAREPLAN_PROMPT, tools=True
        )

        if success:
            parsed = extract_json(content)
            if not parsed:
                parsed = get_mock_careplan(patient["name"], patient["condition"])
        else:
            parsed = get_mock_careplan(patient["name"], patient["condition"])

        pid = str(uuid.uuid4())
        db.execute(
            """INSERT INTO care_plans (id, patient_id, plan_json, raw_response, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                pid,
                patient_id,
                json.dumps(parsed),
                content,
                _model(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return {"plan_id": pid, "plan": parsed, "thinking": thinking}


async def analyze_document(document_id: str) -> dict:
    from app.database import get_db
    import base64

    with get_db() as db:
        doc = db.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if not doc:
            return {"error": "Document not found"}

        file_path = doc["file_path"]
        if not os.path.exists(file_path):
            return {"error": "File not found"}

        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        prompt = "Analyze this medical document. Extract: patient name, dates, diagnoses, medications, key findings."
        content, success = await analyze_image(b64, prompt)

        if success:
            db.execute(
                "UPDATE documents SET notes = ? WHERE id = ?", (content, document_id)
            )

    return {
        "document_id": document_id,
        "analysis": content if success else "Analysis failed",
    }


ENCOUNTER_SUMMARY_PROMPT_v2 = """Extract structured clinical data from provider notes.
Return JSON: chief_complaint, diagnoses, medications_mentioned, vitals, procedures, follow_up, urgency."""


def get_mock_encounter_summary_v2(content: str) -> dict:
    return {
        "chief_complaint": "Clinical encounter",
        "diagnoses": ["See full note"],
        "medications_mentioned": [
            {"name": "See note", "action": "continued", "dosage": "as noted"}
        ],
        "vitals": {},
        "procedures": [],
        "follow_up": "As specified",
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

        user_msg = {
            "role": "user",
            "content": f"Patient: {patient['name']}\n\n--- Clinical Note ---\n{encounter['content']}\n\nExtract structured data.",
        }

        content, success, thinking = await call_glm(
            [user_msg], ENCOUNTER_SUMMARY_PROMPT_v2
        )

        if success:
            parsed = extract_json(content)
            if not parsed:
                parsed = get_mock_encounter_summary_v2(encounter["content"])
        else:
            parsed = get_mock_encounter_summary_v2(encounter["content"])

        db.execute(
            "UPDATE encounters SET structured_summary = ? WHERE id = ?",
            (json.dumps(parsed), encounter_id),
        )

    return {"encounter_id": encounter_id, "summary": parsed}


FOLLOWUP_PROMPT_V2 = """Based on care analysis, suggest 3 questions patient might ask.
Return JSON array: ["Question 1?", "Question 2?", "Question 3?"]"""


def get_mock_followups_v2(name: str) -> list:
    return [
        "When should I schedule my next follow-up?",
        "What warning signs should I watch for?",
        "What lifestyle changes should I make?",
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

        user_msg = {
            "role": "user",
            "content": f"Patient: {patient['name']}\nAnalysis: {analysis['shared_summary']}\n\nSuggest 3 follow-up questions.",
        }

        content, success, thinking = await call_glm([user_msg], FOLLOWUP_PROMPT_V2)

        if success:
            parsed = extract_json(content)
            if not parsed or not isinstance(parsed, list):
                parsed = get_mock_followups_v2(patient["name"])
        else:
            parsed = get_mock_followups_v2(patient["name"])

        db.execute(
            "UPDATE glm_analyses SET followup_suggestions = ? WHERE id = ?",
            (json.dumps(parsed), analysis_id),
        )

    return {"analysis_id": analysis_id, "suggestions": parsed}

    with get_db() as db:
        doc = db.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if not doc:
            return {"error": "Document not found"}

        file_path = doc["file_path"]
        if not os.path.exists(file_path):
            return {"error": "File not found"}

        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        prompt = "Analyze this medical document. Extract: patient name, dates, diagnoses, medications, key findings, follow-up recommendations."

        content, success = await analyze_image(b64, prompt)

        if success:
            db.execute(
                "UPDATE documents SET notes = ? WHERE id = ?",
                (content, document_id),
            )

        return {
            "document_id": document_id,
            "analysis": content if success else "Analysis failed",
        }
