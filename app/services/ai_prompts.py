
def build_lesson_prompt(age:int, topic:str, objectives:list, aspects:list, activities:list, images:list, subject: str = None):
    """Build an optimized, concise prompt for faster generation"""
    # Format: SUBJECT (all caps) then Topic
    subject_title = (subject or "GENERAL").upper()
    
    # Limit items for faster generation
    obj_lines = "\n".join([f"• {o}" for o in objectives[:5]]) if objectives else "• Understand key concepts\n• Apply knowledge"
    aspects_lines = "\n".join([f"• {a}" for a in aspects[:4]]) if aspects else "• Core concepts\n• Examples"
    activities_lines = "\n".join([f"• {a}" for a in activities[:3]]) if activities else "• Practical exercises"

    # More concise prompt for faster generation
    prompt = f"""Create a lesson for {age}-year-olds:

{subject_title}
{topic}

Objectives
By the end of this lesson, you should be able to:
{obj_lines}

[For each concept, include:]
[Concept Name]
[Brief description]
Uses of [Concept Name]
[Key uses]

{aspects_lines}

Activity 1
{activities_lines}

Format: ALL CAPS subject, topic, Objectives, concepts with Uses, Activity. British English. Write to students directly."""
    
    return prompt

def build_custom_lesson_prompt(custom_prompt, topic, age, subject=None):
    subject_title = (subject or "GENERAL").upper() if subject else "GENERAL"
    prompt = f"""Create a lesson following this EXACT format:

{subject_title}
{topic}

Objectives
By the end of this lesson, you should be able to:
[List objectives based on: {custom_prompt}]

[For each main concept, include:]
[Concept Name]
[Description]
Uses of [Concept Name]
[Uses list]

Activity 1
[Activity description]

CRITICAL: Follow the format exactly - ALL CAPS subject title, then topic, then Objectives section, then concepts with Uses subsections, then Activities. Use British English. Write directly to students."""
    return prompt

def build_activity_question_prompt(topic: str, subject: str, age_range: dict, grade_range: dict, ability_levels: list, question_type: str, num_questions: int):
    """Build prompt for generating activity questions using Ollama"""
    parts = []
    
    # Header
    header = f"Create {num_questions} activity questions for students on the topic: \"{topic}\""
    if subject:
        header += f" in the subject of {subject}"
    parts.append(header)
    
    # Student range specifications
    range_specs = []
    if age_range and age_range.get('min_age') and age_range.get('max_age'):
        range_specs.append(f"Age range: {age_range['min_age']}-{age_range['max_age']} years old")
    if grade_range and grade_range.get('min_grade') and grade_range.get('max_grade'):
        range_specs.append(f"Grade range: Grade {grade_range['min_grade']}-{grade_range['max_grade']}")
    if ability_levels:
        levels_str = ", ".join(ability_levels)
        range_specs.append(f"Ability levels: {levels_str}")
    
    if range_specs:
        parts.append("\n\nStudent specifications:\n" + "\n".join([f"• {s}" for s in range_specs]))
    
    # Question type
    question_type_map = {
        'multiple_choice': 'multiple choice questions with 4 options each',
        'short_answer': 'short answer questions (1-2 sentences)',
        'essay': 'essay questions requiring detailed responses',
        'mixed': 'a mix of question types (multiple choice, short answer, and essay)'
    }
    qtype_desc = question_type_map.get(question_type, 'mixed questions')
    parts.append(f"\n\nQuestion type: {qtype_desc}")
    
    # Format requirements
    parts.append("\n\nFormat the output clearly with:")
    parts.append("• Question number and question text")
    if question_type in ['multiple_choice', 'mixed']:
        parts.append("• For multiple choice: List options A, B, C, D and indicate the correct answer")
    if question_type in ['essay', 'mixed']:
        parts.append("• For essay questions: Include suggested marking criteria or key points")
    parts.append("\nUse British English spelling and terminology.")
    
    return "\n".join(parts)
