"""
Interview Coach - Vercel Serverless API
========================================
Main API handler for the Interview Coach application.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import random
from typing import Dict, List, Optional
from enum import Enum
import anthropic


# =============================================================================
# CONFIGURATION
# =============================================================================

class QuestionType(str, Enum):
    BEHAVIORAL = "behavioral"
    ALIGNMENT = "alignment"
    CRO_MANAGEMENT = "cro_management"
    MOTIVATION = "motivation"
    CURVEBALL = "curveball"


class TrainingStep(str, Enum):
    IDENTIFY_PRINCIPLE = "identify_principle"
    CREATE_ANCHORS = "create_anchors"
    GUIDED_RECALL = "guided_recall"
    DELIVERY_PRACTICE = "delivery_practice"
    COMPRESSION = "compression"
    RANDOM_ENTRY = "random_entry"


# In-memory session storage (for demo - use Redis/DB in production)
SESSIONS: Dict[str, Dict] = {}


# =============================================================================
# QUESTION BANKS
# =============================================================================

CURVEBALL_QUESTIONS = [
    "You've managed CROs before — but what makes you think you can actually hold them accountable when timelines slip and they push back?",
    "Tell me about a time a CRO completely failed you. What did you do wrong?",
    "If your CRO partner says the timeline is impossible, what's your move?",
    "Why should we hire you over someone with 10 years of experience?",
    "Your last trial had enrollment delays. Convince me that won't happen here.",
    "What's the biggest mistake you've made in clinical operations? Don't give me a humble brag.",
    "That's interesting — but what really went wrong?",
    "Why wasn't that your fault?",
    "What would you do differently if you could go back?",
    "In 30 seconds, why Taiho?",
    "What if I told you this role is 80% firefighting?",
    "A patient safety signal emerges mid-trial. Walk me through your first hour.",
    "Your PI wants to deviate from protocol for a single patient. What do you do?",
]

ALIGNMENT_QUESTIONS = [
    "Why Taiho Oncology specifically?",
    "What does 'People first' mean to you in clinical operations?",
    "How do you ensure alignment when working with global teams across time zones?",
    "Tell me about a time when you had to align stakeholders with competing priorities.",
    "How do you balance sponsor expectations with site capabilities?",
    "What's your approach when a CRO's priorities don't align with yours?",
]

CRO_MANAGEMENT_QUESTIONS = [
    "Walk me through how you set up CRO oversight from day one.",
    "How do you handle a CRO that's meeting metrics but the quality is suffering?",
    "Your CRO says they need more budget to hit timelines. How do you respond?",
    "Describe your approach to CRO performance reviews.",
    "How do you maintain visibility into CRO activities without micromanaging?",
]

BEHAVIORAL_QUESTIONS = [
    "Tell me about a time you had to deliver difficult news to leadership.",
    "Describe a situation where you had to make a decision with incomplete information.",
    "Give me an example of when you identified a risk before it became a problem.",
    "Tell me about a conflict with a vendor and how you resolved it.",
    "Describe a time you had to influence without authority.",
]

MOTIVATION_QUESTIONS = [
    "Why clinical operations? Why not stay on the CRO side?",
    "Where do you see yourself in 5 years?",
    "What drives you in this work?",
    "What's the most meaningful trial you've worked on and why?",
]

QUESTION_BANKS = {
    QuestionType.CURVEBALL: CURVEBALL_QUESTIONS,
    QuestionType.ALIGNMENT: ALIGNMENT_QUESTIONS,
    QuestionType.CRO_MANAGEMENT: CRO_MANAGEMENT_QUESTIONS,
    QuestionType.BEHAVIORAL: BEHAVIORAL_QUESTIONS,
    QuestionType.MOTIVATION: MOTIVATION_QUESTIONS,
}

INTERRUPTIONS = {
    "redirect": [
        "Hold on — what really went wrong there?",
        "Wait. Why wasn't that your fault?",
        "Interesting. But what would you do differently?",
        "Stop. Start over, but lead with the outcome.",
    ],
    "clarify": [
        "Give me a specific example. Right now.",
        "You mentioned risk — what risk exactly?",
        "Who pushed back? Be specific.",
        "What was the actual number?",
    ],
    "challenge": [
        "That sounds rehearsed. What's the real story?",
        "I don't buy it. What aren't you telling me?",
        "That's what everyone says. What makes you different?",
        "Convince me in 10 seconds.",
    ],
    "executive": [
        "Bottom line it for me.",
        "So what? Why should I care?",
        "What's the one thing you want me to remember?",
        "If you had 30 seconds with the CEO, what would you say?",
    ]
}


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

COACH_SYSTEM_PROMPT = """You are an expert interview coach. Your role is to help candidates become confident, fluent, and controlled in interview answers WITHOUT memorizing scripts.

## CORE RULES (ALWAYS FOLLOW):

1. **Reduce cognitive load** - Help build anchors, spines, and principles, not long answers
2. **Break answers into small drills** - anchors, short sentences, compression, random entry
3. **Ask ONE focused question at a time**
4. **Do NOT move forward** until the candidate explicitly says they feel confident
5. **Actively correct delivery issues** - filler words, rambling, weak verbs, unclear endings
6. **Teach recovery** - how to restart mid-answer if they start wrong or get interrupted
7. **Prefer short, declarative sentences** and pauses over long explanations

## TRAINING STRUCTURE:

* Step 1: Identify the core PRINCIPLE behind the answer
* Step 2: Create 3-4 ANCHORS (e.g., Moment / Risk / Moves / Win)
* Step 3: Run GUIDED RECALL using one anchor at a time
* Step 4: Practice DELIVERY with short sentences and pauses
* Step 5: ONE-SENTENCE COMPRESSION
* Step 6: RANDOM ENTRY & recovery drills

## FEEDBACK STYLE:

* Be SPECIFIC and ACTIONABLE
* Explain WHY something works or doesn't
* Normalize nerves - focus on CONTROL, not perfection
* Use short, punchy feedback. No long paragraphs.

## ROLE CONTEXT:

The candidate is interviewing for: {role} at {company}

Key competencies:
- Global clinical trial management and leadership
- CRO oversight and vendor management
- Cross-functional collaboration
- Risk identification and mitigation
- GCP/ICH compliance
- Oncology drug development

## CURRENT SESSION STATE:

Question Type: {question_type}
Current Step: {current_step}
Current Question: {current_question}
Anchors: {anchors}
Principle: {principle}

Keep responses SHORT and FOCUSED. Use line breaks. Be punchy."""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_session(session_id: str) -> Optional[Dict]:
    return SESSIONS.get(session_id)


def create_session(session_id: str, role: str = None, company: str = None) -> Dict:
    session = {
        "session_id": session_id,
        "role": role or "Senior Study Manager",
        "company": company or "Taiho Oncology",
        "question_type": "curveball",
        "current_step": "identify_principle",
        "current_question": "",
        "anchors": [],
        "principle": "",
        "history": []
    }
    SESSIONS[session_id] = session
    return session


def get_coaching_response(session: Dict, user_message: str) -> str:
    """Get coaching feedback using Claude API."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    system_prompt = COACH_SYSTEM_PROMPT.format(
        role=session["role"],
        company=session["company"],
        question_type=session["question_type"],
        current_step=session["current_step"],
        current_question=session["current_question"],
        anchors=", ".join(session["anchors"]) if session["anchors"] else "None yet",
        principle=session["principle"] or "Not identified yet"
    )

    # Build message history
    messages = session.get("history", [])[-10:]  # Last 10 messages for context
    messages.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=messages
    )

    assistant_message = response.content[0].text

    # Update history
    session["history"].append({"role": "user", "content": user_message})
    session["history"].append({"role": "assistant", "content": assistant_message})

    return assistant_message


# =============================================================================
# API HANDLER
# =============================================================================

class handler(BaseHTTPRequestHandler):
    def _send_response(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self._send_response(200, {})

    def do_GET(self):
        if self.path == "/api" or self.path == "/api/":
            self._send_response(200, {
                "status": "healthy",
                "service": "Interview Coach",
                "endpoints": [
                    "POST /api/sessions - Create session",
                    "POST /api/question - Get question",
                    "POST /api/respond - Submit response",
                    "POST /api/confirm - Confirm confidence",
                    "POST /api/interrupt - Get interruption"
                ]
            })
        else:
            self._send_response(404, {"error": "Not found"})

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        path = self.path.rstrip('/')

        # Create session
        if path == "/api/sessions":
            session_id = data.get("session_id", f"session_{random.randint(10000, 99999)}")
            role = data.get("role")
            company = data.get("company")

            session = create_session(session_id, role, company)
            self._send_response(200, {
                "session_id": session_id,
                "message": "Session created. Ready to begin coaching.",
                "session": session
            })

        # Get question
        elif path == "/api/question":
            session_id = data.get("session_id")
            question_type = data.get("question_type", "curveball")

            session = get_session(session_id)
            if not session:
                self._send_response(400, {"error": "Session not found"})
                return

            questions = QUESTION_BANKS.get(QuestionType(question_type), CURVEBALL_QUESTIONS)
            question = random.choice(questions)

            session["question_type"] = question_type
            session["current_question"] = question
            session["current_step"] = "identify_principle"
            session["anchors"] = []
            session["principle"] = ""

            self._send_response(200, {
                "question_type": question_type,
                "question": question,
                "instruction": "Take your time. Say it out loud if you can. When done, I'll give specific feedback.",
                "current_step": session["current_step"]
            })

        # Submit response
        elif path == "/api/respond":
            session_id = data.get("session_id")
            response = data.get("response", "")

            session = get_session(session_id)
            if not session:
                self._send_response(400, {"error": "Session not found"})
                return

            if not response:
                self._send_response(400, {"error": "Response is required"})
                return

            context = f"""
CURRENT STEP: {session['current_step']}
QUESTION: {session['current_question']}

CANDIDATE RESPONSE: {response}

Provide coaching based on the current step. Do NOT advance until they say confident.
"""

            feedback = get_coaching_response(session, context)

            self._send_response(200, {
                "feedback": feedback,
                "current_step": session["current_step"],
                "session": session
            })

        # Confirm confidence
        elif path == "/api/confirm":
            session_id = data.get("session_id")

            session = get_session(session_id)
            if not session:
                self._send_response(400, {"error": "Session not found"})
                return

            steps = ["identify_principle", "create_anchors", "guided_recall",
                     "delivery_practice", "compression", "random_entry"]
            current_idx = steps.index(session["current_step"]) if session["current_step"] in steps else 0

            if current_idx < len(steps) - 1:
                session["current_step"] = steps[current_idx + 1]

                instructions = {
                    "create_anchors": "Now create 3-4 anchors. What are the key moments?",
                    "guided_recall": "Guided recall time. I'll call an anchor, you expand on just that part.",
                    "delivery_practice": "Delivery time. Short sentences. Pauses. No fillers. Go.",
                    "compression": "Compress it. One sentence that captures everything.",
                    "random_entry": "Random entry drill. I'll interrupt. Stay anchored.",
                }

                self._send_response(200, {
                    "message": f"Moving to: {session['current_step']}",
                    "instruction": instructions.get(session["current_step"], "Continue."),
                    "current_step": session["current_step"]
                })
            else:
                self._send_response(200, {
                    "message": "Training complete for this question!",
                    "instruction": "Ready for a new question?",
                    "current_step": "complete"
                })

        # Interrupt
        elif path == "/api/interrupt":
            session_id = data.get("session_id")
            interrupt_type = data.get("type", "redirect")

            session = get_session(session_id)
            if not session:
                self._send_response(400, {"error": "Session not found"})
                return

            interrupts = INTERRUPTIONS.get(interrupt_type, INTERRUPTIONS["redirect"])
            interrupt = random.choice(interrupts)

            self._send_response(200, {
                "interruption": interrupt,
                "type": interrupt_type,
                "instruction": "Recover. Stay anchored. Land it."
            })

        # Set anchors
        elif path == "/api/anchors":
            session_id = data.get("session_id")
            anchors = data.get("anchors", [])

            session = get_session(session_id)
            if not session:
                self._send_response(400, {"error": "Session not found"})
                return

            session["anchors"] = anchors

            self._send_response(200, {
                "message": f"Anchors set: {', '.join(anchors)}",
                "anchors": anchors
            })

        # Set principle
        elif path == "/api/principle":
            session_id = data.get("session_id")
            principle = data.get("principle", "")

            session = get_session(session_id)
            if not session:
                self._send_response(400, {"error": "Session not found"})
                return

            session["principle"] = principle

            self._send_response(200, {
                "message": "Principle captured.",
                "principle": principle
            })

        else:
            self._send_response(404, {"error": "Endpoint not found"})
