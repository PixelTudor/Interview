"""
Interview Coach - Vercel Serverless API
========================================
Main API handler for the Interview Coach application.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import random
import re
import base64
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


class InterviewerType(str, Enum):
    HIRING_MANAGER = "hiring_manager"
    RECRUITER = "recruiter"
    SKIP_LEVEL = "skip_level"
    PEER = "peer"
    HR = "hr"
    PANEL = "panel"


INTERVIEWER_CONTEXTS = {
    InterviewerType.HIRING_MANAGER: {
        "name": "Hiring Manager",
        "focus": "technical depth, team fit, day-to-day responsibilities, management style compatibility",
        "style": "Direct and detailed. Will probe deeply into past experiences and specific examples. Wants to know HOW you work, not just WHAT you've done.",
        "tips": "Be specific about methodologies. Show you understand the role deeply. Ask thoughtful questions about the team."
    },
    InterviewerType.RECRUITER: {
        "name": "Recruiter/Talent Acquisition",
        "focus": "culture fit, compensation expectations, availability, high-level qualifications, red flags",
        "style": "Warm but screening. Looking for deal-breakers and cultural alignment. Questions are broader and less technical.",
        "tips": "Be concise and positive. Don't over-explain technical details. Show enthusiasm for the company."
    },
    InterviewerType.SKIP_LEVEL: {
        "name": "Skip-Level Manager (Hiring Manager's Boss)",
        "focus": "strategic thinking, leadership potential, business impact, long-term vision",
        "style": "Big picture focused. Less interested in details, more interested in impact and trajectory. Tests executive presence.",
        "tips": "Lead with outcomes and business impact. Show strategic thinking. Keep answers concise and impactful."
    },
    InterviewerType.PEER: {
        "name": "Peer/Colleague",
        "focus": "collaboration style, technical credibility, team dynamics, culture add",
        "style": "Conversational and evaluating chemistry. Looking for someone they'd want to work with daily.",
        "tips": "Be authentic and collaborative. Show curiosity about their work. Demonstrate you're a team player."
    },
    InterviewerType.HR: {
        "name": "HR/People Operations",
        "focus": "behavioral competencies, conflict resolution, values alignment, compliance awareness",
        "style": "Structured behavioral questions. Often uses STAR format. Looking for consistency and professionalism.",
        "tips": "Use STAR format. Be consistent with your stories. Show emotional intelligence."
    },
    InterviewerType.PANEL: {
        "name": "Panel Interview",
        "focus": "multiple perspectives, handling pressure, consistent messaging, engaging multiple stakeholders",
        "style": "Multiple interviewers with different agendas. Tests your ability to manage attention and adapt communication style.",
        "tips": "Make eye contact with everyone. Address the questioner but include others. Stay consistent across different questions."
    }
}


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

## INTERVIEWER CONTEXT:

Interviewer Type: {interviewer_name}
Focus Areas: {interviewer_focus}
Interview Style: {interviewer_style}
Coaching Tips: {interviewer_tips}

Adapt your coaching based on WHO is interviewing. Different interviewers look for different things.

## CANDIDATE BACKGROUND (FROM RESUME):
{resume_context}

## JOB REQUIREMENTS:
{job_context}

## CURRENT SESSION STATE:

Question Type: {question_type}
Current Step: {current_step}
Current Question: {current_question}
Anchors: {anchors}
Principle: {principle}

Keep responses SHORT and FOCUSED. Use line breaks. Be punchy.
If resume/job description are provided, tailor your coaching to highlight how the candidate's experience aligns with the role requirements.
Point out gaps and help the candidate prepare stories that address them."""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_session(session_id: str) -> Optional[Dict]:
    return SESSIONS.get(session_id)


def create_session(session_id: str, role: str = None, company: str = None, interviewer_type: str = None) -> Dict:
    session = {
        "session_id": session_id,
        "role": role or "Senior Study Manager",
        "company": company or "Taiho Oncology",
        "interviewer_type": interviewer_type or InterviewerType.HIRING_MANAGER.value,
        "question_type": "curveball",
        "current_step": "identify_principle",
        "current_question": "",
        "anchors": [],
        "principle": "",
        "history": [],
        "resume": None,
        "job_description": None,
        "parsed_resume": None,
        "parsed_job_description": None
    }
    SESSIONS[session_id] = session
    return session


def _is_section_header(line: str, headers: List[str]) -> bool:
    """Check if a line is a section header (not just contains header words)."""
    line_clean = re.sub(r'[:\-–—]', '', line.lower()).strip()

    # A header line should be short and match or start with a known header
    if len(line_clean) > 50:
        return False

    # Check for exact match or starts with header
    for header in headers:
        if line_clean == header or line_clean.startswith(header + ' '):
            return True
        # Also check if line is just the header with some punctuation
        if header in line_clean and len(line_clean) < len(header) + 15:
            return True

    return False


def parse_resume(resume_text: str) -> Dict:
    """Parse resume text and extract key information."""
    parsed = {
        "raw_text": resume_text,
        "skills": [],
        "experience": [],
        "education": [],
        "summary": ""
    }

    if not resume_text:
        return parsed

    lines = resume_text.strip().split('\n')
    current_section = None
    section_content = []

    # Common section headers
    skill_headers = ['skills', 'technical skills', 'core competencies', 'competencies', 'expertise']
    exp_headers = ['experience', 'work experience', 'professional experience', 'employment', 'work history']
    edu_headers = ['education', 'academic background', 'qualifications', 'degrees']
    summary_headers = ['summary', 'professional summary', 'profile', 'objective', 'about']

    for line in lines:
        # Check for section headers (must be short header-like lines)
        if _is_section_header(line, skill_headers):
            if current_section and section_content:
                _save_section(parsed, current_section, section_content)
            current_section = 'skills'
            section_content = []
        elif _is_section_header(line, exp_headers):
            if current_section and section_content:
                _save_section(parsed, current_section, section_content)
            current_section = 'experience'
            section_content = []
        elif _is_section_header(line, edu_headers):
            if current_section and section_content:
                _save_section(parsed, current_section, section_content)
            current_section = 'education'
            section_content = []
        elif _is_section_header(line, summary_headers):
            if current_section and section_content:
                _save_section(parsed, current_section, section_content)
            current_section = 'summary'
            section_content = []
        elif line.strip():
            section_content.append(line.strip())

    # Save last section
    if current_section and section_content:
        _save_section(parsed, current_section, section_content)

    # If no sections found, use full text as summary
    if not parsed['summary'] and not parsed['experience']:
        parsed['summary'] = resume_text[:1000]

    return parsed


def _save_section(parsed: Dict, section: str, content: List[str]) -> None:
    """Helper to save parsed section content."""
    if section == 'skills':
        # Extract individual skills from bullet points or comma-separated lists
        for line in content:
            # Handle comma or bullet-separated skills
            skills = re.split(r'[,•·\|]', line)
            for skill in skills:
                skill = skill.strip()
                if skill and len(skill) > 1:
                    parsed['skills'].append(skill)
    elif section == 'experience':
        parsed['experience'] = content
    elif section == 'education':
        parsed['education'] = content
    elif section == 'summary':
        parsed['summary'] = ' '.join(content)


def parse_job_description(jd_text: str) -> Dict:
    """Parse job description and extract key requirements."""
    parsed = {
        "raw_text": jd_text,
        "title": "",
        "requirements": [],
        "responsibilities": [],
        "qualifications": [],
        "company_info": ""
    }

    if not jd_text:
        return parsed

    lines = jd_text.strip().split('\n')
    current_section = None
    section_content = []
    title_candidates_checked = 0

    # Common section headers
    req_headers = ['requirements', 'required', 'must have', 'essential']
    resp_headers = ['responsibilities', 'duties', 'what you will do', 'role', 'job duties']
    qual_headers = ['qualifications', 'preferred', 'nice to have', 'desired', 'skills']
    about_headers = ['about', 'about the company', 'company', 'who we are', 'overview']

    for line in lines:
        # Check for section headers first (must be short header-like lines)
        if _is_section_header(line, req_headers):
            if current_section and section_content:
                _save_jd_section(parsed, current_section, section_content)
            current_section = 'requirements'
            section_content = []
            continue
        elif _is_section_header(line, resp_headers):
            if current_section and section_content:
                _save_jd_section(parsed, current_section, section_content)
            current_section = 'responsibilities'
            section_content = []
            continue
        elif _is_section_header(line, qual_headers):
            if current_section and section_content:
                _save_jd_section(parsed, current_section, section_content)
            current_section = 'qualifications'
            section_content = []
            continue
        elif _is_section_header(line, about_headers):
            if current_section and section_content:
                _save_jd_section(parsed, current_section, section_content)
            current_section = 'company_info'
            section_content = []
            continue

        # If we haven't found a title yet and haven't entered a section,
        # the first non-empty line is likely the title
        if line.strip():
            if not parsed['title'] and current_section is None and title_candidates_checked < 3:
                parsed['title'] = line.strip()
                title_candidates_checked += 1
            else:
                section_content.append(line.strip())

    # Save last section
    if current_section and section_content:
        _save_jd_section(parsed, current_section, section_content)

    return parsed


def _save_jd_section(parsed: Dict, section: str, content: List[str]) -> None:
    """Helper to save parsed job description section content."""
    if section == 'requirements':
        parsed['requirements'] = content
    elif section == 'responsibilities':
        parsed['responsibilities'] = content
    elif section == 'qualifications':
        parsed['qualifications'] = content
    elif section == 'company_info':
        parsed['company_info'] = ' '.join(content)


def generate_personalized_questions(session: Dict) -> List[str]:
    """Generate interview questions based on resume and job description."""
    questions = []

    resume = session.get('parsed_resume') or {}
    jd = session.get('parsed_job_description') or {}

    # Generate questions based on experience
    if resume.get('experience'):
        for exp in resume['experience'][:3]:
            if len(exp) > 20:
                questions.append(f"Tell me more about your experience with: {exp[:100]}...")

    # Generate questions based on skills vs requirements
    resume_skills = set(s.lower() for s in resume.get('skills', []))
    jd_requirements = jd.get('requirements', [])

    for req in jd_requirements[:5]:
        req_lower = req.lower()
        # Check if any skill matches the requirement
        matching = any(skill in req_lower for skill in resume_skills)
        if matching:
            questions.append(f"You mentioned relevant experience. Can you elaborate on: {req}")
        else:
            questions.append(f"This role requires: {req}. How would you approach this?")

    # Generate questions about responsibilities
    for resp in jd.get('responsibilities', [])[:3]:
        questions.append(f"How would you handle: {resp}")

    # Add gap analysis questions
    if jd.get('qualifications'):
        questions.append(f"What makes you qualified for this role given the requirements: {', '.join(jd['qualifications'][:3])}?")

    return questions if questions else None


def _build_resume_context(parsed_resume: Optional[Dict]) -> str:
    """Build resume context string for the system prompt."""
    if not parsed_resume:
        return "No resume provided yet."

    parts = []
    if parsed_resume.get('summary'):
        parts.append(f"Summary: {parsed_resume['summary'][:500]}")
    if parsed_resume.get('skills'):
        parts.append(f"Skills: {', '.join(parsed_resume['skills'][:15])}")
    if parsed_resume.get('experience'):
        exp_text = '; '.join(parsed_resume['experience'][:5])
        parts.append(f"Experience highlights: {exp_text[:500]}")
    if parsed_resume.get('education'):
        parts.append(f"Education: {', '.join(parsed_resume['education'][:3])}")

    return '\n'.join(parts) if parts else "Resume uploaded but no key details extracted."


def _build_job_context(parsed_jd: Optional[Dict]) -> str:
    """Build job description context string for the system prompt."""
    if not parsed_jd:
        return "No job description provided yet."

    parts = []
    if parsed_jd.get('title'):
        parts.append(f"Job Title: {parsed_jd['title']}")
    if parsed_jd.get('requirements'):
        parts.append(f"Key Requirements: {'; '.join(parsed_jd['requirements'][:5])}")
    if parsed_jd.get('responsibilities'):
        parts.append(f"Responsibilities: {'; '.join(parsed_jd['responsibilities'][:5])}")
    if parsed_jd.get('qualifications'):
        parts.append(f"Qualifications: {'; '.join(parsed_jd['qualifications'][:5])}")

    return '\n'.join(parts) if parts else "Job description uploaded but no key details extracted."


def _get_interviewer_context(interviewer_type: str) -> Dict:
    """Get interviewer context based on type."""
    try:
        int_type = InterviewerType(interviewer_type)
        return INTERVIEWER_CONTEXTS.get(int_type, INTERVIEWER_CONTEXTS[InterviewerType.HIRING_MANAGER])
    except (ValueError, KeyError):
        return INTERVIEWER_CONTEXTS[InterviewerType.HIRING_MANAGER]


def get_coaching_response(session: Dict, user_message: str) -> str:
    """Get coaching feedback using Claude API."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    resume_context = _build_resume_context(session.get("parsed_resume"))
    job_context = _build_job_context(session.get("parsed_job_description"))
    interviewer_ctx = _get_interviewer_context(session.get("interviewer_type", "hiring_manager"))

    system_prompt = COACH_SYSTEM_PROMPT.format(
        role=session["role"],
        company=session["company"],
        question_type=session["question_type"],
        current_step=session["current_step"],
        current_question=session["current_question"],
        anchors=", ".join(session["anchors"]) if session["anchors"] else "None yet",
        principle=session["principle"] or "Not identified yet",
        resume_context=resume_context,
        job_context=job_context,
        interviewer_name=interviewer_ctx["name"],
        interviewer_focus=interviewer_ctx["focus"],
        interviewer_style=interviewer_ctx["style"],
        interviewer_tips=interviewer_ctx["tips"]
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
                    "GET /api/interviewer-types - List interviewer types",
                    "POST /api/sessions - Create session (accepts interviewer_type)",
                    "POST /api/question - Get question",
                    "POST /api/respond - Submit response",
                    "POST /api/confirm - Confirm confidence",
                    "POST /api/interrupt - Get interruption",
                    "POST /api/resume - Upload resume",
                    "POST /api/job-description - Upload job description",
                    "POST /api/personalized-question - Get personalized question"
                ]
            })
        elif self.path == "/api/interviewer-types" or self.path == "/api/interviewer-types/":
            types = []
            for int_type in InterviewerType:
                ctx = INTERVIEWER_CONTEXTS[int_type]
                types.append({
                    "value": int_type.value,
                    "name": ctx["name"],
                    "focus": ctx["focus"],
                    "tips": ctx["tips"]
                })
            self._send_response(200, {"interviewer_types": types})
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
            interviewer_type = data.get("interviewer_type")

            session = create_session(session_id, role, company, interviewer_type)

            # Get interviewer context for response
            interviewer_ctx = _get_interviewer_context(session["interviewer_type"])

            self._send_response(200, {
                "session_id": session_id,
                "message": f"Session created. You're preparing for an interview with: {interviewer_ctx['name']}",
                "interviewer_tips": interviewer_ctx["tips"],
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

        # Upload resume
        elif path == "/api/resume":
            session_id = data.get("session_id")
            resume_text = data.get("resume_text", "")

            session = get_session(session_id)
            if not session:
                self._send_response(400, {"error": "Session not found"})
                return

            if not resume_text:
                self._send_response(400, {"error": "Resume text is required"})
                return

            session["resume"] = resume_text
            session["parsed_resume"] = parse_resume(resume_text)

            self._send_response(200, {
                "message": "Resume uploaded and parsed successfully.",
                "parsed": session["parsed_resume"],
                "skills_found": len(session["parsed_resume"].get("skills", [])),
                "experience_items": len(session["parsed_resume"].get("experience", []))
            })

        # Upload job description
        elif path == "/api/job-description":
            session_id = data.get("session_id")
            jd_text = data.get("job_description", "")

            session = get_session(session_id)
            if not session:
                self._send_response(400, {"error": "Session not found"})
                return

            if not jd_text:
                self._send_response(400, {"error": "Job description is required"})
                return

            session["job_description"] = jd_text
            session["parsed_job_description"] = parse_job_description(jd_text)

            # Update role and company from JD if available
            if session["parsed_job_description"].get("title"):
                session["role"] = session["parsed_job_description"]["title"]

            self._send_response(200, {
                "message": "Job description uploaded and parsed successfully.",
                "parsed": session["parsed_job_description"],
                "requirements_found": len(session["parsed_job_description"].get("requirements", [])),
                "responsibilities_found": len(session["parsed_job_description"].get("responsibilities", []))
            })

        # Get personalized questions based on resume and JD
        elif path == "/api/personalized-question":
            session_id = data.get("session_id")

            session = get_session(session_id)
            if not session:
                self._send_response(400, {"error": "Session not found"})
                return

            if not session.get("parsed_resume") and not session.get("parsed_job_description"):
                self._send_response(400, {
                    "error": "Please upload a resume or job description first"
                })
                return

            personalized_questions = generate_personalized_questions(session)

            if personalized_questions:
                question = random.choice(personalized_questions)
                session["current_question"] = question
                session["question_type"] = "personalized"
                session["current_step"] = "identify_principle"
                session["anchors"] = []
                session["principle"] = ""

                self._send_response(200, {
                    "question_type": "personalized",
                    "question": question,
                    "instruction": "This question is tailored to your resume and the job requirements. Take your time.",
                    "current_step": session["current_step"],
                    "total_personalized_available": len(personalized_questions)
                })
            else:
                self._send_response(200, {
                    "message": "Could not generate personalized questions. Using standard questions.",
                    "suggestion": "Try adding more detail to your resume or job description."
                })

        else:
            self._send_response(404, {"error": "Endpoint not found"})
