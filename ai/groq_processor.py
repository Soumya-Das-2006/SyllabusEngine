import json
import os
from groq import Groq

client = Groq(api_key=os.environ.get('GROQ_API_KEY') or 'your-groq-api-key')
MODEL = "llama-3.3-70b-versatile"

SYLLABUS_SYSTEM_PROMPT = """You are an expert academic syllabus analyzer called the "Syllabus-to-Success Engine".

Your job is to extract structured information from university course syllabi and generate a complete semester study plan.

CRITICAL RULES:
1. Return ONLY valid JSON. No markdown, no explanations, no code blocks.
2. Never invent assignments or exams that are not mentioned.
3. If a date is ambiguous, set "confidence": "low" on that item.
4. All dates must be in YYYY-MM-DD format or null if unknown.
5. Generate exactly the number of weeks specified.
"""

def analyze_syllabus(text: str, semester_length: int = 15, start_date=None) -> str:
    """
    Two-pass analysis:
    Pass 1: Extract raw facts (assignments, exams, topics, dates)
    Pass 2: Generate structured study plan
    Returns JSON string.
    """
    start_str = start_date.isoformat() if start_date else "unknown"

    pass1_prompt = f"""Analyze this syllabus text and extract ALL facts.

SYLLABUS TEXT:
{text[:8000]}

Extract EVERY:
- Assignment (name + due date if mentioned)
- Quiz or exam (name + date if mentioned)  
- Topic or module listed
- Reading assignment
- Important deadline

Return JSON with this exact structure:
{{
  "course_information": {{
    "course_title": "",
    "instructor": "",
    "grading_policy": ""
  }},
  "raw_assignments": [
    {{"title": "", "due_date": null, "description": "", "confidence": "high|medium|low"}}
  ],
  "raw_exams": [
    {{"name": "", "date": null, "type": "quiz|midterm|final", "confidence": "high|medium|low"}}
  ],
  "raw_topics": ["topic1", "topic2"],
  "raw_readings": ["reading1"],
  "semester_length_detected": {semester_length}
}}

Course start date is: {start_str}
Return ONLY JSON."""

    pass1_response = _call_groq(pass1_prompt)
    facts = _safe_parse(pass1_response)

    pass2_prompt = f"""You have extracted these facts from a {semester_length}-week course syllabus:

EXTRACTED FACTS:
{json.dumps(facts, indent=2)}

Course start date: {start_str}
Semester length: {semester_length} weeks

Now generate a complete structured study plan.

Return JSON with this exact structure:
{{
  "course_information": {{
    "course_title": "",
    "instructor": "",
    "grading_policy": ""
  }},
  "weekly_plan": [
    {{
      "week_number": 1,
      "topics": ["topic1"],
      "key_concepts": ["concept1"],
      "difficulty": "easy|medium|hard",
      "study_hours": 6,
      "readings": ["Chapter 1"],
      "assignments": [
        {{
          "title": "Assignment Name",
          "due_date": "YYYY-MM-DD or null",
          "estimated_hours": 3,
          "preparation_steps": ["step1", "step2"],
          "confidence": "high|medium|low"
        }}
      ],
      "revision_tasks": ["Review lecture notes", "Practice problems"],
      "study_advice": "Hey! This week you'll tackle [topics]. Focus on [key concept] early...",
      "is_exam_week": false
    }}
  ],
  "assignments": [
    {{
      "title": "",
      "due_date": "YYYY-MM-DD or null",
      "week_number": 1,
      "estimated_hours": 2,
      "confidence": "high|medium|low"
    }}
  ],
  "exams": [
    {{
      "name": "",
      "exam_date": "YYYY-MM-DD or null",
      "type": "quiz|midterm|final",
      "coverage_weeks": [1, 2, 3],
      "preparation_plan": "Start reviewing Week 1-3 material 5 days before...",
      "confidence": "high|medium|low"
    }}
  ]
}}

RULES:
- Generate EXACTLY {semester_length} weeks
- Distribute topics logically across weeks
- study_advice must sound like friendly study buddy "Kai" speaking to the student
- Mark is_exam_week: true for weeks containing exams
- If dates are unknown, set them to null
- Return ONLY JSON"""

    pass2_response = _call_groq(pass2_prompt)
    return pass2_response


def chat_with_assistant(system_prompt: str, messages: list) -> str:
    """Chat with the AI study assistant."""
    groq_messages = [{'role': 'system', 'content': system_prompt}] + messages
    response = client.chat.completions.create(
        model=MODEL,
        messages=groq_messages,
        max_tokens=1000,
        temperature=0.7
    )
    return response.choices[0].message.content


def _call_groq(prompt: str, temperature: float = 0.2) -> str:
    """Single Groq API call."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {'role': 'system', 'content': SYLLABUS_SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt}
        ],
        max_tokens=4000,
        temperature=temperature
    )
    return response.choices[0].message.content


def _safe_parse(text: str) -> dict:
    """Safely parse JSON from AI response."""
    text = text.strip()
    # Remove markdown code blocks if present
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON within the text
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return {}
