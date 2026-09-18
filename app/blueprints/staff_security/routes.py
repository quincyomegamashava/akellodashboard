"""Staff security routes extracted from app/routes.py (Phase 2 incremental split).

Stable endpoint names (logout, upload_users, generate_lesson, …) are preserved
so existing templates keep working. See init_app().
"""

from __future__ import annotations

import csv
import io
import json
import os
import secrets
import string

import requests
from flask import jsonify, redirect, request, send_file, session, url_for
from flask_login import current_user, login_required, logout_user

from app import db
from app.auth_decorators import admin_required
from app.cors_util import is_production_env
from app.forms import CSVUploadForm
from app.http_errors import client_error_payload
from app.learning_hub.csrf_post_guard import csrf_protect_unsafe
from app.models import User


def _content_dev_or_admin():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    if current_user.userRole == 'Admin' or current_user.has_privilege('Content Development'):
        return None
    return jsonify({'error': 'Content Development access required'}), 403


def logout():
    """Clear the session and send the browser to /login. Ignores next= (no open redirect)."""
    logout_user()
    session.clear()
    return redirect(url_for('login'))


@login_required
def generate_lesson():
    """Legacy lesson-plan generator (Ollama). Auth required; no silent success drop."""
    denied = _content_dev_or_admin()
    if denied is not None:
        return denied

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'JSON body with topic and age is required'}), 400

    topic = data.get('topic')
    objectives = data.get('objectives', [])
    age = data.get('age')
    subject = data.get('subject', '')
    duration = data.get('duration', 45)
    class_size = data.get('class_size', 25)
    notes = data.get('notes', '')

    if not topic or not age:
        return jsonify({'error': 'Please provide topic and age'}), 400

    objectives_text = ', '.join(objectives) if isinstance(objectives, list) else objectives
    subject_context = f' for {subject}' if subject else ''
    duration_context = f'The lesson should be designed for {duration} minutes.'
    class_context = f'Consider a class size of approximately {class_size} students.'
    notes_context = f'\n\nAdditional requirements: {notes}' if notes else ''

    prompt = f"""
    You are an experienced British teacher. Create a detailed, age-appropriate lesson plan{subject_context}.

    Topic: {topic}
    Learner age: {age} years old
    Subject: {subject if subject else "General"}
    Duration: {duration} minutes
    Class size: {class_size} students
    Learning objectives: {objectives_text if objectives_text else "To understand and explain the key concepts of the topic"}{notes_context}

    {duration_context} {class_context}

    The lesson plan should include:
    - A clear, engaging title
    - Learning objectives (specific, measurable, and age-appropriate)
    - An engaging introduction/warm-up activity (5-10% of lesson time)
    - Main content broken into logical sections with timing
    - At least 3 varied exercises or activities suitable for the class size
    - Assessment opportunities
    - A brief summary/plenary at the end
    - Required materials/resources
    - Differentiation strategies for different ability levels

    Use British spelling and educational terminology. Make it practical and actionable for teachers.

    Please return the result in structured JSON format like this:
    {{
      "title": "",
      "objectives": [],
      "introduction": "",
      "content": [],
      "exercises": [],
      "assessment": "",
      "summary": "",
      "materials": [],
      "differentiation": ""
    }}
    """

    from flask import current_app

    base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')
    model = os.getenv('OLLAMA_MODEL') or 'llama3.1'

    content = ''
    headers = {}
    authz = os.getenv('OLLAMA_AUTHORIZATION')
    api_key = os.getenv('OLLAMA_API_KEY')
    if authz:
        headers['Authorization'] = authz
    elif api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    def _fail(exc, what):
        current_app.logger.exception('generate_lesson failed during %s', what)
        return jsonify(client_error_payload(status=502, exc=exc, public_message='Failed to generate lesson plan')), 502

    try:
        resp = requests.post(
            f'{base_url}/api/generate',
            json={'model': model, 'prompt': prompt, 'stream': False},
            timeout=120,
            headers=headers,
        )
        resp.raise_for_status()
        payload = resp.json()
        content = payload.get('response') or payload.get('message') or ''
        if not content:
            content = payload.get('data') or ''
    except Exception as exc:
        current_app.logger.warning('generate_lesson HTTP generate failed: %s', exc)

    if not content:
        try:
            resp2 = requests.post(
                f'{base_url}/api/chat',
                json={
                    'model': model,
                    'messages': [
                        {
                            'role': 'system',
                            'content': (
                                'You are a professional British lesson plan designer with '
                                'expertise in creating engaging, age-appropriate educational content.'
                            ),
                        },
                        {'role': 'user', 'content': prompt},
                    ],
                    'stream': False,
                },
                timeout=120,
                headers=headers,
            )
            resp2.raise_for_status()
            payload2 = resp2.json()
            content = payload2.get('message', {}).get('content') or ''
        except Exception as exc:
            current_app.logger.warning('generate_lesson HTTP chat failed: %s', exc)

    if not content:
        try:
            from ollama import Client

            client = Client(host=base_url)
            res = client.generate(model=model, prompt=prompt, stream=False)
            content = res.get('response') or res.get('message', {}).get('content') or ''
            if not content:
                res2 = client.chat(
                    model=model,
                    messages=[
                        {
                            'role': 'system',
                            'content': (
                                'You are a professional British lesson plan designer with '
                                'expertise in creating engaging, age-appropriate educational content.'
                            ),
                        },
                        {'role': 'user', 'content': prompt},
                    ],
                )
                content = res2.get('message', {}).get('content') or ''
        except Exception as exc:
            return _fail(exc, 'ollama python client')

    if not content:
        current_app.logger.error('generate_lesson produced empty content after all providers')
        return jsonify({'error': 'Failed to generate lesson plan from Ollama'}), 502

    return jsonify({'lesson': content})


@login_required
@admin_required
@csrf_protect_unsafe
def analyze_users_csv():
    """Analyze user CSV for duplicates and validate columns before uploading."""
    from flask import current_app

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'Please upload a .csv file'}), 400

    try:
        stream = io.TextIOWrapper(file.stream, encoding='utf-8')
        reader = csv.DictReader(stream)

        required_columns = ['firstname', 'lastname', 'email', 'userRole', 'department', 'province']
        csv_columns = reader.fieldnames or []

        missing_columns = [col for col in required_columns if col not in csv_columns]
        if missing_columns:
            return jsonify({
                'error': 'Missing required columns',
                'missing_columns': missing_columns,
                'required_columns': required_columns,
                'found_columns': csv_columns,
            }), 400

        email_duplicates = []
        csv_email_duplicates = []
        seen_emails = {}

        users_to_create = []
        row_num = 1

        for row in reader:
            row_num += 1
            email = (row.get('email') or '').strip().lower()
            firstname = (row.get('firstname') or '').strip()
            lastname = (row.get('lastname') or '').strip()

            if not email:
                continue

            if email in seen_emails:
                csv_email_duplicates.append({
                    'email': email,
                    'firstname': firstname,
                    'lastname': lastname,
                    'rows': [seen_emails[email], row_num],
                })
            else:
                seen_emails[email] = row_num

            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                email_duplicates.append({
                    'email': email,
                    'firstname': firstname,
                    'lastname': lastname,
                    'existing_user': f'{existing_user.firstname} {existing_user.lastname}',
                    'existing_username': existing_user.username,
                    'row': row_num,
                })
            else:
                users_to_create.append({
                    'email': email,
                    'firstname': firstname,
                    'lastname': lastname,
                    'userRole': row.get('userRole', '').strip(),
                    'department': row.get('department', '').strip(),
                    'province': row.get('province', '').strip(),
                })

        has_duplicates = len(email_duplicates) > 0 or len(csv_email_duplicates) > 0

        return jsonify({
            'success': True,
            'has_duplicates': has_duplicates,
            'csv_email_duplicates': csv_email_duplicates,
            'existing_email_duplicates': email_duplicates,
            'total_new_users': len(users_to_create),
            'total_duplicates': len(email_duplicates),
        }), 200

    except Exception as exc:
        current_app.logger.exception('analyze_users_csv failed')
        return jsonify(client_error_payload(status=500, exc=exc)), 500


@login_required
@admin_required
@csrf_protect_unsafe
def upload_users_confirmed():
    """Upload users CSV with skip options. Admin only."""
    from flask import current_app

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    skip_emails = request.form.get('skip_emails', '[]')

    try:
        skip_emails = json.loads(skip_emails)
    except Exception:
        skip_emails = []

    try:
        stream = io.TextIOWrapper(file.stream, encoding='utf-8')
        reader = csv.DictReader(stream)

        created = 0
        skipped = 0
        errors = []

        for row in reader:
            try:
                firstname = row.get('firstname', '').strip()
                lastname = row.get('lastname', '').strip()
                email = row.get('email', '').strip().lower()
                role = row.get('userRole', '').strip()
                department = row.get('department', '').strip()
                province = row.get('province', '').strip()

                if not (firstname and lastname and email and role and department and province):
                    continue

                if email in skip_emails:
                    skipped += 1
                    continue

                base_username = f'{firstname.lower()}{lastname.lower()}'
                username = base_username
                count = 1
                while User.query.filter_by(username=username).first():
                    username = f'{base_username}{count}'
                    count += 1

                password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
                user = User(
                    username=username,
                    firstname=firstname,
                    lastname=lastname,
                    email=email,
                    userRole=role,
                    department=department,
                    province=province,
                )
                user.set_password(password)
                db.session.add(user)
                created += 1

            except Exception as exc:
                errors.append('row failed' if is_production_env() else str(exc))

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Upload complete! Created: {created}, Skipped: {skipped}',
            'created': created,
            'skipped': skipped,
            'errors': errors,
        }), 200

    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('upload_users_confirmed failed')
        return jsonify(client_error_payload(status=500, exc=exc)), 500


@login_required
@admin_required
@csrf_protect_unsafe
def upload_users():
    """Legacy CSV user ingest. Admin only; non-admins receive 403."""
    from flask import current_app

    form = CSVUploadForm()
    if form.validate_on_submit():
        file = form.csv_file.data
        stream = io.StringIO(file.stream.read().decode('UTF8'), newline=None)
        reader = csv.DictReader(stream)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['First Name', 'Last Name', 'Email', 'Username', 'Password', 'Status'])

        for row in reader:
            try:
                firstname = row.get('firstname', '').strip()
                lastname = row.get('lastname', '').strip()
                email = row.get('email', '').strip()
                role = row.get('userRole', '').strip()
                department = row.get('department', '').strip()
                province = row.get('province', '').strip()

                if not (firstname and lastname and email and role and department and province):
                    writer.writerow([firstname, lastname, email, '', '', 'Missing Fields'])
                    continue

                base_username = f'{firstname.lower()}{lastname.lower()}'
                username = base_username
                count = 1
                while User.query.filter_by(username=username).first():
                    username = f'{base_username}{count}'
                    count += 1

                if User.query.filter_by(email=email).first():
                    writer.writerow([firstname, lastname, email, username, '', 'Email Exists'])
                    continue

                password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
                user = User(
                    username=username,
                    firstname=firstname,
                    lastname=lastname,
                    email=email,
                    userRole=role,
                    department=department,
                    province=province,
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()

                writer.writerow([firstname, lastname, email, username, password, 'Created'])
                current_app.logger.info('Created user %s (%s)', username, email)

            except Exception as exc:
                db.session.rollback()
                current_app.logger.exception('Error while creating user from CSV')
                writer.writerow([firstname, lastname, email, '', '', f'Error: {exc}'])

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='registered_users_report.csv',
        )
    return redirect(url_for('settings'))


def init_app(app):
    """Register staff-security views with the historic endpoint names templates use."""
    app.add_url_rule('/logout', endpoint='logout', view_func=logout)
    app.add_url_rule(
        '/generate_lesson',
        endpoint='generate_lesson',
        view_func=generate_lesson,
        methods=['POST'],
    )
    app.add_url_rule(
        '/analyze_users_csv',
        endpoint='analyze_users_csv',
        view_func=analyze_users_csv,
        methods=['POST'],
    )
    app.add_url_rule(
        '/upload_users_confirmed',
        endpoint='upload_users_confirmed',
        view_func=upload_users_confirmed,
        methods=['POST'],
    )
    app.add_url_rule(
        '/upload_users',
        endpoint='upload_users',
        view_func=upload_users,
        methods=['GET', 'POST'],
    )
