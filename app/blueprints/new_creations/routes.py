import json
import time
import requests
from flask import Response, current_app, flash, jsonify, redirect, render_template, request, stream_with_context, url_for
from flask_login import current_user, login_required

from app import db
from app.blueprints.new_creations import bp
from app.blueprints.new_creations.models import Curriculum, Grade, Subject, TopicLesson
from app.services.llm_service import LLMService


def _is_admin():
    return current_user.userRole == "Admin"


def _wants_json():
    return request.is_json or request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def _admin_denied_response():
    message = "Only admins can perform this action."
    if _wants_json():
        return jsonify({"error": message}), 403
    flash(message, "error")
    return redirect(url_for("new_creations.index"))


def _can_manage_topic(topic):
    return _is_admin() or topic.created_by == current_user.id


def _extract_prompt_inputs():
    payload = request.get_json(silent=True) or {}
    if not request.is_json:
        payload = request.form.to_dict()
    objectives = (payload.get("objectives") or "").strip()
    detailed_objectives = (payload.get("detailed_objectives") or "").strip()
    return objectives, detailed_objectives


def _normalize_provider_name(value):
    if not value:
        return None
    p = str(value).strip().lower()
    if p in ("ollama", "gemini", "openai"):
        return p
    return None


def _extract_provider_override():
    if request.method == "GET":
        return _normalize_provider_name(request.args.get("provider"))
    payload = request.get_json(silent=True) or {}
    if not request.is_json:
        payload = request.form.to_dict()
    return _normalize_provider_name(payload.get("provider"))


def _effective_generation_provider(override=None):
    return override or _normalize_provider_name(_get_generation_provider()) or "ollama"


def _build_master_prompt(topic, objectives, detailed_objectives):
    grade_name = topic.subject.grade.name
    lesson_topic = topic.title
    return f"""**ROLE AND CONTEXT**
You are a top 1% primary school curriculum strategist and textbook author. Your task is to produce a structured, learner-facing lesson for the specified grade. Develop this for Zimbabwean students using formal British English language. The output must be professional, concise, and implementation-focused, strictly following the national syllabus.

**SYLLABUS INPUT** (paste syllabus data below)
Grade
{grade_name}
Key Concept
{lesson_topic}

Objectives
{objectives}

Content List
{detailed_objectives}

Suggested Activities
Generate questions based on detailed objectives

**STRICT COMPLIANCE PROTOCOLS**
1. **Closed-World Assumption**: Use only the inputs provided above. Do not introduce outside historical figures, advanced scientific theories, or commercial practices not listed in the syllabus.
2. **Linguistic Standard**: Use formal British English.
3. **Contextual Accuracy**: All examples must be practical, observable, and reflect Zimbabwean or African contexts.
4. **Formatting & Style**: Follow the exact structure, tone, and depth shown in the example below. Use clear section numbering, integrated activities, and learner-friendly language.

**OUTPUT FORMAT (MANDATORY – follow this exact structure)**

**Lesson Title**
A clear, syllabus-aligned title.

**Objectives**
“By the end of this lesson, you should be able to:” followed by the syllabus objectives exactly as written in the input, each on a new line with a dash.

**Introduction**
One short paragraph (3–4 sentences) linking the topic to daily student life. Use a friendly, curious tone. End with a sentence explaining why the topic matters.

**1. [First core content heading]**
- Write 3–4 short sentences in bullet form (using `•`). Each bullet should include a topic sentence, an explanation, and an example where possible.
- After the bullet list, insert an image reference in italics:
  *Fig X: [One-sentence description of what the image shows. Keep it simple and suitable for children. Do not describe camera shots or technical composition.]*
- Then immediately add **Activities for Section X (to be completed on your own)** with numbered tasks. Activities must be practical, low-resource, and based on the syllabus’s “Suggested Activities”. Include at least two tasks per activity.

**2. [Second core content heading]**
- For each sub-item:
  - Write 3–4 bullet points as described above.
  - After the sub-item, insert an image reference (Fig X) if appropriate.
- After covering all sub-items, add **Activities for Section X** with at least two practical tasks.

**3. [Third core content heading]**
- For each sub-item write 3–4 bullet points as above.
- After the sub-items, add an image reference.
- Then add **Activities for Section X** with at least two tasks.

**Assessment Task**
One summative task that requires learners to apply knowledge from the whole lesson. Use a real-world scenario. Write clear, step-by-step instructions.

**Do NOT include** a “Suggested Resources” section unless the syllabus input explicitly requires it.
"""


def _call_openai(prompt_text):
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        return None, "OPENAI_API_KEY is not configured."

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": current_app.config.get("OPENAI_MODEL", "gpt-4.1-mini"),
                "input": prompt_text,
            },
            timeout=60,
        )
        if response.status_code >= 400:
            error_message = ""
            try:
                error_payload = response.json() or {}
                error_message = str((error_payload.get("error") or {}).get("message") or "").lower()
            except ValueError:
                error_message = ""

            if response.status_code == 401:
                return None, "Generation provider authentication failed. Please check OPENAI_API_KEY."
            if response.status_code == 403:
                return None, "Generation provider access denied for the configured model."
            if response.status_code == 429:
                if "quota" in error_message or "billing" in error_message:
                    return None, "Generation provider quota exceeded. Please check OpenAI billing/usage and retry."
                return None, "Generation provider rate limit reached. Please retry shortly."
            if response.status_code >= 500:
                return None, "Generation provider is currently unavailable. Please retry."
            return None, "Generation provider returned an error."
        data = response.json()
        output_text = data.get("output_text")
        if output_text:
            return output_text, None
        # Fallback for cases where output_text is absent
        return str(data), None
    except requests.RequestException:
        return None, "Unable to reach generation provider."


def _call_ollama(prompt_text):
    model = current_app.config.get("OLLAMA_CONTENT_MODEL") or current_app.config.get("OLLAMA_MODEL", "llama3.1")
    try:
        llm = LLMService()
        options = {
            "temperature": float(current_app.config.get("OLLAMA_TEMPERATURE", 0.2)),
            "num_predict": int(current_app.config.get("OLLAMA_NUM_PREDICT", 900)),
        }
        output = llm.generate_chat(
            model=model,
            messages=[{"role": "user", "content": prompt_text}],
            options=options,
            timeout=120,
        )
        if not output:
            return None, "Ollama returned an empty response."
        return output, None
    except Exception as exc:
        message = str(exc)
        if "not found" in message.lower() and "model" in message.lower():
            available_models = []
            try:
                available_models = LLMService().list_models()
            except Exception:
                available_models = []
            if available_models:
                return None, f"Ollama model '{model}' was not found. Available models: {', '.join(available_models[:8])}."
            return None, f"Ollama model '{model}' was not found. Pull it first or change OLLAMA_MODEL."
        return None, "Unable to generate via Ollama. Check OLLAMA_BASE_URL and selected model."


def _get_generation_provider():
    return (current_app.config.get("GENERATION_PROVIDER", "ollama") or "ollama").strip().lower()


def _call_gemini(prompt_text):
    api_key = current_app.config.get("GEMINI_API_KEY")
    model = current_app.config.get("GEMINI_MODEL", "gemini-2.0-flash")
    if not api_key:
        return None, "GEMINI_API_KEY is not configured."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        response = requests.post(
            url,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt_text}]}],
                "generationConfig": {
                    "temperature": float(current_app.config.get("GEMINI_TEMPERATURE", 0.2)),
                    "maxOutputTokens": int(current_app.config.get("GEMINI_MAX_OUTPUT_TOKENS", 8192)),
                },
            },
            timeout=120,
        )
        if response.status_code >= 400:
            err_msg = "Gemini request failed."
            try:
                body = response.json() or {}
                err_msg = str((body.get("error") or {}).get("message") or err_msg)
            except ValueError:
                pass
            if response.status_code == 401 or response.status_code == 403:
                return None, "Gemini authentication failed. Check GEMINI_API_KEY and API access."
            if response.status_code == 429:
                return None, "Gemini rate limit or quota exceeded. Retry later or check billing."
            return None, err_msg[:500]
        data = response.json() or {}
        candidates = data.get("candidates") or []
        if not candidates:
            return None, "Gemini returned no candidates."
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join((p.get("text") or "") for p in parts if isinstance(p, dict))
        if not text.strip():
            return None, "Gemini returned an empty response."
        return text, None
    except requests.RequestException:
        return None, "Unable to reach Gemini API."


def _call_generation_provider(prompt_text, provider_override=None):
    provider = _effective_generation_provider(provider_override)
    if provider == "ollama":
        return _call_ollama(prompt_text)
    if provider == "gemini":
        return _call_gemini(prompt_text)
    return _call_openai(prompt_text)


@bp.route("/new-creations/ai-connection-test", methods=["GET"])
@login_required
def test_ai_connection():
    provider = _effective_generation_provider(_extract_provider_override())

    if provider == "ollama":
        model = current_app.config.get("OLLAMA_MODEL", "llama3.1")
        try:
            llm = LLMService()
            available_models = llm.list_models()
            output = llm.generate_chat(
                model=model,
                messages=[{"role": "user", "content": "Connection test. Reply with OK."}],
                options={"temperature": 0},
                timeout=30,
            )
            if not output:
                return jsonify({"ok": False, "error": "Ollama returned empty response.", "provider": provider, "model": model}), 503
            return jsonify({
                "ok": True,
                "message": "Ollama connection is healthy.",
                "provider": provider,
                "model": model,
                "available_models": available_models,
            })
        except Exception:
            return jsonify({
                "ok": False,
                "error": "Unable to reach Ollama. Verify OLLAMA_BASE_URL and that the model is pulled.",
                "provider": provider,
                "model": model,
            }), 503

    if provider == "gemini":
        model = current_app.config.get("GEMINI_MODEL", "gemini-2.0-flash")
        api_key = current_app.config.get("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"ok": False, "error": "GEMINI_API_KEY is not configured.", "provider": provider, "model": model}), 503
        out, err = _call_gemini("Reply with the single word OK.")
        if err:
            return jsonify({"ok": False, "error": err, "provider": provider, "model": model}), 503
        return jsonify({
            "ok": True,
            "message": "Gemini connection is healthy.",
            "provider": provider,
            "model": model,
            "preview": (out or "")[:80],
        })

    api_key = current_app.config.get("OPENAI_API_KEY")
    model = current_app.config.get("OPENAI_MODEL", "gpt-4.1-mini")
    if not api_key:
        return jsonify({"ok": False, "error": "OPENAI_API_KEY is not configured.", "provider": provider, "model": model}), 503

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": "Connection test. Reply with OK.",
                "max_output_tokens": 8,
            },
            timeout=20,
        )
        if response.status_code < 400:
            return jsonify({"ok": True, "message": "OpenAI connection is healthy.", "provider": provider, "model": model})

        error_message = ""
        try:
            payload = response.json() or {}
            error_message = str((payload.get("error") or {}).get("message") or "")
        except ValueError:
            error_message = ""

        if response.status_code == 401:
            return jsonify({"ok": False, "error": "Authentication failed. Check OPENAI_API_KEY.", "provider": provider, "model": model}), 503
        if response.status_code == 403:
            return jsonify({"ok": False, "error": "Access denied for configured model.", "provider": provider, "model": model}), 503
        if response.status_code == 429:
            lowered = error_message.lower()
            if "quota" in lowered or "billing" in lowered:
                return jsonify({"ok": False, "error": "Quota exceeded. Check OpenAI billing/usage.", "provider": provider, "model": model}), 503
            return jsonify({"ok": False, "error": "Rate limited. Retry shortly.", "provider": provider, "model": model}), 503
        if response.status_code >= 500:
            return jsonify({"ok": False, "error": "OpenAI service unavailable. Retry shortly.", "provider": provider, "model": model}), 503
        return jsonify({"ok": False, "error": "Provider returned an error.", "provider": provider, "model": model}), 503
    except requests.RequestException:
        return jsonify({"ok": False, "error": "Unable to reach OpenAI endpoint.", "provider": provider, "model": model}), 503


@bp.route("/new-creations", methods=["GET"])
@login_required
def index():
    curriculums = Curriculum.query.order_by(Curriculum.name.asc()).all()
    return render_template("new_creations/index.html", title="New Creations", curriculums=curriculums)


@bp.route("/new-creations/curriculums/<int:curriculum_id>", methods=["GET"])
@login_required
def curriculum_detail(curriculum_id):
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    grades = Grade.query.filter_by(curriculum_id=curriculum.id).order_by(Grade.name.asc()).all()
    return render_template(
        "new_creations/curriculum_detail.html",
        title=f"Curriculum - {curriculum.name}",
        curriculum=curriculum,
        grades=grades,
    )


@bp.route("/new-creations/grades/<int:grade_id>", methods=["GET"])
@login_required
def grade_detail(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    subjects = Subject.query.filter_by(grade_id=grade.id).order_by(Subject.name.asc()).all()
    return render_template("new_creations/grade_detail.html", title=f"Grade - {grade.name}", grade=grade, subjects=subjects)


@bp.route("/new-creations/subjects/<int:subject_id>", methods=["GET"])
@login_required
def subject_detail(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    topics = TopicLesson.query.filter_by(subject_id=subject.id).order_by(TopicLesson.id.desc()).all()
    return render_template("new_creations/subject_detail.html", title=f"Subject - {subject.name}", subject=subject, topics=topics)


@bp.route("/curriculums", methods=["GET"])
@login_required
def get_curriculums():
    curriculums = Curriculum.query.order_by(Curriculum.name.asc()).all()
    return jsonify(
        {
            "curriculums": [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "created_by": c.created_by,
                }
                for c in curriculums
            ]
        }
    )


@bp.route("/curriculums", methods=["POST"])
@login_required
def create_curriculum():
    if not _is_admin():
        return _admin_denied_response()

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        name = (payload.get("name") or name).strip()
        description = (payload.get("description") or description).strip()

    if not name:
        if _wants_json():
            return jsonify({"error": "Curriculum name is required."}), 400
        flash("Curriculum name is required.", "error")
        return redirect(url_for("new_creations.index"))

    if Curriculum.query.filter_by(name=name).first():
        if _wants_json():
            return jsonify({"error": "Curriculum name already exists."}), 400
        flash("Curriculum name already exists.", "error")
        return redirect(url_for("new_creations.index"))

    curriculum = Curriculum(name=name, description=description or None, created_by=current_user.id)
    db.session.add(curriculum)
    db.session.commit()

    if _wants_json():
        return jsonify({"message": "Curriculum created.", "id": curriculum.id}), 201
    flash("Curriculum created successfully.", "success")
    return redirect(url_for("new_creations.index"))


@bp.route("/curriculums/<int:curriculum_id>", methods=["PUT", "POST"])
@login_required
def update_curriculum(curriculum_id):
    if not _is_admin():
        return _admin_denied_response()

    curriculum = Curriculum.query.get_or_404(curriculum_id)
    payload = request.get_json(silent=True) or {}
    if not request.is_json:
        payload = request.form.to_dict()

    name = (payload.get("name") or curriculum.name).strip()
    description = payload.get("description")
    if description is None:
        description = curriculum.description
    else:
        description = description.strip() or None

    if not name:
        return jsonify({"error": "Curriculum name is required."}), 400

    duplicate = Curriculum.query.filter(Curriculum.name == name, Curriculum.id != curriculum.id).first()
    if duplicate:
        return jsonify({"error": "Another curriculum already uses that name."}), 400

    curriculum.name = name
    curriculum.description = description
    db.session.commit()
    return jsonify({"message": "Curriculum updated."})


@bp.route("/curriculums/<int:curriculum_id>/delete", methods=["POST"])
@login_required
def delete_curriculum_form(curriculum_id):
    if not _is_admin():
        return _admin_denied_response()
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    db.session.delete(curriculum)
    db.session.commit()
    flash("Curriculum deleted.", "success")
    return redirect(url_for("new_creations.index"))


@bp.route("/curriculums/<int:curriculum_id>", methods=["DELETE"])
@login_required
def delete_curriculum(curriculum_id):
    if not _is_admin():
        return jsonify({"error": "Only admins can perform this action."}), 403
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    db.session.delete(curriculum)
    db.session.commit()
    return jsonify({"message": "Curriculum deleted."})


@bp.route("/curriculums/<int:curriculum_id>/grades", methods=["GET"])
@login_required
def get_grades(curriculum_id):
    Curriculum.query.get_or_404(curriculum_id)
    grades = Grade.query.filter_by(curriculum_id=curriculum_id).order_by(Grade.name.asc()).all()
    return jsonify({"grades": [{"id": g.id, "name": g.name, "curriculum_id": g.curriculum_id} for g in grades]})


@bp.route("/grades", methods=["POST"])
@login_required
def create_grade():
    if not _is_admin():
        return _admin_denied_response()

    payload = request.get_json(silent=True) or {}
    if not request.is_json:
        payload = request.form.to_dict()

    name = (payload.get("name") or "").strip()
    curriculum_id = payload.get("curriculum_id")
    if not name or not curriculum_id:
        error = "Both name and curriculum_id are required."
        if _wants_json():
            return jsonify({"error": error}), 400
        flash(error, "error")
        return redirect(url_for("new_creations.index"))

    curriculum = Curriculum.query.get(curriculum_id)
    if not curriculum:
        return jsonify({"error": "Curriculum not found."}), 404

    grade = Grade(name=name, curriculum_id=curriculum.id)
    db.session.add(grade)
    db.session.commit()

    if _wants_json():
        return jsonify({"message": "Grade created.", "id": grade.id}), 201
    flash("Grade created.", "success")
    return redirect(url_for("new_creations.curriculum_detail", curriculum_id=curriculum.id))


@bp.route("/grades/<int:grade_id>/subjects", methods=["GET"])
@login_required
def get_subjects(grade_id):
    Grade.query.get_or_404(grade_id)
    subjects = Subject.query.filter_by(grade_id=grade_id).order_by(Subject.name.asc()).all()
    return jsonify({"subjects": [{"id": s.id, "name": s.name, "grade_id": s.grade_id} for s in subjects]})


@bp.route("/subjects", methods=["POST"])
@login_required
def create_subject():
    if not _is_admin():
        return _admin_denied_response()

    payload = request.get_json(silent=True) or {}
    if not request.is_json:
        payload = request.form.to_dict()

    name = (payload.get("name") or "").strip()
    grade_id = payload.get("grade_id")
    if not name or not grade_id:
        error = "Both name and grade_id are required."
        if _wants_json():
            return jsonify({"error": error}), 400
        flash(error, "error")
        return redirect(url_for("new_creations.index"))

    grade = Grade.query.get(grade_id)
    if not grade:
        return jsonify({"error": "Grade not found."}), 404

    subject = Subject(name=name, grade_id=grade.id)
    db.session.add(subject)
    db.session.commit()

    if _wants_json():
        return jsonify({"message": "Subject created.", "id": subject.id}), 201
    flash("Subject created.", "success")
    return redirect(url_for("new_creations.grade_detail", grade_id=grade.id))


@bp.route("/subjects/<int:subject_id>/topics", methods=["GET"])
@login_required
def get_topics(subject_id):
    Subject.query.get_or_404(subject_id)
    topics = TopicLesson.query.filter_by(subject_id=subject_id).order_by(TopicLesson.id.desc()).all()
    return jsonify(
        {
            "topics": [
                {
                    "id": t.id,
                    "title": t.title,
                    "subject_id": t.subject_id,
                    "content": t.content,
                    "questions": t.questions,
                    "objectives": t.objectives,
                    "detailed_objectives": t.detailed_objectives,
                }
                for t in topics
            ]
        }
    )


@bp.route("/topics", methods=["POST"])
@login_required
def create_topic():
    payload = request.get_json(silent=True) or {}
    if not request.is_json:
        payload = request.form.to_dict()

    title = (payload.get("title") or "").strip()
    subject_id = payload.get("subject_id")
    if not title or not subject_id:
        error = "Both title and subject_id are required."
        if _wants_json():
            return jsonify({"error": error}), 400
        flash(error, "error")
        return redirect(url_for("new_creations.index"))

    subject = Subject.query.get(subject_id)
    if not subject:
        return jsonify({"error": "Subject not found."}), 404

    topic = TopicLesson(title=title, subject_id=subject.id, created_by=current_user.id)
    db.session.add(topic)
    db.session.commit()

    if _wants_json():
        return jsonify({"message": "Topic lesson created.", "id": topic.id}), 201
    flash("Topic lesson created.", "success")
    return redirect(url_for("new_creations.subject_detail", subject_id=subject.id))


@bp.route("/topics/<int:topic_id>", methods=["PUT", "POST"])
@login_required
def update_topic(topic_id):
    topic = TopicLesson.query.get_or_404(topic_id)
    if not _can_manage_topic(topic):
        if _wants_json():
            return jsonify({"error": "Only the topic creator or an admin can edit this topic."}), 403
        flash("Only the topic creator or an admin can edit this topic.", "error")
        return redirect(url_for("new_creations.subject_detail", subject_id=topic.subject_id))

    payload = request.get_json(silent=True) or {}
    if not request.is_json:
        payload = request.form.to_dict()
    title = payload.get("title")
    content = payload.get("content")
    questions = payload.get("questions")
    objectives = payload.get("objectives")
    detailed_objectives = payload.get("detailed_objectives")

    if title is not None:
        title = title.strip()
        if not title:
            if _wants_json():
                return jsonify({"error": "Title cannot be empty."}), 400
            flash("Title cannot be empty.", "error")
            return redirect(url_for("new_creations.subject_detail", subject_id=topic.subject_id))
        topic.title = title
    if content is not None:
        topic.content = content
    if questions is not None:
        topic.questions = questions
    if objectives is not None:
        topic.objectives = objectives
    if detailed_objectives is not None:
        topic.detailed_objectives = detailed_objectives

    db.session.commit()
    if _wants_json():
        return jsonify({"message": "Topic lesson updated."})
    flash("Topic lesson updated.", "success")
    return redirect(url_for("new_creations.subject_detail", subject_id=topic.subject_id))


@bp.route("/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
def delete_topic_form(topic_id):
    topic = TopicLesson.query.get_or_404(topic_id)
    subject_id = topic.subject_id
    if not _can_manage_topic(topic):
        flash("Only the topic creator or an admin can delete this topic.", "error")
        return redirect(url_for("new_creations.subject_detail", subject_id=subject_id))
    db.session.delete(topic)
    db.session.commit()
    flash("Topic lesson deleted.", "success")
    return redirect(url_for("new_creations.subject_detail", subject_id=subject_id))


@bp.route("/topics/<int:topic_id>", methods=["DELETE"])
@login_required
def delete_topic(topic_id):
    topic = TopicLesson.query.get_or_404(topic_id)
    if not _can_manage_topic(topic):
        return jsonify({"error": "Only the topic creator or an admin can delete this topic."}), 403
    db.session.delete(topic)
    db.session.commit()
    return jsonify({"message": "Topic lesson deleted."})


@bp.route("/topics/<int:topic_id>/generate-content", methods=["POST"])
@login_required
def generate_content(topic_id):
    topic = TopicLesson.query.get_or_404(topic_id)
    if not topic.subject or not topic.subject.grade:
        return jsonify({"error": "Topic grade context not found."}), 404
    objectives, detailed_objectives = _extract_prompt_inputs()
    if not objectives or not detailed_objectives:
        error = "Objectives and detailed objectives are required before generation."
        if _wants_json():
            return jsonify({"error": error}), 400
        flash(error, "error")
        return redirect(url_for("new_creations.subject_detail", subject_id=topic.subject_id))

    topic.objectives = objectives
    topic.detailed_objectives = detailed_objectives
    prompt_used = _build_master_prompt(topic, objectives, detailed_objectives)
    generated_text, generation_error = _call_generation_provider(
        prompt_used, provider_override=_extract_provider_override()
    )
    if generation_error:
        if _wants_json():
            return jsonify({"error": generation_error}), 503
        flash(generation_error, "error")
        return redirect(url_for("new_creations.subject_detail", subject_id=topic.subject_id))

    topic.content = generated_text
    db.session.commit()
    if _wants_json():
        return jsonify({"message": "Content generated.", "content": topic.content, "prompt_used": prompt_used})
    flash("Content generated successfully.", "success")
    return redirect(url_for("new_creations.subject_detail", subject_id=topic.subject_id))


@bp.route("/topics/<int:topic_id>/generate-content-stream", methods=["POST"])
@login_required
def generate_content_stream(topic_id):
    topic = TopicLesson.query.get_or_404(topic_id)
    if not topic.subject or not topic.subject.grade:
        return jsonify({"error": "Topic grade context not found."}), 404

    objectives, detailed_objectives = _extract_prompt_inputs()
    if not objectives or not detailed_objectives:
        return jsonify({"error": "Objectives and detailed objectives are required before generation."}), 400

    topic.objectives = objectives
    topic.detailed_objectives = detailed_objectives
    db.session.commit()

    body = request.get_json(silent=True) or {}
    provider = _effective_generation_provider(_normalize_provider_name(body.get("provider")))

    prompt_used = _build_master_prompt(topic, objectives, detailed_objectives)
    model = current_app.config.get("OLLAMA_CONTENT_MODEL") or current_app.config.get("OLLAMA_MODEL", "llama3.1")
    target_chars = int(current_app.config.get("GENERATION_PROGRESS_TARGET_CHARS", 2600))
    options = {
        "temperature": float(current_app.config.get("OLLAMA_TEMPERATURE", 0.2)),
        "num_predict": int(current_app.config.get("OLLAMA_NUM_PREDICT", 900)),
    }

    def _emit(payload):
        return json.dumps(payload) + "\n"

    @stream_with_context
    def generate():
        if provider == "gemini":
            try:
                yield _emit({"type": "progress", "percent": 10, "eta_seconds": None, "message": "Calling Gemini..."})
                text, err = _call_gemini(prompt_used)
                if err:
                    yield _emit({"type": "error", "error": err})
                    return
                yield _emit({"type": "progress", "percent": 85, "eta_seconds": 2, "message": "Saving response..."})
                topic.content = text
                db.session.commit()
                yield _emit({"type": "complete", "percent": 100, "eta_seconds": 0, "message": "Content generated successfully."})
            except Exception:
                yield _emit({"type": "error", "error": "Gemini generation failed."})
            return

        if provider != "ollama":
            yield _emit({"type": "error", "error": "Streaming for this action is only wired for Ollama or Gemini. Use non-stream generate or switch provider."})
            return

        started = time.time()
        full_content = ""
        yielded_once = False
        try:
            llm = LLMService()
            yield _emit({"type": "progress", "percent": 3, "eta_seconds": None, "message": "Starting generation..."})
            for raw_line in llm.generate_chat_stream(
                model=model,
                messages=[{"role": "user", "content": prompt_used}],
                options=options,
                timeout=(30, None),
            ):
                if not raw_line:
                    continue

                try:
                    if isinstance(raw_line, bytes):
                        chunk = json.loads(raw_line.decode("utf-8"))
                    else:
                        chunk = json.loads(raw_line)
                except Exception:
                    continue

                piece = ""
                if isinstance(chunk.get("message"), dict):
                    piece = chunk["message"].get("content") or ""
                elif chunk.get("response"):
                    piece = chunk.get("response") or ""

                if piece:
                    yielded_once = True
                    full_content += piece
                    elapsed = max(time.time() - started, 0.2)
                    chars_done = len(full_content)
                    chars_per_sec = max(chars_done / elapsed, 1.0)
                    remaining_chars = max(target_chars - chars_done, 0)
                    eta_seconds = int(remaining_chars / chars_per_sec) if remaining_chars > 0 else 0
                    percent = min(98, max(5, int((chars_done / max(target_chars, 1)) * 100)))
                    yield _emit({
                        "type": "progress",
                        "percent": percent,
                        "eta_seconds": eta_seconds,
                        "chars_generated": chars_done,
                    })

                if chunk.get("done"):
                    break

            if not yielded_once or not full_content.strip():
                yield _emit({"type": "error", "error": "Ollama returned an empty response."})
                return

            topic.content = full_content
            db.session.commit()
            yield _emit({
                "type": "complete",
                "percent": 100,
                "eta_seconds": 0,
                "message": "Content generated successfully.",
            })
        except Exception as exc:
            message = str(exc)
            if "not found" in message.lower() and "model" in message.lower():
                try:
                    available_models = LLMService().list_models()
                except Exception:
                    available_models = []
                if available_models:
                    yield _emit({"type": "error", "error": f"Ollama model '{model}' was not found. Available models: {', '.join(available_models[:8])}."})
                    return
                yield _emit({"type": "error", "error": f"Ollama model '{model}' was not found."})
                return
            yield _emit({"type": "error", "error": "Unable to generate via Ollama. Check OLLAMA_BASE_URL and selected model."})

    return Response(generate(), mimetype="application/x-ndjson")


@bp.route("/topics/<int:topic_id>/generate-questions", methods=["POST"])
@login_required
def generate_questions(topic_id):
    topic = TopicLesson.query.get_or_404(topic_id)
    if not topic.subject or not topic.subject.grade:
        return jsonify({"error": "Topic grade context not found."}), 404
    objectives, detailed_objectives = _extract_prompt_inputs()
    if not objectives or not detailed_objectives:
        error = "Objectives and detailed objectives are required before generation."
        if _wants_json():
            return jsonify({"error": error}), 400
        flash(error, "error")
        return redirect(url_for("new_creations.subject_detail", subject_id=topic.subject_id))

    topic.objectives = objectives
    topic.detailed_objectives = detailed_objectives
    prompt_used = _build_master_prompt(topic, objectives, detailed_objectives)
    generated_text, generation_error = _call_generation_provider(
        prompt_used, provider_override=_extract_provider_override()
    )
    if generation_error:
        if _wants_json():
            return jsonify({"error": generation_error}), 503
        flash(generation_error, "error")
        return redirect(url_for("new_creations.subject_detail", subject_id=topic.subject_id))

    topic.questions = generated_text
    db.session.commit()
    if _wants_json():
        return jsonify({"message": "Questions generated.", "questions": topic.questions, "prompt_used": prompt_used})
    flash("Questions generated successfully.", "success")
    return redirect(url_for("new_creations.subject_detail", subject_id=topic.subject_id))
