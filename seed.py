"""CareLoop — Seed demo data for hackathon demo."""
import uuid
from datetime import datetime, timedelta
from app.database import init_db, get_db


def seed():
    """Insert demo patients and sample encounters."""
    init_db()

    with get_db() as db:
        # Check if already seeded
        existing = db.execute("SELECT COUNT(*) as cnt FROM patients").fetchone()["cnt"]
        if existing > 0:
            print(f"Database already has {existing} patients. Skipping seed.")
            return

        now = datetime.utcnow()

        # ─── Patient 1: Maria Santos ────────────────────────
        p1_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO patients (id, name, date_of_birth, condition, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (p1_id, "Maria Santos", "1958-03-15",
             "Post-cardiac surgery recovery",
             "Underwent CABG (coronary artery bypass graft) 3 weeks ago. Managing recovery at home.",
             (now - timedelta(days=21)).isoformat())
        )

        # Provider update for Maria
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), p1_id, "provider", "Dr. James Chen",
             "provider_update",
             "Patient is 3 weeks post-CABG. Incision site healing well, no signs of infection. "
             "Echocardiogram shows EF improved to 45% from pre-op 35%. "
             "Reduced metoprolol from 50mg to 25mg BID. "
             "Started cardiac rehab referral. "
             "Blood pressure 128/82 — slightly elevated, monitoring. "
             "Patient reports occasional chest tightness during light activity, likely musculoskeletal. "
             "Next follow-up in 2 weeks.",
             (now - timedelta(days=3)).isoformat())
        )

        # Patient check-in for Maria
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), p1_id, "patient", "Maria Santos",
             "patient_checkin",
             "I walked to the mailbox and back today without stopping — first time since surgery! "
             "Still get some tightness in my chest when I do too much, but it goes away when I rest. "
             "Taking all my medications on time. The new lower dose of the heart pill seems fine. "
             "My daughter is helping me with meal prep — eating more fish and vegetables. "
             "Sleeping better but still wake up once or twice. "
             "A bit anxious about starting cardiac rehab next week.",
             (now - timedelta(days=1)).isoformat())
        )

        # ─── Patient 2: Robert Kim ──────────────────────────
        p2_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO patients (id, name, date_of_birth, condition, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (p2_id, "Robert Kim", "1971-09-22",
             "Type 2 Diabetes — insulin management",
             "Recently transitioned from oral medications to insulin therapy. Adjusting to new regimen.",
             (now - timedelta(days=14)).isoformat())
        )

        # Provider update for Robert
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), p2_id, "provider", "Dr. Sarah Patel",
             "provider_update",
             "Robert transitioned to insulin glargine 20 units at bedtime 2 weeks ago after A1C remained 9.2% on max oral therapy. "
             "Fasting glucose logs show gradual improvement: 220→180→165 over past week. "
             "Continuing metformin 1000mg BID alongside insulin. "
             "Patient reporting some hypoglycemic episodes in late afternoon — may need to adjust lunch timing. "
             "Ordered repeat A1C in 6 weeks. "
             "Foot exam normal. Annual eye exam overdue — needs scheduling. "
             "BMI 31.2, discussed weight management strategies. "
             "Consider increasing insulin to 24 units if fasting glucose not below 140 by next visit.",
             (now - timedelta(days=2)).isoformat())
        )

        # Patient check-in for Robert
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), p2_id, "patient", "Robert Kim",
             "patient_checkin",
             "Getting more comfortable with the insulin pen but still nervous about the needles. "
             "My morning numbers have been between 155-175 this week, which I think is better? "
             "Had two episodes where I felt shaky and sweaty around 3pm — ate some crackers and felt better. "
             "Trying to eat better but it's hard with my work schedule — lots of fast food temptation. "
             "Haven't scheduled the eye appointment yet, need to find time. "
             "My feet feel fine, no numbness or tingling. "
             "Started walking 15 minutes after dinner most nights.",
             (now - timedelta(hours=12)).isoformat())
        )

        # ─── Patient 3: Eleanor Davis ───────────────────────
        p3_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO patients (id, name, date_of_birth, condition, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (p3_id, "Eleanor Davis", "1945-06-08",
             "Chronic pain management + mild cognitive decline",
             "Managing chronic lower back pain and early-stage cognitive changes. Lives with spouse.",
             (now - timedelta(days=30)).isoformat())
        )

        # Provider update for Eleanor
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), p3_id, "provider", "Dr. Michael Torres",
             "provider_update",
             "Eleanor presents with increased confusion reported by husband over past 2 weeks. "
             "MMSE score 22/30, down from 25/30 six months ago. "
             "Pain levels remain 5-6/10 despite current regimen of gabapentin 300mg TID. "
             "Considering adding low-dose duloxetine for dual pain/mood benefit. "
             "Fall risk assessment: moderate — recommended grab bars in bathroom. "
             "Medication reconciliation shows she may be double-dosing gabapentin — husband confirms confusion about timing. "
             "Referred to neuropsychology for comprehensive cognitive evaluation. "
             "Must monitor for medication interactions given polypharmacy concerns.",
             (now - timedelta(days=1)).isoformat())
        )

    print(f"✅ Seeded 3 patients with encounters")
    print(f"   - Maria Santos ({p1_id})")
    print(f"   - Robert Kim ({p2_id})")
    print(f"   - Eleanor Davis ({p3_id})")


if __name__ == "__main__":
    seed()
