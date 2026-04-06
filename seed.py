"""CareLoop — Seed demo data for hackathon demo."""

import uuid
from datetime import datetime, timedelta, timezone
from app.database import init_db, get_db


def seed():
    init_db()

    with get_db() as db:
        existing = db.execute("SELECT COUNT(*) as cnt FROM patients").fetchone()["cnt"]
        if existing > 0:
            print(f"Database already has {existing} patients. Skipping seed.")
            return

        now = datetime.now(timezone.utc)

        # ─── Patient 1: Maria Santos ───────────────────────────
        p1_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO patients (id, name, date_of_birth, condition, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                p1_id,
                "Maria Santos",
                "1958-03-15",
                "Post-cardiac surgery recovery",
                "Underwent CABG (coronary artery bypass graft) 3 weeks ago. Managing recovery at home.",
                (now - timedelta(days=21)).isoformat(),
            ),
        )

        # Encounter 1: Initial post-op assessment
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                p1_id,
                "provider",
                "Dr. James Chen",
                "provider_update",
                "Patient is 1 week post-CABG x3. Incision site clean and dry, no signs of infection. "
                "Echocardiogram shows EF 35%, unchanged from pre-op. "
                "Current medications: Metoprolol 50mg BID, Lisinopril 10mg daily, Aspirin 81mg daily, Atorvastatin 40mg QHS. "
                "Patient reports fatigue with minimal exertion, poor appetite, difficulty sleeping in supine position. "
                "Bilateral pedal edema 1+. Lung sounds with mild bibasilar crackles. "
                "Blood pressure 142/88, heart rate 72 and regular. "
                "Cardiac rehab referral placed. Follow-up in 1 week.",
                (now - timedelta(days=14)).isoformat(),
            ),
        )

        # Encounter 2: Week 2 progress
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                p1_id,
                "provider",
                "Dr. James Chen",
                "provider_update",
                "2-week post-op follow-up. Incision healing well, Steri-Strips intact. "
                "Echocardiogram shows EF improved to 42% — encouraging sign. "
                "Reduced metoprolol from 50mg to 25mg BID due to bradycardia episodes (HR dipping to 48 during sleep). "
                "Continuing all other medications unchanged. "
                "Blood pressure 132/82 — improved from last visit. "
                "Patient reports occasional chest tightness during light activity, likely musculoskeletal in nature. "
                "Edema resolving. Lung sounds clear bilaterally. "
                "Cardiac rehab enrollment confirmed — starts next week. "
                "Lab work ordered: CBC, BMP, BNP, INR. Next follow-up in 2 weeks.",
                (now - timedelta(days=7)).isoformat(),
            ),
        )

        # Encounter 3: Patient check-in
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                p1_id,
                "patient",
                "Maria Santos",
                "patient_checkin",
                "I walked to the mailbox and back today without stopping — first time since surgery! "
                "Still get some tightness in my chest when I do too much, but it goes away when I rest. "
                "Taking all my medications on time. The new lower dose of the heart pill seems fine — "
                "not feeling as dizzy when I wake up. "
                "My daughter is helping me with meal prep — eating more fish and vegetables, less salt. "
                "Sleeping better but still wake up once or twice to use the bathroom. "
                "A bit anxious about starting cardiac rehab next week — will there be other people my age? "
                "Also wondering when I can drive again.",
                (now - timedelta(days=1)).isoformat(),
            ),
        )

        # Encounter 4: Lab results
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                p1_id,
                "provider",
                "Dr. James Chen",
                "provider_update",
                "Lab results from yesterday: CBC normal (WBC 6.2, Hgb 12.8, Plt 245). "
                "BMP: Na 140, K 4.1, Cr 0.9, BUN 18 — all within normal limits. "
                "BNP decreased from 420 to 285 pg/mL — trending in right direction. "
                "INR 1.1 — not on anticoagulation so expected. "
                "Lipid panel: Total cholesterol 178, LDL 98, HDL 42, Triglycerides 190 — "
                "LDL still above target of <70 for secondary prevention. "
                "Consider increasing Atorvastatin to 80mg or adding ezetimibe if not at goal by next visit. "
                "Overall encouraging recovery trajectory.",
                (now - timedelta(hours=6)).isoformat(),
            ),
        )

        # ─── Patient 2: Robert Kim ────────────────────────────
        p2_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO patients (id, name, date_of_birth, condition, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                p2_id,
                "Robert Kim",
                "1971-09-22",
                "Type 2 Diabetes — insulin management",
                "Recently transitioned from oral medications to insulin therapy. Adjusting to new regimen.",
                (now - timedelta(days=14)).isoformat(),
            ),
        )

        # Encounter 1: Insulin initiation visit
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                p2_id,
                "provider",
                "Dr. Sarah Patel",
                "provider_update",
                "Robert returns for insulin initiation after A1C remained 9.2% on max oral therapy "
                "(Metformin 1000mg BID + Glipizide 10mg BID). "
                "Fasting glucose consistently 200-240 mg/dL over past month. "
                "Starting insulin glargine 20 units at bedtime. Continuing metformin, discontinuing glipizide. "
                "Provided insulin pen training, glucose monitoring education, and hypoglycemia management plan. "
                "BMI 31.2. Blood pressure 138/86. "
                "Foot exam: normal sensation, no ulcers. Monofilament intact bilaterally. "
                "Annual eye exam overdue by 8 months — referral sent to ophthalmology. "
                "Urine microalbumin/creatinine ratio 45 mg/g — early nephropathy marker, starting ACE inhibitor. "
                "Follow-up in 2 weeks with glucose logs.",
                (now - timedelta(days=14)).isoformat(),
            ),
        )

        # Encounter 2: 1-week insulin check
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                p2_id,
                "provider",
                "Dr. Sarah Patel",
                "provider_update",
                "1-week insulin follow-up. Glucose logs show gradual improvement: "
                "fasting readings 220→180→165 mg/dL over past week. "
                "Patient reports 2 hypoglycemic episodes (glucose 62 and 58) in late afternoon — "
                "likely from lingering glipizide effect (stopped 1 week ago). "
                "No severe hypoglycemia. Patient using glucose gel when symptomatic. "
                "Continue current insulin dose. May increase to 24 units if fasting glucose "
                "not below 140 by next visit in 1 week. "
                "Discussed carbohydrate counting basics. Referred to diabetes educator. "
                "Ophthalmology appointment scheduled for next Tuesday.",
                (now - timedelta(days=7)).isoformat(),
            ),
        )

        # Encounter 3: Patient check-in
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                p2_id,
                "patient",
                "Robert Kim",
                "patient_checkin",
                "Getting more comfortable with the insulin pen but still nervous about the needles — "
                "the spring-loaded ones help a lot. "
                "My morning numbers have been between 155-175 this week, which seems better? "
                "Had two episodes where I felt shaky and sweaty around 3pm — ate some crackers and felt better. "
                "Trying to eat better but it's hard with my work schedule — lots of fast food temptation. "
                "Haven't scheduled the eye appointment yet, need to find time off work. "
                "My feet feel fine, no numbness or tingling. "
                "Started walking 15 minutes after dinner most nights. "
                "The diabetes educator called and we set up a virtual session for next Thursday.",
                (now - timedelta(hours=12)).isoformat(),
            ),
        )

        # ─── Patient 3: Eleanor Davis ─────────────────────────
        p3_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO patients (id, name, date_of_birth, condition, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                p3_id,
                "Eleanor Davis",
                "1945-06-08",
                "Chronic pain management + mild cognitive decline",
                "Managing chronic lower back pain and early-stage cognitive changes. Lives with spouse.",
                (now - timedelta(days=30)).isoformat(),
            ),
        )

        # Encounter 1: Initial assessment
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                p3_id,
                "provider",
                "Dr. Michael Torres",
                "provider_update",
                "Eleanor presents for follow-up of chronic lumbar pain (L4-L5 degenerative disc disease, "
                "diagnosed 2019) and newly reported cognitive changes per husband. "
                "Pain currently 5-6/10, worse in morning, improved with movement. "
                "Current pain regimen: Gabapentin 300mg TID, Acetaminophen 500mg Q6H PRN, "
                "Capsaicin cream to lumbar area BID. "
                "Husband reports increased forgetfulness over past 2 months — misplacing items, "
                "missing appointments, difficulty following recipes she previously knew by heart. "
                "MMSE score 25/30 — down from 28/30 one year ago. "
                "Notable deficits in recall and attention. "
                "Medication reconciliation: also taking Lisinopril 20mg daily, Atorvastatin 20mg QHS, "
                "Calcium/Vitamin D supplements, Omeprazole 20mg daily. "
                "Concern about possible double-dosing of Gabapentin — husband found extra pills in pillbox. "
                "Referred to neuropsychology for comprehensive cognitive evaluation. "
                "Fall risk: moderate — recommended grab bars in bathroom, removed throw rugs. "
                "Follow-up in 2 weeks after neuropsych results.",
                (now - timedelta(days=14)).isoformat(),
            ),
        )

        # Encounter 2: Neuropsych results
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                p3_id,
                "provider",
                "Dr. Michael Torres",
                "provider_update",
                "Neuropsychology results received. Comprehensive evaluation shows: "
                "MMSE 22/30, down from 25/30 six months ago. "
                "Significant deficits in: delayed recall (2/5 words at 10 min), "
                "serial 7 subtraction, and clock drawing test (missing numbers, hands incorrect). "
                "Preserved: registration, orientation to person/place, naming, repetition. "
                "Impression: Mild Cognitive Impairment (amnestic type), possible early Alzheimer's disease. "
                "Recommended: Brain MRI to rule out structural causes, "
                "consider adding Donepezil 5mg daily (can also help with pain modulation). "
                "Gabapentin confirmed being double-dosed at times — switching to pill pack service. "
                "Also adding low-dose Duloxetine 20mg daily for dual benefit (pain + mood). "
                "Fall risk reassessment: high — physical therapy referral for balance training. "
                "Discussed driving safety with patient and husband — agreed to limit to daytime/local roads for now.",
                (now - timedelta(days=3)).isoformat(),
            ),
        )

        # Encounter 3: Patient check-in (via husband)
        db.execute(
            "INSERT INTO encounters (id, patient_id, author_role, author_name, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                p3_id,
                "patient",
                "Eleanor Davis (via husband Richard)",
                "patient_checkin",
                "Richard writing on Eleanor's behalf. "
                "She's been taking the new medications (Donepezil and Duloxetine) for 3 days now. "
                "Seems a bit more tired than usual, sleeping about 10 hours. "
                "No nausea or headaches. "
                "The pill pack service starts Monday — I think that will really help with the gabapentin confusion. "
                "She seemed more oriented yesterday — remembered our granddaughter's birthday. "
                "Still having trouble with the back pain in the mornings, the stretching exercises from the "
                "handout seem to help a little. "
                "Physical therapy evaluation is scheduled for next Wednesday. "
                "MRI is scheduled for Friday — she's nervous about the enclosed space. "
                "Grab bars installed in both bathrooms. We removed all the throw rugs.",
                (now - timedelta(hours=8)).isoformat(),
            ),
        )

    print(f"Seeded 3 patients with 10 encounters (3-4 per patient)")
    print(f"   - Maria Santos: post-cardiac surgery (4 encounters)")
    print(f"   - Robert Kim: T2D insulin management (3 encounters)")
    print(f"   - Eleanor Davis: chronic pain + cognitive decline (3 encounters)")


if __name__ == "__main__":
    seed()
