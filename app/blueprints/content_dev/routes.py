import os
import json
import requests
from flask import render_template, jsonify, request, Response, stream_with_context, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import User, Workspace, Lesson, ActivityQuestion, Project, Task, WorkspaceFile
from app.blueprints.content_dev import bp
from app.services.llm_service import LLMService
from app.services.ai_prompts import build_lesson_prompt, build_custom_lesson_prompt, build_activity_question_prompt

@bp.route('/content-development', methods=['GET'])
@login_required
def content_development():
    # Check if user is admin or has Content Development privilege
    if current_user.userRole != 'Admin' and not current_user.has_privilege('Content Development'):
        return "Unauthorized", 403
    return render_template('content_development.html', title='Content Development')


# -------- Content Development API --------
@bp.route('/api/ollama/models', methods=['GET'])
@login_required
def list_ollama_models():
    llm = LLMService()
    models = llm.list_models()
    return jsonify({'models': models})

# -------- End Content Development API --------

@bp.route('/api/lessons/<int:lesson_id>', methods=['GET'])
@login_required
def get_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    # Ensure user has access via membership
    ws = Workspace.query.get(lesson.workspace_id)
    if current_user not in ws.members:
        return jsonify({'error': 'Not authorized'}), 403
    return jsonify({
        'id': lesson.id,
        'workspace_id': lesson.workspace_id,
        'topic': lesson.topic,
        'subject': lesson.subject,
        'age': lesson.age,
        'content': lesson.content,
        'created_at': lesson.created_at.isoformat() if lesson.created_at else None
    })

@bp.route('/api/workspaces/<int:ws_id>', methods=['DELETE', 'PATCH'])
@login_required
def modify_workspace(ws_id):
    ws = Workspace.query.get_or_404(ws_id)
    # Only creator can modify/delete for now
    if ws.created_by != current_user.id:
        return jsonify({'error': 'Only the creator can modify or delete this workspace'}), 403

    if request.method == 'DELETE':
        db.session.delete(ws)
        db.session.commit()
        return jsonify({'status': 'deleted'})

    # PATCH
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    if name:
        ws.name = name
    # allow empty description to clear
    if 'description' in data:
        ws.description = description
    db.session.commit()
    return jsonify({'status': 'updated', 'workspace': {'id': ws.id, 'name': ws.name, 'description': ws.description or ''}})

@bp.route('/api/workspaces/mine', methods=['GET'])
@login_required
def workspaces_mine():
    # Workspaces where current user is a member
    wss = Workspace.query.join(Workspace.members).filter(User.id == current_user.id).order_by(Workspace.created_at.desc()).all()

    def file_to_dict(f):
        # make a URL-ish path for front-end anchors
        url_path = '/' + f.stored_path.replace('\\\\', '/').lstrip('/')
        return {
            'id': f.id,
            'name': f.original_name,
            'url': url_path,
            'uploaded_at': f.uploaded_at.isoformat() if f.uploaded_at else None
        }

    def lesson_to_dict(l):
        return {
            'id': l.id,
            'topic': l.topic,
            'age': l.age,
            'subject': l.subject,
            'created_at': l.created_at.isoformat() if l.created_at else None
        }
    
    def activity_question_to_dict(aq):
        return {
            'id': aq.id,
            'lesson_id': aq.lesson_id,
            'topic': aq.topic,
            'subject': aq.subject,
            'age_range': aq.age_range,
            'grade_range': aq.grade_range,
            'ability_levels': aq.ability_levels,
            'question_type': aq.question_type,
            'num_questions': aq.num_questions,
            'created_at': aq.created_at.isoformat() if aq.created_at else None
        }

    def tasks_for_workspace(ws_id):
        # Collect all tasks in all projects under this workspace
        projects = Project.query.filter_by(workspace_id=ws_id).all()
        project_ids = [p.id for p in projects]
        if not project_ids:
            return []
        all_tasks = Task.query.filter(Task.project_id.in_(project_ids)).all()
        by_parent = {}
        parents = []
        for t in all_tasks:
            if t.parent_id is None:
                parents.append(t)
            else:
                by_parent.setdefault(t.parent_id, []).append(t)
        result = []
        for p in parents:
            result.append({
                'id': p.id,
                'title': p.title,
                'status': p.status,
                'subtasks': [
                    {'id': c.id, 'title': c.title, 'status': c.status}
                    for c in by_parent.get(p.id, [])
                ]
            })
        return result

    data = []
    for ws in wss:
        files = [file_to_dict(f) for f in ws.files]
        lessons = [lesson_to_dict(l) for l in ws.lessons]
        activity_questions = [activity_question_to_dict(aq) for aq in ws.activity_questions]
        tasks = tasks_for_workspace(ws.id)
        data.append({
            'id': ws.id,
            'name': ws.name,
            'description': ws.description or '',
            'created_at': ws.created_at.isoformat() if ws.created_at else None,
            'files': files,
            'lessons': lessons,
            'activity_questions': activity_questions,
            'tasks': tasks
        })
    return jsonify({'workspaces': data})

@bp.route('/api/content-dev/bootstrap', methods=['GET'])
@login_required
def content_dev_bootstrap():
    # Allowed collaborators: all users where userRole != 'Brand Ambassador'
    allowed_users = User.query.filter(User.userRole != 'Brand Ambassador').order_by(User.firstname.asc()).all()

    # Workspaces where current user is a member
    member_ws = Workspace.query.join(Workspace.members).filter(User.id == current_user.id).order_by(Workspace.created_at.desc()).all()

    def ws_summary(ws):
        return { 'id': ws.id, 'name': ws.name }

    return jsonify({
        'collaborators': [
            {
                'id': u.id,
                'username': u.username,
                'name': f"{(u.firstname or '').strip()} {(u.lastname or '').strip()}".strip() or u.username
            } for u in allowed_users
        ],
        'workspaces': [ws_summary(w) for w in member_ws]
    })


@bp.route('/api/workspaces', methods=['POST'])
@login_required
def create_workspace_api():
    # Expect multipart/form-data
    subject = request.form.get('subject', '').strip()
    grade = request.form.get('grade', '').strip()
    term = request.form.get('term', '').strip()
    description = request.form.get('description', '').strip()
    collab_field = request.form.getlist('collaborators')
    if not collab_field:
        raw = request.form.get('collaborators', '')
        collab_field = [x for x in raw.split(',') if x] if raw else []

    tasks_json = request.form.get('tasks')
    try:
        tasks = json.loads(tasks_json) if tasks_json else []
    except Exception:
        tasks = []

    if not subject or not grade:
        return jsonify({'error': 'Subject and Grade are required'}), 400

    name = f"{subject} Grade {grade}"
    ws = Workspace(name=name, description=(term + ('\n' + description if description else '')) if term else description, created_by=current_user.id)
    db.session.add(ws)

    # Add members: current user + selected collaborators
    try:
        member_ids = {int(mid) for mid in collab_field if str(mid).isdigit()}
    except Exception:
        member_ids = set()
    # ensure current user is included
    member_ids.add(current_user.id)
    if member_ids:
        users = User.query.filter(User.id.in_(member_ids)).all()
        ws.members = list(set(users))

    # Create a default project to hold tasks
    project = Project(title='Content Plan', description='Auto-created for workspace tasks', workspace=ws, status='Not Started')
    db.session.add(project)
    db.session.flush()

    # Insert tasks + subtasks
    for t in tasks:
        title = (t.get('title') or '').strip()
        if not title:
            continue
        parent_task = Task(title=title, project=project, status='To Do')
        db.session.add(parent_task)
        for st in t.get('subtasks', []) or []:
            st_title = (st or '').strip()
            if not st_title:
                continue
            db.session.add(Task(title=st_title, project=project, parent_id=parent_task.id, status='To Do'))

    db.session.flush()

    # Handle file uploads
    upload_folder = current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, 'static', 'uploads', 'workspaces'))
    os.makedirs(upload_folder, exist_ok=True)
    saved_files = []
    for file in request.files.getlist('files'):
        if not file or not getattr(file, 'filename', None):
            continue
        fname = secure_filename(file.filename)
        # Store within a subfolder per workspace
        ws_dir = os.path.join(upload_folder, str(ws.id))
        os.makedirs(ws_dir, exist_ok=True)
        stored_path = os.path.join(ws_dir, fname)
        file.save(stored_path)
        rel_path = os.path.relpath(stored_path, current_app.root_path)
        wf = WorkspaceFile(workspace=ws, original_name=fname, stored_path=rel_path, uploaded_by=current_user.id)
        db.session.add(wf)
        saved_files.append({'original_name': fname, 'path': rel_path.replace('\\', '/')})

    db.session.commit()

    return jsonify({
        'workspace': {'id': ws.id, 'name': ws.name},
        'files': saved_files
    }), 201





@bp.route('/api/lessons/generate-stream', methods=['POST'])
@login_required
def generate_lesson_api_stream():
    """Streaming endpoint for lesson generation with progress updates"""
    
    def send_error(error_msg):
        return f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
    
    try:
        data = request.get_json(silent=True) or {}
        workspace_id = data.get('workspace_id')
        topic = (data.get('topic') or '').strip()
        age = data.get('age')
        subject_field = (data.get('subject') or '').strip() or None
        objectives = data.get('objectives') or []
        aspects = data.get('aspects') or []
        activities = data.get('activities') or []
        images = data.get('images') or []
        custom_prompt = (data.get('custom_prompt') or '').strip()

        if not workspace_id:
            return Response(send_error('workspace_id is required'), mimetype='text/event-stream'), 400

        workspace_id_int = int(workspace_id)
        ws = Workspace.query.get_or_404(workspace_id_int)
        if current_user not in ws.members:
            return Response(send_error('Not a member of this workspace'), mimetype='text/event-stream'), 403
        
        # Store values we need in the generator (avoid detached instance errors)
        user_id = current_user.id
    except Exception as e:
        return Response(send_error(f'Error: {str(e)}'), mimetype='text/event-stream'), 500

    # Ollama config
    model = (data.get('model') or os.getenv('OLLAMA_MODEL') or 'phi3:mini')
    num_predict = int(os.getenv('OLLAMA_MAX_TOKENS', '1500'))
    temperature = float(os.getenv('OLLAMA_TEMPERATURE', '0.6'))
    
    llm_service = LLMService()

    def generate():
        content = ''
        total_chars = 0
        estimated_total = num_predict * 4
        
        try:
            # Build prompt
            if custom_prompt:
                if not topic or not age:
                    yield send_error('topic and age are required even when using custom prompt (for reference)')
                    return
                prompt = build_custom_lesson_prompt(custom_prompt, topic, age, subject_field)
            else:
                if not topic or not age:
                    yield send_error('workspace_id, topic and age are required')
                    return
                prompt = build_lesson_prompt(int(age), topic, objectives, aspects, activities, images, subject_field)
            
            yield f"data: {json.dumps({'type': 'progress', 'percentage': 5, 'message': 'Starting generation...'})}\n\n"
            
            messages = [
                {'role': 'system', 'content': 'You are an expert educator. Write clear, engaging student lessons in British English following the exact format specified.'},
                {'role': 'user', 'content': prompt}
            ]
            options = {
                'num_predict': num_predict,
                'temperature': temperature
            }
            
            # Use LLM Service
            stream_iter = llm_service.generate_chat_stream(model, messages, options=options)
            
            yield f"data: {json.dumps({'type': 'progress', 'percentage': 10, 'message': 'Model processing...'})}\n\n"
            
            for line in stream_iter:
                if line:
                    try:
                        chunk = json.loads(line)
                        if 'message' in chunk and 'content' in chunk['message']:
                            new_content = chunk['message']['content']
                            content += new_content
                            total_chars += len(new_content)
                            progress = min(95, 10 + int((total_chars / estimated_total) * 85))
                            yield f"data: {json.dumps({'type': 'progress', 'percentage': progress, 'message': f'Generating... {progress}%', 'content': new_content})}\n\n"
                        elif 'response' in chunk:
                            new_content = chunk['response']
                            content += new_content
                            total_chars += len(new_content)
                            progress = min(95, 10 + int((total_chars / estimated_total) * 85))
                            yield f"data: {json.dumps({'type': 'progress', 'percentage': progress, 'message': f'Generating... {progress}%', 'content': new_content})}\n\n"
                    except json.JSONDecodeError:
                        continue
            
            # Save lesson
            lesson = Lesson(
                workspace_id=workspace_id_int,
                topic=topic,
                subject=subject_field,
                age=int(age),
                objectives=objectives,
                aspects=aspects,
                activities=activities,
                images=images,
                prompt=prompt,
                content=content,
                created_by=user_id
            )
            db.session.add(lesson)
            db.session.commit()
            
            yield f"data: {json.dumps({'type': 'complete', 'percentage': 100, 'message': 'Lesson generation complete!', 'lesson_id': lesson.id, 'content': content})}\n\n"
            
        except requests.exceptions.ReadTimeout as e:
            error_msg = 'Generation timed out. The model is taking longer than expected. Try using a faster model (phi3:mini) or reducing the content length.'
            current_app.logger.error(f"Lesson generation timeout: {str(e)}")
            if content:
                try:
                    lesson = Lesson(
                        workspace_id=workspace_id_int,
                        topic=topic,
                        subject=subject_field,
                        age=int(age),
                        objectives=objectives,
                        aspects=aspects,
                        activities=activities,
                        images=images,
                        prompt=prompt,
                        content=content + "\n\n[Note: Generation was interrupted - partial content]",
                        created_by=user_id
                    )
                    db.session.add(lesson)
                    db.session.commit()
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg + ' Partial content saved.', 'partial_content': content, 'lesson_id': lesson.id})}\n\n"
                except Exception as save_err:
                    current_app.logger.error(f"Error saving partial content: {save_err}")
                    yield send_error(error_msg)
            else:
                yield send_error(error_msg)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
             import traceback
             error_msg = f'Network error: {str(e)}'
             current_app.logger.error(f"Lesson generation connection error: {traceback.format_exc()}")
             if content:
                 try:
                     lesson = Lesson(
                         workspace_id=workspace_id_int,
                         topic=topic,
                         subject=subject_field,
                         age=int(age),
                         objectives=objectives,
                         aspects=aspects,
                         activities=activities,
                         images=images,
                         prompt=prompt,
                         content=content + "\n\n[Note: Generation was interrupted due to network error - partial content]",
                         created_by=user_id
                     )
                     db.session.add(lesson)
                     db.session.commit()
                     yield f"data: {json.dumps({'type': 'error', 'message': error_msg + ' Partial content saved.', 'partial_content': content, 'lesson_id': lesson.id})}\n\n"
                 except Exception as save_err:
                     current_app.logger.error(f"Error saving partial content on network error: {save_err}")
                     yield send_error(error_msg)
             else:
                 yield send_error(error_msg)
        except Exception as e:
            import traceback
            error_msg = f'Error generating lesson: {str(e)}'
            current_app.logger.error(f"Lesson generation error: {traceback.format_exc()}")
            yield send_error(error_msg)

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@bp.route('/api/lessons/generate', methods=['POST'])
@login_required
def generate_lesson_api():
    data = request.get_json(silent=True) or {}
    workspace_id = data.get('workspace_id')
    topic = (data.get('topic') or '').strip()
    age = data.get('age')
    subject_field = (data.get('subject') or '').strip() or None
    objectives = data.get('objectives') or []
    aspects = data.get('aspects') or []
    activities = data.get('activities') or []
    images = data.get('images') or []
    custom_prompt = (data.get('custom_prompt') or '').strip()  # For single prompt mode

    if not workspace_id:
        return jsonify({'error': 'workspace_id is required'}), 400

    ws = Workspace.query.get_or_404(int(workspace_id))
    # ensure requester is a member
    if current_user not in ws.members:
        return jsonify({'error': 'Not a member of this workspace'}), 403

    # If custom prompt is provided, use it directly; otherwise build from structured inputs
    if custom_prompt:
        if not topic or not age:
            return jsonify({'error': 'topic and age are required even when using custom prompt (for reference)'}), 400
        subject_title = (subject_field or "GENERAL").upper() if subject_field else "GENERAL"
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
    else:
        if not topic or not age:
            return jsonify({'error': 'workspace_id, topic and age are required'}), 400
        prompt = build_lesson_prompt(int(age), topic, objectives, aspects, activities, images, subject_field)

    # Ollama config
    base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')
    model = (data.get('model') or os.getenv('OLLAMA_MODEL') or 'llama3.1')
    
    # Optimization: Use faster parameters for quicker generation
    # num_predict limits output length (2000 tokens ≈ 1500 words, enough for a complete lesson)
    num_predict = int(os.getenv('OLLAMA_MAX_TOKENS', '2000'))
    # Lower temperature = faster, more focused responses (0.7 is a good balance)
    temperature = float(os.getenv('OLLAMA_TEMPERATURE', '0.7'))

    # Try generate
    llm_service = LLMService()
    messages = [
        {'role': 'system', 'content': 'You are an expert educator. Write clear, engaging student lessons in British English following the exact format specified.'},
        {'role': 'user', 'content': prompt}
    ]
    options = {
        'num_predict': num_predict,
        'temperature': temperature
    }
    
    try:
        content = llm_service.generate_chat(model, messages, options=options)
    except Exception as e:
        return jsonify({'error': f'Failed to generate lesson: {str(e)}'}), 502

    # Save lesson
    lesson = Lesson(
        workspace_id=ws.id,
        topic=topic,
        subject=subject_field,
        age=int(age),
        objectives=objectives,
        aspects=aspects,
        activities=activities,
        images=images,
        prompt=prompt,
        content=content,
        created_by=current_user.id
    )
    db.session.add(lesson)
    db.session.commit()

    return jsonify({
        'lesson': {
            'id': lesson.id,
            'workspace_id': ws.id,
            'topic': lesson.topic,
            'subject': lesson.subject,
            'age': lesson.age,
            'content': lesson.content
        },
        'model': model
    }), 201





@bp.route('/api/activity-questions/generate', methods=['POST'])
@login_required
def generate_activity_questions_api():
    data = request.get_json(silent=True) or {}
    workspace_id = data.get('workspace_id')
    topic = (data.get('topic') or '').strip()
    subject_field = (data.get('subject') or '').strip() or None
    age_range = data.get('age_range')  # {min_age: int, max_age: int}
    grade_range = data.get('grade_range')  # {min_grade: int, max_grade: int}
    ability_levels = data.get('ability_levels') or []
    question_type = data.get('question_type', 'mixed')
    num_questions = data.get('num_questions', 5)
    lesson_id = data.get('lesson_id')  # Optional link to a lesson
    
    if not workspace_id or not topic:
        return jsonify({'error': 'workspace_id and topic are required'}), 400
    
    if not isinstance(num_questions, int) or num_questions < 1:
        num_questions = 5
    
    # Validate age range if provided
    if age_range:
        min_age = age_range.get('min_age')
        max_age = age_range.get('max_age')
        if min_age and max_age and min_age > max_age:
            return jsonify({'error': 'min_age must be less than or equal to max_age'}), 400
    
    # Validate grade range if provided
    if grade_range:
        min_grade = grade_range.get('min_grade')
        max_grade = grade_range.get('max_grade')
        if min_grade and max_grade and min_grade > max_grade:
            return jsonify({'error': 'min_grade must be less than or equal to max_grade'}), 400
    
    ws = Workspace.query.get_or_404(int(workspace_id))
    # ensure requester is a member
    if current_user not in ws.members:
        return jsonify({'error': 'Not a member of this workspace'}), 403
    
    # Validate lesson_id if provided
    if lesson_id:
        lesson = Lesson.query.get(lesson_id)
        if not lesson or lesson.workspace_id != ws.id:
            return jsonify({'error': 'Invalid lesson_id or lesson does not belong to workspace'}), 400
    
    prompt = build_activity_question_prompt(topic, subject_field, age_range, grade_range, ability_levels, question_type, num_questions)
    
    # Ollama config
    base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')
    model = (data.get('model') or os.getenv('OLLAMA_MODEL') or 'llama3.1')
    
    # Try HTTP API first
    llm_service = LLMService()
    try:
        content = llm_service.generate_chat(model, [{'role': 'user', 'content': prompt}], timeout=120)
        if not content:
            raise Exception("No content generated")
    except Exception as e:
        return jsonify({'error': f'Failed to generate activity questions: {str(e)}'}), 502
    
    # Save activity question
    activity_question = ActivityQuestion(
        workspace_id=ws.id,
        lesson_id=lesson_id if lesson_id else None,
        topic=topic,
        subject=subject_field,
        age_range=age_range,
        grade_range=grade_range,
        ability_levels=ability_levels,
        question_type=question_type,
        num_questions=num_questions,
        prompt=prompt,
        content=content,
        created_by=current_user.id
    )
    db.session.add(activity_question)
    db.session.commit()
    
    return jsonify({
        'activity_question': {
            'id': activity_question.id,
            'workspace_id': ws.id,
            'topic': activity_question.topic,
            'subject': activity_question.subject,
            'content': activity_question.content
        },
        'model': model
    }), 201


@bp.route('/api/activity-questions/<int:question_id>', methods=['GET'])
@login_required
def get_activity_question(question_id):
    activity_question = ActivityQuestion.query.get_or_404(question_id)
    # Ensure user has access via membership
    ws = Workspace.query.get(activity_question.workspace_id)
    if current_user not in ws.members:
        return jsonify({'error': 'Not authorized'}), 403
    return jsonify({
        'id': activity_question.id,
        'workspace_id': activity_question.workspace_id,
        'lesson_id': activity_question.lesson_id,
        'topic': activity_question.topic,
        'subject': activity_question.subject,
        'age_range': activity_question.age_range,
        'grade_range': activity_question.grade_range,
        'ability_levels': activity_question.ability_levels,
        'question_type': activity_question.question_type,
        'num_questions': activity_question.num_questions,
        'content': activity_question.content,
        'created_at': activity_question.created_at.isoformat() if activity_question.created_at else None
    })

@bp.route('/api/workspaces/<int:ws_id>/activity-questions', methods=['GET'])
@login_required
def get_workspace_activity_questions(ws_id):
    ws = Workspace.query.get_or_404(ws_id)
    if current_user not in ws.members:
        return jsonify({'error': 'Not authorized'}), 403
    
    questions = ActivityQuestion.query.filter_by(workspace_id=ws_id).order_by(ActivityQuestion.created_at.desc()).all()
    
    def question_to_dict(aq):
        return {
            'id': aq.id,
            'lesson_id': aq.lesson_id,
            'topic': aq.topic,
            'subject': aq.subject,
            'age_range': aq.age_range,
            'grade_range': aq.grade_range,
            'ability_levels': aq.ability_levels,
            'question_type': aq.question_type,
            'num_questions': aq.num_questions,
            'created_at': aq.created_at.isoformat() if aq.created_at else None
        }
    
    return jsonify({
        'activity_questions': [question_to_dict(aq) for aq in questions]
    })

