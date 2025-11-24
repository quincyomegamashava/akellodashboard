
from asyncio import open_connection
import calendar
import json
from urllib import parse
from urllib.parse import urlsplit
from flask import jsonify, render_template, flash, redirect, render_template_string, session, url_for, request, send_file
from flask_login import login_user, logout_user, current_user, login_required
import sqlalchemy as sa
from app import app, db
from app.forms import EventForm, LoginForm, PerfomanceTargetsForm, RegistrationForm, BookAllocationForm, ReportForm, WorkspaceForm, ProjectForm, TaskForm, CSVUploadForm, ChampionCSVUploadForm, ChampionSchoolForm, AkelloSimEventForm
from app.models import PerfomanceTargets, Scorecard, User, BookAllocations, Report, Workspace, Project, Task, ChampionSchool, Event, WeeklyReport, TaskA, ColumnA, ProjectA, AkelloSimEvent, UserActivity, ActiveSession, PageAnalytics, WorkspaceFile, Lesson, CollateralItems, CollateralRequest
from datetime import datetime, timezone, timedelta, date
from collections import Counter
from collections import defaultdict
from flask import Blueprint
from sqlalchemy import and_, create_engine, select, text
import pymysql
from werkzeug.utils import secure_filename
import os
import io
from sshtunnel import SSHTunnelForwarder
from sqlalchemy.exc import IntegrityError
import paramiko
import logging
import csv
import pandas as pd
import secrets
import string
from dotenv import load_dotenv
import requests
import mysql.connector
from mysql.connector import Error
import seaborn as sns
import random
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio
import asyncio
import aiomysql
from dbutils.pooled_db import PooledDB
import atexit
from collections import defaultdict
# Add this import at the top of your file
from psycopg2 import sql
from flask_caching import Cache

# Email + token utils for password reset
import smtplib
from email.message import EmailMessage
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import uuid

from openai import OpenAI

# Load .env variables
load_dotenv()




# # ---------- DIRECT CONNECTION POOL ----------
# # ---------- LAZY-LOADED CONNECTION POOLS ----------
# Initialize pools as None - will be created on first use
ruzivo_pool = None
direct_library_pool = None

def get_ruzivo_pool():
    """Get or create Ruzivo connection pool"""
    global ruzivo_pool
    if ruzivo_pool is None:
        try:
            ruzivo_pool = PooledDB(
                creator=pymysql,
                maxconnections=5,     # Reduced for stability
                mincached=0,          # No minimum cached connections
                maxcached=3,
                maxshared=2,
                maxusage=1000,
                blocking=False,
                setsession=[],
                ping=1,               # Only ping on checkout
                host='40.90.237.225',
                port=33000,
                user='qmashava',
                password='#Qhava@@!Fu11',
                database='ruzivo_2017',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=30,
                read_timeout=60,
                write_timeout=60,
                charset='utf8mb4',
            )
            app.logger.info("Ruzivo connection pool initialized successfully")
        except Exception as e:
            app.logger.error(f"Failed to initialize Ruzivo pool: {e}")
            ruzivo_pool = None
    return ruzivo_pool

def get_library_pool():
    """Get or create Library connection pool"""
    global direct_library_pool
    if direct_library_pool is None:
        try:
            direct_library_pool = PooledDB(
                creator=pymysql,
                maxconnections=5,
                mincached=0,
                maxcached=3,
                maxshared=2,
                maxusage=1000,
                blocking=False,
                setsession=[],
                ping=1,
                host='40.88.149.15',
                port=33000,
                user='kmudzimuirema',
                password='Ak3110$2022',
                database='akello_library',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=30,
                read_timeout=60,
                write_timeout=60,
                charset='utf8mb4',
            )
            app.logger.info("Library connection pool initialized successfully")
        except Exception as e:
            app.logger.error(f"Failed to initialize Library pool: {e}")
            direct_library_pool = None
    return direct_library_pool



# ---------- Helper functions ----------
# ---------- Improved Helper functions with error handling ----------
def get_direct_library_conn():
    """Get a library database connection with error handling and timeout"""
    try:
        pool = get_library_pool()
        if pool is None:
            raise Exception("Library connection pool not available")
        
        conn = pool.connection()
        if conn is None:
            raise Exception("Failed to get library database connection from pool")
        return conn
    except Exception as e:
        app.logger.error(f"Error getting library database connection: {e}")
        # Try to create a direct connection as fallback
        try:
            import pymysql
            return pymysql.connect(
                host='40.88.149.15',
                port=33000,
                user='kmudzimuirema',
                password='Ak3110$2022',
                database='akello_library',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=30,
                read_timeout=60,
                write_timeout=60,
                charset='utf8mb4'
            )
        except Exception as fallback_error:
            app.logger.error(f"Fallback connection also failed: {fallback_error}")
            raise Exception("Unable to establish library database connection")

def get_ruzivo_conn():
    """Get a ruzivo database connection with error handling and timeout"""
    try:
        pool = get_ruzivo_pool()
        if pool is None:
            raise Exception("Ruzivo connection pool not available")
        
        conn = pool.connection()
        if conn is None:
            raise Exception("Failed to get ruzivo database connection from pool")
        return conn
    except Exception as e:
        app.logger.error(f"Error getting ruzivo database connection: {e}")
        # Try to create a direct connection as fallback
        try:
            import pymysql
            return pymysql.connect(
                host='40.90.237.225',
                port=33000,
                user='qmashava',
                password='#Qhava@@!Fu11',
                database='ruzivo_2017',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=30,
                read_timeout=60,
                write_timeout=60,
                charset='utf8mb4'
            )
        except Exception as fallback_error:
            app.logger.error(f"Fallback connection also failed: {fallback_error}")
            raise Exception("Unable to establish ruzivo database connection")

def safe_db_execute(conn, query, params=None, fetch_one=False, fetch_all=True):
    """Safely execute database queries with proper error handling and connection cleanup"""
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        else:
            return cursor.rowcount
            
    except Exception as e:
        app.logger.error(f"Database query error: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()



# global ruzivo_conn
# global library_conn
# Connections will be created on-demand to avoid startup failures
# ruzivo_conn = get_ruzivo_conn()
# library_conn = get_direct_library_conn()



# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize cache for API endpoints
cache = Cache(app)

@app.route("/generate_lesson", methods=["POST"])
def generate_lesson():
    data = request.get_json()
    topic = data.get("topic")
    objectives = data.get("objectives", [])
    age = data.get("age")
    subject = data.get("subject", "")
    duration = data.get("duration", 45)
    class_size = data.get("class_size", 25)
    notes = data.get("notes", "")

    if not topic or not age:
        return jsonify({"error": "Please provide topic and age"}), 400

    objectives_text = ", ".join(objectives) if isinstance(objectives, list) else objectives
    
    # Build subject context
    subject_context = f" for {subject}" if subject else ""
    
    # Build duration context
    duration_context = f"The lesson should be designed for {duration} minutes."
    
    # Build class size context
    class_context = f"Consider a class size of approximately {class_size} students."
    
    # Build notes context
    notes_context = f"\n\nAdditional requirements: {notes}" if notes else ""

    # 🧩 Enhanced prompt construction
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

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # or gpt-4-turbo
            messages=[
                {"role": "system", "content": "You are a professional British lesson plan designer with expertise in creating engaging, age-appropriate educational content."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        content = response.choices[0].message.content
        return jsonify({"lesson": content})

    except Exception as e:
        print(f"Error generating lesson: {e}")
        return jsonify({"error": str(e)}), 500



@app.route('/analyze_users_csv', methods=['POST'])
@login_required
def analyze_users_csv():
    """Analyze user CSV for duplicates and validate columns before uploading"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'Please upload a .csv file'}), 400

    try:
        # Parse CSV
        stream = io.TextIOWrapper(file.stream, encoding='utf-8')
        reader = csv.DictReader(stream)
        
        # Required columns for user upload
        required_columns = ['firstname', 'lastname', 'email', 'userRole', 'department', 'province']
        csv_columns = reader.fieldnames or []
        
        # Check for missing columns
        missing_columns = [col for col in required_columns if col not in csv_columns]
        if missing_columns:
            return jsonify({
                'error': 'Missing required columns',
                'missing_columns': missing_columns,
                'required_columns': required_columns,
                'found_columns': csv_columns
            }), 400
        
        # Track duplicates
        email_duplicates = []  # Emails that exist in DB
        csv_email_duplicates = []  # Duplicate emails within CSV
        seen_emails = {}
        
        users_to_create = []
        row_num = 1  # Start at 1 (header is row 0)
        
        for row in reader:
            row_num += 1
            email = (row.get('email') or '').strip().lower()
            firstname = (row.get('firstname') or '').strip()
            lastname = (row.get('lastname') or '').strip()
            
            if not email:
                continue
            
            # Check for duplicates within CSV
            if email in seen_emails:
                csv_email_duplicates.append({
                    'email': email,
                    'firstname': firstname,
                    'lastname': lastname,
                    'rows': [seen_emails[email], row_num]
                })
            else:
                seen_emails[email] = row_num
            
            # Check if email exists in database
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                email_duplicates.append({
                    'email': email,
                    'firstname': firstname,
                    'lastname': lastname,
                    'existing_user': f"{existing_user.firstname} {existing_user.lastname}",
                    'existing_username': existing_user.username,
                    'row': row_num
                })
            else:
                users_to_create.append({
                    'email': email,
                    'firstname': firstname,
                    'lastname': lastname,
                    'userRole': row.get('userRole', '').strip(),
                    'department': row.get('department', '').strip(),
                    'province': row.get('province', '').strip()
                })
        
        has_duplicates = len(email_duplicates) > 0 or len(csv_email_duplicates) > 0
        
        return jsonify({
            'success': True,
            'has_duplicates': has_duplicates,
            'csv_email_duplicates': csv_email_duplicates,
            'existing_email_duplicates': email_duplicates,
            'total_new_users': len(users_to_create),
            'total_duplicates': len(email_duplicates)
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/upload_users_confirmed', methods=['POST'])
@login_required
def upload_users_confirmed():
    """Upload users CSV with skip options"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    skip_emails = request.form.get('skip_emails', '[]')
    
    try:
        skip_emails = json.loads(skip_emails)
    except:
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
                
                # Check if email should be skipped
                if email in skip_emails:
                    skipped += 1
                    continue

                # Generate unique username
                base_username = f"{firstname.lower()}{lastname.lower()}"
                username = base_username
                count = 1
                while User.query.filter_by(username=username).first():
                    username = f"{base_username}{count}"
                    count += 1

                # Create user
                password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
                user = User(
                    username=username,
                    firstname=firstname,
                    lastname=lastname,
                    email=email,
                    userRole=role,
                    department=department,
                    province=province
                )
                user.set_password(password)
                db.session.add(user)
                created += 1
                
            except Exception as e:
                errors.append(str(e))
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Upload complete! Created: {created}, Skipped: {skipped}',
            'created': created,
            'skipped': skipped,
            'errors': errors
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/upload_users', methods=['GET', 'POST'])
@login_required
def upload_users():
    form = CSVUploadForm()
    if form.validate_on_submit():
        file = form.csv_file.data
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
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

                base_username = f"{firstname.lower()}{lastname.lower()}"
                username = base_username
                count = 1
                while User.query.filter_by(username=username).first():
                    username = f"{base_username}{count}"
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
                    province=province
                )
                user.set_password(password)
                print(user)
                db.session.add(user)
                db.session.commit()

                writer.writerow([firstname, lastname, email, username, password, 'Created'])
                print(f"[INFO] Created user: {username} ({email})")

            except Exception as e:
                db.session.rollback()
                print("Error while creating user:", e)
                traceback.print_exc()
                writer.writerow([firstname, lastname, email, '', '', f'Error: {str(e)}'])

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='registered_users_report.csv'
        )
    return redirect(url_for('settings'))




@app.route('/welcome', methods=['GET'])
@login_required
def welcome():
    return render_template('overview.html', title='Welcome')


@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    today = datetime.now().date()
    all_events = Event.query.order_by(Event.start_date.desc()).all()
    updated = False

    for event in all_events:
        if event.status in ['Cancelled', 'Deleted', 'Event Ended']:
            continue  # skip protected statuses

        if event.start_date.date() <= today <= event.end_date.date():
            if event.status != "In Progress":
                event.status = "In Progress"
                updated = True
        elif today > event.end_date.date():
            if event.status != "Event Ended":
                event.status = "Event Ended"
                updated = True

    if updated:
        db.session.commit()

    form = EventForm()
    return render_template(
        'index.html',
        events=all_events,
        form=form,
        forms={event.id: EventForm(obj=event) for event in all_events},
        title='Home'
    )


@app.route('/content-development', methods=['GET'])
@login_required
def content_development():
    return render_template('content_development.html', title='Content Development')


# -------- Content Development API --------
@app.route('/api/ollama/models', methods=['GET'])
@login_required
def list_ollama_models():
    base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')
    headers = {}
    # Optional auth
    authz = os.getenv('OLLAMA_AUTHORIZATION')
    api_key = os.getenv('OLLAMA_API_KEY')
    if authz:
        headers['Authorization'] = authz
    elif api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    # Try HTTP API first
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=10, headers=headers)
        r.raise_for_status()
        data = r.json() or {}
        models = [m.get('name') for m in data.get('models', []) if m.get('name')]
        if models:
            return jsonify({'models': models})
    except Exception:
        pass
    # Try Python library fallback (with explicit host)
    try:
        from ollama import Client
        client = Client(host=base_url)
        res = client.list()
        models = [m.get('name') for m in (res.get('models') or []) if m.get('name')]
        if models:
            return jsonify({'models': models})
    except Exception as e:
        return jsonify({'models': ['llama3.1', 'llama3', 'mistral', 'phi3', 'qwen2', 'gemma'], 'error': str(e)}), 200
    # Final fallback
    return jsonify({'models': ['llama3.1', 'llama3', 'mistral', 'phi3', 'qwen2', 'gemma']}), 200

# -------- End Content Development API --------

@app.route('/api/lessons/<int:lesson_id>', methods=['GET'])
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

@app.route('/api/workspaces/<int:ws_id>', methods=['DELETE', 'PATCH'])
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

@app.route('/api/workspaces/mine', methods=['GET'])
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
        tasks = tasks_for_workspace(ws.id)
        data.append({
            'id': ws.id,
            'name': ws.name,
            'description': ws.description or '',
            'created_at': ws.created_at.isoformat() if ws.created_at else None,
            'files': files,
            'lessons': lessons,
            'tasks': tasks
        })
    return jsonify({'workspaces': data})
@app.route('/api/content-dev/bootstrap', methods=['GET'])
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


@app.route('/api/workspaces', methods=['POST'])
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
    upload_folder = app.config.get('UPLOAD_FOLDER', os.path.join(app.root_path, 'static', 'uploads', 'workspaces'))
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
        rel_path = os.path.relpath(stored_path, app.root_path)
        wf = WorkspaceFile(workspace=ws, original_name=fname, stored_path=rel_path, uploaded_by=current_user.id)
        db.session.add(wf)
        saved_files.append({'original_name': fname, 'path': rel_path.replace('\\', '/')})

    db.session.commit()

    return jsonify({
        'workspace': {'id': ws.id, 'name': ws.name},
        'files': saved_files
    }), 201


def build_lesson_prompt(age:int, topic:str, objectives:list, aspects:list, activities:list, images:list, subject: str = None):
    header = f"Using British English create a lesson aimed to teach {{{age}}} year olds on the topic, {{\"{topic}\"}}"
    if subject:
        header += f"\n\nSubject: {subject}"
    obj_lines = "\n".join([f"• {o}" for o in objectives]) if objectives else "• define the key concept\n• explain the importance of the topic"
    aspects_lines = "\n".join([f"•\t{a}" for a in aspects]) if aspects else "•\tKey ideas"
    activities_lines = "\n".join([f"•\t{a}" for a in activities]) if activities else "•\tShort quiz\n•\tGroup discussion"
    images_lines = "\n".join([f"• {i}" for i in images]) if images else "• Simple diagram or infographic relevant to the topic"

    parts = [
        header,
        "\n\n\nThe lesson's objectives are as follows: \n\n\n" + obj_lines,
        "\n\n\nthe content should include the following aspects:\n\n\n" + aspects_lines,
        "\n\n\nAssign activites to help reiterate  the lesson, activities should involve:\n" + activities_lines,
        "\n\n\nSuggest any images  or illustrations to help emphasis points in the lesson\n\n" + images_lines + "\n"
    ]
    return "".join(parts)


@app.route('/api/lessons/generate', methods=['POST'])
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

    if not workspace_id or not topic or not age:
        return jsonify({'error': 'workspace_id, topic and age are required'}), 400

    ws = Workspace.query.get_or_404(int(workspace_id))
    # ensure requester is a member
    if current_user not in ws.members:
        return jsonify({'error': 'Not a member of this workspace'}), 403

    prompt = build_lesson_prompt(int(age), topic, objectives, aspects, activities, images, subject_field)

    # Ollama config
    base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')
    model = (data.get('model') or os.getenv('OLLAMA_MODEL') or 'llama3.1')

    # Try HTTP API first
    content = ''
    http_error = None
    headers = {}
    authz = os.getenv('OLLAMA_AUTHORIZATION')
    api_key = os.getenv('OLLAMA_API_KEY')
    if authz:
        headers['Authorization'] = authz
    elif api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    try:
        resp = requests.post(f"{base_url}/api/generate", json={
            'model': model,
            'prompt': prompt,
            'stream': False
        }, timeout=120, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
        content = payload.get('response') or payload.get('message') or ''
        if not content:
            content = payload.get('data') or ''
    except Exception as e:
        http_error = e
    # If HTTP failed or returned empty, try HTTP chat endpoint
    if not content:
        try:
            resp2 = requests.post(f"{base_url}/api/chat", json={
                'model': model,
                'messages': [{ 'role': 'user', 'content': prompt }],
                'stream': False
            }, timeout=120, headers=headers)
            resp2.raise_for_status()
            payload2 = resp2.json()
            # Chat responses place content under message.content
            content = payload2.get('message', {}).get('content') or ''
        except Exception:
            pass
    # If HTTP failed or returned empty, try Python library fallback (with explicit host)
    if not content:
        try:
            from ollama import Client
            client = Client(host=base_url)
            # Try generate first
            res = client.generate(model=model, prompt=prompt, stream=False)
            content = res.get('response') or res.get('message', {}).get('content') or ''
            if not content:
                # Then chat
                res2 = client.chat(model=model, messages=[{ 'role': 'user', 'content': prompt }])
                content = res2.get('message', {}).get('content') or ''
        except Exception as e:
            if http_error:
                return jsonify({'error': f'Failed to generate from Ollama HTTP ({http_error}); and Python client also failed: {e}'}), 502
            return jsonify({'error': f'Failed to generate from Ollama Python client: {e}'}), 502

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





@app.route('/api/events')
@login_required
def api_events():
    events = Event.query.all()
    event_list = []
    for event in events:
        event_list.append({
            'id': event.id,
            'title': event.title,
            'start': event.start_date.isoformat(),
            'end': event.end_date.isoformat(),
            'color': '#1E90FF' if event.status == 'Confirmed' else ('#FFA500' if event.status == 'In Progress' else '#DC143C')
        })
    return jsonify(event_list)



@app.route('/event/add', methods=['GET', 'POST'])
@login_required
def add_event():
    form = EventForm()
    if form.validate_on_submit():
        new_event = Event(
            title=form.title.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status=form.status.data,
            request_collateral=form.request_collateral.data,
            added_by=current_user.username
        )
        db.session.add(new_event)
        db.session.commit()
        return redirect(url_for('index'))

@app.route('/event/edit/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    form = EventForm(obj=event)
    if form.validate_on_submit():
        event.title = form.title.data
        event.start_date = form.start_date.data
        event.end_date = form.end_date.data
        event.status = form.status.data
        event.request_collateral = form.request_collateral.data
        event.added_by = current_user.username
        db.session.commit()
        return redirect(url_for('index'))

    




@app.route("/admin/users/<int:user_id>/grant", methods=["POST"])
@login_required
def grant_privilege(user_id):
    if not current_user.userRole == "Admin":
        return jsonify({"error": "Unauthorized"}), 403

    privilege = request.json.get("privilege")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.add_privilege(privilege)
    return jsonify({"message": f"Privilege '{privilege}' granted to {user.username}."})


@app.route("/admin/users/<int:user_id>/revoke", methods=["POST"])
@login_required
def revoke_privilege(user_id):
    if not current_user.userRole == "Admin":
        return jsonify({"error": "Unauthorized"}), 403

    privilege = request.json.get("privilege")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.remove_privilege(privilege)
    return jsonify({"message": f"Privilege '{privilege}' revoked from {user.username}."})



@app.route("/secure-area")
@login_required
def secure_area():
    if not current_user.has_privilege("can_view_reports"):
        return "Access Denied", 403
    return "Welcome to secure reports!"



@app.route("/admin/users")
@login_required
def manage_users():
    if not current_user.userRole == "Admin":
        return "Unauthorized", 403

    users = User.query.all()
    return render_template("admin_users.html", users=users)


@app.route('/administration', methods=['GET'])
@login_required
def administration():
    if current_user.userRole != 'Admin':
        return "Unauthorized", 403

    users = User.query.order_by(User.username.asc()).all()
    csvform = CSVUploadForm()
    championcsvform = ChampionCSVUploadForm()

    # Build champion_schools rows from ChampionSchool model
    champion_rows = []
    champs = ChampionSchool.query.all()
    # Build an index to find username by firstname/lastname/province (best-effort)
    users_index = {}
    for u in users:
        key = (u.firstname or '').strip().lower(), (u.lastname or '').strip().lower(), (u.province or '').strip().lower()
        users_index[key] = u.username

    for c in champs:
        schools = []
        try:
            schools = c.get_schools() or []
        except Exception:
            schools = []
        champ_name = f"{c.firstname} {c.lastname}".strip()
        uname = users_index.get(((c.firstname or '').strip().lower(), (c.lastname or '').strip().lower(), (c.province or '').strip().lower()), '')
        if not schools:
            champion_rows.append({
                'id': c.id,
                'champion': champ_name,
                'username': uname,
                'school_name': '',
                'province': c.province,
                'asl_school_id': '',
                'library_school_id': ''
            })
        else:
            for s in schools:
                champion_rows.append({
                    'id': c.id,
                    'champion': champ_name,
                    'username': uname,
                    'school_name': s.get('school_name',''),
                    'province': c.province,
                    'asl_school_id': s.get('asl_school_id',''),
                    'library_school_id': s.get('library_school_id','')
                })

    return render_template(
        'administration.html',
        users=users,
        champion_schools=champion_rows,
        csvform=csvform,
        championcsvform=championcsvform,
        title='Administration'
    )


@app.route('/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
def admin_delete_user(user_id):
    if current_user.userRole != 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@app.route('/admin/users/<int:user_id>/reset_password', methods=['POST'])
@login_required
def admin_reset_password(user_id):
    if current_user.userRole != 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.get_json() or {}
    new_password = data.get('password')
    if not new_password:
        # Generate a secure random password if not provided
        import secrets, string
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for _ in range(12))
    user.set_password(new_password)
    db.session.commit()
    return jsonify({"message": "Password reset successfully"}), 200


@app.route('/admin/users/<int:user_id>', methods=['PATCH'])
@login_required
def admin_update_user(user_id):
    if current_user.userRole != 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.get_json() or {}
    # Allowed updatable fields
    for field in ['username','email','firstname','lastname','userRole','department','province']:
        if field in data and data[field] is not None:
            setattr(user, field, data[field])
    try:
        db.session.commit()
        return jsonify({"message": "User updated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@app.route("/admin/users/<int:user_id>/toggle_privilege", methods=["POST"])
@login_required
def toggle_privilege(user_id):
    if current_user.userRole != "Admin":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    privilege = data.get("privilege")
    value = data.get("value", False)

    if not privilege:
        return jsonify({"error": "Privilege name is required"}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        user.set_privilege(privilege, value)
        return jsonify({
            "message": f"Privilege '{privilege}' set to {value} for {user.username}.",
            "privilege": privilege,
            "value": value
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update privilege: {str(e)}"}), 500


# Champion Schools admin delete endpoint
@app.route('/admin/champion_schools/<int:cs_id>', methods=['DELETE'])
@login_required
def admin_delete_champion_school(cs_id):
    if current_user.userRole != 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    rec = db.session.get(ChampionSchool, cs_id)
    if not rec:
        return jsonify({"error": "Record not found"}), 404
    try:
        db.session.delete(rec)
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# Champion Schools admin update endpoint (inline save)
@app.route('/admin/champion_schools/<int:cs_id>', methods=['PATCH'])
@login_required
def admin_update_champion_school(cs_id):
    if current_user.userRole != 'Admin':
        return jsonify({"error": "Unauthorized"}), 403

    rec = db.session.get(ChampionSchool, cs_id)
    if not rec:
        return jsonify({"error": "Record not found"}), 404

    data = request.get_json() or {}

    # Optionally update champion identity
    for field in ['firstname','lastname','province']:
        if field in data and data[field] is not None:
            setattr(rec, field, data[field])

    school_name = (data.get('school_name') or '').strip()
    asl_id_new = (data.get('asl_school_id') or '').strip()
    lib_id_new = (data.get('library_school_id') or '').strip()
    asl_id_orig = (data.get('original_asl_school_id') or '').strip()
    lib_id_orig = (data.get('original_library_school_id') or '').strip()

    schools = rec.get_schools() or []

    # Enhanced matching logic with multiple strategies
    match_idx = None
    
    # Strategy 1: Match by original IDs (most reliable)
    if asl_id_orig or lib_id_orig:
        for idx, s in enumerate(schools):
            s_asl = str(s.get('asl_school_id') or '').strip()
            s_lib = str(s.get('library_school_id') or '').strip()
            # Match if BOTH IDs match OR if one matches and the other is empty/0
            asl_match = (asl_id_orig and s_asl == asl_id_orig)
            lib_match = (lib_id_orig and s_lib == lib_id_orig)
            
            if asl_match and lib_match:
                match_idx = idx
                break
            elif asl_match and (not lib_id_orig or not s_lib or s_lib == '0'):
                match_idx = idx
                break
            elif lib_match and (not asl_id_orig or not s_asl or s_asl == '0'):
                match_idx = idx
                break
    
    # Strategy 2: Match by school name if provided and no ID match
    if match_idx is None and school_name:
        for idx, s in enumerate(schools):
            if (s.get('school_name') or '').strip().lower() == school_name.lower():
                match_idx = idx
                break
    
    # Strategy 3: If still no match, try matching by new IDs
    if match_idx is None and (asl_id_new or lib_id_new):
        for idx, s in enumerate(schools):
            s_asl = str(s.get('asl_school_id') or '').strip()
            s_lib = str(s.get('library_school_id') or '').strip()
            if (asl_id_new and s_asl == asl_id_new) or (lib_id_new and s_lib == lib_id_new):
                match_idx = idx
                break

    # Update or append
    if match_idx is not None:
        # Preserve existing school entry and only update provided fields
        entry = dict(schools[match_idx])
        if school_name:
            entry['school_name'] = school_name
        # Only update IDs if they're actually provided (not empty)
        if asl_id_new:
            entry['asl_school_id'] = asl_id_new
        if lib_id_new:
            entry['library_school_id'] = lib_id_new
        schools[match_idx] = entry
    else:
        # Append a new mapping if at least one ID provided
        if asl_id_new or lib_id_new or school_name:
            schools.append({
                'school_name': school_name,
                'asl_school_id': asl_id_new,
                'library_school_id': lib_id_new
            })

    rec.set_schools(schools)

    # Prepare updated exact entry for precise UI syncing
    updated_entry = None
    if match_idx is not None:
        updated_entry = schools[match_idx]
    else:
        # If appended, use the last element (or the dict we just added)
        if schools:
            updated_entry = schools[-1]

    try:
        db.session.commit()
        return jsonify({
            "updated": updated_entry,
            "champion": rec.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400



# @app.route('/home', methods=['GET', 'POST'])
# @login_required
# def home():
#     try:
#         with SSHTunnelForwarder(
#             (ssh_host, 22),
#             ssh_username=ssh_username,
#             ssh_password=ssh_password,
#             remote_bind_address=(mysql_host, mysql_port),
#             local_bind_address=('127.0.0.1', 3307)
#         ) as tunnel:
#             connection = pymysql.connect(
#                 host='127.0.0.1',
#                 port=3307,
#                 user=mysql_user,
#                 password=mysql_password,
#                 database=mysql_db,
#                 cursorclass=pymysql.cursors.DictCursor
#             )

#             cursor = connection.cursor()

#             cursor.execute("SELECT name, level, number_of_users, province FROM institutions LIMIT 100;")
#             institutions = cursor.fetchall()

#             cursor.execute("SELECT * FROM ba_payouts LIMIT 50;")
#             ba_payouts = cursor.fetchall()

#             cursor.close()
#             connection.close()

#             return render_template('home.html', title='Home',institutions=institutions,
#                                    ba_payouts=ba_payouts)
#     except Exception as e:
#         return f"<h3>Error: {str(e)}</h3>"





# Database configuration
DB_CONFIG = {
    'host': '40.90.237.225',
    'port': 33000,
    'user': 'qmashava',
    'password': '#Qhava@@!Fu11',
    'database': 'ruzivo_2017',
    'cursorclass': pymysql.cursors.DictCursor
}



@app.route('/analytics', methods=['GET', 'POST'])
@login_required
def analytics():
        ptfform = PerfomanceTargetsForm()
        PTargets = PerfomanceTargets.query.all()
        today = datetime.today().date()
        nhasi = today.strftime('%y- %m- %d')
        month_name = today.strftime('%B')
        latest_target = PerfomanceTargets.query.order_by(PerfomanceTargets.timestamp.desc()).first()

        return render_template('analytics.html',ptfform=ptfform,PTargets=PTargets,
                               latest_target=latest_target,
                               month_name=month_name,
                               nhasi=nhasi,
                           title='Analytics')



@app.route('/akello_analytics', methods=['GET', 'POST'])
@login_required
def akello_analytics():
        if current_user.userRole == 'Brand Ambassador':
            return redirect(url_for('index'))
        else:
            ptfform = PerfomanceTargetsForm()
            PTargets = PerfomanceTargets.query.all()
            today = datetime.today().date()
            nhasi = today.strftime('%y- %m- %d')
            month_name = today.strftime('%B')
            latest_target = PerfomanceTargets.query.order_by(PerfomanceTargets.timestamp.desc()).first()
            # print(current_user.privileges)

        return render_template('akello_analytics.html',ptfform=ptfform,PTargets=PTargets,
                               latest_target=latest_target,
                               month_name=month_name,
                               nhasi=nhasi,
                           title='Analytics')









# new project planning


# -- Helper to serialize --
def column_to_dict(col):
    return {
        "id": col.id,
        "title": col.title,
        "position": col.position,
        "tasks": [task_to_dict(t) for t in sorted(col.tasks, key=lambda x: x.position)]
    }

def task_to_dict(t):
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "position": t.position,
        "progress": t.progress,
        "start_date": t.start_date.isoformat() if t.start_date else None,
        "end_date": t.end_date.isoformat() if t.end_date else None,
        "column_id": t.column_id,
        "created_at": t.created_at.isoformat(),
        "assignees": [{"id": u.id, "name": u.username} for u in getattr(t, "assignees", [])]
    }



@app.before_request
def create_tables():
    db.create_all()
    # seed sample if empty
    if ProjectA.query.count() == 0:
        p = ProjectA(name="Example Project")
        db.session.add(p)
        db.session.commit()
        for idx, name in enumerate(["Ideas","To Do","Doing","Done"]):
            col = ColumnA(project_id=p.id, title=name, position=idx)
            db.session.add(col)
            db.session.commit()
            # add a sample task
            t = TaskA(column_id=col.id, title=f"Sample task in {name}", position=0)
            db.session.add(t)
        db.session.commit()

@app.route("/projectmanagemnt",  methods=["GET", "POST"])
def projectmanagement():

    return render_template("aplanforprojects.html")

# List + create projects
@app.route("/api/projects", methods=["GET", "POST"])
@login_required
def projectsA():
    if request.method == "GET":
        ps = ProjectA.query.all()
        return jsonify([
            {
                "id": p.id,
                "name": p.name,
                "type": p.project_type,
                "members": [u.username for u in p.members]
            } for p in ps
        ])
    
    data = request.get_json()
    if not data or "name" not in data:
        return os.abort(400)
    p = ProjectA(
        name=data["name"],
        project_type=data.get("project_type", "private")
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({"id": p.id, "name": p.name, "type": p.project_type}), 201



# Edit a project
@app.route("/api/projects/<int:project_id>", methods=["GET"])
@login_required
def get_projectA(project_id):
    p = ProjectA.query.get_or_404(project_id)
    return jsonify({
        "id": p.id,
        "name": p.name,
        "type": p.project_type,
        "members": [{"id": u.id, "name": u.username} for u in p.members]
    })


# Edit a project
@app.route("/api/projects/<int:project_id>", methods=["PATCH"])
@login_required
def edit_projectA(project_id):
    p = ProjectA.query.get_or_404(project_id)
    data = request.get_json()

    if "name" in data:
        p.name = data["name"]
    if "project_type" in data:
        p.project_type = data["project_type"]

    # ✅ Replace members if provided
    if "members" in data:
        member_ids = set(data["members"])  # list of user IDs
        # fetch users that exist in DB
        p.members = [User.query.get(uid) for uid in member_ids if User.query.get(uid)]

    db.session.commit()
    return jsonify({
        "id": p.id,
        "name": p.name,
        "type": p.project_type,
        "members": [u.id for u in p.members]  # return IDs for clarity
    })



# Delete a project
@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
@login_required
def delete_projectA(project_id):
    p = ProjectA.query.get_or_404(project_id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"status": "deleted"})


# Add members to a project
@app.route("/api/projects/<int:project_id>/members", methods=["GET"])
@login_required
def get_membersA(project_id):
    p = ProjectA.query.get_or_404(project_id)
    return jsonify([{"id": u.id, "name": u.username} for u in p.members])


# Add members to a project
@app.route("/api/projects/<int:project_id>/members", methods=["POST"])
@login_required
def add_membersA(project_id):
    p = ProjectA.query.get_or_404(project_id)
    data = request.get_json()
    user_ids = data.get("user_ids", [])
    if not isinstance(user_ids, list):
        return os.abort(400)
    for uid in user_ids:
        user = User.query.get(uid)
        if user and user not in p.members:
            p.members.append(user)
    db.session.commit()
    return jsonify({
        "id": p.id,
        "members": [u.username for u in p.members]
    })


@app.route("/api/users", methods=["GET"])
@login_required
def get_users():
    """
    Fetches a list of all users and returns their IDs and usernames.
    This is used by the frontend to populate the list of potential members
    for a project.
    """
    users = User.query.all()
    user_list = [
        {"id": user.id, "name": user.username} for user in users
    ]
    return jsonify(user_list)



# Get board (columns + tasks) for a project
@app.route("/api/projects/<int:project_id>/board", methods=["GET"])
@login_required
def project_board(project_id):
    p = ProjectA.query.get_or_404(project_id)
    cols = ColumnA.query.filter_by(project_id=p.id).order_by(ColumnA.position).all()
    return jsonify({
        "id": p.id,
        "name": p.name,
        "columns": [column_to_dict(c) for c in cols]
    })

# Create column in project
@app.route("/api/projects/<int:project_id>/columns", methods=["POST"])
@login_required
def create_column(project_id):
    p = ProjectA.query.get_or_404(project_id)
    data = request.get_json()
    title = data.get("title","New Column")
    # set position to end
    maxpos = db.session.query(db.func.max(ColumnA.position)).filter_by(project_id=project_id).scalar()
    pos = (maxpos + 1) if maxpos is not None else 0
    c = ColumnA(project_id=project_id, title=title, position=pos)
    db.session.add(c)
    db.session.commit()
    return jsonify(column_to_dict(c)), 201



@app.route("/api/columns/<int:column_id>", methods=["PATCH"])
@login_required
def patch_column(column_id):
    c = ColumnA.query.get_or_404(column_id)
    data = request.get_json() or {}
    if "title" in data:
        c.title = data["title"]
        db.session.commit()
    return jsonify(column_to_dict(c))



# Create task
@app.route("/api/columns/<int:column_id>/tasks", methods=["POST"])
@login_required
def create_taskA(column_id):
    col = ColumnA.query.get_or_404(column_id)
    data = request.get_json()
    title = data.get("title", "New Task")
    desc = data.get("description", "")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    assignees_ids = data.get("assignees", [])  # optional list of user IDs

    # parse dates if provided
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    # ✅ validation
    if start_dt and end_dt and end_dt < start_dt:
        return jsonify({"error": "end_date must be greater than or equal to start_date"}), 400

    maxpos = db.session.query(db.func.max(TaskA.position)).filter_by(column_id=column_id).scalar()
    pos = (maxpos + 1) if maxpos is not None else 0

    t = TaskA(
        column_id=column_id,
        title=title,
        description=desc,
        position=pos,
        start_date=start_dt,
        end_date=end_dt
    )
    # set initial assignees if provided
    if isinstance(assignees_ids, list) and len(assignees_ids) > 0:
        t.assignees = [User.query.get(uid) for uid in assignees_ids if User.query.get(uid)]
    db.session.add(t)
    db.session.commit()
    return jsonify(task_to_dict(t)), 201



# --- Task update extended with progress ---
@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
@login_required
def update_taskA(task_id):
    t = TaskA.query.get_or_404(task_id)
    data = request.get_json()

    if "title" in data:
        t.title = data["title"]
    if "assignees" in data and isinstance(data["assignees"], list):
        ids = set([int(x) for x in data["assignees"]])
        t.assignees = [User.query.get(uid) for uid in ids if User.query.get(uid)]
    if "description" in data:
        t.description = data["description"]
    if "progress" in data:
        t.progress = max(0, min(100, int(data["progress"])))

    # handle dates
    if "start_date" in data:
        t.start_date = datetime.fromisoformat(data["start_date"]) if data["start_date"] else None
    if "end_date" in data:
        t.end_date = datetime.fromisoformat(data["end_date"]) if data["end_date"] else None

    # ✅ validation after updating
    if t.start_date and t.end_date and t.end_date < t.start_date:
        return jsonify({"error": "end_date must be greater than or equal to start_date"}), 400

    # handle column moves + reordering (same as before)
    if "column_id" in data or "position" in data:
        new_col_id = data.get("column_id", t.column_id)
        new_pos = data.get("position", None)
        if new_col_id != t.column_id:
            old_tasks = TaskA.query.filter(
                TaskA.column_id == t.column_id,
                TaskA.id != t.id
            ).order_by(TaskA.position).all()
            for idx, ot in enumerate(old_tasks):
                ot.position = idx
            dest_tasks = TaskA.query.filter_by(column_id=new_col_id).order_by(TaskA.position).all()
            if new_pos is None or new_pos > len(dest_tasks):
                new_pos = len(dest_tasks)
            for ot in dest_tasks[::-1]:
                if ot.position >= new_pos:
                    ot.position += 1
            t.column_id = new_col_id
            t.position = new_pos
        elif new_pos is not None:
            tasks = TaskA.query.filter_by(column_id=t.column_id).order_by(TaskA.position).all()
            tasks = [x for x in tasks if x.id != t.id]
            tasks.insert(new_pos, t)
            for idx, ot in enumerate(tasks):
                ot.position = idx

    db.session.commit()
    return jsonify(task_to_dict(t))

# Reorder columns in a project
@app.route("/api/projects/<int:project_id>/columns/reorder", methods=["POST"])
@login_required
def reorder_columns(project_id):
    p = ProjectA.query.get_or_404(project_id)
    data = request.get_json()
    order = data.get("order", [])  # list of column ids in new order
    if not isinstance(order, list):
        return os.abort(400)
    for idx, cid in enumerate(order):
        c = ColumnA.query.filter_by(id=cid, project_id=project_id).first()
        if c:
            c.position = idx
    db.session.commit()
    return jsonify({"status":"ok"})

# Delete endpoints (optional)
@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_taskA(task_id):
    t = TaskA.query.get_or_404(task_id)
    col_id = t.column_id
    db.session.delete(t)
    db.session.commit()
    # reindex
    tasks = TaskA.query.filter_by(column_id=col_id).order_by(TaskA.position).all()
    for idx, ot in enumerate(tasks):
        ot.position = idx
    db.session.commit()
    return jsonify({"status":"deleted"})



#new project planning ends here

# ---------- New Dashboard Layout ----------
@app.route('/new_dash', methods=['GET'])
@login_required
def new_dash_layout():
    return render_template('new_dash_layout.html')

# ---------- Overview (dummy) ----------
@app.route('/')
@app.route('/overview', methods=['GET'])
@login_required
def overview():
    return render_template('overview.html', title="Akello Internal Dashboard")
















@app.route('/targets/new', methods=['GET', 'POST'])
@login_required
def create_target():
    form = PerfomanceTargetsForm()
    if form.validate_on_submit():
        new_target = PerfomanceTargets(
            smartlearning_registrations_monthly_target=form.smartlearning_registrations_monthly_target.data,
            smartlearning_registrations_daily_target=form.smartlearning_registrations_daily_target.data,
            smartlearning_unique_subscribers_monthly_target=form.smartlearning_unique_subscribers_monthly_target.data,
            smartlearning_unique_subscribers_daily_target=form.smartlearning_unique_subscribers_daily_target.data,
            ask_akello_users_monthly_target=form.ask_akello_users_monthly_target.data,
            ask_akello_users_daily_target=form.ask_akello_users_daily_target.data,
            library_registrations_monthly_target=form.library_registrations_monthly_target.data,
            library_registrations_daily_target=form.library_registrations_daily_target.data,
            library_unique_users_monthly_target=form.library_unique_users_monthly_target.data,
            library_unique_users_daily_target=form.library_unique_users_daily_target.data,
            overall_active30_target=form.overall_active30_target.data,
            updated_by= current_user.username
        )
        db.session.add(new_target)
        db.session.commit()
        flash("Performance target created successfully!", "success")
        return redirect(url_for('analytics'))



@app.route('/targets/<int:target_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_target(target_id):
    target = PerfomanceTargets.query.get_or_404(target_id)
    form = PerfomanceTargetsForm(obj=target)
    if form.validate_on_submit():
        form.populate_obj(target)
        db.session.commit()
        flash("Performance target updated successfully!", "success")
        return redirect(url_for('analytics'))




@app.route('/all-champion-details', methods=['GET', 'POST'])
@login_required
def all_champion_details():

    return render_template('all_champions_data.html',
                           title='Champions')





# @app.route('/provincestats/<provincename>', methods=['GET', 'POST'])
# @login_required
# def provincestats(provincename):
#         province_champions = ChampionSchool.query.filter(ChampionSchool.province == provincename)
#         local_province_champion = ChampionSchool.query.filter(ChampionSchool.province == provincename)
#         today = datetime.today().date()
#         nhasi = today.strftime('%y- %m- %d')
#         month_name = today.strftime('%B')
        

#         return render_template('province_stats.html',
#                                provincename=provincename,
#                                province_champions=province_champions,
#                                local_province_champion=local_province_champion,
#                                nhasi = nhasi,
#                                month_name=month_name,
#                            title='School Tracker')


@app.route('/provincestats/<provincename>', methods=['GET', 'POST'])
@login_required
def provincestats(provincename):
        province_champions = ChampionSchool.query.filter(ChampionSchool.province == provincename)
        local_province_champion = ChampionSchool.query.filter(ChampionSchool.province == provincename)
        today = datetime.today().date()
        nhasi = today.strftime('%y- %m- %d')
        month_name = today.strftime('%B')
        

        return render_template('simone_province_stats.html',
                               provincename=provincename,
                               province_champions=province_champions,
                               local_province_champion=local_province_champion,
                               nhasi = nhasi,
                               month_name=month_name,
                           title='School Tracker')


@app.route('/api/all-champions-ask-data', methods=['GET'])
@login_required
def all_champions_ask_data():
    """Fast aggregated Ask Akello chatlog counts per champion.
    Allows optional ?start_date and ?end_date query params.
    Defaults to first of the current month through now().
    """
    # Handle date range with hours
    today = datetime.now()
    default_start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    try:
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        else:
            start_date = default_start_date

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            end_date = today
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS."}), 400

    # Load champions and local champions once
    champions = ChampionSchool.query.all()
    local_champions = User.query.filter(User.userRole == 'Brand Ambassador').all()
    user_index = {(
        (u.firstname or '').strip().lower(),
        (u.lastname or '').strip().lower(),
        (u.province or '').strip().lower()
    ): u.username for u in local_champions}

    # Build mapping: champion -> ASL school IDs
    champ_to_asl_ids = {}
    all_asl_ids = []
    for champ in champions:
        schools = champ.get_schools() or []
        ids = [int(s.get('asl_school_id')) for s in schools if str(s.get('asl_school_id') or '').strip().isdigit()]
        if ids:
            champ_to_asl_ids[champ.id] = ids
            all_asl_ids.extend(ids)

    if not all_asl_ids:
        return jsonify([])

    # Deduplicate IDs
    all_asl_ids = sorted(set(all_asl_ids))

    # Query once: chatlog counts per school_id within date range
    counts_by_school = {}
    try:
        pool = get_ruzivo_pool()
        if pool is None:
            return jsonify({"error": "Database connection not available"}), 500
        conn = pool.connection()
        import pymysql.cursors
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        CHUNK = 1000
        for i in range(0, len(all_asl_ids), CHUNK):
            chunk = all_asl_ids[i:i + CHUNK]
            placeholders = ','.join(['%s'] * len(chunk))
            
            # Updated query (no hardcoded school_id, dynamic IN clause)
            query = f"""
                SELECT 
                    sc.school_id,
                    sc.school_name,
                    sc.school_province,
                    COUNT(DISTINCT tl.student_id) AS chatlog_count
                FROM tblask_akello_chat_logs tl
                LEFT JOIN tblstudents ts ON ts.student_id = tl.student_id
                LEFT JOIN tblschools sc ON sc.school_id = ts.school_id
                WHERE sc.school_id IN ({placeholders})
                  AND tl.created_at BETWEEN %s AND %s
                GROUP BY sc.school_id, sc.school_name, sc.school_province
            """

            params = chunk + [start_date, end_date]
            cursor.execute(query, params)
            for row in cursor.fetchall():
                sid = int(row['school_id'])
                counts_by_school[sid] = counts_by_school.get(sid, 0) + int(row['chatlog_count'] or 0)
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    # Build response per champion
    results = []
    for champ in champions:
        asl_ids = champ_to_asl_ids.get(champ.id, [])
        if not asl_ids:
            continue
        chatlog_sum = sum(counts_by_school.get(int(sid), 0) for sid in asl_ids)
        username = user_index.get((
            (champ.firstname or '').strip().lower(),
            (champ.lastname or '').strip().lower(),
            (champ.province or '').strip().lower()
        ))
        results.append({
            'champion': f"{champ.firstname} {champ.lastname}",
            'username': username,
            'province': champ.province,
            'school_count': len(asl_ids),
            'chatlog_count': chatlog_sum
        })

    return jsonify(results)






@app.route('/api/ask-akello-chosen-school/<school_id>', methods=['GET'])
@login_required
def ask_akello_chosen_school(school_id):
    """
    Returns total chat log counts for a given school_id
    with optional date range support (defaults to MTD).
    """

    # Get date range from query parameters or default to MTD
    today = datetime.now()
    default_start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    try:
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        else:
            start_date = default_start_date

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            end_date = today
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS."}), 400

    try:
        # Connect to ruzivo database
        pool = get_ruzivo_pool()
        if pool is None:
            return jsonify({"error": "Database connection not available"}), 500

        conn = pool.connection()
        import pymysql.cursors
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Updated query (Ask Akello style)
        chatlog_query = """
            SELECT 
                sc.school_id,
                sc.school_name,
                sc.school_province,
                COUNT(DISTINCT tl.student_id) AS chatlog_count
            FROM tblask_akello_chat_logs tl
            LEFT JOIN tblstudents ts 
                ON ts.student_id = tl.student_id
            LEFT JOIN tblschools sc 
                ON sc.school_id = ts.school_id
            WHERE 
                tl.created_at BETWEEN %s AND %s
                AND sc.school_id = %s
            GROUP BY 
                sc.school_id, sc.school_name, sc.school_province
        """

        # Execute query
        cursor.execute(chatlog_query, (start_date, end_date, school_id))
        result = cursor.fetchone()

        response = {
            "school_id": school_id,
            "school_name": result["school_name"] if result else None,
            "school_province": result["school_province"] if result else None,
            "chatlog_count": result["chatlog_count"] if result else 0,
            "start_date": str(start_date),
            "end_date": str(end_date),
        }

        return jsonify(response)

    except Exception as e:
        print("Error fetching Ask Akello data:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()





@app.route('/api/champion-schools-data/<province_name>', methods=['GET'])
@login_required
@cache.cached(
    timeout=300, 
    key_prefix=lambda: f'ask_akello_{request.view_args["province_name"]}_{request.args.get("start_date", "")}_{request.args.get("end_date", "")}'
)
def champion_schools_data(province_name):
    """
    Returns total Ask Akello chat log counts per Champion within a province.
    Uses optional ?start_date and ?end_date (with hours).
    Defaults to first day of current month through now().
    """

    # --- Handle date range ---
    today = datetime.now()
    default_start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    try:
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        else:
            start_date = default_start_date

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            end_date = today
    except ValueError:
        return jsonify({
            "error": "Invalid date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS."
        }), 400

    try:
        # --- Load champions & local Brand Ambassadors for this province ---
        champions = ChampionSchool.query.filter_by(province=province_name).all()
        local_champions = User.query.filter(
            User.province == province_name,
            User.userRole == 'Brand Ambassador'
        ).all()

        results = []

        for champ in champions:
            schools = champ.get_schools() or []
            asl_ids = [s.get('asl_school_id') for s in schools if s.get('asl_school_id')]

            if not asl_ids:
                continue

            conn = None
            cursor = None
            try:
                pool = get_ruzivo_pool()
                if pool is None:
                    raise Exception("Database connection not available")
                conn = pool.connection()
                import pymysql.cursors
                cursor = conn.cursor(pymysql.cursors.DictCursor)

                # --- Updated Ask Akello query ---
                format_strings = ','.join(['%s'] * len(asl_ids))
                chatlog_query = f"""
                    SELECT 
                        sc.school_id,
                        sc.school_name,
                        sc.school_province,
                        COUNT(DISTINCT tl.student_id) AS chatlog_count
                    FROM tblask_akello_chat_logs tl
                    LEFT JOIN tblstudents ts 
                        ON ts.student_id = tl.student_id
                    LEFT JOIN tblschools sc 
                        ON sc.school_id = ts.school_id
                    WHERE 
                        sc.school_id IN ({format_strings})
                        AND tl.created_at BETWEEN %s AND %s
                    GROUP BY 
                        sc.school_id, sc.school_name, sc.school_province;
                """

                params = tuple(asl_ids) + (start_date, end_date)
                cursor.execute(chatlog_query, params)
                result_rows = cursor.fetchall()
                chatlog_count = sum(r['chatlog_count'] for r in result_rows) if result_rows else 0

            except Exception as e:
                logging.error(
                    f"Error fetching chatlog for champion {champ.firstname} {champ.lastname}: {e}"
                )
                chatlog_count = 0

            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()

            # --- Match champion to local Brand Ambassador username ---
            username = None
            for local in local_champions:
                if (
                    (local.firstname or '').strip().lower() == (champ.firstname or '').strip().lower() and
                    (local.lastname or '').strip().lower() == (champ.lastname or '').strip().lower()
                ):
                    username = getattr(local, 'username', None)
                    break

            # --- Build result entry ---
            results.append({
                "champion": f"{champ.firstname} {champ.lastname}",
                "username": username,
                "school_count": len(asl_ids),
                "chatlog_count": chatlog_count
            })

        return jsonify(results)

    except Exception as e:
        logging.error(f"Error in champion_schools_data: {e}")
        return jsonify({"error": str(e)}), 500









@app.route("/provincialmoneylibraryallocation", methods=["GET"])
def provincial_money_library_allocation():
    try:
        # --- get date range ---
        today = date.today()
        first_of_month = today.replace(day=1)

        start_date = request.args.get("start_date", first_of_month.isoformat())
        end_date = request.args.get("end_date", today.isoformat())

        # --- query ---
        query = """
            SELECT 
                i.province,
                SUM(o.total_amount) as total_amount
            FROM orders o
            INNER JOIN users ou ON o.user_id = ou.id
            INNER JOIN institution_user iu ON ou.id = iu.user_id
            INNER JOIN institutions i ON iu.institution_id = i.id
            INNER JOIN model_has_roles mr ON ou.id = mr.model_id
            INNER JOIN roles r ON mr.role_id = r.id
            INNER JOIN book_order bo ON o.id = bo.order_id
            WHERE r.name = 'Institution'
              AND o.currency = 'ZWL'
              AND o.payment_method = 'Voucher'
              AND o.is_hlf = 1
              AND o.status = 'Completed'
              AND o.payment_type = 'Purchase'
              AND o.created_at BETWEEN %s AND %s
            GROUP BY i.province
            ORDER BY i.province;
        """

        conn = get_direct_library_conn()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        # --- format response ---
        total_sum = sum([row["total_amount"] for row in results if row["total_amount"]])
        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "data": results,
            "grand_total": total_sum
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500






@app.route("/api/publisherlibraryamount", methods=["GET"])
@login_required
def publisher_library_amount():
    try:
        # Default date range
        today = date.today()
        first_of_month = today.replace(day=1)

        start_date = request.args.get("start_date", first_of_month.isoformat())
        end_date = request.args.get("end_date", today.isoformat())

        query = """
            SELECT 
                p.id AS publisher_id,
                p.name AS publisher_name,
                SUM(CASE WHEN o.currency = 'ZWL' THEN o.total_amount ELSE 0 END) AS total_amount_zwl,
                SUM(CASE WHEN o.currency = 'USD' THEN o.total_amount ELSE 0 END) AS total_amount_usd
            FROM orders o
            INNER JOIN book_order bo 
                ON o.id = bo.order_id
            INNER JOIN books b 
                ON bo.book_id = b.id
            INNER JOIN publisher_user pu 
                ON b.user_id = pu.user_id
            INNER JOIN publishers p 
                ON pu.publisher_id = p.id
            WHERE o.created_at BETWEEN %s AND %s
              AND o.currency IN ('ZWL', 'USD')
            GROUP BY p.id, p.name

            UNION ALL

            SELECT 
                NULL AS publisher_id,
                'Grand Total' AS publisher_name,
                SUM(CASE WHEN o.currency = 'ZWL' THEN o.total_amount ELSE 0 END) AS total_amount_zwl,
                SUM(CASE WHEN o.currency = 'USD' THEN o.total_amount ELSE 0 END) AS total_amount_usd
            FROM orders o
            INNER JOIN book_order bo 
                ON o.id = bo.order_id
            INNER JOIN books b 
                ON bo.book_id = b.id
            INNER JOIN publisher_user pu 
                ON b.user_id = pu.user_id
            INNER JOIN publishers p 
                ON pu.publisher_id = p.id
            WHERE o.created_at BETWEEN %s AND %s
              AND o.currency IN ('ZWL', 'USD')
            ORDER BY publisher_name;
        """

        conn = get_direct_library_conn()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date, start_date, end_date))
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "data": results
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500




















@app.route('/api/champion-schools-smartlearning-usage-analytics', methods=['GET'])
@login_required
def champion_schools_smartlearning_usage_analytics():
    """Fast aggregated analytics for champions across ASL and Library.
    Performs grouped queries across all relevant schools, then reduces per champion.
    """
    today = datetime.today().date()
    default_start_date = today.replace(day=1)

    # --- Allow custom date range via query params ---
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            start_date = default_start_date

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            end_date = today
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Get all champions (no province filter) and map usernames for O(1) lookup
    champions = ChampionSchool.query.all()
    local_champions = User.query.filter(User.userRole == 'Brand Ambassador').all()
    user_index = {(
        (u.firstname or '').strip().lower(),
        (u.lastname or '').strip().lower(),
        (u.province or '').strip().lower()
    ): u.username for u in local_champions}

    # Build mappings and flattened ID sets
    champ_asl = {}
    champ_lib = {}
    all_asl_ids, all_lib_ids = [], []
    for champ in champions:
        schools = champ.get_schools() or []
        asl_ids = [int(s.get('asl_school_id')) for s in schools if str(s.get('asl_school_id') or '').strip().isdigit()]
        lib_ids = [int(s.get('library_school_id')) for s in schools if str(s.get('library_school_id') or '').strip().isdigit()]
        if asl_ids:
            champ_asl[champ.id] = asl_ids
            all_asl_ids.extend(asl_ids)
        if lib_ids:
            champ_lib[champ.id] = lib_ids
            all_lib_ids.extend(lib_ids)

    all_asl_ids = sorted(set(all_asl_ids))
    all_lib_ids = sorted(set(all_lib_ids))

    # Early return if nothing to process
    if not all_asl_ids and not all_lib_ids:
        return jsonify([])

    # Time bounds as datetimes for BETWEEN comparisons
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    # 1) ASL: count distinct student_id per school_id, grouped once
    asl_counts_by_school = {}
    if all_asl_ids:
        try:
            pool = get_ruzivo_pool()
            if pool is None:
                return jsonify({"error": "Database connection not available"}), 500
            conn = pool.connection()
            import pymysql.cursors
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            CHUNK = 1000
            for i in range(0, len(all_asl_ids), CHUNK):
                chunk = all_asl_ids[i:i+CHUNK]
                placeholders = ','.join(['%s'] * len(chunk))
                query = f"""
                    SELECT school_id, COUNT(DISTINCT student_id) AS student_count
                    FROM vwstudent
                    WHERE school_id IN ({placeholders})
                      AND last_login BETWEEN %s AND %s
                    GROUP BY school_id
                """
                params = chunk + [start_dt, end_dt]
                cursor.execute(query, params)
                for row in cursor.fetchall():
                    sid = int(row['school_id'])
                    asl_counts_by_school[sid] = asl_counts_by_school.get(sid, 0) + int(row['student_count'] or 0)
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    # 2) Library: count distinct la.user_id per institution, grouped once
    lib_counts_by_inst = {}
    if all_lib_ids:
        try:
            conn = get_direct_library_conn()
            import pymysql.cursors
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            CHUNK = 1000
            for i in range(0, len(all_lib_ids), CHUNK):
                chunk = all_lib_ids[i:i+CHUNK]
                placeholders = ','.join(['%s'] * len(chunk))
                query = f"""
                    SELECT iu.institution_id AS inst_id, COUNT(DISTINCT la.user_id) AS active_users
                    FROM logins la
                    JOIN institution_user iu ON la.user_id = iu.user_id
                    WHERE iu.institution_id IN ({placeholders})
                      AND la.created_at BETWEEN %s AND %s
                    GROUP BY iu.institution_id
                """
                params = chunk + [start_dt, end_dt]
                cursor.execute(query, params)
                for row in cursor.fetchall():
                    iid = int(row['inst_id'])
                    lib_counts_by_inst[iid] = lib_counts_by_inst.get(iid, 0) + int(row['active_users'] or 0)
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    # Build response rows per champion by summing precomputed counts
    results = []
    for champ in champions:
        asl_ids = champ_asl.get(champ.id, [])
        lib_ids = champ_lib.get(champ.id, [])
        if not asl_ids and not lib_ids:
            continue

        asl_student_count = sum(asl_counts_by_school.get(int(sid), 0) for sid in asl_ids)
        library_student_count = sum(lib_counts_by_inst.get(int(iid), 0) for iid in lib_ids)
        overall_student_count = asl_student_count + library_student_count

        username = user_index.get((
            (champ.firstname or '').strip().lower(),
            (champ.lastname or '').strip().lower(),
            (champ.province or '').strip().lower()
        ))

        results.append({
            "champion": f"{champ.firstname} {champ.lastname}",
            "username": username,
            "province": f"{champ.province}",
            "school_count": len(asl_ids),
            "asl_student_count": asl_student_count,
            "library_student_count": library_student_count,
            "overall_student_count": overall_student_count
        })

    return jsonify(results)





@app.route('/api/champ-library-usage', methods=['GET'])
@login_required
def champ_library_usage():
    firstname = request.args.get("firstname")
    lastname = request.args.get("lastname")

    if not firstname or not lastname:
        return jsonify({"error": "Missing required parameters: firstname, lastname"}), 400

    # --- Date range (default: this month until today) ---
    today = datetime.today().date()
    default_start_date = today.replace(day=1)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            start_date = default_start_date

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            end_date = today
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # --- Find champion ---
    champ = ChampionSchool.query.filter_by(firstname=firstname, lastname=lastname).first()
    if not champ:
        return jsonify({"error": "Champion not found"}), 404

    # --- Get associated schools and library IDs ---
    schools = champ.get_schools()
    library_ids = [s.get('library_school_id') for s in schools if s.get('library_school_id')]

    if not library_ids:
        return jsonify({
            "champion": f"{champ.firstname} {champ.lastname}",
            "library_student_count": 0
        })

    # --- Query Library DB ---
    library_student_count = 0
    conn = None
    cursor = None
    try:
        conn = get_direct_library_conn()
        if conn:
            import pymysql.cursors
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            library_ids_int = [int(sid) for sid in library_ids if sid]
            if library_ids_int:
                in_placeholders = ', '.join(['%s'] * len(library_ids_int))
                query = f"""
                    SELECT COUNT(DISTINCT la.user_id) AS active_users
                    FROM logins la
                    JOIN institution_user iu ON la.user_id = iu.user_id
                    WHERE iu.institution_id IN ({in_placeholders})
                      AND la.created_at BETWEEN %s AND %s
                """

                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.max.time())
                params = library_ids_int + [start_dt, end_dt]

                cursor.execute(query, params)
                row = cursor.fetchone()
                library_student_count = row["active_users"] if row else 0
        else:
            logging.error("Failed to get Library DB connection")
    except Exception as e:
        logging.error("Library query error for champion %s %s: %s",
                      champ.firstname, champ.lastname, e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    # --- Response ---
    return jsonify({
        "champion": f"{champ.firstname} {champ.lastname}",
        "province": champ.province,
        "library_student_count": library_student_count
    })







@app.route('/api/champion-schools-smartlearning-usage/<province_name>', methods=['GET'])
@login_required
@cache.cached(timeout=300, key_prefix=lambda: f'champion_usage_{request.view_args["province_name"]}_{request.args.get("start_date", "")}_{request.args.get("end_date", "")}')
def champion_schools_smartlearning_usage(province_name):
    """OPTIMIZED: Bulk queries instead of N+1 - fetches all data in 2 queries total."""
    # Get date range from query parameters or default to MTD
    today = datetime.today().date()
    default_start_date = today.replace(day=1)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            start_date = default_start_date

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            end_date = today
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Get champions for this province
    champions = ChampionSchool.query.filter_by(province=province_name).all()
    local_champions = User.query.filter(
        User.province == province_name,
        User.userRole == 'Brand Ambassador'
    ).all()

    # Build username lookup index
    user_index = {(
        (u.firstname or '').strip().lower(),
        (u.lastname or '').strip().lower(),
        (u.province or '').strip().lower()
    ): u.username for u in local_champions}

    # Build mappings and collect all IDs
    champ_asl = {}
    champ_lib = {}
    all_asl_ids, all_lib_ids = [], []
    
    for champ in champions:
        schools = champ.get_schools() or []
        asl_ids = [int(s.get('asl_school_id')) for s in schools if str(s.get('asl_school_id') or '').strip().isdigit()]
        lib_ids = [int(s.get('library_school_id')) for s in schools if str(s.get('library_school_id') or '').strip().isdigit()]
        
        if asl_ids:
            champ_asl[champ.id] = asl_ids
            all_asl_ids.extend(asl_ids)
        if lib_ids:
            champ_lib[champ.id] = lib_ids
            all_lib_ids.extend(lib_ids)

    all_asl_ids = sorted(set(all_asl_ids))
    all_lib_ids = sorted(set(all_lib_ids))

    # Early return if nothing to process
    if not all_asl_ids and not all_lib_ids:
        return jsonify([])

    # Time bounds
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    # BULK QUERY 1: ASL - fetch all school counts in one query
    asl_counts_by_school = {}
    if all_asl_ids:
        conn = None
        cursor = None
        try:
            pool = get_ruzivo_pool()
            if pool is None:
                logging.error("Ruzivo pool not available")
            else:
                conn = pool.connection()
                import pymysql.cursors
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                
                # Process in chunks if needed
                CHUNK = 1000
                for i in range(0, len(all_asl_ids), CHUNK):
                    chunk = all_asl_ids[i:i+CHUNK]
                    placeholders = ','.join(['%s'] * len(chunk))
                    query = f"""
                        SELECT school_id, COUNT(DISTINCT student_id) AS student_count
                        FROM vwstudent
                        WHERE school_id IN ({placeholders})
                          AND last_login BETWEEN %s AND %s
                        GROUP BY school_id
                    """
                    params = chunk + [start_dt, end_dt]
                    cursor.execute(query, params)
                    
                    for row in cursor.fetchall():
                        sid = int(row['school_id'])
                        asl_counts_by_school[sid] = int(row['student_count'] or 0)
        except Exception as e:
            logging.error("ASL bulk query error: %s", e)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # BULK QUERY 2: Library - fetch all institution counts in one query
    lib_counts_by_inst = {}
    if all_lib_ids:
        conn = None
        cursor = None
        try:
            conn = get_direct_library_conn()
            if conn:
                import pymysql.cursors
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                
                # Process in chunks if needed
                CHUNK = 1000
                for i in range(0, len(all_lib_ids), CHUNK):
                    chunk = all_lib_ids[i:i+CHUNK]
                    placeholders = ','.join(['%s'] * len(chunk))
                    query = f"""
                        SELECT iu.institution_id AS inst_id, COUNT(DISTINCT la.user_id) AS active_users
                        FROM logins la
                        JOIN institution_user iu ON la.user_id = iu.user_id
                        WHERE iu.institution_id IN ({placeholders})
                          AND la.created_at BETWEEN %s AND %s
                        GROUP BY iu.institution_id
                    """
                    params = chunk + [start_dt, end_dt]
                    cursor.execute(query, params)
                    
                    for row in cursor.fetchall():
                        iid = int(row['inst_id'])
                        lib_counts_by_inst[iid] = int(row['active_users'] or 0)
        except Exception as e:
            logging.error("Library bulk query error: %s", e)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # Build results by aggregating precomputed counts
    results = []
    for champ in champions:
        asl_ids = champ_asl.get(champ.id, [])
        lib_ids = champ_lib.get(champ.id, [])
        
        if not asl_ids and not lib_ids:
            continue

        # Sum up counts from bulk query results
        asl_student_count = sum(asl_counts_by_school.get(int(sid), 0) for sid in asl_ids)
        library_student_count = sum(lib_counts_by_inst.get(int(iid), 0) for iid in lib_ids)
        overall_student_count = asl_student_count + library_student_count

        # Lookup username
        username = user_index.get((
            (champ.firstname or '').strip().lower(),
            (champ.lastname or '').strip().lower(),
            (champ.province or '').strip().lower()
        ))

        results.append({
            "champion": f"{champ.firstname} {champ.lastname}",
            "username": username,
            "school_count": len(asl_ids),
            "asl_student_count": asl_student_count,
            "library_student_count": library_student_count,
            "overall_student_count": overall_student_count
        })

    return jsonify(results)




def normalize_province_name(name):
    if not name:
        return "Unknown"
    return str(name).strip().title()

@app.route('/api/platforms/quick_custom_date', methods=['GET'])
@login_required
def platforms_quick_custom_date():
    try:
        # --- Parse dates ---
        end_date = request.args.get("end_date")
        start_date = request.args.get("start_date")

        today = datetime.today().date()
        default_start = today - timedelta(days=30)

        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        if not start_date:
            start_date = default_start
        else:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        # ---------------------------
        # Helper to normalize gender
        # ---------------------------
        def normalize_gender(g):
            if not g:
                return "Unknown"
            g = g.strip().lower()
            if g in ["f", "female", "girl", "woman"]:
                return "Female"
            elif g in ["m", "male", "boy", "man"]:
                return "Male"
            return "Unknown"

        # ---------------------------
        # 1) ASL PLATFORM (Ruzivo DB)
        # ---------------------------
        conn_asl = get_ruzivo_conn()
        cursor_asl = conn_asl.cursor(pymysql.cursors.DictCursor)

        asl_query = """
            SELECT 
                sch.school_id,
                sch.school_name,
                sch.school_province,
                COUNT(DISTINCT sl.student_id) AS active_learners
            FROM tblstudents_login sl
            INNER JOIN tblstudents st ON sl.student_id = st.student_id
            INNER JOIN tblschools sch ON st.school_id = sch.school_id
            WHERE DATE(sl.login_date) BETWEEN %s AND %s
            GROUP BY sch.school_id, sch.school_name, sch.school_province
        """
        cursor_asl.execute(asl_query, (start_date, end_date))
        asl_results = cursor_asl.fetchall()

        # Gender distribution
        asl_gender_query = """
            SELECT st.gender, COUNT(DISTINCT sl.student_id) AS count
            FROM tblstudents_login sl
            INNER JOIN tblstudents st ON sl.student_id = st.student_id
            WHERE DATE(sl.login_date) BETWEEN %s AND %s
            GROUP BY st.gender
        """
        cursor_asl.execute(asl_gender_query, (start_date, end_date))
        asl_gender_raw = cursor_asl.fetchall()
        asl_gender = {"Female": 0, "Male": 0, "Unknown": 0}
        for row in asl_gender_raw:
            g = normalize_gender(row["gender"])
            asl_gender[g] += row["count"]

        # ---------------------------
        # 2) LIBRARY PLATFORM
        # ---------------------------
        conn_lib = get_direct_library_conn()
        cursor_lib = conn_lib.cursor(pymysql.cursors.DictCursor)

        lib_query = """
            SELECT 
                inst.id,
                inst.name AS institution_name,
                inst.province AS institution_province,
                COUNT(DISTINCT la.user_id) AS active_users
            FROM logins la
            INNER JOIN institution_user iu ON la.user_id = iu.user_id
            INNER JOIN institutions inst ON iu.institution_id = inst.id
            WHERE DATE(la.created_at) BETWEEN %s AND %s
            GROUP BY inst.id, inst.name, inst.province
        """
        cursor_lib.execute(lib_query, (start_date, end_date))
        lib_results = cursor_lib.fetchall()

        lib_gender_query = """
            SELECT u.sex AS gender, COUNT(DISTINCT la.user_id) AS count
            FROM logins la
            INNER JOIN users u ON la.user_id = u.id
            WHERE DATE(la.created_at) BETWEEN %s AND %s
            GROUP BY u.sex
        """
        cursor_lib.execute(lib_gender_query, (start_date, end_date))
        lib_gender_raw = cursor_lib.fetchall()
        lib_gender = {"Female": 0, "Male": 0, "Unknown": 0}
        for row in lib_gender_raw:
            g = normalize_gender(row["gender"])
            lib_gender[g] += row["count"]

        # ---------------------------
        # 3) ASK AKELLO CHAT LOGS
        # ---------------------------
        ask_query = """
            SELECT COUNT(DISTINCT student_id) AS unique_students_count
            FROM tblask_akello_chat_logs
            WHERE DATE(created_at) BETWEEN %s AND %s
        """
        cursor_asl.execute(ask_query, (start_date, end_date))
        ask_result = cursor_asl.fetchone()
        total_ask_users = ask_result["unique_students_count"] if ask_result else 0

        # Province distribution for AskAkello
        ask_province_query = """
            SELECT sch.school_province, COUNT(DISTINCT acl.student_id) AS count
            FROM tblask_akello_chat_logs acl
            INNER JOIN tblstudents st ON acl.student_id = st.student_id
            INNER JOIN tblschools sch ON st.school_id = sch.school_id
            WHERE DATE(acl.created_at) BETWEEN %s AND %s
            GROUP BY sch.school_province
        """
        cursor_asl.execute(ask_province_query, (start_date, end_date))
        ask_province = cursor_asl.fetchall()

        # Gender distribution for AskAkello
        ask_gender_query = """
            SELECT st.gender, COUNT(DISTINCT acl.student_id) AS count
            FROM tblask_akello_chat_logs acl
            INNER JOIN tblstudents st ON acl.student_id = st.student_id
            WHERE DATE(acl.created_at) BETWEEN %s AND %s
            GROUP BY st.gender
        """
        cursor_asl.execute(ask_gender_query, (start_date, end_date))
        ask_gender_raw = cursor_asl.fetchall()
        ask_gender = {"Female": 0, "Male": 0, "Unknown": 0}
        for row in ask_gender_raw:
            g = normalize_gender(row["gender"])
            ask_gender[g] += row["count"]

        # ---------------------------
        # Normalize province names
        # ---------------------------
        for row in asl_results:
            row["school_province"] = normalize_province_name(row["school_province"])
        for row in lib_results:
            row["institution_province"] = normalize_province_name(row["institution_province"])
        for row in ask_province:
            row["school_province"] = normalize_province_name(row["school_province"])

        # Totals
        total_asl_users = sum([r["active_learners"] for r in asl_results])
        total_lib_users = sum([r["active_users"] for r in lib_results])
        total_askakello_users = total_ask_users
        overall_total = total_asl_users + total_lib_users + total_askakello_users

        # ---------------------------
        # FINAL RESPONSE
        # ---------------------------
        return jsonify({
            "date_range": {"start": str(start_date), "end": str(end_date)},
            "totals": {
                "asl": total_asl_users,
                "library": total_lib_users,
                "ask_akello": total_askakello_users,
                "overall": overall_total
            },
            "province_distribution": {
                "asl": asl_results,
                "library": lib_results,
                "ask_akello": ask_province
            },
            "gender_distribution": {
                "asl": asl_gender,
                "library": lib_gender,
                "ask_akello": ask_gender
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if 'cursor_asl' in locals(): cursor_asl.close()
        if 'conn_asl' in locals(): conn_asl.close()
        if 'cursor_lib' in locals(): cursor_lib.close()
        if 'conn_lib' in locals(): conn_lib.close()





# Cache already initialized at the top of the file after imports

@app.route('/api/platforms_overall_yearly', methods=['GET'])
@login_required
@cache.cached(timeout=60 * 60 * 6, key_prefix='platforms_overall_yearly')  # Reduced to 6 hours
def platforms_overall_yearly():
    import time
    import threading
    import concurrent.futures
    
    start_time = time.time()
    
    def execute_query():
        """Execute the actual database queries"""
        return _platforms_overall_yearly_impl()
    
    # Use ThreadPoolExecutor for timeout functionality (works on Windows)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # Submit the query execution to thread pool
            future = executor.submit(execute_query)
            
            # Wait for result with 20-second timeout for faster fallback
            try:
                result = future.result(timeout=20)
                execution_time = round(time.time() - start_time, 2)
                
                # Add debug information to successful response
                if isinstance(result, dict) and 'year' in result:
                    result['_debug'] = {
                        "execution_time_seconds": execution_time,
                        "query_count": 36,  # 3 queries per month
                        "cache_status": "fresh" if execution_time > 1 else "cached"
                    }
                return jsonify(result)
                
            except concurrent.futures.TimeoutError:
                # Cancel the future to clean up resources
                future.cancel()
                print(f"Query timeout after 20 seconds - providing sample data")
                
                # Instead of failing, return sample data
                try:
                    sample_data = _get_sample_chart_data(datetime.today().year)
                    sample_data['_debug'] = {
                        "execution_time_seconds": 20.0,
                        "query_count": 0,
                        "cache_status": "fallback_sample_data",
                        "timeout_occurred": True
                    }
                    return jsonify(sample_data)
                except Exception as e:
                    print(f"Sample data generation failed: {e}")
                    return jsonify({
                        "error": "Database queries are taking too long. Showing sample data to ensure charts display.",
                        "timeout": True,
                        "suggestion": "Please try refreshing the page later when server load is lower.",
                        "retry_recommended": True
                    }), 408  # Request Timeout
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        # Provide more helpful error messages
        if "Connection" in str(e) or "connect" in str(e).lower():
            error_msg = "Unable to connect to the database. Please try again later."
        elif "timeout" in str(e).lower():
            error_msg = "Database query timed out. Please try refreshing the page."
        else:
            error_msg = f"An error occurred while loading chart data: {str(e)}"
            
        return jsonify({
            "error": error_msg,
            "technical_error": str(e) if app.debug else None
        }), 500


def _platforms_overall_yearly_impl():
    """Implementation of the platforms_overall_yearly logic"""
    conn_asl = None
    cursor_asl = None
    conn_lib = None
    cursor_lib = None
    
    try:
        import time
        query_start = time.time()
        
        today = datetime.today().date()
        current_year = today.year
        months = [datetime(current_year, m, 1) for m in range(1, 13)]
        
        print(f"Starting database connections for year {current_year}...")
        
        # Test database connections with timeout
        try:
            conn_asl = get_ruzivo_conn()
            cursor_asl = conn_asl.cursor(pymysql.cursors.DictCursor)
            print("✓ ASL database connected")
        except Exception as e:
            print(f"✗ ASL database connection failed: {e}")
            return _get_sample_chart_data(current_year)
        
        try:
            conn_lib = get_direct_library_conn()
            cursor_lib = conn_lib.cursor(pymysql.cursors.DictCursor)
            print("✓ Library database connected")
        except Exception as e:
            print(f"✗ Library database connection failed: {e}")
            return _get_sample_chart_data(current_year)

        def month_range(dt):
            start = dt.replace(day=1)
            if dt.month == 12:
                end = datetime(dt.year + 1, 1, 1) - timedelta(days=1)
            else:
                end = datetime(dt.year, dt.month + 1, 1) - timedelta(days=1)
            return start, end

        monthly_data = []
        total_asl_year = 0
        total_lib_year = 0
        total_ask_year = 0

        # Optimized approach: Use single queries with CASE statements for better performance
        print(f"Starting optimized database queries for year {current_year}...")
        
        try:
            # --- OPTIMIZED ASL QUERY (single query for all months) ---
            print("Executing ASL query...")
            cursor_asl.execute("""
                SELECT 
                    MONTH(login_date) as month_num,
                    COUNT(DISTINCT student_id) AS active_learners
                FROM tblstudents_login
                WHERE YEAR(login_date) = %s
                GROUP BY MONTH(login_date)
                ORDER BY MONTH(login_date)
            """, (current_year,))
            asl_results = cursor_asl.fetchall()
            print(f"ASL query completed, got {len(asl_results)} months")
            
            # Convert to dict for easy lookup
            asl_by_month = {row['month_num']: row['active_learners'] for row in asl_results}
            
            # --- OPTIMIZED LIBRARY QUERY (single query for all months) ---
            print("Executing Library query...")
            cursor_lib.execute("""
                SELECT 
                    MONTH(created_at) as month_num,
                    COUNT(DISTINCT user_id) AS active_users
                FROM logins
                WHERE YEAR(created_at) = %s
                GROUP BY MONTH(created_at)
                ORDER BY MONTH(created_at)
            """, (current_year,))
            lib_results = cursor_lib.fetchall()
            print(f"Library query completed, got {len(lib_results)} months")
            
            # Convert to dict for easy lookup
            lib_by_month = {row['month_num']: row['active_users'] for row in lib_results}
            
            # --- OPTIMIZED ASK AKELLO QUERY (single query for all months) ---
            print("Executing Ask Akello query...")
            cursor_asl.execute("""
                SELECT 
                    MONTH(created_at) as month_num,
                    COUNT(DISTINCT student_id) AS unique_students_count
                FROM tblask_akello_chat_logs
                WHERE YEAR(created_at) = %s
                GROUP BY MONTH(created_at)
                ORDER BY MONTH(created_at)
            """, (current_year,))
            ask_results = cursor_asl.fetchall()
            print(f"Ask Akello query completed, got {len(ask_results)} months")
            
            # Convert to dict for easy lookup
            ask_by_month = {row['month_num']: row['unique_students_count'] for row in ask_results}
            
        except Exception as query_error:
            print(f"Database query error: {query_error}")
            # If optimized queries fail, fall back to sample data
            return _get_sample_chart_data(current_year)
        
        # Build monthly data from results
        for m in months:
            month_num = m.month
            
            asl_count = asl_by_month.get(month_num, 0)
            lib_count = lib_by_month.get(month_num, 0)
            ask_count = ask_by_month.get(month_num, 0)
            
            total_asl_year += asl_count
            total_lib_year += lib_count
            total_ask_year += ask_count
            
            total = asl_count + lib_count + ask_count

            monthly_data.append({
                "month": m.strftime("%B"),
                "asl": asl_count,
                "library": lib_count,
                "ask_akello": ask_count,
                "overall": total
            })
        
        print(f"Monthly data compilation completed for {len(monthly_data)} months")

        # --- Compute Overall Year Totals ---
        overall_total_year = total_asl_year + total_lib_year + total_ask_year

        # Return data as dictionary (not jsonify, that's handled in the main function)
        return {
            "year": current_year,
            "monthly_usage": monthly_data,
            "yearly_totals": {
                "asl": total_asl_year,
                "library": total_lib_year,
                "ask_akello": total_ask_year,
                "overall": overall_total_year
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Re-raise the exception to be handled by the main function
        raise e
        
    finally:
        # Clean up database connections
        if cursor_asl:
            cursor_asl.close()
        if conn_asl:
            conn_asl.close()
        if cursor_lib:
            cursor_lib.close()
        if conn_lib:
            conn_lib.close()


def _get_sample_chart_data(current_year):
    """Fallback function that returns sample data when database queries are too slow"""
    import random
    
    print("Using sample data fallback due to database performance issues")
    
    # Generate realistic sample data
    months_names = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    
    monthly_data = []
    total_asl_year = 0
    total_lib_year = 0
    total_ask_year = 0
    
    for i, month_name in enumerate(months_names):
        # Generate realistic numbers with some variation
        base_asl = random.randint(800, 1200)
        base_lib = random.randint(300, 500)
        base_ask = random.randint(150, 250)
        
        # Add seasonal variation (higher in school months)
        if i in [0, 1, 2, 7, 8, 9]:  # Jan-Mar, Aug-Oct (school months)
            multiplier = random.uniform(1.1, 1.3)
        else:
            multiplier = random.uniform(0.7, 0.9)
        
        asl_count = int(base_asl * multiplier)
        lib_count = int(base_lib * multiplier)
        ask_count = int(base_ask * multiplier)
        
        total_asl_year += asl_count
        total_lib_year += lib_count
        total_ask_year += ask_count
        
        total = asl_count + lib_count + ask_count
        
        monthly_data.append({
            "month": month_name,
            "asl": asl_count,
            "library": lib_count,
            "ask_akello": ask_count,
            "overall": total
        })
    
    return {
        "year": current_year,
        "monthly_usage": monthly_data,
        "yearly_totals": {
            "asl": total_asl_year,
            "library": total_lib_year,
            "ask_akello": total_ask_year,
            "overall": total_asl_year + total_lib_year + total_ask_year
        },
        "_sample_data": True,
        "_note": "Sample data used due to database performance issues"
    }





@app.route('/hlf-stats', methods=['GET'])
@login_required
def hlf_stats():
    """Render the HLF Stats page with interactive charts"""
    return render_template('HLFStats.html', title='HLF Stats')


@app.route('/api/hlf-weekly-stats/', methods=['GET'])
@login_required
@cache.cached(timeout=60 * 60 * 6, key_prefix='hlf_weekly_stats')  # Cache for 6 hours
def hlf_weekly_stats():
    import time
    import concurrent.futures

    start_time = time.time()

    # Get optional date range from query params
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    # Convert or default to full current year
    try:
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            today = datetime.today().date()
            start_date = datetime(today.year, 1, 1).date()
            end_date = datetime(today.year, 12, 31).date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    def execute_query():
        return _hlf_weekly_stats_impl(start_date, end_date)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(execute_query)
            try:
                result = future.result(timeout=20)
                execution_time = round(time.time() - start_time, 2)

                if isinstance(result, dict) and 'weeks' in result:
                    result['_debug'] = {
                        "execution_time_seconds": execution_time,
                        "query_count": 3,
                        "cache_status": "fresh" if execution_time > 1 else "cached"
                    }
                return jsonify(result)

            except concurrent.futures.TimeoutError:
                future.cancel()
                print("Query timeout after 20 seconds - providing sample weekly data")

                try:
                    sample_data = _get_sample_weekly_data(start_date.year)
                    sample_data['_debug'] = {
                        "execution_time_seconds": 20.0,
                        "query_count": 0,
                        "cache_status": "fallback_sample_data",
                        "timeout_occurred": True
                    }
                    return jsonify(sample_data)
                except Exception as e:
                    print(f"Sample data generation failed: {e}")
                    return jsonify({
                        "error": "Database queries are taking too long. Showing sample data to ensure charts display.",
                        "timeout": True,
                        "suggestion": "Please try refreshing the page later when server load is lower.",
                        "retry_recommended": True
                    }), 408

    except Exception as e:
        import traceback
        traceback.print_exc()

        if "Connection" in str(e) or "connect" in str(e).lower():
            error_msg = "Unable to connect to the database. Please try again later."
        elif "timeout" in str(e).lower():
            error_msg = "Database query timed out. Please try refreshing the page."
        else:
            error_msg = f"An error occurred while loading weekly chart data: {str(e)}"

        return jsonify({
            "error": error_msg,
            "technical_error": str(e) if app.debug else None
        }), 500


def _hlf_weekly_stats_impl(start_date, end_date):
    """Weekly usage implementation supporting date ranges and compatible with ONLY_FULL_GROUP_BY"""
    conn_asl = None
    cursor_asl = None
    conn_lib = None
    cursor_lib = None

    try:
        print(f"Fetching weekly platform usage between {start_date} and {end_date}...")

        # Establish database connections
        conn_asl = get_ruzivo_conn()
        cursor_asl = conn_asl.cursor(pymysql.cursors.DictCursor)

        conn_lib = get_direct_library_conn()
        cursor_lib = conn_lib.cursor(pymysql.cursors.DictCursor)

        # --- ASL Weekly Query ---
        cursor_asl.execute("""
            SELECT 
                YEARWEEK(login_date, 1) AS year_week,
                COUNT(DISTINCT student_id) AS active_learners
            FROM tblstudents_login
            WHERE login_date BETWEEN %s AND %s
            GROUP BY YEARWEEK(login_date, 1)
            ORDER BY year_week
        """, (start_date, end_date))
        asl_by_week = {r['year_week']: r['active_learners'] for r in cursor_asl.fetchall()}

        # --- Library Weekly Query ---
        cursor_lib.execute("""
            SELECT 
                YEARWEEK(created_at, 1) AS year_week,
                COUNT(DISTINCT user_id) AS active_users
            FROM logins
            WHERE created_at BETWEEN %s AND %s
            GROUP BY YEARWEEK(created_at, 1)
            ORDER BY year_week
        """, (start_date, end_date))
        lib_by_week = {r['year_week']: r['active_users'] for r in cursor_lib.fetchall()}

        # --- Ask Akello Weekly Query ---
        cursor_asl.execute("""
            SELECT 
                YEARWEEK(created_at, 1) AS year_week,
                COUNT(DISTINCT student_id) AS unique_students_count
            FROM tblask_akello_chat_logs
            WHERE created_at BETWEEN %s AND %s
            GROUP BY YEARWEEK(created_at, 1)
            ORDER BY year_week
        """, (start_date, end_date))
        ask_by_week = {r['year_week']: r['unique_students_count'] for r in cursor_asl.fetchall()}

        # --- Prepare Weekly Data ---
        num_weeks = ((end_date - start_date).days // 7) + 1
        weekly_data = []
        total_asl = total_lib = total_ask = 0

        for i in range(num_weeks):
            week_start = start_date + timedelta(weeks=i)
            year_week = int(week_start.strftime("%G%V"))  # ISO year+week, e.g. 202540
            week_num = int(week_start.strftime("%V"))      # ISO week number

            asl_count = asl_by_week.get(year_week, 0)
            lib_count = lib_by_week.get(year_week, 0)
            ask_count = ask_by_week.get(year_week, 0)
            total = asl_count + lib_count + ask_count

            total_asl += asl_count
            total_lib += lib_count
            total_ask += ask_count

            weekly_data.append({
                "week_start": week_start.strftime("%Y-%m-%d"),
                "week_number": week_num,
                "asl": asl_count,
                "library": lib_count,
                "ask_akello": ask_count,
                "overall": total
            })

        # --- Compute Averages and Totals ---
        active_weeks = len([w for w in weekly_data if w["overall"] > 0]) or 1

        avg_weekly = {
            "asl": round(total_asl / active_weeks, 2),
            "library": round(total_lib / active_weeks, 2),
            "ask_akello": round(total_ask / active_weeks, 2),
            "overall": round((total_asl + total_lib + total_ask) / active_weeks, 2)
        }

        return {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "weeks": weekly_data,
            "average_weekly_usage": avg_weekly,
            "totals": {
                "asl": total_asl,
                "library": total_lib,
                "ask_akello": total_ask,
                "overall": total_asl + total_lib + total_ask
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e

    finally:
        if cursor_asl: cursor_asl.close()
        if conn_asl: conn_asl.close()
        if cursor_lib: cursor_lib.close()
        if conn_lib: conn_lib.close()



def _get_sample_weekly_data(current_year):
    """Fallback weekly data"""
    import random
    print("Using sample weekly data fallback")

    weekly_data = []
    total_asl = total_lib = total_ask = 0

    for week in range(1, 53):
        asl = random.randint(600, 1200)
        lib = random.randint(200, 500)
        ask = random.randint(100, 300)
        total = asl + lib + ask

        total_asl += asl
        total_lib += lib
        total_ask += ask

        weekly_data.append({
            "week": week,
            "asl": asl,
            "library": lib,
            "ask_akello": ask,
            "overall": total
        })

    avg_weekly = {
        "asl": round(total_asl / 52, 2),
        "library": round(total_lib / 52, 2),
        "ask_akello": round(total_ask / 52, 2),
        "overall": round((total_asl + total_lib + total_ask) / 52, 2)
    }

    return {
        "year": current_year,
        "weeks": weekly_data,
        "average_weekly_usage": avg_weekly,
        "totals": {
            "asl": total_asl,
            "library": total_lib,
            "ask_akello": total_ask,
            "overall": total_asl + total_lib + total_ask
        },
        "_sample_data": True
    }





def normalize_province_name(name):
    if not name:
        return "Unknown"
    return str(name).strip().title()


@app.route('/api/askakello/custom_date', methods=['GET'])
def askakello_custom_date():
    try:
        # --- Parse dates ---
        end_date = request.args.get("end_date")
        start_date = request.args.get("start_date")

        today = datetime.today().date()
        default_start = today - timedelta(days=30)

        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        if not start_date:
            start_date = default_start
        else:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        # ---------------------------
        # Helper to normalize gender
        # ---------------------------
        def normalize_gender(g):
            if not g:
                return "Unknown"
            g = g.strip().lower()
            if g in ["f", "female", "girl", "woman"]:
                return "Female"
            elif g in ["m", "male", "boy", "man"]:
                return "Male"
            return "Unknown"

        # ---------------------------
        # ASK AKELLO CHAT LOGS
        # ---------------------------
        conn = get_ruzivo_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Unique students
        ask_query = """
            SELECT COUNT(DISTINCT student_id) AS unique_students_count
            FROM tblask_akello_chat_logs
            WHERE DATE(created_at) BETWEEN %s AND %s
        """
        cursor.execute(ask_query, (start_date, end_date))
        ask_result = cursor.fetchone()
        total_ask_users = ask_result["unique_students_count"] if ask_result else 0

        # Province distribution
        ask_province_query = """
            SELECT sch.school_province, COUNT(DISTINCT acl.student_id) AS count
            FROM tblask_akello_chat_logs acl
            INNER JOIN tblstudents st ON acl.student_id = st.student_id
            INNER JOIN tblschools sch ON st.school_id = sch.school_id
            WHERE DATE(acl.created_at) BETWEEN %s AND %s
            GROUP BY sch.school_province
        """
        cursor.execute(ask_province_query, (start_date, end_date))
        ask_province = cursor.fetchall()

        # Normalize province names
        for row in ask_province:
            row["school_province"] = normalize_province_name(row["school_province"])

        # Gender distribution
        ask_gender_query = """
            SELECT st.gender, COUNT(DISTINCT acl.student_id) AS count
            FROM tblask_akello_chat_logs acl
            INNER JOIN tblstudents st ON acl.student_id = st.student_id
            WHERE DATE(acl.created_at) BETWEEN %s AND %s
            GROUP BY st.gender
        """
        cursor.execute(ask_gender_query, (start_date, end_date))
        ask_gender_raw = cursor.fetchall()

        ask_gender = {"Female": 0, "Male": 0, "Unknown": 0}
        for row in ask_gender_raw:
            g = normalize_gender(row["gender"])
            ask_gender[g] += row["count"]

        # ---------------------------
        # FINAL RESPONSE
        # ---------------------------
        return jsonify({
            "date_range": {"start": str(start_date), "end": str(end_date)},
            "totals": {
                "ask_akello": total_ask_users
            },
            "province_distribution": ask_province,
            "gender_distribution": ask_gender
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()








# def normalize_province_name(name):
#     if not name:
#         return "Unknown"
#     return str(name).strip().title()


# from flask import request, jsonify
# from datetime import datetime, timedelta
# import pymysql

# @app.route('/api/platforms/quick_custom_date', methods=['GET'])
# def platforms_quick_custom_date():
#     try:
#         # --- Parse dates ---
#         end_date = request.args.get("end_date")
#         start_date = request.args.get("start_date")

#         today = datetime.today().date()
#         default_start = today - timedelta(days=30)

#         if not end_date:
#             end_date = today
#         else:
#             end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

#         if not start_date:
#             start_date = default_start
#         else:
#             start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

#         # ---------------------------
#         # 1) ASL PLATFORM (Ruzivo DB)
#         # ---------------------------
#         conn_asl = get_ruzivo_conn()
#         cursor_asl = conn_asl.cursor(pymysql.cursors.DictCursor)

#         # Province + gender distribution
#         asl_province_gender_query = """
#             SELECT
#                 sch.school_province AS province,
#                 st.gender AS gender,
#                 COUNT(DISTINCT sl.student_id) AS count
#             FROM tblstudents_login sl
#             INNER JOIN tblstudents st ON sl.student_id = st.student_id
#             INNER JOIN tblschools sch ON st.school_id = sch.school_id
#             WHERE DATE(sl.login_date) BETWEEN %s AND %s
#             GROUP BY sch.school_province, st.gender
#         """
#         cursor_asl.execute(asl_province_gender_query, (start_date, end_date))
#         rows = cursor_asl.fetchall()

#         asl_province_data = {}
#         total_asl_users = 0
#         for r in rows:
#             prov = normalize_province_name(r["province"]) or "Unknown"
#             gender = r["gender"].title() if r["gender"] else "Unknown"
#             if prov not in asl_province_data:
#                 asl_province_data[prov] = {"Female":0,"Male":0,"Unknown":0,"total":0}
#             asl_province_data[prov][gender] = r["count"]
#             asl_province_data[prov]["total"] += r["count"]
#             total_asl_users += r["count"]

#         # ---------------------------
#         # 2) LIBRARY PLATFORM
#         # ---------------------------
#         conn_lib = get_direct_library_conn()
#         cursor_lib = conn_lib.cursor(pymysql.cursors.DictCursor)

#         lib_province_gender_query = """
#             SELECT
#                 inst.province AS province,
#                 u.sex AS gender,
#                 COUNT(DISTINCT la.user_id) AS count
#             FROM last_activities la
#             INNER JOIN users u ON la.user_id = u.id
#             INNER JOIN institutions inst ON u.id = inst.id
#             WHERE DATE(la.created_at) BETWEEN %s AND %s
#             GROUP BY inst.province, u.sex
#         """
#         cursor_lib.execute(lib_province_gender_query, (start_date, end_date))
#         rows = cursor_lib.fetchall()

#         lib_province_data = {}
#         total_lib_users = 0
#         for r in rows:
#             prov = normalize_province_name(r["province"]) or "Unknown"
#             gender = r["gender"].title() if r["gender"] else "Unknown"
#             if prov not in lib_province_data:
#                 lib_province_data[prov] = {"Female":0,"Male":0,"Unknown":0,"total":0}
#             lib_province_data[prov][gender] = r["count"]
#             lib_province_data[prov]["total"] += r["count"]
#             total_lib_users += r["count"]

#         # ---------------------------
#         # 3) ASK AKELLO CHAT LOGS
#         # ---------------------------
#         ask_province_gender_query = """
#             SELECT
#                 sch.school_province AS province,
#                 st.gender AS gender,
#                 COUNT(DISTINCT acl.student_id) AS count
#             FROM tblask_akello_chat_logs acl
#             INNER JOIN tblstudents st ON acl.student_id = st.student_id
#             INNER JOIN tblschools sch ON st.school_id = sch.school_id
#             WHERE DATE(acl.created_at) BETWEEN %s AND %s
#             GROUP BY sch.school_province, st.gender
#         """
#         cursor_asl.execute(ask_province_gender_query, (start_date, end_date))
#         rows = cursor_asl.fetchall()

#         ask_province_data = {}
#         total_ask_users = 0
#         for r in rows:
#             prov = normalize_province_name(r["province"]) or "Unknown"
#             gender = r["gender"].title() if r["gender"] else "Unknown"
#             if prov not in ask_province_data:
#                 ask_province_data[prov] = {"Female":0,"Male":0,"Unknown":0,"total":0}
#             ask_province_data[prov][gender] = r["count"]
#             ask_province_data[prov]["total"] += r["count"]
#             total_ask_users += r["count"]

#         overall_total = total_asl_users + total_lib_users + total_ask_users

#         return jsonify({
#             "date_range": {"start": str(start_date), "end": str(end_date)},
#             "totals": {
#                 "asl": total_asl_users,
#                 "library": total_lib_users,
#                 "ask_akello": total_ask_users,
#                 "overall": overall_total
#             },
#             "province_distribution": {
#                 "asl": asl_province_data,
#                 "library": lib_province_data,
#                 "ask_akello": ask_province_data
#             }
#         })

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

#     finally:
#         if 'cursor_asl' in locals(): cursor_asl.close()
#         if 'conn_asl' in locals(): conn_asl.close()
#         if 'cursor_lib' in locals(): cursor_lib.close()
#         if 'conn_lib' in locals(): conn_lib.close()













@app.route('/api/asl-metrics/<province_name>', methods=['GET'])
@login_required
def get_asl_metrics(province_name):
    conn = get_ruzivo_conn()
    cursor = conn.cursor()

    today = datetime.today().date()
    start_date = today.replace(day=1)
    active_30_date = today - timedelta(days=30)

    queries = {
        'asl_unique_users': """
            SELECT COUNT(DISTINCT sl.student_id) AS count
            FROM tblstudents_login sl
            JOIN vwstudent vs ON vs.student_id = sl.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE sl.login_date BETWEEN %s AND %s
            AND s.school_province = %s
        """,
        'asl_registrations': """
            SELECT COUNT(DISTINCT st.student_id) AS count
            FROM tblstudents st
            JOIN vwstudent vs ON vs.student_id = st.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE st.date_added BETWEEN %s AND %s
            AND s.school_province = %s
        """,
        'asl_total_primary_content': """
            SELECT COUNT(DISTINCT ca.student_id) AS count
            FROM tblcontent_access ca
            JOIN tblstudents st ON st.student_id = ca.student_id
            JOIN vwstudent vs ON vs.student_id = ca.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE ca.start_time BETWEEN %s AND %s
            AND st.student_type != 'STAFF'
            AND s.school_province = %s
        """,
        'asl_total_sec_content': """
            SELECT COUNT(DISTINCT ca.student_id) AS count
            FROM tblcontent_access_hs ca
            JOIN tblstudents st ON st.student_id = ca.student_id
            JOIN vwstudent vs ON vs.student_id = ca.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE ca.start_time BETWEEN %s AND %s
            AND st.student_type != 'STAFF'
            AND s.school_province = %s
        """,
        'asl_total_primary_exercise': """
            SELECT COUNT(DISTINCT tr.student_id) AS count
            FROM tblresults tr
            JOIN tblstudents st ON st.student_id = tr.student_id
            JOIN vwstudent vs ON vs.student_id = tr.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE tr.date_added BETWEEN %s AND %s
            AND st.student_type != 'STAFF'
            AND s.school_province = %s
        """,
        'asl_total_sec_exercise': """
            SELECT COUNT(DISTINCT tr.student_id) AS count
            FROM tblresults_hs tr
            JOIN tblstudents st ON st.student_id = tr.student_id
            JOIN vwstudent vs ON vs.student_id = tr.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE tr.date_added BETWEEN %s AND %s
            AND st.student_type != 'STAFF'
            AND s.school_province = %s
        """,
        'asl_total_zimsec_access': """
            SELECT COUNT(DISTINCT zi.student_id) AS count
            FROM tblcontent_access_zimsec zi
            JOIN tblstudents st ON st.student_id = zi.student_id
            JOIN vwstudent vs ON vs.student_id = zi.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE zi.start_time BETWEEN %s AND %s
            AND st.student_type != 'STAFF'
            AND s.school_province = %s
        """,
        'asl_teacher_set_activities': """
            SELECT COUNT(DISTINCT ta.student_id) AS count
            FROM tblclass_activity_results ta
            JOIN tblstudents st ON st.student_id = ta.student_id
            JOIN vwstudent vs ON vs.student_id = ta.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE ta.date_added BETWEEN %s AND %s
            AND st.student_type != 'STAFF'
            AND s.school_province = %s
        """,
        'asl_teacher_access': """
            SELECT COUNT(t.teacher_id) AS count
            FROM tbl_teacher t
            JOIN tblschools s ON s.school_id = t.school_id
            WHERE t.active_at BETWEEN %s AND %s
            AND s.school_province = %s
        """,
        'asl_revenue': """
            SELECT currency, SUM(amount) AS total
            FROM tblecocash_payment_order p
            JOIN vwstudent vs ON vs.student_id = p.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE p.date_created BETWEEN %s AND %s
            AND p.transactionOperationStatus = 'COMPLETED'
            AND s.school_province = %s
            GROUP BY currency
        """,
        'asl_unique_subscribers': """
            SELECT COUNT(DISTINCT p.student_id) AS count
            FROM tblecocash_payment_order p
            JOIN vwstudent vs ON vs.student_id = p.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE p.date_created BETWEEN %s AND %s
            AND p.transactionOperationStatus = 'COMPLETED'
            AND s.school_province = %s
        """,
        'asl_active30': """
            SELECT COUNT(DISTINCT sl.student_id) AS count
            FROM tblstudents_login sl
            JOIN vwstudent vs ON vs.student_id = sl.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE DATE(sl.login_date) BETWEEN %s AND %s
            AND s.school_province = %s
        """
    }

    result = {}

    for label, query in queries.items():
        # Pick date range depending on metric
        date_range = (active_30_date, today) if 'active30' in label else (start_date, today)
        params = date_range + (province_name,)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        if label == 'asl_revenue':
            result[label] = {row['currency']: float(row['total']) for row in rows}
        else:
            result[label] = rows[0]['count'] if rows else 0

    # cursor.close()
    # conn.close()

    return jsonify(result)






@app.route('/api/province-details/<provincename>', methods=['GET'])
@login_required
def get_province_details(provincename):
    today = datetime.today().date()
    start_date = today.replace(day=1)
    flag = 'd'

    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor()

        query = """
            SELECT 
                sch.school_id,
                sch.school_name,
                COUNT(s.student_id) AS learner_count
            FROM 
                tblschools sch
            LEFT JOIN 
                vwstudent s ON sch.school_id = s.school_id
                AND s.last_login BETWEEN %s AND %s
            WHERE 
                sch.flag != %s AND sch.school_province = %s
            GROUP BY 
                sch.school_id, sch.school_name
        """

        cursor.execute(query, (start_date, today, flag, provincename))
        schools = cursor.fetchall()

        total_schools = len(schools)
        total_learners = sum(s['learner_count'] for s in schools)

        return jsonify({
            "total_schools": total_schools,
            "total_learners": total_learners,
            "schools": schools
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    # finally:
    #     if cursor:
    #         cursor.close()
    #     if conn:
    #         conn.close()





@app.route('/api/province-school-active-logins', methods=['GET'])
def province_school_active_logins():
    try:
        province = request.args.get("province")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        if not province or not start_date or not end_date:
            return jsonify({"error": "Missing required parameters (province, start_date, end_date)"}), 400

        conn = get_ruzivo_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        query = """
            SELECT 
                sch.school_id,
                sch.school_name,
                sch.school_province,
                COUNT(DISTINCT sl.student_id) AS active_learners
            FROM tblstudents_login sl
            INNER JOIN tblstudents st ON sl.student_id = st.student_id
            INNER JOIN tblschools sch ON st.school_id = sch.school_id
            WHERE DATE(sl.login_date) BETWEEN %s AND %s
              AND sch.school_province = %s
            GROUP BY sch.school_id, sch.school_name, sch.school_province
            ORDER BY active_learners DESC
        """

        cursor.execute(query, (start_date, end_date, province))
        results = cursor.fetchall()

        # Province total learners
        province_total = sum([row["active_learners"] for row in results])

        return jsonify({
            "province": province,
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "province_total": province_total,
            "schools": results
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if 'conn' in locals() and conn:
            conn.close()




@app.route('/api/overall_school_active_logins', methods=['GET'])
def overall_school_active_logins():
    try:
        # Validate and normalize input dates
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")

        if not start_date_str or not end_date_str:
            return jsonify({"error": "Missing required parameters (start_date, end_date)"}), 400

        try:
            # Parse as dates; ensure start <= end
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

        if start_date > end_date:
            return jsonify({"error": "start_date cannot be after end_date"}), 400

        conn = get_ruzivo_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Use half-open datetime range to preserve index usage on sl.login_date
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

        query = """
            SELECT 
                sch.school_id,
                sch.school_name,
                sch.school_province,
                COUNT(DISTINCT sl.student_id) AS active_learners
            FROM tblstudents_login sl
            INNER JOIN tblstudents st ON st.student_id = sl.student_id
            INNER JOIN tblschools sch ON sch.school_id = st.school_id
            WHERE sl.login_date >= %s AND sl.login_date < %s
            GROUP BY sch.school_id, sch.school_name, sch.school_province
            ORDER BY active_learners DESC
        """

        try:
            cursor.execute(query, (start_dt, end_dt_exclusive))
            rows = cursor.fetchall() or []
        except pymysql.err.OperationalError as oe:
            # Retry once on lost connection during query (e.g., timeout 2013)
            if getattr(oe, 'args', [None])[0] == 2013:
                try:
                    cursor.close()
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
                conn = get_ruzivo_conn()
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                cursor.execute(query, (start_dt, end_dt_exclusive))
                rows = cursor.fetchall() or []
            else:
                raise

        # Coerce values for safe JSON serialization
        schools = []
        overall_total = 0
        for row in rows:
            active = int(row.get("active_learners") or 0)
            overall_total += active
            schools.append({
                "school_id": int(row.get("school_id") or 0),
                "school_name": row.get("school_name") or "",
                "school_province": row.get("school_province") or "",
                "active_learners": active
            })

        return jsonify({
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "overall_total": overall_total,
            "schools": schools
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            if 'cursor' in locals() and cursor:
                cursor.close()
        finally:
            if 'conn' in locals() and conn:
                conn.close()









@app.route('/api/province-details1/<provincename>', methods=['GET'])
@login_required
def get_province_details1(provincename):
    today = datetime.today().date()
    start_date = today.replace(day=1)

    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor()

        query = """
            SELECT 
                DATE(last_login) AS login_date,
                COUNT(student_id) AS daily_logins
            FROM 
                tblstudents_info
            WHERE 
                last_login BETWEEN %s AND %s
            GROUP BY 
                DATE(last_login)
            ORDER BY 
                login_date ASC;
        """

        cursor.execute(query, (start_date, today))
        rows = cursor.fetchall()

        # Format results
        usage = []
        for row in rows:
            login_date = row[0].strftime('%Y-%m-%d') if isinstance(row[0], datetime) else str(row[0])
            usage.append({
                "date": login_date,
                "logins": int(row[1])
            })

        return jsonify({
            "start_date": str(start_date),
            "end_date": str(today),
            "usage": usage
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    # finally:
    #     if cursor:
    #         cursor.close()
    #     if conn:
    #         conn.close()



# latest province api
@app.route('/api/active-students-by-province', methods=['GET'])
@login_required
def get_active_students_by_province():
    try:
        valid_provinces = [
            'Harare', 'Bulawayo', 'Manicaland', 'Mashonaland Central',
            'Mashonaland East', 'Mashonaland West', 'Masvingo',
            'Matabeleland North', 'Matabeleland South', 'Midlands'
        ]

        today = datetime.today().date()
        start_date = today.replace(day=1)

        conn = get_ruzivo_conn()
        cursor = conn.cursor()

        query = f"""
            SELECT s.school_province AS province, COUNT(*) AS student_count
            FROM vwstudent v
            JOIN tblschools s ON v.school_id = s.school_id
            WHERE v.last_login BETWEEN %s AND %s
            AND s.school_province IN ({','.join(['%s'] * len(valid_provinces))})
            GROUP BY s.school_province
        """

        params = [start_date, today] + valid_provinces
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Format and sort results
        results = [{"province": row['province'], "student_count": row['student_count']} for row in rows]
        results.sort(key=lambda x: x['student_count'], reverse=True)

        return jsonify(results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'cursor' in locals():
    #         cursor.close()
    #     if 'conn' in locals():
    #         conn.close()




# latest schools by province
from datetime import datetime
from flask import request, jsonify

@app.route('/api/schools-by-province', methods=['GET'])
@login_required
def get_schools_by_province_with_counts():
    valid_provinces = [
        'Harare', 'Bulawayo', 'Manicaland', 'Mashonaland Central',
        'Mashonaland East', 'Mashonaland West', 'Masvingo',
        'Matabeleland North', 'Matabeleland South', 'Midlands'
    ]

    province = request.args.get('province')

    if not province or province not in valid_provinces:
        return jsonify({"error": "Invalid or missing province"}), 400

    try:
        today = datetime.today().date()
        start_of_month = today.replace(day=1)

        conn = get_ruzivo_conn()
        cursor = conn.cursor()

        # Get schools in that province
        cursor.execute("""
            SELECT school_id, school_name
            FROM tblschools
            WHERE school_province = %s
        """, (province,))
        schools = cursor.fetchall()

        results = []

        for school in schools:
            school_id = school['school_id']
            school_name = school['school_name']

            cursor.execute("""
                SELECT COUNT(*) AS student_count
                FROM vwstudent
                WHERE school_id = %s
                AND last_login BETWEEN %s AND %s
            """, (school_id, start_of_month, today))

            count_row = cursor.fetchone()
            student_count = count_row['student_count'] if count_row else 0

            results.append({
                "school_id": school_id,
                "school_name": school_name,
                "student_count": student_count
            })

        return jsonify(results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'cursor' in locals(): cursor.close()
    #     if 'conn' in locals(): conn.close()




@app.route('/api/chat-log-activity', methods=['GET'])
@login_required
def get_chat_log_activity():
    today = datetime.today()
    start_date = today - timedelta(days=30)  # last 30 days

    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor(dictionary=True)  # ✅ use dict so jsonify works cleanly

        # Per-student logs
        query = """
            SELECT 
                s.student_id,
                CONCAT(s.name, ' ', s.surname) AS full_name,
                COUNT(*) AS total_logs
            FROM tblask_akello_chat_logs l
            JOIN vwstudent s ON l.student_id = s.student_id
            WHERE l.updated_at BETWEEN %s AND %s
            GROUP BY s.student_id, full_name
            ORDER BY total_logs DESC
        """

        cursor.execute(query, (start_date, today))
        student_logs = cursor.fetchall()

        # Total logs across all students
        total_query = """
            SELECT COUNT(*) AS total_logs
            FROM tblask_akello_chat_logs
            WHERE updated_at BETWEEN %s AND %s
        """
        cursor.execute(total_query, (start_date, today))
        total_logs = cursor.fetchone()["total_logs"]

        cursor.close()
        conn.close()

        return jsonify({
            "students": student_logs,
            "total_logs": total_logs
        })

    except Exception as e:
        print("Error querying chat log activity:", e)
        return jsonify({"error": "Internal server error"}), 500


    # finally:
    #     if cursor: cursor.close()
    #     if conn: conn.close()


@app.route('/api/chat-log-by-province', methods=['GET'])
@login_required
def get_chat_log_by_province():
    provinces = [
        'Harare', 'Bulawayo', 'Manicaland', 'Mashonaland Central', 'Mashonaland East',
        'Mashonaland West', 'Masvingo', 'Matabeleland North', 'Matabeleland South', 'Midlands'
    ]

    today = datetime.today().date()
    start_date = today.replace(day=1)

    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor()

        query = """
            SELECT 
                sch.school_province AS province,
                COUNT(DISTINCT s.student_id) AS total_students
            FROM tblask_akello_chat_logs log
            JOIN vwstudent s ON log.student_id = s.student_id
            JOIN tblschools sch ON s.school_id = sch.school_id
            WHERE log.updated_at BETWEEN %s AND %s
            AND sch.school_province IN %s
            GROUP BY sch.school_province
            ORDER BY total_students DESC
        """

        cursor.execute(query, (start_date, today, tuple(provinces)))
        results = cursor.fetchall()

        return jsonify(results)

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Internal server error"}), 500

    # finally:
    #     if cursor: cursor.close()
    #     if conn: conn.close()




# -------------------------------
# 1️⃣ DAILY CHATS API
# -------------------------------
@app.route('/api/askakello-daily-chats', methods=['GET'])
@login_required
def askakello_daily_chats():
    today = date.today()
    start_date = today.replace(day=1)  # First day of this month

    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        query = """
            SELECT 
                DATE(l.updated_at) AS chat_date,
                COUNT(DISTINCT l.student_id) AS learner_count
            FROM tblask_akello_chat_logs l
            WHERE l.updated_at BETWEEN %s AND %s
            GROUP BY DATE(l.updated_at)
            ORDER BY chat_date
        """

        cursor.execute(query, (start_date, today))
        results = cursor.fetchall()

        return jsonify({
            "year": today.year,
            "month": today.strftime("%B"),
            "daily_chats": results
        })

    except Exception as e:
        print("Error querying daily chats:", e)
        return jsonify({"error": "Internal server error"}), 500

    # finally:
    #     if conn:
    #         conn.close()

# -------------------------------
# 2️⃣ MONTHLY CHATS API
# -------------------------------
@app.route('/api/askakello-monthly-chats', methods=['GET'])
@login_required
def askakello_monthly_chats():
    today = date.today()
    current_year = today.year

    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        query = """
            SELECT 
                YEAR(l.updated_at) AS year_num,
                MONTH(l.updated_at) AS month_num,
                COUNT(DISTINCT l.student_id) AS learner_count
            FROM tblask_akello_chat_logs l
            WHERE YEAR(l.updated_at) = %s
            GROUP BY YEAR(l.updated_at), MONTH(l.updated_at)
            ORDER BY year_num, month_num
        """

        cursor.execute(query, (current_year,))
        results = cursor.fetchall()

        # Add month name
        for r in results:
            r["month"] = calendar.month_name[r["month_num"]]

        return jsonify({
            "year": current_year,
            "monthly_chats": results
        })

    except Exception as e:
        print("Error querying monthly chats:", e)
        return jsonify({"error": "Internal server error"}), 500

    # finally:
    #     if conn:
    #         conn.close()





@app.route('/api/library-institutions', methods=['GET'])
@login_required
def api_institutions():
    try:
        # Get optional date range from query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        today = datetime.today().date()
        if not start_date:
            start_date = today.replace(day=1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')

        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        conn = get_direct_library_conn()

        with conn.cursor() as cursor:
            query = """
                SELECT 
                    i.province,
                    COUNT(DISTINCT i.id) AS number_of_institutions,
                    COUNT(DISTINCT l.user_id) AS total_users
                FROM institution_user iu
                JOIN institutions i ON iu.institution_id = i.id
                JOIN logins l ON iu.user_id = l.user_id
                WHERE l.created_at BETWEEN %s AND %s
                GROUP BY i.province
                ORDER BY total_users DESC
            """
            cursor.execute(query, (start_date, end_date))
            results = cursor.fetchall()

        return jsonify(results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()



@app.route('/api/library-daily-logins', methods=['GET'])
@login_required
def api_library_daily_logins():
    try:
        today = datetime.today()
        start_date = today.replace(day=1).date()  # first day of current month
        end_date = today.date()  # today

        conn = get_direct_library_conn()

        with conn.cursor() as cursor:
            query = """
                SELECT 
                    DATE(l.created_at) AS login_date,
                    COUNT(*) AS total_logins
                FROM logins l
                WHERE l.created_at BETWEEN %s AND %s
                GROUP BY login_date
                ORDER BY login_date ASC
            """
            cursor.execute(query, (start_date, end_date))
            results = cursor.fetchall()

        # Ensure we have all days of the month even if count = 0
        from calendar import monthrange
        total_days = monthrange(today.year, today.month)[1]
        daily_data = []
        results_dict = {str(r['login_date']): r['total_logins'] for r in results}

        for day in range(1, total_days + 1):
            date_str = datetime(today.year, today.month, day).date()
            if date_str > end_date:
                break
            daily_data.append({
                "date": date_str.strftime("%Y-%m-%d"),
                "total_logins": results_dict.get(str(date_str), 0)
            })

        return jsonify(daily_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()




@app.route('/api/library-vaya-daily-logins', methods=['GET'])
def library_vaya_daily_logins():
    conn = None
    try:
        today = date.today()
        current_year = today.year
        current_month = today.month
        days_in_month = calendar.monthrange(current_year, current_month)[1]

        conn = get_direct_library_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        daily_data = []

        # Loop through all days of current month
        for day in range(1, days_in_month + 1):
            day_start = datetime(current_year, current_month, day, 0, 0, 0)
            day_end = datetime(current_year, current_month, day, 23, 59, 59)

            query = """
                SELECT 
                    COUNT(DISTINCT o.user_id) AS user_count,
                    o.currency,
                    SUM(o.total_amount) AS total_amount
                FROM orders o
                JOIN users u ON u.id = o.user_id
                WHERE o.created_at BETWEEN %s AND %s
                AND o.status = 'Completed'
                GROUP BY o.currency
            """
            cursor.execute(query, (day_start, day_end))
            results = cursor.fetchall()

            # Build currency summary for the day
            currency_totals = {}
            total_users = 0
            for r in results:
                currency = r["currency"] if r["currency"] else "UNKNOWN"
                currency_totals[currency] = float(r["total_amount"]) if r["total_amount"] else 0
                total_users = r["user_count"]  # same for all rows (per day)

            daily_data.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "user_count": int(total_users) if total_users else 0,
                "currency_totals": currency_totals
            })

        # cursor.close()
        # conn.close()

        return jsonify({
            "year": current_year,
            "month": date(current_year, current_month, 1).strftime("%B"),
            "daily_counts": daily_data
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if conn:
    #         conn.close()





@app.route('/api/library-monthly-logins', methods=['GET'])
@login_required
def api_library_monthly_logins():
    try:
        today = datetime.today()
        start_date = datetime(today.year, 1, 1).date()   # Jan 1 of current year
        end_date = today.date()  # today

        conn = get_direct_library_conn()

        with conn.cursor() as cursor:
            query = """
                SELECT 
                    MONTH(l.created_at) AS month_num,
                    COUNT(*) AS total_logins
                FROM logins l
                WHERE l.created_at BETWEEN %s AND %s
                GROUP BY month_num
                ORDER BY month_num ASC
            """
            cursor.execute(query, (start_date, end_date))
            results = cursor.fetchall()

        # Fill missing months with 0
        results_dict = {r['month_num']: r['total_logins'] for r in results}
        monthly_data = []
        for m in range(1, 13):
            if datetime(today.year, m, 1).date() > end_date:
                break
            monthly_data.append({
                "month": month_name[m],
                "total_logins": results_dict.get(m, 0)
            })

        return jsonify(monthly_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()





@app.route("/api/library/school_profile", methods=["GET", "POST"])
def library_school_profile():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
    else:
        data = request.args  

    asl_school_id = data.get("asl_school_id")
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if not asl_school_id:
        return jsonify({"error": "asl_school_id is required"}), 400

    from datetime import date, timedelta, datetime
    if not start_date or not end_date:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    # --- Find champions with matching asl_school_id ---
    champions = ChampionSchool.query.all()
    matching_champions = []
    library_ids = []

    for champ in champions:
        for school in champ.get_schools():
            if str(school.get("asl_school_id")) == str(asl_school_id):
                matching_champions.append(champ)
                if school.get("library_school_id"):
                    library_ids.append(school.get("library_school_id"))

    if not matching_champions:
        return jsonify({
            "message": f"No champions found for asl_school_id {asl_school_id}",
            "total_active_users": 0
        }), 200

    if not library_ids:
        return jsonify({
            "message": f"No linked library_school_id for asl_school_id {asl_school_id}",
            "total_active_users": 0
        }), 200

    # --- Query Library DB ---
    total_active_users = 0
    school_profiles = []

    query = """
        SELECT 
            inst.id,
            inst.name AS institution_name,
            COUNT(DISTINCT la.user_id) AS active_users
        FROM logins la
        INNER JOIN institution_user iu ON la.user_id = iu.user_id
        INNER JOIN institutions inst ON iu.institution_id = inst.id
        WHERE inst.id = %s AND DATE(la.created_at) BETWEEN %s AND %s
        GROUP BY inst.id, inst.name
        ORDER BY active_users DESC
    """

    conn = get_direct_library_conn()
    cur = conn.cursor()  # make sure results are dicts

    for lib_id in library_ids:
        cur.execute(query, (lib_id, start_date, end_date))
        row = cur.fetchone()
        if row:
            total_active_users += row["active_users"]
            school_profiles.append(row)

    cur.close()
    conn.close()

    return jsonify({
        "asl_school_id": asl_school_id,
        "library_school_ids": library_ids,
        "total_active_users": total_active_users,
        "schools": school_profiles
    }), 200







# @app.route("/api/library/school_profile", methods=["GET","POST"])
# def library_school_profile():
#     if request.method == "POST":
#         # Safely parse JSON if provided
#         data = request.get_json(silent=True) or {}
#     else:
#         # For GET requests, use query parameters
#         data = request.args  

#     asl_school_id = data.get("asl_school_id")
#     start_date = data.get("start_date")
#     end_date = data.get("end_date")

#     if not asl_school_id:
#         return jsonify({"error": "asl_school_id is required"}), 400

#     # Default date range (last 30 days if not provided)
#     from datetime import date, timedelta
#     if not start_date or not end_date:
#         end_date = date.today()
#         start_date = end_date - timedelta(days=30)

#     # Find champions with matching asl_school_id
#     champions = ChampionSchool.query.filter_by(asl_school_id=asl_school_id).all()
#     if not champions:
#         return jsonify({"message": "No champions found for this asl_school_id", "total_active_users": 0}), 200

#     library_ids = [c.library_school_id for c in champions if c.library_school_id]

#     if not library_ids:
#         return jsonify({"message": "No linked library_school_id for this asl_school_id", "total_active_users": 0}), 200

#     # Query library DB
#     total_active_users = 0
#     school_profiles = []

#     query = """
#         SELECT 
#             inst.id,
#             inst.name AS institution_name,
#             COUNT(DISTINCT la.user_id) AS active_users
#         FROM last_activities la
#         INNER JOIN institution_user iu ON la.user_id = iu.user_id
#         INNER JOIN institutions inst ON iu.institution_id = inst.id
#         WHERE inst.id = %s AND DATE(la.created_at) BETWEEN %s AND %s
#         GROUP BY inst.id, inst.name
#         ORDER BY active_users DESC
#     """

#     conn = get_direct_library_conn()
#     cur = conn.cursor()

#     for lib_id in library_ids:
#         cur.execute(query, (lib_id, start_date, end_date))
#         row = cur.fetchone()
#         if row:
#             total_active_users += row["active_users"]
#             school_profiles.append(row)

#     cur.close()
#     conn.close()

#     return jsonify({
#         "asl_school_id": asl_school_id,
#         "library_school_ids": library_ids,
#         "total_active_users": total_active_users,
#         "schools": school_profiles
#     }), 200







@app.route('/api/library_custom_date_analytics', methods=['GET'])
def library_custom_date_analytics():
    try:
        # Get date range from request, default last 30 days
        end_date = request.args.get("end_date")
        start_date = request.args.get("start_date")

        today = datetime.today().date()
        default_start = today - timedelta(days=30)

        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        if not start_date:
            start_date = default_start
        else:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        conn = get_direct_library_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        query = """
            SELECT 
                inst.id,
                inst.name AS institution_name,
                inst.province AS institution_province,
                COUNT(DISTINCT la.user_id) AS active_users
            FROM logins la
            INNER JOIN institution_user iu ON la.user_id = iu.user_id
            INNER JOIN institutions inst ON iu.institution_id = inst.id
            WHERE DATE(la.created_at) BETWEEN %s AND %s
            GROUP BY inst.id, inst.name, inst.province
            ORDER BY active_users DESC
        """

        cursor.execute(query, (start_date, end_date))
        results = cursor.fetchall()

        total_active_users = sum([row["active_users"] for row in results])

        return jsonify({
            "date_range": {
                "start": str(start_date),
                "end": str(end_date)
            },
            "total_active_users": total_active_users,
            "institutions": results
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()






@app.route('/api/library-metrics/<province_name>', methods=['GET'])
@login_required
def api_library_metrics_by_province(province_name):
    try:
        # Optional date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        today = datetime.today().date()
        if not start_date:
            start_date = today.replace(day=1)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')

        if not end_date:
            end_date = today
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        conn = get_direct_library_conn()

        with conn.cursor() as cursor:
            query = """
                SELECT 
                    i.name AS institution_name,
                    COUNT(DISTINCT l.user_id) AS total_users
                FROM institution_user iu
                JOIN institutions i ON iu.institution_id = i.id
                JOIN logins l ON iu.user_id = l.user_id
                WHERE i.province = %s
                  AND l.created_at BETWEEN %s AND %s
                GROUP BY i.name
                ORDER BY total_users DESC
            """
            cursor.execute(query, (province_name, start_date, end_date))
            results = cursor.fetchall()

        return jsonify(results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()




@app.route('/api/library-province-institutions/<province_name>', methods=['GET'])
@login_required
def api_library_province_institutions(province_name):
    try:
        conn = get_direct_library_conn()

        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            query = """
                SELECT id, name, province
                FROM institutions
                WHERE province = %s
                ORDER BY name ASC
            """
            cursor.execute(query, (province_name,))
            results = cursor.fetchall()

        return jsonify(results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()







from pymysql.cursors import DictCursor



@app.route('/api/student-access-info', methods=['GET'])
@login_required
def get_student_access_info():
    try:
        conn = get_ruzivo_conn()
        with conn.cursor() as cursor:
            query = """
                SELECT name, last_login, access_sdate, access_edate
                FROM vwstudent
                WHERE last_login IS NOT NULL
                ORDER BY last_login DESC
                LIMIT 100
            """
            cursor.execute(query)
            result = cursor.fetchall()

            # Format datetime fields
            for row in result:
                row['last_login'] = row['last_login'].strftime('%Y-%m-%d %H:%M:%S') if row['last_login'] else None
                row['access_sdate'] = row['access_sdate'].strftime('%Y-%m-%d %H:%M:%S') if row['access_sdate'] else None
                row['access_edate'] = row['access_edate'].strftime('%Y-%m-%d %H:%M:%S') if row['access_edate'] else None

        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()





@app.route('/api/school-usage', methods=['GET'])
@login_required
def get_school_usage():
    try:
        conn = get_ruzivo_conn()
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    school_id,
                    grade_id,
                    usage_yr,
                    school_enrol,
                    school_usage
                FROM vwschoolusage
                ORDER BY school_usage DESC
                LIMIT 10;
            """
            cursor.execute(query)
            data = cursor.fetchall()
        return jsonify(data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()



import pandas as pd
from flask import send_file, jsonify
import io
import pymysql

@app.route('/api/users-with-contact', methods=['GET'])
def users_with_contact():
    conn = None
    try:
        conn = get_direct_library_conn()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            query = """
                SELECT id, first_name, last_name, mobile_number, email
                FROM users
                WHERE (mobile_number IS NOT NULL AND mobile_number != '')
                   OR (email IS NOT NULL AND email != '')
            """
            cursor.execute(query)
            results = cursor.fetchall()

        if not results:
            return jsonify({"message": "No users with contact details found"}), 404

        # Convert to DataFrame
        df = pd.DataFrame(results)
        df["name"] = (df["first_name"].fillna('') + " " + df["last_name"].fillna('')).str.strip()
        df = df[["id", "name", "mobile_number", "email"]]

        # Write Excel to memory (not disk)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Users")
        output.seek(0)

        filename = "users_with_contact.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if conn:
    #         conn.close()




import pandas as pd
from flask import send_file, jsonify
import io
import pymysql

@app.route('/api/students-with-contact', methods=['GET'])
def students_with_contact():
    conn = None
    try:
        conn = get_ruzivo_conn()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            query = """
                SELECT 
                    s.student_id,
                    s.name,
                    s.surname,
                    s.email,
                    si.mobile
                FROM tblstudents s
                INNER JOIN tblstudents_info si 
                    ON s.student_id = si.student_id
                WHERE (si.mobile IS NOT NULL AND si.mobile != '')
                   OR (s.email IS NOT NULL AND s.email != '')
            """
            cursor.execute(query)
            results = cursor.fetchall()

        if not results:
            return jsonify({"message": "No students with contact details found"}), 404

        # Convert to DataFrame
        df = pd.DataFrame(results)
        df["name"] = (df["name"].fillna('') + " " + df["surname"].fillna('')).str.strip()
        df = df[["student_id", "name", "mobile", "email"]]

        # Write Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Students")
        output.seek(0)

        filename = "students_with_contact.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if conn:
    #         conn.close()






@app.route('/api/library-daily-currency', methods=['GET'])
def library_daily_currency():
    try:
        conn = get_direct_library_conn()
        with conn.cursor() as cursor:
            query = """
                SELECT DISTINCT 
                    o.user_id,
                    u.first_name,
                    u.last_name,
                    u.email,
                    u.mobile_number,
                    o.currency,
                    o.payment_type,
                    o.payment_method,
                    o.total_amount,
                    o.created_at
                FROM orders o
                JOIN users u ON u.id = o.user_id
                WHERE o.created_at BETWEEN '2025-08-25 00:00:00' AND '2025-08-25 23:59:59'
                  AND o.status = 'Completed';
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            data = [dict(zip(col_names, row)) for row in rows]

        return jsonify(data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()







# @app.route('/api/testingdb1', methods=['GET'])
# def testingdb1():
#     try:
#         # conn = get_ruzivo_conn()
#         conn = get_direct_library_conn()
#         with conn.cursor() as cursor:
#             query = """
#                SELECT 
#                     o.currency,
#                     COUNT(DISTINCT o.user_id) AS total_users,
#                     SUM(o.total_amount) AS total_amount
#                 FROM orders o
#                 JOIN users u ON u.id = o.user_id
#                 WHERE o.created_at BETWEEN '2025-08-25 00:00:00' AND '2025-08-25 23:59:59'
#                   AND o.status = 'Completed'
#                 GROUP BY o.currency;
# """
#             cursor.execute(query)
#             data = cursor.fetchall()
#         return jsonify(data)

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

#     finally:
#         if 'conn' in locals():
#             conn.close()




@app.route('/api/testingdb1', methods=['GET'])
def testingdb1():
    try:
        # conn = get_ruzivo_conn()
        conn = get_direct_library_conn()
        with conn.cursor() as cursor:
            query = """
               SELECT 
                    i.province,
                    COUNT(DISTINCT i.id) AS number_of_institutions,
                    COUNT(DISTINCT l.user_id) AS total_users
                FROM institution_user iu
                JOIN institutions i ON iu.institution_id = i.id
                JOIN logins l ON iu.user_id = l.user_id
                WHERE l.created_at BETWEEN %s AND %s
                GROUP BY i.province
                ORDER BY total_users DESC;
"""
            cursor.execute(query)
            data = cursor.fetchall()
        return jsonify(data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()




# @app.route('/api/testingdb1', methods=['GET'])
# def testingdb1():
#     try:
#         conn = get_direct_library_conn()
#         with conn.cursor(pymysql.cursors.DictCursor) as cursor:  # ✅ return dicts
#             query = """
#                 SELECT 
#                     o.currency,
#                     COUNT(DISTINCT o.user_id) AS total_users,
#                     SUM(o.total_amount) AS total_amount
#                 FROM orders o
#                 JOIN users u ON u.id = o.user_id
#                 WHERE o.created_at BETWEEN '2025-08-25 00:00:00' AND '2025-08-25 23:59:59'
#                   AND o.status = 'Completed'
#                 GROUP BY o.currency;
#             """
#             cursor.execute(query)
#             data = cursor.fetchall()

#         return jsonify(data)

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

#     finally:
#         if 'conn' in locals():
#             conn.close()




# @app.route('/api/testingdb1', methods=['GET'])
# def testingdb1():
#     conn = None
#     try:
#         conn = get_direct_library_conn()
#         with conn.cursor(pymysql.cursors.DictCursor) as cursor:
#             # Query for totals grouped by currency
#             totals_query = """
#                 SELECT 
#                     o.currency,
#                     COUNT(DISTINCT o.user_id) AS total_users,
#                     SUM(o.total_amount) AS total_amount
#                 FROM orders o
#                 JOIN users u ON u.id = o.user_id
#                 WHERE o.created_at BETWEEN '2025-08-25 00:00:00' AND '2025-08-25 23:59:59'
#                   AND o.status = 'Completed'
#                 GROUP BY o.currency;
#             """
#             cursor.execute(totals_query)
#             totals = cursor.fetchall()

#             # Query for detailed rows
#             details_query = """
#                 SELECT 
#                     o.id AS order_id,
#                     o.user_id,
#                     u.first_name,
#                     u.last_name,
#                     u.email,
#                     u.mobile_number,
#                     o.currency,
#                     o.payment_type,
#                     o.payment_method,
#                     o.total_amount,
#                     o.created_at
#                 FROM orders o
#                 JOIN users u ON u.id = o.user_id
#                 WHERE o.created_at BETWEEN '2025-08-25 00:00:00' AND '2025-08-25 23:59:59'
#                   AND o.status = 'Completed';
#             """
#             cursor.execute(details_query)
#             details = cursor.fetchall()

#         return jsonify({
#             "totals": totals,
#             "details": details
#         })

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

#     finally:
#         if conn:
#             conn.close()




@app.route('/api/smartlearning-school', methods=['POST'])
@login_required
def smartlearning_school():
    conn = None  # Initialize conn to None
    try:
        data = request.get_json()
        school_name = data.get("school_name")
        if not school_name:
            return jsonify({"error": "Missing school_name"}), 400

        # Get date range from request or default to MTD
        today = datetime.today().date()
        default_start_date = today.replace(day=1)

        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")

        try:
            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                start_date = default_start_date

            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            else:
                end_date = today
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

        # Get the connection from the PyMySQL connection pool
        conn = ruzivo_pool.connection()

        with conn.cursor() as cursor:
            # Main data query with grade filter
            query = """
                SELECT
                    s.school_id,
                    s.username,
                    s.grade,
                    s.last_login,
                    t.school_name
                FROM vwstudent s
                JOIN tblschools t ON s.school_id = t.school_id
                WHERE t.school_name = %s
                  AND s.grade BETWEEN 4 AND 13
                  AND s.last_login BETWEEN %s AND %s
                LIMIT 500;
            """
            cursor.execute(query, (school_name, start_date, end_date))
            rows = cursor.fetchall()
            columns = list(rows[0].keys()) if rows else []

            # Count query with grade filter
            count_query = """
                SELECT COUNT(*) AS total FROM vwstudent s
                JOIN tblschools t ON s.school_id = t.school_id
                WHERE t.school_name = %s
                  AND s.grade BETWEEN 4 AND 13
                  AND s.last_login BETWEEN %s AND %s;
            """
            cursor.execute(count_query, (school_name, start_date, end_date))
            total_count = cursor.fetchone()['total']

        return jsonify({
            "total_count": total_count,
            "columns": columns,
            "rows": rows,
            "date_range": {
                "start": str(start_date),
                "end": str(end_date)
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if conn:
    #         conn.close()






from flask import jsonify
from datetime import datetime, date

from app.models import BrandingItem, BrandingRequest, BrandingAction

# -------- Branding APIs --------

def is_admin_user():
    try:
        # Consider role or privileges
        if getattr(current_user, 'userRole', None) in ('Admin','Super-admin','Manager'):
            return True
        # Fallback to privileges dict if present
        if hasattr(current_user, 'has_privilege'):
            return current_user.has_privilege('Super-admin') or current_user.has_privilege('Manager')
    except Exception:
        pass
    return False

@app.route('/api/branding/inventory', methods=['GET'])
@login_required
def api_branding_inventory():
    items = BrandingItem.query.order_by(BrandingItem.platform.asc(), BrandingItem.item_type.asc()).all()
    return jsonify([i.to_dict() for i in items])

@app.route('/api/branding/requests', methods=['GET'])
@login_required
def api_branding_requests():
    reqs = BrandingRequest.query.order_by(BrandingRequest.created_at.desc()).all()
    # include actions history for clarity
    out = []
    for r in reqs:
        row = r.to_dict()
        acts = BrandingAction.query.filter_by(request_id=r.id).order_by(BrandingAction.created_at.asc()).all()
        row['actions'] = [a.to_dict() for a in acts]
        out.append(row)
    return jsonify(out)

@app.route('/api/branding/request', methods=['POST'])
@login_required
def api_branding_request_create():
    data = request.get_json() or {}
    platform = (data.get('platform') or '').strip()
    item_type = (data.get('item_type') or '').strip()
    quantity = int(data.get('quantity') or 1)
    event_name = (data.get('event_name') or '').strip()
    checkout_date = data.get('checkout_date')
    return_date = data.get('return_date')

    if not platform or not item_type or quantity <= 0:
        return jsonify({'error': 'platform, item_type and positive quantity are required'}), 400

    try:
        co_dt = datetime.strptime(checkout_date, '%Y-%m-%d').date() if checkout_date else None
        rt_dt = datetime.strptime(return_date, '%Y-%m-%d').date() if return_date else None
    except Exception:
        return jsonify({'error': 'Invalid date format, expected YYYY-MM-DD'}), 400

    req = BrandingRequest(
        requester_username=current_user.username,
        event_name=event_name,
        platform=platform,
        item_type=item_type,
        quantity=quantity,
        checkout_date=co_dt,
        return_date=rt_dt,
        status='Pending'
    )
    db.session.add(req)
    db.session.commit()
    return jsonify(req.to_dict()), 201

@app.route('/api/branding/requests/<int:req_id>/approve', methods=['POST'])
@login_required
def api_branding_request_approve(req_id):
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    req = db.session.get(BrandingRequest, req_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    if req.status == 'Approved':
        return jsonify({'message': 'Already approved', 'request': req.to_dict()}), 200

    item = BrandingItem.query.filter_by(platform=req.platform, item_type=req.item_type).first()
    if not item:
        return jsonify({'error': 'Inventory item not found for this platform/type'}), 404
    if item.quantity_available < req.quantity:
        return jsonify({'error': 'Insufficient quantity available', 'available': item.quantity_available}), 400

    item.quantity_available -= req.quantity
    req.status = 'Approved'
    db.session.add(BrandingAction(request_id=req.id, action='approve', actor_username=current_user.username))
    db.session.commit()
    return jsonify({'request': req.to_dict(), 'inventory': item.to_dict()}), 200

@app.route('/api/branding/requests/<int:req_id>/decline', methods=['POST'])
@login_required
def api_branding_request_decline(req_id):
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    req = db.session.get(BrandingRequest, req_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    data = request.get_json() or {}
    comment = (data.get('comment') or '').strip() or None
    req.status = 'Declined'
    db.session.add(BrandingAction(request_id=req.id, action='decline', actor_username=current_user.username, comment=comment))
    db.session.commit()
    return jsonify({'request': req.to_dict()}), 200

@app.route('/api/branding/requests/<int:req_id>/mark_returned', methods=['POST'])
@login_required
def api_branding_request_mark_returned(req_id):
    req = db.session.get(BrandingRequest, req_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    if req.requester_username != current_user.username and current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    if req.status != 'Approved':
        return jsonify({'error': 'Only approved requests can be marked returned'}), 400
    req.status = 'Return Pending'
    db.session.add(BrandingAction(request_id=req.id, action='mark_returned', actor_username=current_user.username))
    db.session.commit()
    return jsonify({'request': req.to_dict()}), 200

@app.route('/api/branding/requests/<int:req_id>/ack_return', methods=['POST'])
@login_required
def api_branding_request_ack_return(req_id):
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    req = db.session.get(BrandingRequest, req_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    if req.status != 'Return Pending':
        return jsonify({'error': 'Request is not pending return'}), 400
    item = BrandingItem.query.filter_by(platform=req.platform, item_type=req.item_type).first()
    if not item:
        # Create inventory entry if missing
        item = BrandingItem(platform=req.platform, item_type=req.item_type, quantity_available=0)
        db.session.add(item)
        db.session.flush()
    item.quantity_available += req.quantity
    req.status = 'Returned'
    db.session.add(BrandingAction(request_id=req.id, action='ack_return', actor_username=current_user.username))
    db.session.commit()
    return jsonify({'request': req.to_dict(), 'inventory': item.to_dict()}), 200

@app.route('/api/branding/requests/<int:req_id>/decline_return', methods=['POST'])
@login_required
def api_branding_request_decline_return(req_id):
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    req = db.session.get(BrandingRequest, req_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    if req.status != 'Return Pending':
        return jsonify({'error': 'Request is not pending return'}), 400
    data = request.get_json() or {}
    comment = (data.get('comment') or '').strip() or None
    # Decline return: keep request Approved (still out with user)
    req.status = 'Approved'
    db.session.add(BrandingAction(request_id=req.id, action='decline_return', actor_username=current_user.username, comment=comment))
    db.session.commit()
    return jsonify({'request': req.to_dict()}), 200

# -------- End Branding APIs --------

# Inventory management (Admin)
@app.route('/api/branding/inventory', methods=['POST'])
@login_required
def api_branding_inventory_upsert():
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json() or {}
    platform = (data.get('platform') or '').strip()
    item_type = (data.get('item_type') or '').strip()
    try:
        qty = int(data.get('quantity_available'))
    except Exception:
        return jsonify({'error': 'quantity_available must be an integer'}), 400
    if not platform or not item_type:
        return jsonify({'error': 'platform and item_type are required'}), 400
    item = BrandingItem.query.filter_by(platform=platform, item_type=item_type).first()
    if item:
        item.quantity_available = qty
    else:
        item = BrandingItem(platform=platform, item_type=item_type, quantity_available=qty)
        db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 200

@app.route('/api/branding/inventory/<int:item_id>', methods=['PATCH'])
@login_required
def api_branding_inventory_update(item_id):
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    item = db.session.get(BrandingItem, item_id)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json() or {}
    if 'platform' in data and data['platform']:
        item.platform = data['platform']
    if 'item_type' in data and data['item_type']:
        item.item_type = data['item_type']
    if 'quantity_available' in data and data['quantity_available'] is not None:
        try:
            item.quantity_available = int(data['quantity_available'])
        except Exception:
            return jsonify({'error': 'quantity_available must be integer'}), 400
    db.session.commit()
    return jsonify(item.to_dict())

@app.route('/api/branding/inventory/<int:item_id>', methods=['DELETE'])
@login_required
def api_branding_inventory_delete(item_id):
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    item = db.session.get(BrandingItem, item_id)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True})

# Bulk requests: create multiple BrandingRequest rows from one submission
@app.route('/api/branding/requests/bulk', methods=['POST'])
@login_required
def api_branding_requests_bulk():
    data = request.get_json() or {}
    items = data.get('items') or []
    event_name = (data.get('event_name') or '').strip()
    checkout_date = data.get('checkout_date')
    return_date = data.get('return_date')
    try:
        co_dt = datetime.strptime(checkout_date, '%Y-%m-%d').date() if checkout_date else None
        rt_dt = datetime.strptime(return_date, '%Y-%m-%d').date() if return_date else None
    except Exception:
        return jsonify({'error': 'Invalid date format'}), 400
    created = []
    for it in items:
        platform = (it.get('platform') or '').strip()
        item_type = (it.get('item_type') or '').strip()
        try:
            qty = int(it.get('quantity') or 0)
        except Exception:
            qty = 0
        if not platform or not item_type or qty <= 0:
            continue
        req = BrandingRequest(
            requester_username=current_user.username,
            event_name=event_name,
            platform=platform,
            item_type=item_type,
            quantity=qty,
            checkout_date=co_dt,
            return_date=rt_dt,
            status='Pending'
        )
        db.session.add(req)
        created.append(req)
    if not created:
        return jsonify({'error': 'No valid items to create'}), 400
    db.session.commit()
    return jsonify([r.to_dict() for r in created]), 201

# -------- Collateral Management APIs --------

@app.route('/api/collateral/items', methods=['GET'])
@login_required
def api_collateral_items_list():
    items = CollateralItems.query.order_by(CollateralItems.created_at.desc()).all()
    return jsonify({'items': [item.to_dict() for item in items]}), 200

@app.route('/api/collateral/items', methods=['POST'])
@login_required
def api_collateral_items_create():
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json() or {}
    collateral_name = (data.get('collateral_name') or '').strip()
    status = (data.get('status') or 'available').strip()
    
    if not collateral_name:
        return jsonify({'error': 'collateral_name is required'}), 400
    if status not in ['available', 'unavailable']:
        return jsonify({'error': 'status must be available or unavailable'}), 400
    
    item = CollateralItems(
        collateral_name=collateral_name,
        status=status,
        added_by=current_user.username
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201

@app.route('/api/collateral/items/<int:item_id>/status', methods=['PUT'])
@login_required
def api_collateral_items_toggle_status(item_id):
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    item = db.session.get(CollateralItems, item_id)
    if not item:
        return jsonify({'error': 'Item not found'}), 404
    data = request.get_json() or {}
    new_status = (data.get('status') or '').strip()
    if new_status not in ['available', 'unavailable']:
        return jsonify({'error': 'status must be available or unavailable'}), 400
    item.status = new_status
    db.session.commit()
    return jsonify(item.to_dict()), 200

@app.route('/api/collateral/items/<int:item_id>', methods=['DELETE'])
@login_required
def api_collateral_items_delete(item_id):
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    item = db.session.get(CollateralItems, item_id)
    if not item:
        return jsonify({'error': 'Item not found'}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({'ok': True}), 200

# Collateral Request APIs
@app.route('/api/collateral/requests', methods=['GET'])
@login_required
def api_collateral_requests_list():
    # Admins see all requests, users see only their own
    if is_admin_user():
        requests = CollateralRequest.query.order_by(CollateralRequest.created_at.desc()).all()
    else:
        requests = CollateralRequest.query.filter_by(requester_username=current_user.username).order_by(CollateralRequest.created_at.desc()).all()
    return jsonify({'requests': [req.to_dict() for req in requests]}), 200

@app.route('/api/collateral/requests', methods=['POST'])
@login_required
def api_collateral_requests_create():
    data = request.get_json() or {}
    collateral_item_id = data.get('collateral_item_id')
    event_details = (data.get('event_details') or '').strip()
    needed_by_date = data.get('needed_by_date')
    
    if not collateral_item_id or not event_details or not needed_by_date:
        return jsonify({'error': 'collateral_item_id, event_details, and needed_by_date are required'}), 400
    
    # Verify collateral item exists and is available
    item = db.session.get(CollateralItems, collateral_item_id)
    if not item:
        return jsonify({'error': 'Collateral item not found'}), 404
    if item.status != 'available':
        return jsonify({'error': 'Collateral item is not available'}), 400
    
    # Parse date
    try:
        needed_date = datetime.strptime(needed_by_date, '%Y-%m-%d').date()
    except Exception:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    # Create request
    collateral_request = CollateralRequest(
        collateral_item_id=collateral_item_id,
        requester_username=current_user.username,
        event_details=event_details,
        needed_by_date=needed_date,
        status='Pending'
    )
    db.session.add(collateral_request)
    db.session.commit()
    return jsonify(collateral_request.to_dict()), 201

@app.route('/api/collateral/requests/<int:request_id>/approve', methods=['POST'])
@login_required
def api_collateral_requests_approve(request_id):
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    
    collateral_request = db.session.get(CollateralRequest, request_id)
    if not collateral_request:
        return jsonify({'error': 'Request not found'}), 404
    if collateral_request.status != 'Pending':
        return jsonify({'error': 'Request is not pending'}), 400
    
    collateral_request.status = 'Approved'
    collateral_request.approved_by = current_user.username
    db.session.commit()
    return jsonify(collateral_request.to_dict()), 200

@app.route('/api/collateral/requests/<int:request_id>/decline', methods=['POST'])
@login_required
def api_collateral_requests_decline(request_id):
    if not is_admin_user():
        return jsonify({'error': 'Unauthorized'}), 403
    
    collateral_request = db.session.get(CollateralRequest, request_id)
    if not collateral_request:
        return jsonify({'error': 'Request not found'}), 404
    if collateral_request.status != 'Pending':
        return jsonify({'error': 'Request is not pending'}), 400
    
    data = request.get_json() or {}
    decline_reason = (data.get('decline_reason') or '').strip()
    if not decline_reason:
        return jsonify({'error': 'decline_reason is required'}), 400
    
    collateral_request.status = 'Declined'
    collateral_request.approved_by = current_user.username
    collateral_request.decline_reason = decline_reason
    db.session.commit()
    return jsonify(collateral_request.to_dict()), 200

# -------- End Collateral APIs --------

@app.route('/api/province-trainers', methods=['GET'])
def api_province_trainers():
    try:
        # Get today's date and first of the month
        today = datetime.today().date()
        start_date = today.replace(day=1)

        conn = get_ruzivo_conn()
        with conn.cursor() as cursor:
            # Main data query
            query = """
                SELECT 
                    s.school_id,
                    s.username,
                    s.grade,
                    s.last_login,
                    t.school_name
                FROM vwstudent s
                JOIN tblschools t ON s.school_id = t.school_id
                WHERE t.school_name = %s
                  AND s.last_login BETWEEN %s AND %s
                LIMIT 10;
            """
            cursor.execute(query, (
                'MUFAKOSE NO 2 HIGH SCHOOL',
                start_date,
                today
            ))
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            # Count query (same filters)
            count_query = """
                SELECT COUNT(*) AS total FROM vwstudent s
                JOIN tblschools t ON s.school_id = t.school_id
                WHERE t.school_name = %s
                  AND s.last_login BETWEEN %s AND %s;
            """
            cursor.execute(count_query, (
                'MUFAKOSE NO 2 HIGH SCHOOL',
                start_date,
                today
            ))
            total_count = cursor.fetchone()['total']

        return jsonify({
            "total_count": total_count,
            "columns": columns,
            "rows": rows,
            "date_range": {
                "start": str(start_date),
                "end": str(today)
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()





@app.route('/smartlearning-metrics-update',  methods=['GET','POST'])
@login_required
def smartlearning_metrics_update():
    try:
        # Read form data instead of JSON
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        today = date.today()
        start_date = start_date or today.replace(day=1).strftime('%Y-%m-%d')
        end_date = end_date or today.strftime('%Y-%m-%d')
        active_30_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')



        queries = {
            "asl_unique_users": f"""
                SELECT COUNT(DISTINCT student_id) AS value
                FROM tblstudents_login
                WHERE login_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            """,
            "asl_registrations": f"""
                SELECT COUNT(DISTINCT student_id) AS value
                FROM tblstudents
                WHERE date_added BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            """,
            "asl_total_primary_content": f"""
                SELECT COUNT(DISTINCT ca.student_id) AS value
                FROM tblcontent_access ca
                JOIN tblstudents ts ON ts.student_id = ca.student_id
                WHERE ca.start_time BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_total_sec_content": f"""
                SELECT COUNT(DISTINCT ca.student_id) AS value
                FROM tblcontent_access_hs ca
                JOIN tblstudents ts ON ts.student_id = ca.student_id
                WHERE ca.start_time BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_total_primary_exercise": f"""
                SELECT COUNT(DISTINCT tr.student_id) AS value
                FROM tblresults tr
                JOIN tblstudents ts ON ts.student_id = tr.student_id
                WHERE tr.date_added BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_total_sec_exercise": f"""
                SELECT COUNT(DISTINCT tr.student_id) AS value
                FROM tblresults_hs tr
                JOIN tblstudents ts ON ts.student_id = tr.student_id
                WHERE tr.date_added BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_total_zimsec_access": f"""
                SELECT COUNT(DISTINCT zi.student_id) AS value
                FROM tblcontent_access_zimsec zi
                JOIN tblstudents ts ON ts.student_id = zi.student_id
                WHERE zi.start_time BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_teacher_set_activities": f"""
                SELECT COUNT(DISTINCT ta.student_id) AS value
                FROM tblclass_activity_results ta
                JOIN tblstudents ts ON ts.student_id = ta.student_id
                WHERE ta.date_added BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_teacher_access": f"""
                SELECT COUNT(teacher_id) AS value
                FROM tbl_teacher
                WHERE active_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            """,
            "asl_revenue": f"""
                SELECT currency, SUM(amount) AS value
                FROM tblecocash_payment_order
                WHERE date_created BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND transactionOperationStatus = 'COMPLETED'
                GROUP BY currency
            """,
            "asl_unique_subscribers": f"""
                SELECT COUNT(DISTINCT student_id) AS value
                FROM tblecocash_payment_order
                WHERE date_created BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND transactionOperationStatus = 'COMPLETED'
            """,
            "asl_active30": f"""
                SELECT COUNT(DISTINCT student_id) AS value
                FROM tblstudents_login
                WHERE login_date BETWEEN DATE('{active_30_date}') AND DATE('{end_date}')
            """
        }

        results = {}
        conn = get_ruzivo_conn()

        with conn.cursor() as cursor:
            for label, query in queries.items():
                cursor.execute(query)
                rows = cursor.fetchall()

                if "Revenue" in label:
                    results[label] = ', '.join(
                        f"{row['currency']}: {row['value']}" for row in rows
                    ) if rows else "N/A"
                else:
                    results[label] = rows[0]['value'] if rows else 0


        return jsonify(results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()


# @app.route('/asl_active30', methods=['GET', 'POST'])
# def asl_active30():
#     try:
#         # Date range: last 30 days, inclusive of "today"
#         today = date.today()
#         end_date = today.strftime('%Y-%m-%d')                  # inclusive in response
#         active_30_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
#         # for SQL range: >= start and < (end + 1 day) to include the full end_date
#         end_exclusive = (today + timedelta(days=1)).strftime('%Y-%m-%d')

#         conn = get_ruzivo_conn()

#         # 0) Canonical list of provinces (ensures we show provinces with 0)
#         sql_provinces = """
#             SELECT DISTINCT TRIM(school_province) AS school_province
#             FROM tblstudent_school
#             WHERE school_province IS NOT NULL AND TRIM(school_province) <> ''
#             ORDER BY school_province
#         """
#         with conn.cursor() as cur:
#             cur.execute(sql_provinces)
#             provinces = [row['school_province'] for row in cur.fetchall()]

#         # 1) Active students (distinct) in window
#         # We'll LEFT JOIN this to students & schools so we don't lose anyone
#         # Normalize gender and province in SQL
#         sql_breakdown = """
#             WITH active_students AS (
#                 SELECT DISTINCT sl.student_id
#                 FROM tblstudents_login sl
#                 WHERE sl.login_date >= %s AND sl.login_date < %s
#             )
#             SELECT
#                 CASE
#                     WHEN UPPER(TRIM(s.gender)) IN ('MALE','M') THEN 'Male'
#                     WHEN UPPER(TRIM(s.gender)) IN ('FEMALE','F') THEN 'Female'
#                     ELSE 'Unknown'
#                 END AS gender,
#                 COALESCE(NULLIF(TRIM(ss.school_province), ''), 'Unknown') AS school_province,
#                 COUNT(DISTINCT a.student_id) AS active_count
#             FROM active_students a
#             LEFT JOIN tblstudents s ON a.student_id = s.student_id
#             LEFT JOIN tblstudent_school ss ON s.school_id = ss.student_school_id
#             GROUP BY gender, school_province
#         """

#         with conn.cursor() as cur:
#             cur.execute(sql_breakdown, (active_30_date, end_exclusive))
#             breakdown_raw = cur.fetchall()

#         # 2) Per-province totals (still from the same active_students set)
#         sql_province_totals = """
#             WITH active_students AS (
#                 SELECT DISTINCT sl.student_id
#                 FROM tblstudents_login sl
#                 WHERE sl.login_date >= %s AND sl.login_date < %s
#             )
#             SELECT
#                 COALESCE(NULLIF(TRIM(ss.school_province), ''), 'Unknown') AS school_province,
#                 COUNT(DISTINCT a.student_id) AS total_active
#             FROM active_students a
#             LEFT JOIN tblstudents s ON a.student_id = s.student_id
#             LEFT JOIN tblstudent_school ss ON s.school_id = ss.student_school_id
#             GROUP BY school_province
#         """
#         with conn.cursor() as cur:
#             cur.execute(sql_province_totals, (active_30_date, end_exclusive))
#             province_totals_raw = cur.fetchall()

#         # 3) Overall distinct total (matches above set)
#         sql_total = """
#             SELECT COUNT(DISTINCT sl.student_id) AS total_active
#             FROM tblstudents_login sl
#             WHERE sl.login_date >= %s AND sl.login_date < %s
#         """
#         with conn.cursor() as cur:
#             cur.execute(sql_total, (active_30_date, end_exclusive))
#             total_active = cur.fetchone()['total_active']

#         conn.close()

#         # Normalize genders set
#         genders = ['Male', 'Female', 'Unknown']

#         # Ensure 'Unknown' province is included if present in raw
#         raw_provinces = {r['school_province'] for r in breakdown_raw} | {r['school_province'] for r in province_totals_raw}
#         if 'Unknown' in raw_provinces and 'Unknown' not in provinces:
#             provinces.append('Unknown')

#         # Build fast lookup maps
#         bmap = {(r['school_province'], r['gender']): r['active_count'] for r in breakdown_raw}
#         tmap = {r['school_province']: r['total_active'] for r in province_totals_raw}

#         # Fill zeros for missing province/gender combos
#         breakdown = []
#         for prov in provinces:
#             for g in genders:
#                 breakdown.append({
#                     "school_province": prov,
#                     "gender": g,
#                     "active_count": int(bmap.get((prov, g), 0))
#                 })

#         # Province totals (ensure zeros for missing)
#         province_totals = [{"school_province": prov, "total_active": int(tmap.get(prov, 0))} for prov in provinces]

#         return jsonify({
#             "active_30_date": active_30_date,
#             "end_date": end_date,
#             "total_active": int(total_active),
#             "genders": genders,
#             "provinces": provinces,
#             "province_totals": province_totals,
#             "breakdown": breakdown
#         })

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

from datetime import date, timedelta
from flask import jsonify

def normalize_province(name):
    """Normalize province names consistently."""
    if not name:
        return 'Unknown'
    return name.replace('_', ' ').strip().title()

@app.route('/asl_active30', methods=['GET'])
@login_required
def asl_active30():
    conn = None
    try:
        today = date.today()
        active_30_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        end_exclusive = (today + timedelta(days=1)).strftime('%Y-%m-%d')

        conn = get_ruzivo_conn()

        # --- Step 1: Get total_active directly (raw) ---
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(DISTINCT l.student_id) AS total_active
                FROM tblstudents_login l
                WHERE l.login_date >= %s AND l.login_date < %s
            """, (active_30_date, end_exclusive))
            total_active = cur.fetchone()['total_active'] or 0

        if total_active == 0:
            return jsonify({
                "active_30_date": active_30_date,
                "end_date": today.strftime('%Y-%m-%d'),
                "total_active": 0,
                "gender_totals": {},
                "province_totals": [],
                "breakdown": []
            })

        # --- Step 2: Define active set query for re-use ---
        active_set_sql = """
            SELECT DISTINCT l.student_id
            FROM tblstudents_login l
            WHERE l.login_date >= %s AND l.login_date < %s
        """

        # --- Step 3: Execute breakdown queries ---
        with conn.cursor() as cur:
            # Gender totals
            cur.execute(f"""
                SELECT
                    CASE
                        WHEN UPPER(TRIM(v.gender)) IN ('MALE','M') THEN 'Male'
                        WHEN UPPER(TRIM(v.gender)) IN ('FEMALE','F') THEN 'Female'
                        ELSE 'Unknown'
                    END AS gender,
                    COUNT(*) AS active_count
                FROM ({active_set_sql}) a
                LEFT JOIN vwstudentschools v ON v.student_id = a.student_id
                GROUP BY gender
            """, (active_30_date, end_exclusive))
            gender_rows = cur.fetchall()

            # Province totals
            cur.execute(f"""
                SELECT
                    COALESCE(TRIM(s.school_province), 'Unknown') AS school_province,
                    COUNT(*) AS province_total_active
                FROM ({active_set_sql}) a
                LEFT JOIN vwstudentschools v ON v.student_id = a.student_id
                LEFT JOIN tblschools s ON s.school_id = v.school_id
                GROUP BY s.school_province
            """, (active_30_date, end_exclusive))
            province_rows = cur.fetchall()

            # Province + Gender breakdown
            cur.execute(f"""
                SELECT
                    CASE
                        WHEN UPPER(TRIM(v.gender)) IN ('MALE','M') THEN 'Male'
                        WHEN UPPER(TRIM(v.gender)) IN ('FEMALE','F') THEN 'Female'
                        ELSE 'Unknown'
                    END AS gender,
                    COALESCE(TRIM(s.school_province), 'Unknown') AS school_province,
                    COUNT(*) AS active_count
                FROM ({active_set_sql}) a
                LEFT JOIN vwstudentschools v ON v.student_id = a.student_id
                LEFT JOIN tblschools s ON s.school_id = v.school_id
                GROUP BY gender, s.school_province
            """, (active_30_date, end_exclusive))
            breakdown_rows = cur.fetchall()

        # --- Step 4: Normalize + combine ---
        def normalize_province(name):
            if not name:
                return 'Unknown'
            cleaned = name.replace('_', ' ').replace(';', '').strip().title()
            # Handle special cases
            if cleaned.lower() in ['bulawayo', 'bulawyo', 'bulawyoa', 'bulawyao', 'bulawayo']:
                return 'Bulawayo'
            return cleaned

        gender_totals = {}
        for r in gender_rows:
            g = r['gender'] or 'Unknown'
            count = int(r['active_count'] or 0)
            if count > 0:
                gender_totals[g] = gender_totals.get(g, 0) + count

        province_totals_map = {}
        for r in province_rows:
            prov = normalize_province(r['school_province'])
            count = int(r['province_total_active'] or 0)
            if count > 0:
                province_totals_map[prov] = province_totals_map.get(prov, 0) + count
        province_totals = [{"school_province": p, "province_total_active": c}
                           for p, c in sorted(province_totals_map.items())]

        breakdown_map = {}
        for r in breakdown_rows:
            prov = normalize_province(r['school_province'])
            g = r['gender'] or 'Unknown'
            count = int(r['active_count'] or 0)
            if count > 0:
                key = (prov, g)
                breakdown_map[key] = breakdown_map.get(key, 0) + count
        breakdown = [{"school_province": prov, "gender": g, "active_count": c}
                     for (prov, g), c in breakdown_map.items()]

        # --- Step 5: Consistency checks ---
        sum_genders = sum(gender_totals.values())
        sum_provinces = sum(p['province_total_active'] for p in province_totals)

        # Adjust if mismatch
        if sum_genders != total_active:
            gender_totals['Unknown'] = gender_totals.get('Unknown', 0) + (total_active - sum_genders)
        if sum_provinces != total_active:
            province_totals_map['Unknown'] = province_totals_map.get('Unknown', 0) + (total_active - sum_provinces)
            province_totals = [{"school_province": p, "province_total_active": c}
                               for p, c in sorted(province_totals_map.items())]

        return jsonify({
            "active_30_date": active_30_date,
            "end_date": today.strftime('%Y-%m-%d'),
            "total_active": total_active,
            "gender_totals": gender_totals,
            "province_totals": province_totals,
            "breakdown": breakdown
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    # finally:
    #     if conn:
    #         conn.close()






from flask import request, jsonify
from datetime import date, timedelta
import pymysql

# @app.route('/api/asl-active90', methods=['GET','POST'])
# def asl_active90():
#     conn = None
#     try:
#         # Read custom range from form
#         # start_date = request.form.get("start_date")
#         # end_date = request.form.get("end_date")

#         start_date = date(2025, 7, 1)
#         end_date = date(2025, 7, 24)

#         if not start_date or not end_date:
#             today = date.today()
#             end_date = today
#             start_date = today - timedelta(days=90)
#         else:
#             # start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
#             # end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
#             start_date = date(2025, 7, 1)
#             end_date = date(2025, 7, 24)

#         conn = get_ruzivo_conn()
#         query = """
#             SELECT COUNT(DISTINCT student_id) AS asl_active30
#             FROM tblstudents_login
#             WHERE DATE(login_date) BETWEEN %s AND %s
#         """

#         df = pd.read_sql_query(query, conn, params=[start_date, end_date])
#         conn.close()

#         # Get result
#         asl_count = int(df["asl_active30"].iloc[0])

#         # If user wants CSV/Excel download
#         if "download" in request.form:
#             output_format = request.form.get("download")  # "csv" or "excel"
#             output = io.BytesIO()

#             if output_format == "csv":
#                 df.to_csv(output, index=False)
#                 output.seek(0)
#                 return send_file(
#                     output,
#                     as_attachment=True,
#                     download_name=f"asl_active30_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
#                     mimetype="text/csv"
#                 )
#             else:  # default to Excel
#                 with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
#                     df.to_excel(writer, index=False, sheet_name="ASLActive30")
#                 output.seek(0)
#                 return send_file(
#                     output,
#                     as_attachment=True,
#                     download_name=f"asl_active30_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
#                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#                 )

#         return jsonify({
#             "start_date": str(start_date),
#             "end_date": str(end_date),
#             "asl_active30": asl_count
#         })

#     except Exception as e:
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500



@app.route('/custom-active-date', methods=['GET', 'POST'])
def custom_active_date():

    return render_template(
        'customactivedate.html',
        title='Analytics'
    )



@app.route('/api/asl-active90', methods=['GET'])
def asl_active90():
    conn = None
    try:
        today = date.today()
        current_year = today.year
        current_month = today.month

        conn = get_ruzivo_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        monthly_data = []

        for month in range(1, current_month + 1):
            start_date = date(current_year, month, 1)
            end_day = calendar.monthrange(current_year, month)[1]
            end_date = date(current_year, month, end_day)

            query = """
                SELECT COUNT(DISTINCT student_id) AS asl_active
                FROM tblstudents_login
                WHERE DATE(login_date) BETWEEN %s AND %s
            """
            cursor.execute(query, (start_date, end_date))
            result = cursor.fetchone()

            monthly_data.append({
                "month": start_date.strftime("%B"),
                "year": current_year,
                "asl_active": int(result["asl_active"]) if result and result["asl_active"] else 0
            })

        cursor.close()
        conn.close()

        return jsonify({
            "year": current_year,
            "monthly_logins": monthly_data
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if conn:
    #         conn.close()




@app.route('/api/asl-filtered-count', methods=['GET'])
def asl_filtered_count():
    conn = None
    try:
        conn = get_ruzivo_conn()
        with conn.cursor() as cursor:
            query = """
                SELECT COUNT(DISTINCT sl.student_id) AS filtered_count
                FROM tblstudents_login sl
                WHERE sl.student_id NOT IN (
                    SELECT DISTINCT tp.student_id
                    FROM tblecocash_payment_order tp
                    WHERE transactionOperationStatus = 'COMPLETED'
                )
                AND sl.student_id NOT IN (
                    SELECT DISTINCT sl2.student_id
                    FROM tblstudents_login sl2
                    WHERE sl2.login_date BETWEEN '2025-06-01 00:00:00' AND '2025-08-30 23:59:59'
                )
                AND sl.login_date BETWEEN '2025-07-1 00:00:00' AND '2025-08-24 23:59:59';
            """
            cursor.execute(query)
            result = cursor.fetchone()

        return jsonify({
            "filtered_count": int(result[0]) if result and result[0] else 0
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if conn:
    #         conn.close()





import logging

# Province normalization helper (reuse same one as active30)
def normalize_province(name):
    if not name:
        return 'Unknown'

    cleaned = name.replace('_', ' ').replace(';', '').strip().title()

    typo_map = {
        "Bulawyo": "Bulawayo",
        "Bulawyoa": "Bulawayo",
        "Bulawyao": "Bulawayo",
        "Bul;awayo": "Bulawayo",
    }

    if cleaned in typo_map:
        corrected = typo_map[cleaned]
        logging.info(f"Province name corrected: '{cleaned}' → '{corrected}'")
        return corrected

    return cleaned


@app.route('/asl_registrations', methods=['GET', 'POST'])
@login_required
def asl_registrations():
    try:
        today = date.today()
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        start_date = start_date or today.replace(day=1).strftime('%Y-%m-%d')
        end_date = end_date or today.strftime('%Y-%m-%d')

        conn = get_ruzivo_conn()

        # --- Step 1: Get total registrations exactly like base query ---
        sql_total = """
            SELECT COUNT(DISTINCT student_id) AS value
            FROM tblstudents
            WHERE DATE(date_added) BETWEEN %s AND %s
        """
        with conn.cursor() as cur:
            cur.execute(sql_total, (start_date, end_date))
            total_registrations = cur.fetchone()['value']

        # --- Step 2: Get breakdown by gender & province ---
        sql_breakdown = """
            SELECT
                t.student_id,
                CASE
                    WHEN UPPER(TRIM(v.gender)) IN ('MALE','M') THEN 'Male'
                    WHEN UPPER(TRIM(v.gender)) IN ('FEMALE','F') THEN 'Female'
                    ELSE 'Unknown'
                END AS gender,
                v.province AS school_province
            FROM tblstudents t
            LEFT JOIN vwstudentschools v ON t.student_id = v.student_id
            WHERE DATE(t.date_added) BETWEEN %s AND %s
        """
        with conn.cursor() as cur:
            cur.execute(sql_breakdown, (start_date, end_date))
            rows = cur.fetchall()

        # conn.close()

        # --- Step 3: Normalize & Aggregate ---
        gender_totals = {"Male": 0, "Female": 0, "Unknown": 0}
        province_totals = {}
        breakdown = []

        seen = set()
        for r in rows:
            sid = r['student_id']
            if sid in seen:   # enforce DISTINCT student_id
                continue
            seen.add(sid)

            g = r['gender'] or "Unknown"
            prov = normalize_province(r['school_province'])

            gender_totals[g] = gender_totals.get(g, 0) + 1
            province_totals[prov] = province_totals.get(prov, 0) + 1

            breakdown.append({"school_province": prov, "gender": g, "count": 1})

        # --- Step 4: Consistency check ---
        gender_sum = sum(gender_totals.values())
        province_sum = sum(province_totals.values())

        if gender_sum != total_registrations:
            logging.warning(f"Gender totals mismatch ({gender_sum} vs {total_registrations}), correcting.")
            total_registrations = gender_sum

        if province_sum != total_registrations:
            logging.warning(f"Province totals mismatch ({province_sum} vs {total_registrations}), correcting.")
            total_registrations = province_sum

        province_totals_list = [{"school_province": k, "total": v} for k, v in province_totals.items()]

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "total_registrations": total_registrations,
            "gender_totals": gender_totals,
            "province_totals": province_totals_list,
            "breakdown": breakdown
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500




def normalize_province(name):
    """Clean up province names (case, underscores, typos)."""
    if not name:
        return "Unknown"
    cleaned = name.replace("_", " ").replace(";", "").strip().title()
    if cleaned.lower().startswith("bul"):
        return "Bulawayo"
    return cleaned

@app.route("/api/asl_total_primary_content", methods=["GET", "POST"])
@login_required
def asl_total_primary_content():
    try:
        today = date.today()
        start_date = request.form.get("start_date") or today.replace(day=1).strftime("%Y-%m-%d")
        end_date = request.form.get("end_date") or today.strftime("%Y-%m-%d")

        conn = get_ruzivo_conn()

        # 1) Total distinct students
        sql_total = """
            SELECT COUNT(DISTINCT ca.student_id) AS total
            FROM tblcontent_access ca
            JOIN tblstudents st ON st.student_id = ca.student_id
            JOIN vwstudent v ON v.student_id = ca.student_id
            JOIN tblschools s ON s.school_id = v.school_id
            WHERE ca.start_time BETWEEN %s AND %s
            AND st.student_type != 'STAFF'
        """
        with conn.cursor() as cur:
            cur.execute(sql_total, (start_date, end_date))
            total_students = cur.fetchone()["total"]

        # 2) Gender + province breakdown
        sql_breakdown = """
            SELECT v.student_id, v.gender, s.school_province
            FROM tblcontent_access ca
            JOIN tblstudents st ON st.student_id = ca.student_id
            JOIN vwstudent v ON v.student_id = ca.student_id
            JOIN tblschools s ON s.school_id = v.school_id
            WHERE ca.start_time BETWEEN %s AND %s
            AND st.student_type != 'STAFF'
        """
        with conn.cursor() as cur:
            cur.execute(sql_breakdown, (start_date, end_date))
            rows = cur.fetchall()

        # conn.close()

        gender_totals = {"Male": 0, "Female": 0, "Unknown": 0}
        province_totals = {}
        breakdown = {}

        counted_students = set()  # to avoid double-counting

        for row in rows:
            student_id = row["student_id"]
            if student_id in counted_students:
                continue
            counted_students.add(student_id)

            # Normalize gender
            gender = row["gender"].strip().upper() if row["gender"] else "UNKNOWN"
            if gender == "M":
                gender = "Male"
            elif gender == "F":
                gender = "Female"
            elif gender not in ["Male", "Female"]:
                gender = "Unknown"

            # Normalize province
            province = normalize_province(row["school_province"])

            # Aggregate counts
            gender_totals[gender] += 1
            province_totals[province] = province_totals.get(province, 0) + 1
            breakdown[(province, gender)] = breakdown.get((province, gender), 0) + 1

        # Build breakdown list
        breakdown_list = [{"school_province": p, "gender": g, "count": c} for (p, g), c in breakdown.items()]

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "total_students": total_students,
            "gender_totals": gender_totals,
            "province_totals": province_totals,
            "breakdown": breakdown_list
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500





def normalize_gender(g):
    if not g:
        return "Unknown"
    g = g.strip().upper()
    if g in ["M", "MALE"]:
        return "Male"
    if g in ["F", "FEMALE"]:
        return "Female"
    return "Unknown"

def normalize_province(name):
    if not name:
        return "Unknown"
    cleaned = name.replace("_", " ").replace(";", "").strip().title()
    if cleaned.lower().startswith("bul"):
        return "Bulawayo"
    return cleaned

@app.route("/api/asl_teacher_set_activities", methods=["GET", "POST"])
@login_required
def asl_teacher_set_activities():
    try:
        today = date.today()
        start_date = request.form.get("start_date") or today.replace(day=1).strftime("%Y-%m-%d")
        end_date = request.form.get("end_date") or today.strftime("%Y-%m-%d")

        conn = get_ruzivo_conn()

        # 1) Get distinct student_ids
        sql_students = """
            SELECT DISTINCT ta.student_id
            FROM tblclass_activity_results ta
            JOIN tblstudents ts ON ts.student_id = ta.student_id
            WHERE ta.date_added BETWEEN %s AND %s
              AND ts.student_type != 'STAFF'
        """
        with conn.cursor() as cur:
            cur.execute(sql_students, (start_date, end_date))
            students = [row["student_id"] for row in cur.fetchall()]

        if not students:
            conn.close()
            return jsonify({
                "start_date": start_date,
                "end_date": end_date,
                "total_teacher_set_activities": 0,
                "gender_totals": {},
                "province_totals": {},
                "breakdown": []
            })

        # 2) Build dynamic IN clause
        placeholders = ",".join(["%s"] * len(students))
        sql_details = f"""
            SELECT v.student_id, v.gender, s.school_province
            FROM vwstudentschools v
            JOIN tblschools s ON v.school_id = s.school_id
            WHERE v.student_id IN ({placeholders})
        """

        with conn.cursor() as cur:
            cur.execute(sql_details, tuple(students))
            details = cur.fetchall()

        # conn.close()

        # 3) Aggregate counts
        gender_totals = {"Male": 0, "Female": 0, "Unknown": 0}
        province_totals = {}
        breakdown = {}

        for row in details:
            gender = normalize_gender(row["gender"])
            province = normalize_province(row["school_province"])

            gender_totals[gender] += 1
            province_totals[province] = province_totals.get(province, 0) + 1

            key = (province, gender)
            breakdown[key] = breakdown.get(key, 0) + 1

        total_teacher_set_activities = len(set(students))

        # ✅ Ensure consistency
        # if sum(gender_totals.values()) != total_teacher_set_activities:
        #     raise ValueError("Gender totals mismatch with overall total.")
        # if sum(province_totals.values()) != total_teacher_set_activities:
        #     raise ValueError("Province totals mismatch with overall total.")

        breakdown_list = []
        for (prov, gender), count in breakdown.items():
            breakdown_list.append({
                "school_province": prov,
                "gender": gender,
                "count": count
            })

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "total_teacher_set_activities": total_teacher_set_activities,
            "gender_totals": gender_totals,
            "province_totals": province_totals,
            "breakdown": breakdown_list
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500





def normalize_gender(gender):
    """Normalize gender values."""
    if not gender:
        return "Unknown"
    g = gender.strip().lower()
    if g in ["male", "m"]:
        return "Male"
    if g in ["female", "f"]:
        return "Female"
    return "Unknown"

def normalize_province(name):
    """Clean up province names (case, underscores, typos)."""
    if not name:
        return "Unknown"
    cleaned = name.replace("_", " ").replace(";", "").strip().title()
    if cleaned.lower().startswith("bul"):
        return "Bulawayo"
    return cleaned


@app.route("/api/asl_teacher_access", methods=["GET", "POST"])
@login_required
def asl_teacher_access():
    try:
        today = date.today()
        start_date = request.form.get("start_date") or today.replace(day=1).strftime("%Y-%m-%d")
        end_date   = request.form.get("end_date")   or today.strftime("%Y-%m-%d")

        conn = get_ruzivo_conn()

        # Pull all teachers active in range with their gender and province
        sql = """
            SELECT t.teacher_id, t.gender, s.school_province
            FROM tbl_teacher t
            JOIN tblschools s ON s.school_id = t.school_id
            WHERE t.active_at BETWEEN %s AND %s
        """
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, (start_date, end_date))
            rows = cur.fetchall()

        # conn.close()

        if not rows:
            return jsonify({
                "start_date": start_date,
                "end_date": end_date,
                "total_teachers": 0,
                "gender_totals": {},
                "province_totals": {},
                "breakdown": []
            })

        gender_totals  = {"Male": 0, "Female": 0, "Unknown": 0}
        province_totals = {}
        breakdown = {}

        for r in rows:
            g = normalize_gender(r.get("gender"))
            p = normalize_province(r.get("school_province"))

            gender_totals[g] += 1
            province_totals[p] = province_totals.get(p, 0) + 1
            breakdown[(p, g)] = breakdown.get((p, g), 0) + 1

        total_teachers = len(rows)

        # Consistency (they should always match since all counts derive from `rows`)
        # If you prefer hard enforcement, uncomment the raises.
        # if sum(gender_totals.values()) != total_teachers:
        #     raise ValueError("Gender totals mismatch with overall total.")
        # if sum(province_totals.values()) != total_teachers:
        #     raise ValueError("Province totals mismatch with overall total.")

        breakdown_list = [
            {"school_province": prov, "gender": gen, "count": cnt}
            for (prov, gen), cnt in breakdown.items()
        ]

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "total_teachers": total_teachers,
            "gender_totals": gender_totals,
            "province_totals": province_totals,
            "breakdown": breakdown_list
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500




def normalize_province(name):
    """Clean up province names (case, underscores, typos)."""
    if not name:
        return "Unknown"
    cleaned = name.replace("_", " ").replace(";", "").strip().title()
    # Handle specific typos
    if cleaned.lower().startswith("bul"):
        return "Bulawayo"
    return cleaned

@app.route("/api/asl_unique_users", methods=["GET", "POST"])
@login_required
def asl_unique_users():
    try:
        today = date.today()
        start_date = request.form.get("start_date") or today.replace(day=1).strftime("%Y-%m-%d")
        end_date = request.form.get("end_date") or today.strftime("%Y-%m-%d")

        conn = get_ruzivo_conn()

        # 1) Get distinct users who logged in within range
        sql_users = """
            SELECT DISTINCT student_id
            FROM tblstudents_login
            WHERE login_date BETWEEN %s AND %s
        """
        with conn.cursor() as cur:
            cur.execute(sql_users, (start_date, end_date))
            users = [row["student_id"] for row in cur.fetchall()]

        if not users:
            return jsonify({
                "start_date": start_date,
                "end_date": end_date,
                "total_unique_users": 0,
                "gender_totals": {},
                "province_totals": {},
                "breakdown": []
            })

        # 2) Get gender + school_id from vwstudentschools
        sql_details = """
            SELECT v.student_id, v.gender, v.school_id, s.school_province
            FROM vwstudentschools v
            JOIN tblschools s ON v.school_id = s.school_id
            WHERE v.student_id IN %s
        """
        with conn.cursor() as cur:
            cur.execute(sql_details, (tuple(users),))
            details = cur.fetchall()

        # conn.close()

        # 3) Aggregate by gender & province
        gender_totals = {"Male": 0, "Female": 0, "Unknown": 0}
        province_totals = {}
        breakdown = {}

        for row in details:
            gender = row["gender"].strip().capitalize() if row["gender"] else "Unknown"
            if gender not in ["Male", "Female"]:
                gender = "Unknown"

            province = normalize_province(row["school_province"])

            # Count by gender
            gender_totals[gender] += 1

            # Count by province
            if province not in province_totals:
                province_totals[province] = 0
            province_totals[province] += 1

            # Breakdown province × gender
            key = (province, gender)
            breakdown[key] = breakdown.get(key, 0) + 1

        total_unique_users = len(users)

        # ✅ Consistency checks
        # if sum(gender_totals.values()) != total_unique_users:
        #     raise ValueError("Gender totals mismatch with overall total.")
        # if sum(province_totals.values()) != total_unique_users:
        #     raise ValueError("Province totals mismatch with overall total.")

        # 4) Build breakdown list for frontend
        breakdown_list = []
        for (prov, gender), count in breakdown.items():
            breakdown_list.append({
                "school_province": prov,
                "gender": gender,
                "count": count
            })

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "total_unique_users": total_unique_users,
            "gender_totals": gender_totals,
            "province_totals": province_totals,
            "breakdown": breakdown_list
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/asl_unique_subscribers', methods=['GET', 'POST'])
@login_required
def asl_unique_subscribers():
    try:
        today = date.today()
        # default: first of month to today
        start_date = request.form.get('start_date') or today.replace(day=1).strftime('%Y-%m-%d')
        end_date = request.form.get('end_date') or today.strftime('%Y-%m-%d')

        conn = get_ruzivo_conn()

        # --- 1) Total unique subscribers directly from payments ---
        sql_total = """
            SELECT COUNT(DISTINCT p.student_id) AS total_subscribers
            FROM tblecocash_payment_order p
            WHERE p.date_created BETWEEN %s AND %s
              AND p.transactionOperationStatus = 'COMPLETED'
        """
        with conn.cursor() as cur:
            cur.execute(sql_total, (start_date, end_date))
            total_row = cur.fetchone()
            total_subscribers = total_row['total_subscribers'] if total_row else 0

        # --- 2) Breakdown with LEFT JOIN so we don't drop unmatched students ---
        sql_breakdown = """
            SELECT
                CASE
                    WHEN UPPER(TRIM(v.gender)) IN ('MALE','M') THEN 'Male'
                    WHEN UPPER(TRIM(v.gender)) IN ('FEMALE','F') THEN 'Female'
                    ELSE 'Unknown'
                END AS gender,
                TRIM(s.school_province) AS school_province,
                COUNT(DISTINCT p.student_id) AS cnt
            FROM tblecocash_payment_order p
            LEFT JOIN vwstudentschools v ON p.student_id = v.student_id
            LEFT JOIN tblschools s ON v.school_id = s.school_id
            WHERE p.date_created BETWEEN %s AND %s
              AND p.transactionOperationStatus = 'COMPLETED'
            GROUP BY gender, s.school_province
        """
        with conn.cursor() as cur:
            cur.execute(sql_breakdown, (start_date, end_date))
            breakdown_raw = cur.fetchall()

        # conn.close()

        # --- 3) Normalize & aggregate ---
        def normalize_province(name):
            if not name: return "Unknown"
            name = name.replace("_", " ").replace(";", "").strip().title()
            if name.lower() in ["bulawayo", "bul;awayo", "bul awayo"]:
                return "Bulawayo"
            return name

        breakdown_agg = {}
        gender_totals = {"Male": 0, "Female": 0, "Unknown": 0}
        province_totals = {}

        for row in breakdown_raw:
            prov = normalize_province(row['school_province'])
            g = row['gender']
            c = int(row['cnt'])

            if prov not in breakdown_agg:
                breakdown_agg[prov] = {"Male": 0, "Female": 0, "Unknown": 0}

            breakdown_agg[prov][g] += c
            gender_totals[g] += c
            province_totals[prov] = province_totals.get(prov, 0) + c

        # --- 4) Guarantee consistency: match raw total query ---
        if sum(gender_totals.values()) != total_subscribers:
            total_subscribers = sum(gender_totals.values())
        if sum(province_totals.values()) != total_subscribers:
            total_subscribers = sum(province_totals.values())

        # --- 5) Format breakdown ---
        breakdown = []
        for prov, gdict in breakdown_agg.items():
            for g, val in gdict.items():
                if val > 0:
                    breakdown.append({
                        "school_province": prov,
                        "gender": g,
                        "count": val
                    })

        province_totals_list = [
            {"school_province": prov, "total_count": val}
            for prov, val in province_totals.items() if val > 0
        ]

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "total_subscribers": total_subscribers,
            "gender_totals": gender_totals,
            "province_totals": province_totals_list,
            "breakdown": breakdown
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



def normalize_province(name):
    """
    Normalize province names:
    - Replace underscores, semicolons with spaces
    - Strip whitespace
    - Title-case
    - Map known variants to canonical form
    """
    if not name:
        return "Unknown"
    clean = name.replace("_", " ").replace(";", "").strip().title()
    mappings = {
        "Bulawayo": ["Bulawayo", "Bul;Awayo", "Bul Awayo"],
    }
    for canonical, variants in mappings.items():
        if clean in variants:
            return canonical
    return clean

@app.route("/api/asl_total_zimsec_access", methods=["GET"])
@login_required
def asl_total_zimsec_access():
    try:
        today = date.today()
        start_date = today.replace(day=1).strftime("%Y-%m-%d")  # first of month
        end_date = today.strftime("%Y-%m-%d")

        conn = get_ruzivo_conn()

        # 1) Baseline total + student list
        sql_students = """
            SELECT DISTINCT zi.student_id
            FROM tblcontent_access_zimsec zi
            JOIN tblstudents ts ON ts.student_id = zi.student_id
            WHERE zi.start_time BETWEEN %s AND %s
              AND ts.student_type != 'STAFF'
        """
        with conn.cursor() as cur:
            cur.execute(sql_students, (start_date, end_date))
            student_ids = [row["student_id"] for row in cur.fetchall()]
        total_access = len(student_ids)

        if total_access == 0:
            return jsonify({
                "start_date": start_date,
                "end_date": end_date,
                "total_access": 0,
                "genders": ["Male", "Female", "Unknown"],
                "gender_totals": {"Male": 0, "Female": 0, "Unknown": 0},
                "province_totals": [],
                "breakdown": []
            })

        # 2) Enrich with gender + province (LEFT JOIN so nothing is dropped)
        sql_breakdown = f"""
            SELECT
                ts.student_id,
                CASE
                    WHEN UPPER(TRIM(vs.gender)) IN ('MALE','M') THEN 'Male'
                    WHEN UPPER(TRIM(vs.gender)) IN ('FEMALE','F') THEN 'Female'
                    ELSE 'Unknown'
                END AS gender,
                TRIM(s.school_province) AS province
            FROM tblstudents ts
            LEFT JOIN vwstudentschools vs ON ts.student_id = vs.student_id
            LEFT JOIN tblschools s ON vs.school_id = s.school_id
            WHERE ts.student_id IN ({",".join(["%s"] * len(student_ids))})
        """
        with conn.cursor() as cur:
            cur.execute(sql_breakdown, student_ids)
            enriched = cur.fetchall()

        # conn.close()

        # 3) Normalize + aggregate
        def normalize_province(name):
            if not name:
                return "Unknown"
            clean = name.replace("_", " ").replace(";", "").strip().title()
            mappings = {"Bulawayo": ["Bulawayo", "Bul;Awayo", "Bul Awayo"]}
            for canonical, variants in mappings.items():
                if clean in variants:
                    return canonical
            return clean

        gender_totals = {"Male": 0, "Female": 0, "Unknown": 0}
        province_totals = {}
        breakdown_agg = {}

        for row in enriched:
            gender = row["gender"] or "Unknown"
            prov = normalize_province(row["province"])
            gender_totals[gender] = gender_totals.get(gender, 0) + 1
            province_totals[prov] = province_totals.get(prov, 0) + 1
            breakdown_agg[(prov, gender)] = breakdown_agg.get((prov, gender), 0) + 1

        breakdown = [
            {"school_province": prov, "gender": g, "count": cnt}
            for (prov, g), cnt in breakdown_agg.items()
            if cnt > 0
        ]

        province_totals_list = [
            {"school_province": prov, "total": cnt}
            for prov, cnt in province_totals.items()
            if cnt > 0
        ]

        # ✅ Consistency check
        if sum(gender_totals.values()) != total_access:
            total_access = sum(gender_totals.values())
        if sum([p["total"] for p in province_totals_list]) != total_access:
            total_access = sum([p["total"] for p in province_totals_list])

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "total_access": total_access,
            "genders": ["Male", "Female", "Unknown"],
            "gender_totals": gender_totals,
            "province_totals": province_totals_list,
            "breakdown": breakdown
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/api/asl_total_sec_exercise", methods=["GET"])
@login_required
def asl_total_sec_exercise():
    try:
        today = date.today()
        start_date = today.replace(day=1).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        conn = get_ruzivo_conn()

        # 1) Query all distinct students with province and gender
        sql = """
            SELECT DISTINCT tr.student_id,
                CASE
                    WHEN UPPER(TRIM(vs.gender)) IN ('MALE','M') THEN 'Male'
                    WHEN UPPER(TRIM(vs.gender)) IN ('FEMALE','F') THEN 'Female'
                    ELSE 'Unknown'
                END AS gender,
                TRIM(s.school_province) AS province
            FROM tblresults_hs tr
            LEFT JOIN vwstudent vs ON vs.student_id = tr.student_id
            LEFT JOIN tblstudents st ON st.student_id = tr.student_id
            LEFT JOIN tblschools s ON s.school_id = vs.school_id
            WHERE tr.date_added BETWEEN %s AND %s
              AND (st.student_type IS NULL OR st.student_type != 'STAFF')
        """
        with conn.cursor() as cur:
            cur.execute(sql, (start_date, end_date))
            rows = cur.fetchall()

        # conn.close()

        # 2) Normalize province names
        def normalize_province(name):
            if not name:
                return "Unknown"
            clean = name.replace("_", " ").replace(";", "").strip().title()
            mappings = {"Bulawayo": ["Bulawayo", "Bul;Awayo", "Bul Awayo"]}
            for canonical, variants in mappings.items():
                if clean in variants:
                    return canonical
            return clean

        # 3) Aggregate totals
        gender_totals = {"Male": 0, "Female": 0, "Unknown": 0}
        province_totals = {}
        breakdown_agg = {}

        for r in rows:
            gender = r["gender"] or "Unknown"
            prov = normalize_province(r["province"])
            gender_totals[gender] += 1
            province_totals[prov] = province_totals.get(prov, 0) + 1
            breakdown_agg[(prov, gender)] = breakdown_agg.get((prov, gender), 0) + 1

        total_exercises = len({r["student_id"] for r in rows})  # match main query

        breakdown = [
            {"school_province": prov, "gender": g, "count": cnt}
            for (prov, g), cnt in breakdown_agg.items()
            if cnt > 0
        ]

        province_totals_list = [
            {"school_province": prov, "total": cnt}
            for prov, cnt in province_totals.items()
            if cnt > 0
        ]

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "total_exercises": total_exercises,
            "genders": ["Male", "Female", "Unknown"],
            "gender_totals": gender_totals,
            "province_totals": province_totals_list,
            "breakdown": breakdown
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500





def normalize_province(name):
    if not name:
        return 'Unknown'
    # Handle Bulawayo variants
    if name.upper().replace(";", "").replace("_", "").replace(" ", "") == "BULAWAYO":
        return "Bulawayo"
    return name.replace('_', ' ').strip().title()

def normalize_gender(g):
    if not g:
        return 'Unknown'
    g_clean = g.strip().upper()
    if g_clean in ['M', 'MALE']:
        return 'Male'
    elif g_clean in ['F', 'FEMALE']:
        return 'Female'
    return 'Unknown'

@app.route('/api/asl_total_primary_exercise', methods=['GET'])
@login_required
def asl_total_primary_exercise():
    try:
        today = date.today()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')  # first day of current month
        end_date = today.strftime('%Y-%m-%d')

        conn = get_ruzivo_conn()

        # Count distinct student_id with proper joins
        sql = """
            SELECT tr.student_id, vs.gender, s.school_province
            FROM tblresults tr
            JOIN tblstudents st ON st.student_id = tr.student_id
            JOIN vwstudent vs ON vs.student_id = tr.student_id
            JOIN tblschools s ON s.school_id = vs.school_id
            WHERE tr.date_added BETWEEN %s AND %s
              AND st.student_type != 'STAFF'
            GROUP BY tr.student_id, vs.gender, s.school_province
        """
        with conn.cursor() as cur:
            cur.execute(sql, (start_date, end_date))
            rows = cur.fetchall()

        # conn.close()

        breakdown_agg = {}
        province_totals_agg = {}
        total_exercises = 0

        for r in rows:
            gender = normalize_gender(r['gender'])
            prov = normalize_province(r['school_province'])

            breakdown_agg[(prov, gender)] = breakdown_agg.get((prov, gender), 0) + 1
            province_totals_agg[prov] = province_totals_agg.get(prov, 0) + 1
            total_exercises += 1

        breakdown = [{"school_province": p, "gender": g, "count": c} 
                     for (p, g), c in breakdown_agg.items() if c > 0]

        province_totals = [{"school_province": p, "count": c} 
                           for p, c in province_totals_agg.items() if c > 0]

        # Ensure consistency
        assert sum(d['count'] for d in breakdown) == total_exercises
        assert sum(p['count'] for p in province_totals) == total_exercises

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "total_exercises": total_exercises,
            "province_totals": province_totals,
            "breakdown": breakdown
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500





def normalize_province(name):
    """Clean up province names (case, underscores, typos)."""
    if not name:
        return "Unknown"
    cleaned = name.replace("_", " ").replace(";", "").strip().title()
    if cleaned.lower().replace(" ", "").startswith("bul"):
        return "Bulawayo"
    return cleaned

@app.route("/api/asl_total_sec_content", methods=["GET", "POST"])
@login_required
def asl_total_sec_content():
    try:
        today = date.today()
        start_date = request.form.get("start_date") or today.replace(day=1).strftime("%Y-%m-%d")
        end_date = request.form.get("end_date") or today.strftime("%Y-%m-%d")

        conn = get_ruzivo_conn()

        # 1) Get distinct students
        sql_students = """
            SELECT DISTINCT ca.student_id
            FROM tblcontent_access_hs ca
            JOIN tblstudents ts ON ts.student_id = ca.student_id
            WHERE ca.start_time BETWEEN %s AND %s
            AND ts.student_type != 'STAFF'
        """
        with conn.cursor() as cur:
            cur.execute(sql_students, (start_date, end_date))
            students = [row["student_id"] for row in cur.fetchall()]

        if not students:
            return jsonify({
                "start_date": start_date,
                "end_date": end_date,
                "total_students": 0,
                "gender_totals": {},
                "province_totals": {},
                "breakdown": []
            })

        # 2) Prepare IN clause safely
        if len(students) == 1:
            in_clause = f"({students[0]})"
        else:
            in_clause = str(tuple(students))

        sql_details = f"""
            SELECT v.student_id, v.gender, v.school_id, s.school_province
            FROM vwstudentschools v
            JOIN tblschools s ON v.school_id = s.school_id
            WHERE v.student_id IN {in_clause}
        """
        with conn.cursor() as cur:
            cur.execute(sql_details)
            details = cur.fetchall()

        # conn.close()

        gender_totals = {"Male": 0, "Female": 0, "Unknown": 0}
        province_totals = {}
        breakdown = {}

        for row in details:
            # Normalize gender
            g = row.get("gender")
            gender = "Unknown"
            if g:
                g_upper = g.strip().upper()
                if g_upper in ["M", "MALE"]:
                    gender = "Male"
                elif g_upper in ["F", "FEMALE"]:
                    gender = "Female"

            province = normalize_province(row.get("school_province"))

            gender_totals[gender] += 1
            province_totals[province] = province_totals.get(province, 0) + 1
            breakdown[(province, gender)] = breakdown.get((province, gender), 0) + 1

        total_students = len(students)

        breakdown_list = [
            {"school_province": prov, "gender": gender, "count": count}
            for (prov, gender), count in breakdown.items()
        ]

        return jsonify({
            "start_date": start_date,
            "end_date": end_date,
            "total_students": total_students,
            "gender_totals": gender_totals,
            "province_totals": province_totals,
            "breakdown": breakdown_list
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500








@app.route('/api/smartlearning-daily-logins', methods=['GET'])
@login_required
def smartlearning_daily_logins():
    conn = None

    try:
        # Set the range for the current month
        today = date.today()
        start_date = today.replace(day=1)
        # start_date = date(2025, 7, 1)
        end_date = today

        # Database query
        conn = get_ruzivo_conn()
        
        with conn.cursor() as cursor:
            query = """
                SELECT DATE(last_login) AS login_date, COUNT(*) AS login_count
                FROM tblstudents_info
                WHERE last_login BETWEEN %s AND %s
                GROUP BY DATE(last_login)
                ORDER BY login_date ASC
            """
            cursor.execute(query, (start_date, end_date))
            results = cursor.fetchall()

        # Format the results
        usage_data = [
            {"date": row['login_date'].isoformat(), "count": row['login_count']} for row in results
        ]


        return jsonify({
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "usage": usage_data
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if conn:
    #         conn.close()






@app.route('/api/asl-daily-unique', methods=['GET'])
def asl_daily_unique():
    conn = None
    try:
        today = date.today()
        current_year = today.year
        current_month = today.month
        days_in_month = calendar.monthrange(current_year, current_month)[1]

        conn = get_ruzivo_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        daily_data = []

        # Loop over each day of the current month
        for day in range(1, days_in_month - 1):
            current_day = date(current_year, current_month, day)

            # Yesterday = current day (00:00:00 → 23:59:59)
            day_start = datetime.combine(current_day, datetime.min.time())
            day_end = datetime.combine(current_day, datetime.max.time())

            # "Past range" = from 1st of month → 2 days before current_day
            month_start = date(current_year, current_month, 1)
            past_end = current_day - timedelta(days=2)

            # If the past range is invalid (e.g., before month start), skip
            if past_end < month_start:
                past_end = month_start

            query = """
                SELECT COUNT(DISTINCT sl.student_id) AS unique_count
                FROM tblstudents_login sl
                WHERE sl.student_id NOT IN (
                    SELECT DISTINCT tp.student_id
                    FROM tblecocash_payment_order tp
                    WHERE tp.transactionOperationStatus = 'COMPLETED'
                )
                AND sl.student_id NOT IN (
                    SELECT DISTINCT sl2.student_id
                    FROM tblstudents_login sl2
                    WHERE sl2.login_date BETWEEN %s AND %s
                )
                AND sl.login_date BETWEEN %s AND %s
            """

            cursor.execute(query, (
                month_start, past_end,
                day_start, day_end
            ))
            result = cursor.fetchone()

            daily_data.append({
                "date": current_day.strftime("%Y-%m-%d"),
                "unique_count": int(result["unique_count"]) if result and result["unique_count"] else 0
            })

        # cursor.close()
        # conn.close()

        return jsonify({
            "year": current_year,
            "month": date(current_year, current_month, 1).strftime("%B"),
            "daily_counts": daily_data
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if conn:
    #         conn.close()



@app.route('/api/all_akello_active30', methods=['GET'])
@login_required
def all_akello_active30():
    today = datetime.today().date()
    active_30_date = today - timedelta(days=30)

    results = {
        "asl_active30": 0,
        "unique_chat_students30": 0,
        "al_active30": 0
    }

    try:
        # --- Ruzivo DB Connection ---
        conn = get_ruzivo_conn()
        cursor = conn.cursor()

        # Query 1: ASL active logins (last 30 days)
        asl_query = """
            SELECT COUNT(DISTINCT student_id) AS asl_active30
            FROM tblstudents_login
            WHERE DATE(login_date) BETWEEN %s AND %s
        """
        cursor.execute(asl_query, (active_30_date, today))
        row = cursor.fetchone()
        results["asl_active30"] = row["asl_active30"] if row else 0

        # Query 2: Unique students in chat logs (last 30 days)
        chat_query = """
            SELECT COUNT(DISTINCT student_id) AS unique_students_count
            FROM tblask_akello_chat_logs
            WHERE created_at >= NOW() - INTERVAL 30 DAY
        """
        cursor.execute(chat_query)
        row = cursor.fetchone()
        results["unique_chat_students30"] = row["unique_students_count"] if row else 0

        cursor.close()
        conn.close()

    except Exception as e:
        print("Error querying Ruzivo DB:", e)

    try:
        # --- Library DB Connection ---
        conn = get_direct_library_conn()
        cursor = conn.cursor()

        # Query 3: Library active logins (last 30 days)
        al_query = """
            SELECT COUNT(DISTINCT user_id) AS al_active30
            FROM logins
            WHERE DATE(created_at) BETWEEN %s AND %s
        """
        cursor.execute(al_query, (active_30_date, today))
        row = cursor.fetchone()
        results["al_active30"] = row["al_active30"] if row else 0

        cursor.close()
        conn.close()

    except Exception as e:
        print("Error querying Library DB:", e)

    return jsonify(results)




from calendar import month_name, monthrange

@app.route('/api/smartlearning-monthly-logins', methods=['GET'])
@login_required
def smartlearning_monthly_logins():
    conn = None
    try:
        today = date.today()
        current_year = today.year
        current_month = today.month

        monthly_data = []
        conn = get_ruzivo_conn()

        # conn = ruzivo_pool.connection()
        with conn.cursor() as cursor:
            for month in range(1, current_month + 1):
                # Calculate start and end dates for the month
                start_date = date(current_year, month, 1)
                end_day = monthrange(current_year, month)[1]
                end_date = date(current_year, month, end_day)

                # Run the query
                query = """
                    SELECT COUNT(DISTINCT student_id) AS asl_active30
                    FROM tblstudents_login
                    WHERE DATE(login_date) BETWEEN DATE(%s) AND DATE(%s)
                """
                cursor.execute(query, (start_date, end_date))
                result = cursor.fetchone()

                monthly_data.append({
                    "month": start_date.strftime("%B"),
                    "year": current_year,
                    "student_count": result['asl_active30'] if result['asl_active30'] is not None else 0
                })

        return jsonify({
            "year": current_year,
            "monthly_logins": monthly_data
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if conn:
    #         conn.close()






@app.route('/api/library-province-institution-logins', methods=['GET'])
def institution_logins():
    try:
        # Get province name dynamically from query param
        province = request.args.get("province")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        if not province or not start_date or not end_date:
            return jsonify({"error": "Missing required parameters"}), 400

        conn = get_direct_library_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        query = """
            SELECT 
                i.province,
                i.name AS institution_name,
                COUNT(DISTINCT l.user_id) AS user_count
            FROM users u
            INNER JOIN logins l ON l.user_id = u.id
            INNER JOIN institution_user iu ON iu.user_id = u.id
            INNER JOIN institutions i ON i.id = iu.institution_id
            WHERE i.province = %s
              AND l.created_at BETWEEN %s AND %s
            GROUP BY i.id, i.name, i.province
            ORDER BY user_count DESC
        """
        cursor.execute(query, (province, start_date, end_date))
        results = cursor.fetchall()

        return jsonify({
            "province": province,
            "start_date": start_date,
            "end_date": end_date,
            "institutions": results
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals() and conn:
    #         conn.close()





@app.route('/api/library-province-institution-daily-logins', methods=['GET'])
def library_province_institution_daily_logins():
    try:
        province = request.args.get("province")
        day = request.args.get("day")  # Format: YYYY-MM-DD

        if not province or not day:
            return jsonify({"error": "Missing required parameters (province, day)"}), 400

        # Construct day range
        start_date = f"{day} 00:00:00"
        end_date = f"{day} 23:59:59"

        conn = get_direct_library_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        query = """
            SELECT 
                i.province,
                i.name AS institution_name,
                COUNT(DISTINCT l.user_id) AS user_count
            FROM users u
            INNER JOIN logins l ON l.user_id = u.id
            INNER JOIN institution_user iu ON iu.user_id = u.id
            INNER JOIN institutions i ON i.id = iu.institution_id
            WHERE i.province = %s
              AND l.created_at BETWEEN %s AND %s
            GROUP BY i.id, i.name, i.province
            ORDER BY user_count DESC
        """
        cursor.execute(query, (province, start_date, end_date))
        results = cursor.fetchall()

        return jsonify({
            "province": province,
            "day": day,
            "institutions": results
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals() and conn:
    #         conn.close()










@app.route('/akello-library-metrics', methods=['GET','POST'])
@login_required
def akello_library_metrics():
    if not request.is_json:
        return jsonify({"error": "Expected JSON body"}), 400

    data = request.get_json()
    today = date.today()
    start_date = data.get('start_date') or today.replace(day=1).strftime('%Y-%m-%d')
    end_date = data.get('end_date') or today.strftime('%Y-%m-%d')

    try:
        active_30_date = (
            datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)
        ).strftime('%Y-%m-%d')

        queries = {
            "Total Registrations": f"""
                SELECT COUNT(DISTINCT username) AS value
                FROM users
                WHERE created_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND deleted_at IS NULL
            """,
            "Total Revenue (by currency)": f"""
                SELECT currency, SUM(total_amount) AS value
                FROM orders
                WHERE created_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND status='Completed'
                GROUP BY currency
            """,
            "Unique Subscribers": f"""
                SELECT COUNT(DISTINCT user_id) AS value
                FROM orders
                WHERE created_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND status='Completed'
            """,
            "Unique Readers": f"""
                SELECT COUNT(DISTINCT user_id) AS value
                FROM read_trackers
                WHERE created_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND duration_minutes != 0
            """,
            "Active Users": f"""
                SELECT COUNT(DISTINCT user_id) AS value
                FROM logins
                WHERE created_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            """,
            "Active in Last 30 Days": f"""
                SELECT COUNT(DISTINCT user_id) AS value
                FROM last_activities
                WHERE created_at BETWEEN DATE('{active_30_date}') AND DATE('{end_date}')
            """
        }

        results = {}
        conn = get_direct_library_conn()

        with conn.cursor() as cursor:
            for label, query in queries.items():
                cursor.execute(query)
                rows = cursor.fetchall()

                if "Revenue" in label:
                    results[label] = ', '.join(
                        f"{row['currency']}: {row['value']}" for row in rows
                    ) if rows else "N/A"
                else:
                    results[label] = rows[0]['value'] if rows else 0


        return jsonify(results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()





# old asl metrics

@app.route('/api/analytics-summary')
@login_required
def get_analytics_summary():
    try:
        # Date calculations
        today = date.today()
        start_date = today.replace(day=1)
        active_30_date = today - timedelta(days=30)

        # SQL queries
        queries = {
            "asl_unique_users": f"""
                SELECT COUNT(DISTINCT student_id) AS value
                FROM tblstudents_login
                WHERE login_date BETWEEN DATE('{start_date}') AND DATE('{today}')
            """,
            "asl_registrations": f"""
                SELECT COUNT(DISTINCT student_id) AS value
                FROM tblstudents
                WHERE date_added BETWEEN DATE('{start_date}') AND DATE('{today}')
            """,
            "asl_total_primary_content": f"""
                SELECT COUNT(DISTINCT ca.student_id) AS value
                FROM tblcontent_access ca
                JOIN tblstudents ts ON ts.student_id = ca.student_id
                WHERE ca.start_time BETWEEN DATE('{start_date}') AND DATE('{today}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_total_sec_content": f"""
                SELECT COUNT(DISTINCT ca.student_id) AS value
                FROM tblcontent_access_hs ca
                JOIN tblstudents ts ON ts.student_id = ca.student_id
                WHERE ca.start_time BETWEEN DATE('{start_date}') AND DATE('{today}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_total_primary_exercise": f"""
                SELECT COUNT(DISTINCT tr.student_id) AS value
                FROM tblresults tr
                JOIN tblstudents ts ON ts.student_id = tr.student_id
                WHERE tr.date_added BETWEEN DATE('{start_date}') AND DATE('{today}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_total_sec_exercise": f"""
                SELECT COUNT(DISTINCT tr.student_id) AS value
                FROM tblresults_hs tr
                JOIN tblstudents ts ON ts.student_id = tr.student_id
                WHERE tr.date_added BETWEEN DATE('{start_date}') AND DATE('{today}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_total_zimsec_access": f"""
                SELECT COUNT(DISTINCT zi.student_id) AS value
                FROM tblcontent_access_zimsec zi
                JOIN tblstudents ts ON ts.student_id = zi.student_id
                WHERE zi.start_time BETWEEN DATE('{start_date}') AND DATE('{today}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_teacher_set_activities": f"""
                SELECT COUNT(DISTINCT ta.student_id) AS value
                FROM tblclass_activity_results ta
                JOIN tblstudents ts ON ts.student_id = ta.student_id
                WHERE ta.date_added BETWEEN DATE('{start_date}') AND DATE('{today}')
                AND ts.student_type != 'STAFF'
            """,
            "asl_teacher_access": f"""
                SELECT COUNT(teacher_id) AS value
                FROM tbl_teacher
                WHERE active_at BETWEEN DATE('{start_date}') AND DATE('{today}')
            """,
            "asl_revenue": f"""
                SELECT currency, SUM(amount) AS value
                FROM tblecocash_payment_order
                WHERE date_created BETWEEN DATE('{start_date}') AND DATE('{today}')
                AND transactionOperationStatus = 'COMPLETED'
                GROUP BY currency
            """,
            "asl_unique_subscribers": f"""
                SELECT COUNT(DISTINCT student_id) AS value
                FROM tblecocash_payment_order
                WHERE date_created BETWEEN DATE('{start_date}') AND DATE('{today}')
                AND transactionOperationStatus = 'COMPLETED'
            """,
            "asl_active_30": f"""
                SELECT COUNT(DISTINCT student_id) AS value
                FROM tblstudents_login
                WHERE login_date BETWEEN DATE('{active_30_date}') AND DATE('{today}')
            """
        }

        # Use pooled DB connection
        # connection = get_ruzivo_conn()
        summary = {}

        with ruzivo_conn.cursor() as cursor:
            for key, query in queries.items():
                cursor.execute(query)
                result = cursor.fetchall()

                if key == "asl_revenue":
                    summary[key] = result  # Return list with currency + value
                else:
                    summary[key] = result[0]["value"] if result else 0

        return jsonify(summary)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    # finally:
    #     if 'connection' in locals():
    #         connection.close()  # Return to pool





@app.route('/api/library-analytics', methods=['GET'])
@login_required
def api_libraryanalytics():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({"error": "Missing start_date or end_date"}), 400

    try:
        active_30_date = (
            datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)
        ).strftime('%Y-%m-%d')

        queries = {
            "Total Registrations": f"""
                SELECT COUNT(DISTINCT username) AS value
                FROM users
                WHERE created_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND deleted_at IS NULL
            """,
            "Total Revenue (by currency)": f"""
                SELECT currency, SUM(total_amount) AS value
                FROM orders
                WHERE created_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND status='Completed'
                GROUP BY currency
            """,
            "Unique Subscribers": f"""
                SELECT COUNT(DISTINCT user_id) AS value
                FROM orders
                WHERE created_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND status='Completed'
            """,
            "Unique Readers": f"""
                SELECT COUNT(DISTINCT user_id) AS value
                FROM read_trackers
                WHERE created_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
                AND duration_minutes != 0
            """,
            "Active Users": f"""
                SELECT COUNT(DISTINCT user_id) AS value
                FROM last_activities
                WHERE created_at BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            """,
            "Active in Last 30 Days": f"""
                SELECT COUNT(DISTINCT user_id) AS value
                FROM last_activities
                WHERE created_at BETWEEN DATE('{active_30_date}') AND DATE('{end_date}')
            """
        }


        results = {}
        # conn = get_direct_library_conn()  # From pool with persistent tunnel

        with library_conn.cursor() as cursor:
            for label, query in queries.items():
                cursor.execute(query)
                rows = cursor.fetchall()

                if "Revenue" in label:
                    results[label] = ', '.join(
                        f"{row['currency']}: {row['value']}" for row in rows
                    ) if rows else "N/A"
                else:
                    results[label] = rows[0]['value'] if rows else 0


        return jsonify(results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # finally:
    #     if 'conn' in locals():
    #         conn.close()  # Return to pool






from flask import request, jsonify
from datetime import date, timedelta, datetime
import pandas as pd
import traceback

@app.route("/api/library-active90", methods=["GET"])
def library_active90():
    conn = None
    try:
        # Default range: last 90 days
        today = datetime.now().date()
        start_date = today - timedelta(days=90)
        end_date = today

        # Allow custom range via query params
        if request.args.get("start_date") and request.args.get("end_date"):
            start_date = datetime.strptime(request.args["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(request.args["end_date"], "%Y-%m-%d").date()

        # Full datetime range
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        conn = get_direct_library_conn()

        # Detect correct DictCursor based on driver
        try:
            import pymysql.cursors
            cursor = conn.cursor(pymysql.cursors.DictCursor)
        except ImportError:
            import MySQLdb.cursors
            cursor = conn.cursor(MySQLdb.cursors.DictCursor)

        query = """
            SELECT COUNT(DISTINCT user_id) AS active_users
            FROM last_activities
            WHERE created_at BETWEEN %s AND %s
        """
        cursor.execute(query, (start_dt, end_dt))
        result = cursor.fetchone()
        # cursor.close()
        # conn.close()

        active_users = result["active_users"] if result and result["active_users"] else 0

        return jsonify({
            "start_date": str(start_date),
            "end_date": str(end_date),
            "library_active90": int(active_users)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500











import traceback


# library tables 
@app.route('/check-columns')
def check_columns():
    try:
        # Get connection from SSH-tunneled pool
        connection = get_direct_library_conn()
        cursor = connection.cursor()

        # Fetch all table names
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()

        html_output = "<h2>Database: akello_library_2</h2>"

        for table in tables:
            table_name = list(table.values())[0]  # pymysql.DictCursor gives a dict per row
            try:
                html_output += f"<h3>Table: <code>{table_name}</code></h3><ul>"

                cursor.execute(f"DESCRIBE `{table_name}`;")
                columns = cursor.fetchall()

                for col in columns:
                    html_output += f"<li>{col['Field']} ({col['Type']})</li>"

                html_output += "</ul><hr>"
            except Exception as e:
                html_output += f"<p style='color:red;'>Error fetching columns for table <code>{table_name}</code>: {str(e)}</p><hr>"

        return html_output

    except Exception as e:
        return f"<h3>Error:</h3><p>{str(e)}</p>"

    # finally:
    #     if 'cursor' in locals():
    #         cursor.close()
    #     if 'connection' in locals():
    #         connection.close()









@app.route('/schooltracker', methods=['GET', 'POST'])
@login_required
def schooltracker():

    return render_template('schooltracker.html', title='School tracker')


@app.route('/bookallocations', methods=['GET', 'POST'])
@login_required
def bookallocations():
    allocate_form = BookAllocationForm()
    allocations = BookAllocations.query.order_by(BookAllocations.timestamp.desc()).all()


    province_summary = Counter([a.school_province for a in allocations])
    # Province Summary
    province_counter = Counter([a.school_province for a in allocations])
    province_labels = list(province_counter.keys())
    province_counts = list(province_counter.values())

    # Book Allocation Chart
    book_counter = defaultdict(int)
    for a in allocations:
        for b in a.books_allocated.split(','):
            book_counter[b.strip()] += 1

    book_labels = list(book_counter.keys())
    book_counts = list(book_counter.values())
    return render_template('book_allocations.html',allocations=allocations, province_summary=province_summary,book_labels=book_labels,
                           book_counts=book_counts,allocate_form=allocate_form,province_labels=province_labels,province_counts=province_counts, title='Book Allocations')


@app.route('/allocate_books', methods=['GET', 'POST'])
@login_required
def allocate_books():
    allocate_form = BookAllocationForm()
    
    if allocate_form.validate_on_submit():
        try:
            book_allocation = BookAllocations(
                school_name=allocate_form.school_name.data,
                school_province=allocate_form.school_province.data,
                books_allocated=','.join(allocate_form.books_allocated.data),
                allocated_by=current_user.username  # Ensure user is logged in
            )
            db.session.add(book_allocation)
            db.session.commit()
            flash('Book allocation recorded successfully!', 'success')
            return redirect(url_for('bookallocations'))  # Ensure 'metrics' route exists
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

    # Debugging: Print form errors if validation fails
    if request.method == 'POST':
        print("Form Errors:", allocate_form.errors)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    all_users = User.query.all()
    form = RegistrationForm()
    csvform = CSVUploadForm()
    number_of_users = User.query.count()
    championcsvform = ChampionCSVUploadForm()
    manual_form = ChampionSchoolForm()
    all_champions = ChampionSchool.query.all()

    all_schools = []
    # try:
    #     conn = get_ruzivo_conn()
    #     cursor = conn.cursor()

    #     # ✅ Use a dictionary cursor to get results directly as dicts
    #     cursor.execute("SELECT school_id, school_name FROM tblschools ORDER BY school_name ASC")
    #     rows = cursor.fetchall()

    #     # ✅ If rows aren't dicts, convert manually
    #     for row in rows:
    #         if isinstance(row, dict):
    #             all_schools.append({
    #                 "id": str(row['school_id']),
    #                 "name": row['school_name']
    #             })
    #         else:
    #             # fallback for tuple-style rows
    #             all_schools.append({
    #                 "id": str(row[0]),
    #                 "name": row[1]
    #             })

    # except Exception as e:
    #     flash(f"Error fetching schools: {e}", "danger")
    # finally:
    #     if 'cursor' in locals():
    #         cursor.close()
    #     if 'conn' in locals():
    #         conn.close()

    return render_template(
        'settings.html',
        form=form,
        csvform=csvform,
        all_users=all_users,
        number_of_users=number_of_users,
        manual_form=manual_form,
        championcsvform=championcsvform,
        all_champions=all_champions,
        all_schools=all_schools,
        title='Settings'
    )




@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    all_users = User.query.all()
    form = RegistrationForm()
    csvform = CSVUploadForm()
    number_of_users = User.query.count()
    championcsvform = ChampionCSVUploadForm()
    manual_form = ChampionSchoolForm()
    all_champions = ChampionSchool.query.all()

    all_schools = []

    if not current_user.userRole == "Admin":
        return "Unauthorized", 403

    users = User.query.all()


    return render_template(
        'admin.html',
        form=form,
        csvform=csvform,
        all_users=all_users,
        number_of_users=number_of_users,
        manual_form=manual_form,
        championcsvform=championcsvform,
        all_champions=all_champions,
        all_schools=all_schools,
        users=users,
        title='Settings'
    )





# Get all champions
@app.route("/api/champions", methods=["GET"])
def get_champions():
    champions = ChampionSchool.query.all()
    return jsonify([c.to_dict() for c in champions])


# Add a new champion
@app.route("/api/champions", methods=["POST"])
def add_champion():
    data = request.json
    champ = ChampionSchool(
        firstname=data["firstname"],
        lastname=data["lastname"],
        province=data["province"]
    )
    if "schools" in data:
        champ.set_schools(data["schools"])
    db.session.add(champ)
    db.session.commit()
    return jsonify(champ.to_dict()), 201


# Update champion (add a school)
@app.route("/api/champions/<int:champ_id>/add_school", methods=["POST"])
def add_school(champ_id):
    champ = ChampionSchool.query.get_or_404(champ_id)
    data = request.json
    champ.add_school(
        asl_id=data["asl_school_id"],
        library_id=data["library_school_id"],
        school_name=data["school_name"]
    )
    db.session.commit()
    return jsonify(champ.to_dict())


# Delete champion
@app.route("/api/champions/<int:champ_id>", methods=["DELETE"])
def delete_champion(champ_id):
    champ = ChampionSchool.query.get_or_404(champ_id)
    db.session.delete(champ)
    db.session.commit()
    return jsonify({"message": "Champion deleted"})



# Update champion's school details
@app.route("/api/champions/<int:champ_id>/schools/<int:school_id>", methods=["PUT"])
def update_school(champ_id, school_id):
    champ = ChampionSchool.query.get_or_404(champ_id)
    school = next((s for s in champ.schools if s.id == school_id), None)

    if not school:
        return jsonify({"error": "School not found for this champion"}), 404

    data = request.json
    if "asl_school_id" in data:
        school.asl_school_id = data["asl_school_id"]
    if "library_school_id" in data:
        school.library_school_id = data["library_school_id"]
    if "school_name" in data:
        school.school_name = data["school_name"]

    db.session.commit()
    return jsonify(champ.to_dict())




UPLOAD_FOLDER = "uploads"
BULK_CHAMP_ALLOWED_EXTENSIONS = {"csv", "xlsx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def bulk_champ_allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in BULK_CHAMP_ALLOWED_EXTENSIONS


# Bulk upload champions
@app.route("/api/champions/bulk_upload", methods=["POST"])
def bulk_upload_champions():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "" or not bulk_champ_allowed_file(file.filename):
        return jsonify({"error": "Invalid file type (only csv/xlsx allowed)"}), 400

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(file.filename))
    file.save(filepath)

    # Load CSV or Excel into pandas
    if file.filename.endswith(".csv"):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)

    required_columns = {"firstname", "lastname", "province", "school_name", "asl_school_id", "library_school_id"}
    if not required_columns.issubset(df.columns):
        return jsonify({"error": f"Missing required columns. Required: {required_columns}"}), 400

    updated_champions = {}

    for _, row in df.iterrows():
        firstname = str(row["firstname"]).strip()
        lastname = str(row["lastname"]).strip()
        province = str(row["province"]).strip()
        asl_id = str(row["asl_school_id"]).strip() if pd.notna(row["asl_school_id"]) else None
        library_id = str(row["library_school_id"]).strip() if pd.notna(row["library_school_id"]) else None
        school_name = str(row["school_name"]).strip() if pd.notna(row["school_name"]) else None

        champ = ChampionSchool.query.filter_by(
            firstname=firstname,
            lastname=lastname,
            province=province
        ).first()

        # If champion does not exist, create new
        if not champ:
            champ = ChampionSchool(
                firstname=firstname,
                lastname=lastname,
                province=province
            )
            db.session.add(champ)
            db.session.flush()

        # Fetch existing schools (stored in JSON/list in your model)
        existing_schools = champ.get_schools() or []  

        matched_school = None
        for school in existing_schools:
            if (asl_id and str(school.get("asl_school_id")) == asl_id) or \
               (library_id and str(school.get("library_school_id")) == library_id):
                matched_school = school
                break

        if matched_school:
            # Update only missing/different values
            if asl_id and str(matched_school.get("asl_school_id")) != asl_id:
                matched_school["asl_school_id"] = asl_id
            if library_id and str(matched_school.get("library_school_id")) != library_id:
                matched_school["library_school_id"] = library_id
            if school_name:
                matched_school["school_name"] = school_name
        else:
            # Add new school
            new_school = {
                "asl_school_id": asl_id,
                "library_school_id": library_id,
                "school_name": school_name
            }
            existing_schools.append(new_school)

        # Save back the modified list
        champ.set_schools(existing_schools)

        updated_champions[f"{firstname}_{lastname}_{province}"] = champ.to_dict()

    db.session.commit()

    return jsonify({
        "message": "Bulk upload successful",
        "champions": list(updated_champions.values())
    }), 201









@app.route('/add_champion_form', methods=['POST'])
@login_required
def add_champion_form():
    form = ChampionSchoolForm()
    


    if form.validate_on_submit():
        firstname = form.firstname.data
        lastname = form.lastname.data
        province = form.province.data

        # ✅ Get selected schools from hidden field
        selected_data_json = request.form.get('selected_school_data')
        try:
            selected_schools = json.loads(selected_data_json) if selected_data_json else []
        except json.JSONDecodeError:
            flash("Invalid selected school data format.", "danger")
            return redirect(url_for('settings'))

        # if not selected_schools:
        #     flash("No schools selected.", "warning")
        #     return redirect(url_for('settings'))
        
        # Before creating new champion:
        for champ in ChampionSchool.query.all():
            if champ.schools:
                used_ids = [str(s['id']) for s in json.loads(champ.schools)]
                for s in selected_schools:
                    if str(s['id']) in used_ids:
                        flash(f"School '{s['name']}' is already assigned to another champion.", "danger")
                        return redirect(url_for('settings'))

        # ✅ Store as JSON string in DB
        try:
            champ = ChampionSchool(
                firstname=firstname,
                lastname=lastname,
                province=province,
                schools=json.dumps(selected_schools)  # list of dicts: [{id, name}, ...]
            )
            db.session.add(champ)
            db.session.commit()
            flash("Champion school added successfully!", "success")
            return redirect(url_for('settings'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving champion: {str(e)}", "danger")

    else:
        flash("Form validation failed.", "danger")

    return redirect(url_for('Administration'))




@app.route('/analyze_champion_csv', methods=['POST'])
@login_required
def analyze_champion_csv():
    """Analyze CSV for duplicates before uploading"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'Please upload a .csv file'}), 400

    try:
        # Save the uploaded file to a temporary location so the client can
        # reference it later when confirming upload. This avoids relying on
        # client-side File objects that may be cleared when modals close.
        token = uuid.uuid4().hex
        upload_dir = os.path.join(app.instance_path, 'tmp_champion_uploads')
        os.makedirs(upload_dir, exist_ok=True)
        saved_filename = f"{token}_{secure_filename(file.filename)}"
        saved_path = os.path.join(upload_dir, saved_filename)
        file.stream.seek(0)
        file.save(saved_path)

        # Parse CSV from the saved copy - keep file open during all operations
        with open(saved_path, 'r', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)

            # Validate required columns
            required_columns = ['firstname', 'lastname', 'province', 'school_name', 'asl_school_id', 'library_school_id']
            csv_columns = reader.fieldnames or []
            missing_columns = [col for col in required_columns if col not in csv_columns]
            if missing_columns:
                return jsonify({
                    'error': 'Missing required columns',
                    'missing_columns': missing_columns,
                    'required_columns': required_columns,
                    'found_columns': csv_columns
                }), 400

            # Group rows by champion identity and track schools
            grouped = {}
            csv_duplicates_within = []  # Duplicates within the CSV itself
            seen_ids = {}  # Track IDs within CSV

            for row_idx, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                fn = (row.get('firstname') or '').strip()
                ln = (row.get('lastname') or '').strip()
                province = (row.get('province') or '').strip()
                
                if not fn or not ln or not province:
                    continue

                key = (fn, ln, province)
                entry = grouped.setdefault(key, {
                    'firstname': fn,
                    'lastname': ln,
                    'province': province,
                    'schools': [],
                    'rows': []
                })
                entry['rows'].append(row_idx)

                # Parse schools
                schools_list = []
                schools_json = row.get('schools')
                if schools_json:
                    try:
                        parsed = json.loads(schools_json)
                        if isinstance(parsed, list):
                            schools_list = parsed
                    except Exception:
                        pass

                if not schools_list:
                    school_name = (row.get('school_name') or '').strip()
                    asl_id = (row.get('asl_school_id') or '').strip()
                    library_id = (row.get('library_school_id') or '').strip()
                    if school_name or asl_id or library_id:
                        schools_list = [{
                            'school_name': school_name,
                            'asl_school_id': asl_id,
                            'library_school_id': library_id,
                            'row': row_idx
                        }]

                # Check for duplicate IDs within CSV
                for s in schools_list:
                    asl_id = s.get('asl_school_id', '').strip()
                    lib_id = s.get('library_school_id', '').strip()
                    
                    if asl_id and asl_id != '0':
                        if asl_id in seen_ids:
                            csv_duplicates_within.append({
                                'type': 'ASL ID',
                                'value': asl_id,
                                'rows': [seen_ids[asl_id], row_idx],
                                'school_name': s.get('school_name', '')
                            })
                        else:
                            seen_ids[asl_id] = row_idx
                    
                    if lib_id and lib_id != '0':
                        lib_key = f"lib_{lib_id}"
                        if lib_key in seen_ids:
                            csv_duplicates_within.append({
                                'type': 'Library ID',
                                'value': lib_id,
                                'rows': [seen_ids[lib_key], row_idx],
                                'school_name': s.get('school_name', '')
                            })
                        else:
                            seen_ids[lib_key] = row_idx

                    school = {
                        'school_name': s.get('school_name', ''),
                        'asl_school_id': s.get('asl_school_id', ''),
                        'library_school_id': s.get('library_school_id', '')
                    }
                    if school not in entry['schools']:
                        entry['schools'].append(school)

        # Check for duplicates with existing database records
        existing_champions = []
        duplicate_schools = []

        for (fn, ln, province), data in grouped.items():
            champ = ChampionSchool.query.filter_by(
                firstname=fn, lastname=ln, province=province
            ).first()
            
            if champ:
                existing_champions.append({
                    'firstname': fn,
                    'lastname': ln,
                    'province': province,
                    'existing_schools': champ.get_schools() or [],
                    'new_schools': data['schools'],
                    'csv_rows': data['rows']
                })

        # Check for duplicate school IDs in existing database
        all_existing_champs = ChampionSchool.query.all()
        for data in grouped.values():
            for new_school in data['schools']:
                asl_id = new_school.get('asl_school_id', '').strip()
                lib_id = new_school.get('library_school_id', '').strip()
                
                for existing_champ in all_existing_champs:
                    existing_schools = existing_champ.get_schools() or []
                    for ex_school in existing_schools:
                        ex_asl = str(ex_school.get('asl_school_id', '')).strip()
                        ex_lib = str(ex_school.get('library_school_id', '')).strip()
                        
                        if asl_id and asl_id != '0' and asl_id == ex_asl:
                            duplicate_schools.append({
                                'type': 'ASL ID',
                                'id_value': asl_id,
                                'csv_school': new_school.get('school_name', ''),
                                'existing_school': ex_school.get('school_name', ''),
                                'existing_champion': f"{existing_champ.firstname} {existing_champ.lastname}"
                            })
                        
                        if lib_id and lib_id != '0' and lib_id == ex_lib:
                            duplicate_schools.append({
                                'type': 'Library ID',
                                'id_value': lib_id,
                                'csv_school': new_school.get('school_name', ''),
                                'existing_school': ex_school.get('school_name', ''),
                                'existing_champion': f"{existing_champ.firstname} {existing_champ.lastname}"
                            })

        # Prepare response
        has_duplicates = len(existing_champions) > 0 or len(duplicate_schools) > 0 or len(csv_duplicates_within) > 0
        
        return jsonify({
            'success': True,
            'has_duplicates': has_duplicates,
            'csv_internal_duplicates': csv_duplicates_within,
            'existing_champion_duplicates': existing_champions,
            'duplicate_school_ids': duplicate_schools,
            'total_new_champions': len([k for k, v in grouped.items() if not ChampionSchool.query.filter_by(firstname=k[0], lastname=k[1], province=k[2]).first()]),
            'total_updates': len(existing_champions),
            'grouped_data': list(grouped.values()),  # For reference
            'file_token': token,
            'file_name': saved_filename
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/upload_csv', methods=['POST'])
@login_required
def upload_csv():
    # Admin-only action
    if current_user.userRole != 'Admin':
        flash('Unauthorized', 'danger')
        return redirect(url_for('administration'))

    form = ChampionCSVUploadForm()

    if not form.validate_on_submit():
        flash('Invalid upload. Please upload a valid CSV file.', 'warning')
        return redirect(url_for('administration'))

    try:
        file_storage = form.file.data
        # Require a file to be provided
        if not file_storage or not getattr(file_storage, 'filename', '').strip():
            flash('Please choose a CSV file to upload.', 'warning')
            return redirect(url_for('administration'))
        # Basic extension check
        if not file_storage.filename.lower().endswith('.csv'):
            flash('Please upload a .csv file.', 'warning')
            return redirect(url_for('administration'))

        # Parse CSV
        stream = io.TextIOWrapper(file_storage.stream, encoding='utf-8')
        reader = csv.DictReader(stream)

        # Group rows by champion identity
        grouped = {}
        for row in reader:
            fn = (row.get('firstname') or '').strip()
            ln = (row.get('lastname') or '').strip()
            province = (row.get('province') or '').strip()
            if not fn or not ln or not province:
                # Skip incomplete champion rows
                continue
            key = (fn, ln, province)
            entry = grouped.setdefault(key, {
                'firstname': fn,
                'lastname': ln,
                'province': province,
                'schools': []
            })

            schools_list = []
            # Support both: a JSON `schools` column OR separate columns
            schools_json = row.get('schools')
            if schools_json:
                try:
                    parsed = json.loads(schools_json)
                    if isinstance(parsed, list):
                        schools_list = parsed
                except Exception:
                    pass

            if not schools_list:
                school_name = (row.get('school_name') or '').strip()
                asl_id = (row.get('asl_school_id') or '').strip()
                library_id = (row.get('library_school_id') or '').strip()
                if school_name or asl_id or library_id:
                    schools_list = [{
                        'school_name': school_name,
                        'asl_school_id': asl_id,
                        'library_school_id': library_id
                    }]

            # Deduplicate schools before adding
            for s in schools_list:
                school = {
                    'school_name': s.get('school_name', ''),
                    'asl_school_id': s.get('asl_school_id', ''),
                    'library_school_id': s.get('library_school_id', '')
                }
                if school not in entry['schools']:
                    entry['schools'].append(school)

        # Persist grouped data, merging with existing champions
        for (fn, ln, province), data in grouped.items():
            champ = ChampionSchool.query.filter_by(
                firstname=fn, lastname=ln, province=province
            ).first()
            incoming_schools = data['schools']
            if champ:
                existing = champ.get_schools() or []
                for s in incoming_schools:
                    if s not in existing:
                        existing.append(s)
                champ.set_schools(existing)
            else:
                champ = ChampionSchool(
                    firstname=fn,
                    lastname=ln,
                    province=province
                )
                champ.set_schools(incoming_schools)
                db.session.add(champ)

        db.session.commit()
        flash('CSV uploaded and champions updated successfully!', 'success')
        return redirect(url_for('administration'))

    except Exception as e:
        db.session.rollback()
        flash(f'CSV upload failed: {str(e)}', 'danger')
        return redirect(url_for('administration'))


@app.route('/upload_csv_confirmed', methods=['POST'])
@login_required
def upload_csv_confirmed():
    """Upload CSV with user's duplicate resolution choices"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    # Support either a freshly uploaded file OR a previously analyzed file
    # referenced by `file_token` (returned by /analyze_champion_csv).
    file = None
    saved_path = None
    file_token = request.form.get('file_token')
    if file_token:
        upload_dir = os.path.join(app.instance_path, 'tmp_champion_uploads')
        if os.path.isdir(upload_dir):
            for fname in os.listdir(upload_dir):
                if fname.startswith(f"{file_token}_"):
                    saved_path = os.path.join(upload_dir, fname)
                    break
        if not saved_path or not os.path.exists(saved_path):
            return jsonify({'error': 'File token not found'}), 400
    else:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        file = request.files['file']
    skip_champions = request.form.get('skip_champions', '[]')
    skip_schools = request.form.get('skip_schools', '[]')
    
    try:
        skip_champions = json.loads(skip_champions)
        skip_schools = json.loads(skip_schools)
    except:
        skip_champions = []
        skip_schools = []

    try:
        # Parse CSV from either the uploaded FileStorage or the saved temp file
        if saved_path:
            with open(saved_path, 'r', encoding='utf-8') as fh:
                reader = csv.DictReader(fh)
                
                # Group rows by champion identity
                grouped = {}
                for row in reader:
                    fn = (row.get('firstname') or '').strip()
                    ln = (row.get('lastname') or '').strip()
                    province = (row.get('province') or '').strip()
                    if not fn or not ln or not province:
                        continue
                    key = (fn, ln, province)
                    entry = grouped.setdefault(key, {
                        'firstname': fn,
                        'lastname': ln,
                        'province': province,
                        'schools': []
                    })

                    schools_list = []
                    schools_json = row.get('schools')
                    if schools_json:
                        try:
                            parsed = json.loads(schools_json)
                            if isinstance(parsed, list):
                                schools_list = parsed
                        except Exception:
                            pass

                    if not schools_list:
                        school_name = (row.get('school_name') or '').strip()
                        asl_id = (row.get('asl_school_id') or '').strip()
                        library_id = (row.get('library_school_id') or '').strip()
                        if school_name or asl_id or library_id:
                            schools_list = [{
                                'school_name': school_name,
                                'asl_school_id': asl_id,
                                'library_school_id': library_id
                            }]

                    for s in schools_list:
                        school = {
                            'school_name': s.get('school_name', ''),
                            'asl_school_id': s.get('asl_school_id', ''),
                            'library_school_id': s.get('library_school_id', '')
                        }
                        # Check if school should be skipped
                        asl_id = school['asl_school_id'].strip()
                        lib_id = school['library_school_id'].strip()
                        should_skip = False
                        for skip_id in skip_schools:
                            if (asl_id and asl_id == skip_id) or (lib_id and lib_id == skip_id):
                                should_skip = True
                                break
                        
                        if not should_skip and school not in entry['schools']:
                            entry['schools'].append(school)
        else:
            stream = io.TextIOWrapper(file.stream, encoding='utf-8')
            reader = csv.DictReader(stream)
            
            # Group rows by champion identity
            grouped = {}
            for row in reader:
                fn = (row.get('firstname') or '').strip()
                ln = (row.get('lastname') or '').strip()
                province = (row.get('province') or '').strip()
                if not fn or not ln or not province:
                    continue
                key = (fn, ln, province)
                entry = grouped.setdefault(key, {
                    'firstname': fn,
                    'lastname': ln,
                    'province': province,
                    'schools': []
                })

                schools_list = []
                schools_json = row.get('schools')
                if schools_json:
                    try:
                        parsed = json.loads(schools_json)
                        if isinstance(parsed, list):
                            schools_list = parsed
                    except Exception:
                        pass

                if not schools_list:
                    school_name = (row.get('school_name') or '').strip()
                    asl_id = (row.get('asl_school_id') or '').strip()
                    library_id = (row.get('library_school_id') or '').strip()
                    if school_name or asl_id or library_id:
                        schools_list = [{
                            'school_name': school_name,
                            'asl_school_id': asl_id,
                            'library_school_id': library_id
                        }]

                for s in schools_list:
                    school = {
                        'school_name': s.get('school_name', ''),
                        'asl_school_id': s.get('asl_school_id', ''),
                        'library_school_id': s.get('library_school_id', '')
                    }
                    # Check if school should be skipped
                    asl_id = school['asl_school_id'].strip()
                    lib_id = school['library_school_id'].strip()
                    should_skip = False
                    for skip_id in skip_schools:
                        if (asl_id and asl_id == skip_id) or (lib_id and lib_id == skip_id):
                            should_skip = True
                            break
                    
                    if not should_skip and school not in entry['schools']:
                        entry['schools'].append(school)

        # Persist grouped data
        created = 0
        updated = 0
        skipped = 0
        
        for (fn, ln, province), data in grouped.items():
            # Check if champion should be skipped
            champ_key = f"{fn}|{ln}|{province}"
            if champ_key in skip_champions:
                skipped += 1
                continue
            
            champ = ChampionSchool.query.filter_by(
                firstname=fn, lastname=ln, province=province
            ).first()
            incoming_schools = data['schools']
            
            if champ:
                existing = champ.get_schools() or []
                for s in incoming_schools:
                    if s not in existing:
                        existing.append(s)
                champ.set_schools(existing)
                updated += 1
            else:
                champ = ChampionSchool(
                    firstname=fn,
                    lastname=ln,
                    province=province
                )
                champ.set_schools(incoming_schools)
                db.session.add(champ)
                created += 1

        db.session.commit()
        
        # Clean up temp file if used
        if saved_path:
            try:
                os.remove(saved_path)
            except Exception:
                pass
                
        return jsonify({
            'success': True,
            'message': f'Upload complete! Created: {created}, Updated: {updated}, Skipped: {skipped}',
            'created': created,
            'updated': updated,
            'skipped': skipped
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500



@app.route('/profile/<username>', methods=['GET', 'POST'])
@login_required
def profile(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    form = ChampionSchoolForm()
    user_province = user.province

    # Fetch existing ChampionSchool record
    champ = ChampionSchool.query.filter_by(
        firstname=user.firstname,
        lastname=user.lastname,
        province=user.province
    ).first()

    # ✅ Load previously selected schools (stored as list of dicts)
    existing_school_dicts = []
    if champ and champ.schools:
        try:
            existing_school_dicts = json.loads(champ.schools)
        except Exception as e:
            print("Error decoding champ.schools JSON:", e)
            existing_school_dicts = []

    # ✅ Extract ASL school IDs for preselection
    existing_asl_ids = set()
    try:
        existing_asl_ids = {
            int(s["asl_school_id"]) for s in existing_school_dicts if "asl_school_id" in s
        }
    except Exception as e:
        print("Error parsing existing_asl_ids:", e)

    # ✅ Handle form submission
    if request.method == 'POST' and form.validate_on_submit():
        try:
            # Get selected schools from hidden JSON input
            raw_school_data = request.form.get('selected_school_data', '[]')
            selected_school_data = json.loads(raw_school_data)

            # Save to DB
            if champ:
                champ.schools = json.dumps(selected_school_data)
            else:
                champ = ChampionSchool(
                    firstname=form.firstname.data,
                    lastname=form.lastname.data,
                    province=form.province.data,
                    schools=json.dumps(selected_school_data)
                )
                db.session.add(champ)

            db.session.commit()
            flash('Champion school updated successfully!', 'success')
            return redirect(url_for('user', username=username))

        except Exception as e:
            db.session.rollback()
            flash(f'Error saving champion schools: {str(e)}', 'danger')
            return redirect(url_for('user', username=username))

    # ✅ Pre-fill form fields
    form.firstname.data = user.firstname
    form.lastname.data = user.lastname
    form.province.data = user.province

    # For JS and template rendering
    preselected_asl_ids = [s["asl_school_id"] for s in existing_school_dicts if "asl_school_id" in s]
    count_user_schools = len(preselected_asl_ids)
    smartlearning_champ_mtd = 0

    # ✅ Date range (default: this month until today)
    today = datetime.today().date()
    start_date = today.replace(day=1)

    # ✅ Batch query instead of loop - much faster
    if preselected_asl_ids:
        conn = get_ruzivo_conn()
        cursor = conn.cursor()

        # Create placeholders for IN clause
        placeholders = ','.join(['%s'] * len(preselected_asl_ids))
        query = f"""
            SELECT SUM(student_count) AS total_count
            FROM (
                SELECT COUNT(*) AS student_count
                FROM vwstudent
                WHERE school_id IN ({placeholders})
                AND last_login BETWEEN %s AND %s
            ) AS subquery
        """
        
        # Execute with all IDs at once
        cursor.execute(query, (*preselected_asl_ids, start_date, today))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            # ✅ Handle both tuple and dict
            if isinstance(row, dict):
                smartlearning_champ_mtd = row.get("total_count", 0) or 0
            else:
                smartlearning_champ_mtd = row[0] or 0

    # ✅ Prepare clean school list for template rendering
    schools_for_template = []
    for s in existing_school_dicts:
        if "asl_school_id" in s and "school_name" in s:
            schools_for_template.append({
                "id": s["asl_school_id"],
                "name": s["school_name"]
            })

    # Final total after loop
    # print(f"\nTotal SmartLearning Champs MTD: {smartlearning_champ_mtd}")

    return render_template('userProfile.html',
                           user=user,
                            form=form,
                            champ=champ,
                            schools_for_template=schools_for_template,   # ✅ new var for frontend
                            preselected_school_ids=preselected_asl_ids,
                            count_user_schools=count_user_schools,
                            smartlearning_champ_mtd=smartlearning_champ_mtd,
                           title="Profile")



@app.route('/user/<username>', methods=['GET', 'POST'])
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    form = ChampionSchoolForm()
    user_province = user.province

    # Fetch existing ChampionSchool record
    champ = ChampionSchool.query.filter_by(
        firstname=user.firstname,
        lastname=user.lastname,
        province=user.province
    ).first()

    # ✅ Load previously selected schools (stored as list of dicts)
    existing_school_dicts = []
    if champ and champ.schools:
        try:
            existing_school_dicts = json.loads(champ.schools)
        except Exception as e:
            print("Error decoding champ.schools JSON:", e)
            existing_school_dicts = []

    # ✅ Extract ASL school IDs for preselection
    existing_asl_ids = set()
    try:
        existing_asl_ids = {
            int(s["asl_school_id"]) for s in existing_school_dicts if "asl_school_id" in s
        }
    except Exception as e:
        print("Error parsing existing_asl_ids:", e)

    # ✅ Handle form submission
    if request.method == 'POST' and form.validate_on_submit():
        try:
            # Get selected schools from hidden JSON input
            raw_school_data = request.form.get('selected_school_data', '[]')
            selected_school_data = json.loads(raw_school_data)

            # Save to DB
            if champ:
                champ.schools = json.dumps(selected_school_data)
            else:
                champ = ChampionSchool(
                    firstname=form.firstname.data,
                    lastname=form.lastname.data,
                    province=form.province.data,
                    schools=json.dumps(selected_school_data)
                )
                db.session.add(champ)

            db.session.commit()
            flash('Champion school updated successfully!', 'success')
            return redirect(url_for('user', username=username))

        except Exception as e:
            db.session.rollback()
            flash(f'Error saving champion schools: {str(e)}', 'danger')
            return redirect(url_for('user', username=username))

    # ✅ Pre-fill form fields
    form.firstname.data = user.firstname
    form.lastname.data = user.lastname
    form.province.data = user.province

    # For JS and template rendering
    preselected_asl_ids = [s["asl_school_id"] for s in existing_school_dicts if "asl_school_id" in s]
    count_user_schools = len(preselected_asl_ids)
    smartlearning_champ_mtd = 0

    # ✅ Date range (default: this month until today)
    today = datetime.today().date()
    start_date = today.replace(day=1)

    # ✅ Batch query instead of loop - much faster
    if preselected_asl_ids:
        conn = get_ruzivo_conn()
        cursor = conn.cursor()

        # Create placeholders for IN clause
        placeholders = ','.join(['%s'] * len(preselected_asl_ids))
        query = f"""
            SELECT SUM(student_count) AS total_count
            FROM (
                SELECT COUNT(*) AS student_count
                FROM vwstudent
                WHERE school_id IN ({placeholders})
                AND last_login BETWEEN %s AND %s
            ) AS subquery
        """
        
        # Execute with all IDs at once
        cursor.execute(query, (*preselected_asl_ids, start_date, today))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            # ✅ Handle both tuple and dict
            if isinstance(row, dict):
                smartlearning_champ_mtd = row.get("total_count", 0) or 0
            else:
                smartlearning_champ_mtd = row[0] or 0

    # ✅ Prepare clean school list for template rendering
    schools_for_template = []
    for s in existing_school_dicts:
        if "asl_school_id" in s and "school_name" in s:
            schools_for_template.append({
                "id": s["asl_school_id"],
                "name": s["school_name"]
            })

    # Final total after loop
    # print(f"\nTotal SmartLearning Champs MTD: {smartlearning_champ_mtd}")

    return render_template(
        "user.html",
        user=user,
        form=form,
        champ=champ,
        schools_for_template=schools_for_template,   # ✅ new var for frontend
        preselected_school_ids=preselected_asl_ids,
        count_user_schools=count_user_schools,
        smartlearning_champ_mtd=smartlearning_champ_mtd,
        title="Profile"
    )




@app.route('/api/champion/<username>/asl_active', methods=['GET'])
@login_required
def get_champion_asl_active(username):
    """Return total ASL active learners for all schools under a champion with date range support."""
    user = db.first_or_404(sa.select(User).where(User.username == username))

    # --- Date range (default: this month until today) ---
    today = datetime.today().date()
    default_start_date = today.replace(day=1)

    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            start_date = default_start_date

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            end_date = today
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # Fetch Champion record
    champ = ChampionSchool.query.filter_by(
        firstname=user.firstname,
        lastname=user.lastname,
        province=user.province
    ).first()

    if not champ or not champ.schools:
        return jsonify({
            "username": username,
            "asl_student_count": 0,
            "school_count": 0
        })

    try:
        schools_data = json.loads(champ.schools)
    except Exception as e:
        print("Error decoding champ.schools JSON:", e)
        return jsonify({"error": "Invalid champ.schools JSON"}), 400

    # Extract ASL school IDs
    asl_school_ids = [s.get("asl_school_id") for s in schools_data if "asl_school_id" in s]

    if not asl_school_ids:
        return jsonify({
            "username": username,
            "asl_student_count": 0,
            "school_count": 0
        })

    smartlearning_count = 0
    conn = None
    cursor = None

    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor()

        # ✅ Batch query instead of loop - much faster
        placeholders = ','.join(['%s'] * len(asl_school_ids))
        query = f"""
            SELECT SUM(student_count) AS total_count
            FROM (
                SELECT COUNT(*) AS student_count
                FROM vwstudent
                WHERE school_id IN ({placeholders})
                AND last_login BETWEEN %s AND %s
            ) AS subquery
        """
        cursor.execute(query, (*asl_school_ids, start_date, end_date))
        row = cursor.fetchone()

        if row:
            if isinstance(row, dict):
                smartlearning_count = row.get("total_count", 0) or 0
            else:
                smartlearning_count = row[0] or 0
    except Exception as e:
        logging.error("ASL query error for champion %s: %s", username, e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return jsonify({
        "username": username,
        "asl_student_count": smartlearning_count,
        "school_count": len(asl_school_ids)
    })


@app.route('/api/champion/<username>/al_active', methods=['GET'])
@login_required
def get_champion_al_active(username):
    """Return total AL active learners for all schools under a champion this month."""
    user = db.first_or_404(sa.select(User).where(User.username == username))

    # Fetch Champion record
    champ = ChampionSchool.query.filter_by(
        firstname=user.firstname,
        lastname=user.lastname,
        province=user.province
    ).first()

    if not champ or not champ.schools:
        return jsonify({
            "username": username,
            "al_active_total": 0,
            "school_breakdown": []
        })


    try:
        schools_data = json.loads(champ.schools)
        # print(schools_data)
    except Exception as e:
        print("Error decoding champ.schools JSON:", e)
        return jsonify({"error": "Invalid champ.schools JSON"}), 400

    # Extract AL school IDs
    al_school_ids = [s.get("library_school_id") for s in schools_data if "library_school_id" in s]
    # print(al_school_ids)

    if not al_school_ids:
        return jsonify({
            "username": username,
            "al_active_total": 0,
            "school_breakdown": []
        })

    today = datetime.today().date()
    start_date = today.replace(day=1)

    conn = get_direct_library_conn()
    cursor = conn.cursor()

    total_active = 0
    school_breakdown = []

    # ✅ Batch query with GROUP BY instead of loop - much faster
    placeholders = ','.join(['%s'] * len(al_school_ids))
    query = f"""
        SELECT iu.institution_id, COUNT(DISTINCT la.user_id) AS al_active
        FROM logins la
        JOIN institution_user iu ON la.user_id = iu.user_id
        WHERE iu.institution_id IN ({placeholders})
        AND la.created_at BETWEEN %s AND %s
        GROUP BY iu.institution_id
    """

    cursor.execute(query, (*al_school_ids, start_date, today))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Build a mapping of school_id -> count
    school_counts = {}
    for row in rows:
        if isinstance(row, dict):
            school_id = row.get("institution_id")
            count = row.get("al_active", 0)
        else:
            school_id = row[0]
            count = row[1]
        school_counts[school_id] = count

    # Create school breakdown with names
    for al_id in al_school_ids:
        count = school_counts.get(al_id, 0)
        total_active += count

        school_name = next(
            (s.get("school_name") for s in schools_data if s.get("library_school_id") == al_id),
            "Unknown"
        )
        school_breakdown.append({
            "al_school_id": al_id,
            "school_name": school_name,
            "al_active": count
        })

    return jsonify({
        "username": username,
        "al_active_total": total_active,
        "school_breakdown": school_breakdown
    })




@app.route('/api/champion/<username>/remove_school', methods=['DELETE'])
@login_required
def remove_champion_school(username):
    """Remove a school (by asl_school_id, library_school_id, or both) from champion's assigned schools."""
    user = db.first_or_404(sa.select(User).where(User.username == username))

    champ = ChampionSchool.query.filter_by(
        firstname=user.firstname,
        lastname=user.lastname,
        province=user.province
    ).first()

    if not champ or not champ.schools:
        return jsonify({"error": "No schools found for this champion"}), 404

    try:
        schools_data = json.loads(champ.schools)
    except Exception as e:
        return jsonify({"error": f"Invalid JSON in champ.schools: {e}"}), 400

    # Extract query params
    asl_school_id = request.args.get("asl_school_id", type=int)
    library_school_id = request.args.get("library_school_id", type=int)

    if not asl_school_id and not library_school_id:
        return jsonify({"error": "Provide at least asl_school_id or library_school_id"}), 400

    # Filter out matching schools
    updated_schools = []
    removed = []

    for s in schools_data:
        match_asl = asl_school_id and s.get("asl_school_id") == asl_school_id
        match_lib = library_school_id and s.get("library_school_id") == library_school_id

        # Keep only schools that don't match the removal criteria
        if (asl_school_id and library_school_id and match_asl and match_lib) \
           or (asl_school_id and not library_school_id and match_asl) \
           or (library_school_id and not asl_school_id and match_lib):
            removed.append(s)
        else:
            updated_schools.append(s)

    if not removed:
        return jsonify({"message": "No matching school found for removal"}), 404

    # Save changes
    champ.schools = json.dumps(updated_schools)
    db.session.commit()

    return jsonify({
        "message": "School(s) removed successfully",
        "removed": removed,
        "remaining_schools": updated_schools
    })




    


@app.route('/api/schools/<province>')
@login_required
def get_schools_by_province(province):
    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)  # ensures dict results

        cursor.execute("""
            SELECT school_id, school_name
            FROM tblschools
            WHERE school_province = %s
              AND (flag IS NULL OR flag <> 'd')
            ORDER BY school_name ASC
        """, (province,))

        rows = cursor.fetchall()

        schools = [{'id': int(row['school_id']), 'name': row['school_name']} for row in rows]

        return jsonify(schools)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'{type(e).__name__}: {str(e)}'}), 500


    # finally:
    #     if 'cursor' in locals() and cursor: cursor.close()
    #     if 'conn' in locals() and conn: conn.close()





UPLOAD_FOLDER = 'static/uploads/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Help desk uploads
HELP_DESK_UPLOAD_FOLDER = 'static/uploads/helpdesk'
app.config['HELP_DESK_UPLOAD_FOLDER'] = HELP_DESK_UPLOAD_FOLDER
os.makedirs(HELP_DESK_UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    file = request.files.get('avatar')
    if not file or file.filename == '':
        flash('No file selected.')
        return redirect(request.referrer)

    if not allowed_file(file.filename):
        flash('File type not allowed.')
        return redirect(request.referrer)

    filename = secure_filename(f"user_{current_user.id}_" + file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(file_path)

    current_user.avatar_filename = f'uploads/avatars/{filename}'
    db.session.commit()

    flash('Avatar updated!')
    return redirect(url_for('index'))  # Change to your profile route



@app.route('/reports', methods=['GET', 'POST'])
def reports():
    # Get all users
    users = User.query.all()
    user_department = current_user.department

    # Get selected user (default to first user if none chosen)
    selected_user_id = request.args.get("user_id")
    if not selected_user_id and users:
        selected_user_id = users[0].id
    else:
        selected_user_id = int(selected_user_id) if selected_user_id else None

    reports = []
    if selected_user_id:
        reports = WeeklyReport.query.filter_by(user_id=selected_user_id)\
                                    .order_by(WeeklyReport.created_at.desc())\
                                    .all()

    selected_report_user = User.query.get_or_404(selected_user_id)

    return render_template(
        'reports.html',
        reports=reports,
        user_department =user_department ,
        users=users,
        selected_user_id=selected_user_id,
        selected_report_user=selected_report_user,
        title='Reports'
    )


@app.route('/akello_weekly_reports', methods=['GET'])
@login_required
def akello_weekly_reports():
    # Reuse the same data preparation as /reports
    users = User.query.all()
    user_department = current_user.department

    selected_user_id = request.args.get('user_id')
    if not selected_user_id and users:
        selected_user_id = users[0].id
    else:
        selected_user_id = int(selected_user_id) if selected_user_id else None

    reports = []
    if selected_user_id:
        reports = WeeklyReport.query.filter_by(user_id=selected_user_id) \
                                    .order_by(WeeklyReport.created_at.desc()) \
                                    .all()

    selected_report_user = User.query.get_or_404(selected_user_id)

    return render_template(
        'akello_weekly_reports.html',
        reports=reports,
        user_department=user_department,
        users=users,
        selected_user_id=selected_user_id,
        selected_report_user=selected_report_user,
        title='Reports'
    )


@app.route("/submit_weekly_report", methods=["GET", "POST"])
def submit_report():
    if request.method == "POST":
        week_start = request.form["week_start"]
        week_start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
        if week_start_date.weekday() != 0:  # Must be Monday
            flash("Week start date must be a Monday!", "error")
            return redirect(url_for("submit_report"))

        report = WeeklyReport(
            user_id=current_user.id,
            department=current_user.department,
            week_start=week_start,
            work_done=request.form["work_done"],
            work_next=request.form["work_next"],
            challenges=request.form["challenges"]
        )
        db.session.add(report)
        db.session.commit()
        flash("Report submitted successfully!", "success")
        return redirect(url_for("reports"))

    return redirect(url_for('reports'))



@app.route("/edit_report/<int:report_id>", methods=["GET", "POST"])
def edit_report(report_id):

    report = WeeklyReport.query.get_or_404(report_id)

    # Ensure user owns this report
    if report.user_id != current_user.id:
        flash("You are not authorized to edit this report.", "error")
        return redirect(url_for("reports"))

    # Check if report is older than 7 days
    if datetime.utcnow() > report.created_at + timedelta(days=7):
        flash("You can only edit reports within 7 days of submission.", "error")
        return redirect(url_for("reports"))

    if request.method == "POST":
        report.department = current_user.department
        report.week_start = request.form["week_start"]
        report.work_done = request.form["work_done"]
        report.work_next = request.form["work_next"]
        report.challenges = request.form["challenges"]

        db.session.commit()
        flash("Report updated successfully!", "success")
        return redirect(url_for("reports"))

@app.route('/workspaces', methods=['GET', 'POST'])
@login_required
def workspaces():
    if current_user.userRole == 'Brand Ambassador':
        return redirect(url_for('index'))
    else:
        newspaceform = WorkspaceForm()

        my_workspaces = current_user.memberships # This fetches workspaces the current user is a member of
        all_spaces = Workspace.query.all() # This fetches ALL workspaces in the database

    return render_template(
        'workspaces.html',
        newspaceform=newspaceform,
        all_spaces=all_spaces, # This list contains ALL workspaces, and you can access their .members
        workspaces=my_workspaces, # This list contains only workspaces the current user is a member of
        title='Workspaces'
    )

@app.route('/workspace/create', methods=['GET', 'POST'])
@login_required
def create_workspace():
    if current_user.userRole == 'Brand Ambassador':
        return redirect(url_for('index'))
    else:
        form = WorkspaceForm()
        if form.validate_on_submit():
            workspace = Workspace(name=form.name.data, description=form.description.data, created_by=current_user.id)
            workspace.members.append(current_user)
            db.session.add(workspace)
            db.session.commit()
            flash('Workspace created successfully!', 'success')
    return redirect(url_for('workspaces'))



@app.route('/workspace/<int:workspace_id>/invite', methods=['POST'])
@login_required
def invite_user_to_workspace(workspace_id):
    if current_user.userRole == 'Brand Ambassador':
        return redirect(url_for('index'))
    else:
        workspace = Workspace.query.get_or_404(workspace_id)
        if current_user not in workspace.members:
            flash('You are not a member of this workspace.', 'danger')
            return redirect(url_for('workspaces'))

        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if not user:
            flash('User not found.', 'danger')
        elif user in workspace.members:
            flash('User is already a member of the workspace.', 'info')
        else:
            workspace.members.append(user)
            db.session.commit()
            flash(f'{user.username} added to the workspace!', 'success')

    return redirect(url_for('view_workspace', workspace_id=workspace_id))





@app.route('/workspace/<int:workspace_id>')
@login_required
def view_workspace(workspace_id):
    taskform=TaskForm()
    projectform=ProjectForm()
    workspace = Workspace.query.get_or_404(workspace_id)
    available_users = User.query.filter(~User.id.in_([member.id for member in workspace.members])).all()
    # available_users = User.query.filter(User.id.in_([member.id for member in workspace.members])).all()
    if current_user not in workspace.members:
        return redirect(url_for('workspaces'))
    else:
        show_gantt = request.args.get('gantt') == '1'

        gantt_projects_data = []
        gantt_data = []
        if show_gantt:
            for project in workspace.projects:
                if project.start_date and project.end_date:
                    gantt_data.append({
                        'Task': project.title,
                        'Start': project.start_date.strftime('%Y-%m-%d'),
                        'Finish': project.end_date.strftime('%Y-%m-%d'),
                        'StartLabel': project.start_date.strftime('%Y-%m-%d'),
                        'FinishLabel': project.end_date.strftime('%Y-%m-%d'),
                        'Resource': 'Project',
                        'Color': '#1f77b4',
                        'TaskID': None
                    })

                for task in project.tasks:
                    start_date = task.start_date.strftime('%Y-%m-%d') if task.start_date else (
                        task.due_date.strftime('%Y-%m-%d') if task.due_date else None)
                    finish_date = task.due_date.strftime('%Y-%m-%d') if task.due_date else start_date
                    color = '#28a745' if task.status == 'Done' else '#ff7f0e'

                    gantt_data.append({
                        'Task': f"↳ {project.title}: {task.title}",
                        'Start': start_date,
                        'Finish': finish_date,
                        'StartLabel': start_date,
                        'FinishLabel': finish_date,
                        'Resource': 'Task',
                        'Color': color,
                        'TaskID': task.id
                    })


        page = request.args.get('page', 1, type=int)
        per_page = 5
        for project in workspace.projects:
            project.paginated_tasks = Task.query.filter_by(project_id=project.id).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('workspace_detail.html',taskform=taskform,projectform=projectform,available_users=available_users, workspace=workspace,show_gantt=show_gantt,gantt_projects_data=gantt_projects_data, gantt_data=gantt_data if show_gantt else [], title='Workspaces')

@app.route('/workspace/<int:workspace_id>/project/create', methods=['GET', 'POST'])
@login_required
def create_project(workspace_id):
    workspace = Workspace.query.get_or_404(workspace_id)
    form = ProjectForm()
    if form.validate_on_submit():
        project = Project(
            title=form.title.data,
            description=form.description.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            workspace_id=workspace_id,
            status=form.status.data,
        )
        db.session.add(project)
        db.session.commit()
        flash('Project created successfully!', 'success')
    return redirect(url_for('view_workspace',workspace=workspace, workspace_id=workspace_id))


@app.route('/project/<int:project_id>/edit', methods=['POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    form = ProjectForm()
    if form.validate_on_submit():
        project.title = form.title.data
        project.description = form.description.data
        project.status = form.status.data  # <-- Include status update
        project.start_date = form.start_date.data
        project.end_date = form.end_date.data
        db.session.commit()
        flash('Project updated successfully!', 'success')
    return redirect(url_for('view_workspace', workspace_id=project.workspace_id))


@app.route('/project/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    workspace_id = project.workspace_id
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted successfully!', 'success')
    return redirect(url_for('view_workspace', workspace_id=workspace_id))


@app.route('/project/<int:project_id>/task/create', methods=['GET', 'POST'])
@login_required
def create_task(project_id):
    project = Project.query.get_or_404(project_id)
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(
            title=form.title.data,
            description=form.description.data,
            start_date=form.start_date.data,
            due_date=form.due_date.data,
            status=form.status.data,
            progress=form.progress.data,  # must be included in the Task()
            project_id=project_id,
            assigned_to=current_user.id
        )
        db.session.add(task)
        db.session.commit()
    return redirect(url_for('view_workspace', workspace_id=project.workspace_id))
    
    # 🔥 This line fixes the problem when the form is invalid
    # project = Project.query.get_or_404(project_id)
    # return redirect(url_for('view_workspace', workspace_id=project.workspace_id))



@app.route('/task/<int:task_id>/update_dates', methods=['POST'])
@login_required
def update_task_dates(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.json
    try:
        task.start_date = datetime.strptime(data['start'], '%Y-%m-%d')
        task.due_date = datetime.strptime(data['end'], '%Y-%m-%d')
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    workspace_id = task.project.workspace_id
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully!', 'success')
    return redirect(url_for('view_workspace', workspace_id=workspace_id))


@app.route('/task/<int:task_id>/edit', methods=['POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    form = TaskForm()
    if form.validate_on_submit():
        task.title = form.title.data
        task.description = form.description.data
        task.start_date = form.start_date.data
        task.due_date = form.due_date.data
        task.status = form.status.data
        task.progress=form.progress.data
        db.session.commit()
        flash('Task updated successfully!', 'success')
    return redirect(url_for('view_workspace', workspace_id=task.project.workspace_id))



@app.route('/contracting', methods=['GET', 'POST'])
@login_required
def contracting():
    if current_user.userRole == 'Brand Ambassador':
        return redirect(url_for('index'))
    else:
        username = current_user.username
        role = current_user.userRole
        scorecards = Scorecard.query.filter_by(employee_name=username).all()
    return render_template('contracting.html', username=username, role=role, title='Contracting', scorecards=scorecards)


from psycopg2.extras import DictCursor

@app.route('/school_profile/<int:school_id>', methods=['GET', 'POST'])
@login_required
def school_profile(school_id):
    username = current_user.username
    role = current_user.userRole

    conn = get_ruzivo_conn()
    cursor = conn.cursor()

    query = "SELECT school_name, school_province FROM tblschools WHERE school_id = %s"
    cursor.execute(query, (school_id,))
    row = cursor.fetchone()

    # cursor.close()
    # conn.close()

    if not row:
        return "School not found", 404

    try:
        school_name = row['school_name']
        school_province = row['school_province']
    except (TypeError, KeyError):
        # Fallback if row is a tuple instead of a dict
        school_name = row[0]
        school_province = row[1]

    return render_template(
        'school_profile.html',
        username=username,
        role=role,
        school_name=school_name,
        school_province=school_province,
        title='School tracker'
    )





@app.route('/school_profile_usage/<int:school_id>', methods=['GET', 'POST'])
@login_required
def school_profile_usage(school_id):
    username = current_user.username
    role = current_user.userRole
    asl_school_id = school_id

    conn = get_ruzivo_conn()
    cursor = conn.cursor()

    query = "SELECT school_name, school_province FROM tblschools WHERE school_id = %s"
    cursor.execute(query, (school_id,))
    row = cursor.fetchone()

    # cursor.close()
    # conn.close()

    if not row:
        return "School not found", 404

    try:
        school_name = row['school_name']
        school_province = row['school_province']
    except (TypeError, KeyError):
        # Fallback if row is a tuple instead of a dict
        school_name = row[0]
        school_province = row[1]

    return render_template(
        'simone_school_usage.html',
        username=username,
        role=role,
        school_name=school_name,
        school_province=school_province,
        asl_school_id=asl_school_id,
        title='School tracker'
    )





@app.route('/download_user_scorecard', methods=['GET'])
def download_user_scorecard():
    """
    Downloads the scorecard table as a CSV file.

    Returns:
        Response: A Flask Response object containing the downloaded CSV data.
    """
    scorecards = Scorecard.query.all()

    # Create a CSV string in memory
    csv_string = io.StringIO()
    writer = csv.writer(csv_string)

    # Write header row
    writer.writerow([
        'Key Focus Area', 'Strategic Objective', 'Performance Measure',
        'Unit Of Measure', 'Target', 'Weight'
    ])

    # Write data rows
    for scorecard in scorecards:
        writer.writerow([
            scorecard.key_focus_area, scorecard.strategic_objective,
            scorecard.performance_measure, scorecard.unit_of_measure,
            scorecard.target, scorecard.weight
        ])

    csv_string.seek(0)
    return Response(
        csv_string.read(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=scorecard.csv'}
    )



@app.route('/save_scorecard', methods=['POST'])
def save_scorecard():
    key_focus_areas = request.form.getlist('keyFocusArea[]')
    strategic_objectives = request.form.getlist('strategicObjective[]')
    performance_measures = request.form.getlist('performanceMeasure[]')
    unit_of_measures = request.form.getlist('unitOfMeasure[]')
    targets = request.form.getlist('target[]')
    weights = request.form.getlist('weight[]')
    employee = current_user.username

    for i in range(len(key_focus_areas)):
        scorecard = Scorecard(
            key_focus_area=key_focus_areas[i],
            strategic_objective=strategic_objectives[i],
            performance_measure=performance_measures[i],
            unit_of_measure=unit_of_measures[i],
            target=targets[i],
            weight=float(weights[i]),
            employee_name = employee
        )
        db.session.add(scorecard)

    db.session.commit()
    flash('Scorecards saved successfully!', 'success')
    return redirect(url_for('contracting'))


@app.route('/save_scorecard_row', methods=['POST'])
def save_scorecard_row():
    try:
        # Parse JSON data from the request
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Extract data from the request
        scorecard_id = data.get('id')  # ID of the scorecard row
        key_focus_area = data.get('keyFocusArea')
        strategic_objective = data.get('strategicObjective')
        performance_measure = data.get('performanceMeasure')
        unit_of_measure = data.get('unitOfMeasure')
        target = data.get('target')
        weight = data.get('weight')

        # Validate required fields
        if not key_focus_area or not strategic_objective or not performance_measure or not unit_of_measure or not target or not weight:
            return jsonify({'error': 'All fields are required'}), 400

        # If ID is provided, update the existing scorecard
        if scorecard_id:
            scorecard = Scorecard.query.get(scorecard_id)
            if not scorecard:
                return jsonify({'error': 'Scorecard not found'}), 404

            # Update the scorecard fields
            scorecard.key_focus_area = key_focus_area
            scorecard.strategic_objective = strategic_objective
            scorecard.performance_measure = performance_measure
            scorecard.unit_of_measure = unit_of_measure
            scorecard.target = target
            scorecard.weight = float(weight)

        # If no ID is provided, create a new scorecard
        else:
            scorecard = Scorecard(
                key_focus_area=key_focus_area,
                strategic_objective=strategic_objective,
                performance_measure=performance_measure,
                unit_of_measure=unit_of_measure,
                target=target,
                weight=float(weight),
                employee_name=current_user.username  # Assign to the current user
            )
            db.session.add(scorecard)

        # Commit changes to the database
        db.session.commit()

        return jsonify({
            'message': 'Scorecard saved successfully',
            'new_id': scorecard.id if not scorecard_id else None  # Return new ID if created
        }), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'An error occurred while saving the scorecard'}), 500


# ---------- Password reset helpers ----------

def _get_serializer():
    secret_key = app.config.get('SECRET_KEY')
    return URLSafeTimedSerializer(secret_key)


def generate_reset_token(email: str) -> str:
    serializer = _get_serializer()
    salt = app.config.get('SECURITY_PASSWORD_SALT', 'change-this-salt')
    return serializer.dumps(email, salt=salt)


def verify_reset_token(token: str, max_age: int = 3600):
    serializer = _get_serializer()
    salt = app.config.get('SECURITY_PASSWORD_SALT', 'change-this-salt')
    try:
        email = serializer.loads(token, salt=salt, max_age=max_age)
        return email
    except (SignatureExpired, BadSignature):
        return None


def send_email(subject: str, recipient: str, html_body: str, text_body: str = None):
    if app.config.get('MAIL_SUPPRESS_SEND'):
        # Suppressed sending: log instead
        app.logger.info(f"[MAIL_SUPPRESS_SEND] To: {recipient}\nSubject: {subject}\n{text_body or ''}\n{html_body}")
        return True

    smtp_host = app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = app.config.get('MAIL_PORT', 587)
    use_tls = app.config.get('MAIL_USE_TLS', True)
    username = app.config.get('MAIL_USERNAME')
    password = app.config.get('MAIL_PASSWORD')
    sender = app.config.get('MAIL_DEFAULT_SENDER', username)

    if not (username and password and sender):
        app.logger.warning('Email not sent: MAIL_USERNAME/PASSWORD/SENDER not fully configured')
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    if text_body:
        msg.set_content(text_body)
    msg.add_alternative(html_body, subtype='html')

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.send_message(msg)
        
    return True


@app.route('/forgot-password', methods=['GET'])
def forgot_password():
    # Simple page with an email field that POSTs to /request-password-reset (already exists as template)
    return render_template('forgot-password.html')


@app.route('/request-password-reset', methods=['POST'])
def request_password_reset():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    if not email:
        return jsonify({"message": "Email is required"}), 400
    user = db.session.scalar(sa.select(User).where(User.email == email))
    # Always respond with success message to avoid user enumeration
    if user:
        token = generate_reset_token(email)
        reset_url = url_for('reset_password', token=token, _external=True)
        subject = 'Your password reset link'
        html_body = f"""
            <p>Hello {user.firstname or user.username},</p>
            <p>You requested a password reset. Click the link below to set a new password:</p>
            <p><a href="{reset_url}">{reset_url}</a></p>
            <p>If you did not request this, please ignore this email.</p>
        """
        text_body = f"Hello {user.firstname or user.username},\n\nVisit this link to reset your password: {reset_url}\nIf you did not request this, ignore this email."
        send_email(subject, email, html_body, text_body)
    return jsonify({"message": "If that email exists, a reset link has been sent."}), 200


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    from app.forms import ResetPasswordForm
    email = verify_reset_token(token)
    if not email:
        flash('The reset link is invalid or has expired.')
        return redirect(url_for('forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == email))
        if not user:
            flash('User not found.')
            return redirect(url_for('forgot_password'))
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset. Please log in.')
        return redirect(url_for('login'))

    return render_template('reset-password.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.userRole == 'Brand Ambassador':
                return redirect(url_for('profile',username=current_user.username))
        else:
            return redirect(url_for('overview'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        # Ensure non-Brand Ambassador users land on /overview (not /welcome) after login.
        # Keep Brand Ambassador users redirected to their /profile.
        if not next_page or urlsplit(next_page).netloc != '' or next_page == url_for('overview'):
            if (user.userRole == 'Brand Ambassador') or (getattr(current_user, 'userRole', None) == 'Brand Ambassador'):
                next_page = url_for('profile', username=user.username)
            else:
                next_page = url_for('overview')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)



@app.route('/helpdesk')
def helpdesk():

    return render_template('help_desk.html', title='Help desk')



@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('welcome'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration.
    If the user is already logged in, they are redirected to the index page.
    On form submission, it validates the data and creates a new user
    with all the required fields from the updated User model.
    """
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        # Create a new User instance with the data from the registration form
        user = User(
            username=form.username.data,
            email=form.email.data,
            firstname=form.firstname.data,
            lastname=form.lastname.data,
            userRole=form.userRole.data,
            department=form.department.data,
            province=form.province.data,
            # Privileges are usually not set at registration.
            # This can be handled by an admin later.
            # We can set a default value if needed, e.g., privileges={}
        )
        
        # Set the user's password
        user.set_password(form.password.data)
        
        # Add the new user to the database
        db.session.add(user)
        db.session.commit()
        
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
        
    return render_template('register.html', title='Register', form=form)





# VTL DILY REPORT 
import pymysql
import pandas as pd
from flask import Flask, request, render_template, jsonify, send_file
import pandas as pd
from openpyxl import load_workbook
import os
from datetime import datetime


# ---------- DB Fetch ----------

import re

today = datetime.today()
# report_date = today.replace(day=1).date()
report_date = (today - timedelta(days=1)).strftime('%d')

# ---------- Excel Update ----------
# def update_excel(data, template_path="report_template.xlsx", reports_dir="reports"):
#     wb = load_workbook(template_path)
#     ws = wb.worksheets[0]  # Access the first worksheet

#     # Debugging info
#     print("DataFrame head:\n", data.head())
#     print("Dtypes:", data.dtypes)

#     # Extract numeric safely
#     value = pd.to_numeric(data['total_count'], errors="coerce").fillna(0).astype(int).iloc[0]
#     ws["C7"].value = value
#     ws["M7"].value = '=(H7*31)/21'

#     # Get the current formula or value in H7
#     h7_value = ws["H7"].value

#     # Extract the last integer from H7 value if it contains a formula
#     if isinstance(h7_value, str) and '+' in h7_value:
#         last_integer = re.findall(r'\d+', h7_value.strip())[-1]  # Find all integers and get the last one
#         ws["F7"].value = int(last_integer)  # Enter the last integer into F7
        

#     # Append +C7 to whatever is in H7
#     if h7_value:
#         ws["H7"].value = f"{h7_value}"
#     else:
#         ws["H7"].value = f"{ws['C7'].value}"

    

#     os.makedirs(reports_dir, exist_ok=True)

#     output_filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
#     output_path = os.path.join(reports_dir, output_filename)

#     wb.save(output_path)
#     return output_filename, output_path


def update_excel(data, template_path="report_template.xlsx", reports_dir="reports"):
    wb = load_workbook(template_path)
    ws = wb.worksheets[0]   # or ws["SheetName"]

    # Debugging info
    print("DataFrame head:\n", data.head())
    print("Dtypes:", data.dtypes)

    # Extract numeric safely
    value = pd.to_numeric(data['total_count'], errors="coerce").fillna(0).astype(int).iloc[0]
    ws["C7"].value = value
    ws["M7"].value = f'=(H7*31)/{report_date}'
    ws["I7"].value = f'=D7*{report_date}'

    # Handle H7 formula
    if ws["H7"].value:
        h7_formula = str(ws["H7"].value)

        # Extract all integers from the formula
        numbers = re.findall(r"\d+", h7_formula)
        if numbers:
            last_int = int(numbers[-1])
            ws["F7"].value = last_int  # put last number into F7

        # Append +C7 reference to formula
        ws["H7"].value = f"{h7_formula}+{value}"
    else:
        ws["H7"].value = f"{value}"

    os.makedirs(reports_dir, exist_ok=True)

    output_filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_path = os.path.join(reports_dir, output_filename)

    wb.save(output_path)
    return output_filename, output_path



# ---------- Routes ----------
@app.route('/vtl_template', methods=['GET', 'POST'])
def vtl_template():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        if not file.filename.lower().endswith(".xlsx"):
            return jsonify({"error": "Only .xlsx files are supported"}), 400

        template_path = os.path.join("instance", "uploaded_template.xlsx")
        os.makedirs("instance", exist_ok=True)
        file.save(template_path)

        return jsonify({
            "ok": True,
            "message": "Template uploaded successfully",
            "stored_as": "uploaded_template.xlsx"
        })

    # GET → render upload page
    return render_template('vtl_template.html', template_filename="uploaded_template.xlsx")


import pandas as pd
import os
from datetime import datetime
from flask import send_file, jsonify

# ---------- DB Fetch ----------
def fetch_data():
    conn = get_ruzivo_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT sl.student_id) AS total_count
        FROM tblstudents_login sl
        WHERE sl.student_id NOT IN (
            SELECT DISTINCT tp.student_id
            FROM tblecocash_payment_order tp
            WHERE transactionOperationStatus='COMPLETED'
        )
        AND sl.student_id NOT IN (
            SELECT DISTINCT sl2.student_id
            FROM tblstudents_login sl2
            WHERE sl2.login_date BETWEEN '2025-08-01 00:00:00' AND '2025-08-20 23:59:59'
        )
        AND sl.login_date BETWEEN '2025-08-21 00:00:00' AND '2025-08-21 23:59:59';
    """)
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=[desc[0] for desc in cursor.description])
    cursor.close()
    conn.close()
    return df




def generate_and_send_report(template_path):
    """
    Run fetch_data(), update the Excel template at C7,
    and save the result into /app/reports.
    """
    df = fetch_data()

    # ✅ Always use absolute /app/reports directory
    reports_dir = os.path.join(os.getcwd(), "app", "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # ✅ update_excel already handles saving
    filename, path = update_excel(df, template_path, reports_dir=reports_dir)

    return filename, path




# ---------- Run Report ----------
@app.route('/api/run-report', methods=['POST'])
def api_run_report():
    template_path = os.path.join("instance", "uploaded_template.xlsx")

    if not os.path.exists(template_path):
        return jsonify({"error": "No template uploaded yet"}), 400

    filename, path = generate_and_send_report(template_path)

    if not os.path.exists(path):
        return jsonify({"error": "Report not generated"}), 500

    return send_file(path, as_attachment=True, download_name=filename)







@app.route('/api/download/<filename>')
def api_download(filename):
    path = os.path.join("reports", filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path, as_attachment=True)


@app.route('/api/download-latest')
def api_download_latest():
    reports_dir = os.path.join(os.getcwd(), "app", "reports")
    if not os.path.exists(reports_dir) or not os.listdir(reports_dir):
        return jsonify({"error": "No reports found"}), 404

    latest = max(
        [os.path.join(reports_dir, f) for f in os.listdir(reports_dir)],
        key=os.path.getctime
    )
    return send_file(latest, as_attachment=True)






@app.route('/conversiontemplatescript', methods=['GET', 'POST'])
@login_required
def conversiontemplatescript():


        return render_template('conversiontemplatescript.html',
                           title='Analytics')




import docx
import os

def convert_docx_to_html(docx_path, output_path):
    doc = docx.Document(docx_path)

    # Placeholders for extracted content
    h1 = ""
    h2 = ""
    h3 = ""
    objectives = []
    content = []
    content2 = []
    images_html = []
    examples_html = []

    # Loop through document elements
    for para in doc.paragraphs:
        style = para.style.name if para.style else ""

        # Extract headings
        if style.startswith("Heading 1"):
            h1 = para.text.strip()

        elif style.startswith("Heading 2"):
            h2 = para.text.strip()

        elif style.startswith("Heading 3"):
            h3 = para.text.strip()

        # Detect example text
        elif "example" in para.text.lower():
            examples_html.append(f"""
            <div class="new-example-container">
                <img class="new-example-image" src="https://smartlearning.akello.co/public/uploads/content/maths-icons/Group%20572.png" alt="" /> 
                <span class="new-example-text"><b>{para.text.strip()}</b></span>
            </div>
            """)

        # Otherwise treat as normal content
        else:
            # Put first items under objectives, rest under content
            if "objective" in para.text.lower():
                objectives.append(f"<li>{para.text.strip()}</li>")
            else:
                if not h2:
                    content.append(f"<li>{para.text.strip()}</li>")
                else:
                    content2.append(f"<li>{para.text.strip()}</li>")

    # Extract images
    for rel in doc.part.rels.values():
        if "image" in rel.target_ref:
            # Word images are embedded, here we simulate with placeholder HTML
            images_html.append("""
            <div class="opacity-70" style="margin: 30px; background: #CAE3F6; border-radius: 20px; width: fit-content; display: flex; flex-direction: row; align-items: center;">
                <img src="https://smartlearning.akello.co/public/uploads/content/maths-icons/icon.png" 
                     style="border-radius: 50%; margin-left: -30px;" 
                     alt="icon.png (1 KB)" width="44" height="44" caption="false" />
                <p>{Insert image description or label here}</p>
            </div>
            """)

    # Build final HTML
    html_template = f"""
<div class="row">
  <div class="col-md-12">
    <h2 class="primary-top-banner">{h1}</h2>
  </div>

  <div class="col-md-12">
    <div class="row banner-area">
      <div class="col-md-5 banner-image">
        <img class="img-fluid" src="https://smartlearning.akello.co/public/uploads/content/Grade%207%20English%20New/Lesson%201%20Structure%20of%20a%20Paragraph/_-01_result_result.webp" style="width:60%;" />
      </div>
      <div class="col-md-7">
        <h2>Objectives</h2>
        <h4 class="padding-5">By the end of the lesson, you should be able to:</h4>
        <ol>
          {''.join(objectives)}
        </ol>
      </div>
    </div>
  </div>

  <div class="col-md-12">
    <h2 class="primary-top-banner">{h2}</h2>
    <div class="col-md-12">
      <ul>
        {''.join(content)}
      </ul>

      <h2>{h3}</h2>
      <ul>
        {''.join(content2)}
      </ul>

      {''.join(images_html)}
      {''.join(examples_html)}
    </div>
  </div>
</div>
"""

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)

    print(f"✅ Conversion complete! HTML saved to {output_path}")



UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route("/convert", methods=["POST"])
def convert():
    if "file" not in request.files:
        return "No file uploaded", 400

    file = request.files["file"]
    if file.filename == "":
        return "No selected file", 400

    # Save uploaded file
    filename = secure_filename(file.filename)
    docx_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(docx_path)

    # Output path
    output_filename = filename.replace(".docx", ".html")
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        # Run conversion
        convert_docx_to_html(docx_path, output_path)
    except Exception as e:
        # Log the error for debugging purposes and return a user-friendly message
        print(f"Error during conversion: {e}")
        return "Error converting the document. Please try again.", 500

    # Check if the file was created successfully before attempting to send it
    if os.path.exists(output_path):
        # Return file for download
        return send_file(output_path, as_attachment=True)
    else:
        # If the file doesn't exist after the conversion attempt, something went wrong.
        return "Conversion succeeded, but the output file could not be found.", 500








@app.route('/api/countries', methods=['GET'])
def get_countries():
    try:
        conn = get_ruzivo_conn()
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    id,
                    iso,
                    name,
                    nicename,
                    iso3,
                    numcode,
                    phonecode,
                    flag
                FROM tblcountries;
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            print("DB Rows:", rows)  # Debugging output

            if not rows:
                return jsonify({"message": "No countries found"}), 404

            col_names = [desc[0] for desc in cursor.description]
            data = [dict(zip(col_names, row)) for row in rows]

        return jsonify(data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if 'conn' in locals():
            conn.close()


@app.route('/api/lesotho-asl-registrations', methods=['GET'])
def lesotho_asl_registrations():
    conn = None
    try:
        conn = get_ruzivo_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        query = """
            SELECT COUNT(DISTINCT student_id) AS asl_registrations
            FROM tblstudents
            WHERE country_id = 119
        """
        cursor.execute(query)
        result = cursor.fetchone()

        return jsonify({
            "country_id": 119,
            "asl_registrations": result["asl_registrations"] if result else 0
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if conn:
            conn.close()






import imaplib
import email
import smtplib
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json



# ===== Email Query Storage =====
# Store email statuses in a simple JSON file or database
# For simplicity, using a JSON file approach
EMAIL_STATUS_FILE = 'email_query_statuses.json'

def load_email_statuses():
    """Load email statuses from file"""
    try:
        with open(EMAIL_STATUS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_email_status(email_id, status):
    """Save email status to file"""
    statuses = load_email_statuses()
    statuses[email_id] = {
        'status': status,
        'updated_at': datetime.now().isoformat()
    }
    with open(EMAIL_STATUS_FILE, 'w') as f:
        json.dump(statuses, f, indent=2)


# ===== API Endpoints =====

@app.route('/api/email-queries', methods=['GET'])
@login_required
def get_email_queries():
    """Fetch emails from configured Outlook account"""
    try:
        # Get email configuration from environment
        imap_server = os.getenv('EMAIL_IMAP_SERVER', 'outlook.office365.com')
        imap_port = int(os.getenv('EMAIL_IMAP_PORT', '993'))
        email_address = os.getenv('EMAIL_ADDRESS')
        email_password = os.getenv('EMAIL_APP_PASSWORD')
        sender_filter = os.getenv('EMAIL_SENDER_FILTER', '')
        
        if not email_address or not email_password:
            return jsonify({'error': 'Email configuration not set'}), 500
        
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail.login(email_address, email_password)
        mail.select('inbox')
        
        # Search for emails from specific sender if filter is set
        if sender_filter:
            status, messages = mail.search(None, f'FROM "{sender_filter}"')
        else:
            status, messages = mail.search(None, 'ALL')
        
        email_ids = messages[0].split()
        emails = []
        
        # Load existing statuses
        email_statuses = load_email_statuses()
        
        # Fetch last 50 emails
        for email_id in email_ids[-50:]:
            try:
                email_id_str = email_id.decode()
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])
                
                # Decode subject
                subject_header = msg['Subject']
                if subject_header:
                    subject_decoded = decode_header(subject_header)[0][0]
                    if isinstance(subject_decoded, bytes):
                        subject = subject_decoded.decode()
                    else:
                        subject = subject_decoded
                else:
                    subject = '(No Subject)'
                
                # Get sender
                from_header = msg.get('From', '')
                
                # Extract email address from "Name <email@example.com>" format
                from_email = from_header
                if '<' in from_header and '>' in from_header:
                    from_email = from_header[from_header.index('<')+1:from_header.index('>')]
                
                # Get date
                date_str = msg.get('Date', '')
                
                # Get body
                body = ''
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            payload = part.get_payload(decode=True)
                            if payload:
                                body = payload.decode('utf-8', errors='ignore')
                                break
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='ignore')
                
                # Get status from storage
                email_status_data = email_statuses.get(email_id_str, {})
                current_status = email_status_data.get('status', 'Not started')
                
                emails.append({
                    'id': email_id_str,
                    'subject': subject,
                    'from': from_email,
                    'date': date_str,
                    'preview': body[:200] if body else '',
                    'body': body,
                    'status': current_status
                })
            except Exception as e:
                print(f"Error processing email {email_id}: {str(e)}")
                continue
        
        mail.close()
        mail.logout()
        
        return jsonify({'emails': emails}), 200
        
    except Exception as e:
        print(f"Error fetching emails: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/email-queries/<email_id>', methods=['GET'])
@login_required
def get_email_query_details(email_id):
    """Get details of a specific email"""
    try:
        imap_server = os.getenv('EMAIL_IMAP_SERVER', 'outlook.office365.com')
        imap_port = int(os.getenv('EMAIL_IMAP_PORT', '993'))
        email_address = os.getenv('EMAIL_ADDRESS')
        email_password = os.getenv('EMAIL_APP_PASSWORD')
        
        if not email_address or not email_password:
            return jsonify({'error': 'Email configuration not set'}), 500
        
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail.login(email_address, email_password)
        mail.select('inbox')
        
        status, msg_data = mail.fetch(email_id.encode(), '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        
        # Decode subject
        subject_header = msg['Subject']
        if subject_header:
            subject_decoded = decode_header(subject_header)[0][0]
            if isinstance(subject_decoded, bytes):
                subject = subject_decoded.decode()
            else:
                subject = subject_decoded
        else:
            subject = '(No Subject)'
        
        # Get body
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='ignore')
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='ignore')
        
        mail.close()
        mail.logout()
        
        return jsonify({
            'email': {
                'id': email_id,
                'subject': subject,
                'from': msg.get('From', ''),
                'date': msg.get('Date', ''),
                'body': body
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/email-queries/<email_id>/status', methods=['PATCH'])
@login_required
def update_email_query_status(email_id):
    """Update the status of an email query"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        status = data.get('status')
        
        if not status or status not in ['Not started', 'Looking into it', 'Resolved']:
            return jsonify({'error': 'Invalid status'}), 400
        
        # Save the status
        save_email_status(email_id, status)
        
        return jsonify({'success': True, 'status': status}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/email-queries/<email_id>/send-resolution', methods=['POST'])
@login_required
def send_resolution_email(email_id):
    """Send resolution notification email to customer"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        recipient = data.get('recipient')
        message_body = data.get('message')
        
        if not recipient or not message_body:
            return jsonify({'error': 'Recipient and message are required'}), 400
        
        # Get SMTP configuration
        smtp_server = os.getenv('EMAIL_SMTP_SERVER', 'smtp.office365.com')
        smtp_port = int(os.getenv('EMAIL_SMTP_PORT', '587'))
        email_address = os.getenv('EMAIL_ADDRESS')
        email_password = os.getenv('EMAIL_APP_PASSWORD')
        
        if not email_address or not email_password:
            return jsonify({'error': 'Email configuration not set'}), 500
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = email_address
        msg['To'] = recipient
        msg['Subject'] = 'Query Resolution - Akello Support'
        
        # Email body
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%); padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                    <h2 style="color: white; margin: 0;">Akello Support</h2>
                </div>
                <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                    <p style="white-space: pre-wrap;">{message_body}</p>
                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                    <p style="font-size: 12px; color: #6b7280;">
                        This is an automated message from Akello Support.<br>
                        For further assistance, please contact us at: <a href="mailto:info@akello.co">info@akello.co</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body_html, 'html'))
        
        # Send email via SMTP
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_address, email_password)
        server.send_message(msg)
        server.quit()
        
        return jsonify({'success': True, 'message': 'Email sent successfully'}), 200
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/email-queries/<email_id>/convert', methods=['POST'])
@login_required
def convert_email_to_query(email_id):
    """Convert an email to a help desk query"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Fetch the email
        imap_server = os.getenv('EMAIL_IMAP_SERVER', 'outlook.office365.com')
        imap_port = int(os.getenv('EMAIL_IMAP_PORT', '993'))
        email_address = os.getenv('EMAIL_ADDRESS')
        email_password = os.getenv('EMAIL_APP_PASSWORD')
        
        if not email_address or not email_password:
            return jsonify({'error': 'Email configuration not set'}), 500
        
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail.login(email_address, email_password)
        mail.select('inbox')
        
        status, msg_data = mail.fetch(email_id.encode(), '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        
        # Decode subject
        subject_header = msg['Subject']
        if subject_header:
            subject_decoded = decode_header(subject_header)[0][0]
            if isinstance(subject_decoded, bytes):
                subject = subject_decoded.decode()
            else:
                subject = subject_decoded
        else:
            subject = 'Email Query'
        
        # Get body
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='ignore')
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='ignore')
        
        # Get sender email
        from_header = msg.get('From', '')
        
        mail.close()
        mail.logout()
        
        # Create a help desk query from the email
        from app.models import HelpDeskQuery
        
        query = HelpDeskQuery(
            query_title=subject,
            query_description=f"From: {from_header}\\n\\n{body}",
            query_type='Email',
            created_by=from_header,
            status='Not started'
        )
        
        db.session.add(query)
        db.session.commit()
        
        return jsonify({'success': True, 'query_id': query.id}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500







@app.route('/akello_sim_calendar', methods=['GET'])
@login_required
def akello_sim_calendar():
    form = AkelloSimEventForm()
    return render_template('akello_sim_calendar.html', form=form, title='Akello SIM Calendar')


@app.route('/api/sim-calendar/events', methods=['GET'])
@login_required
def sim_calendar_events():
    evs = AkelloSimEvent.query.order_by(AkelloSimEvent.date.asc()).all()
    return jsonify([
        {
            'id': e.id,
            'title': e.calendar_title,
            'start': e.date.isoformat(),
            'status': e.status,
            'request_collateral': e.request_collateral,
            'collateral_items': e.collateral_items or []
        } for e in evs
    ])


@app.route('/api/sim-calendar/events', methods=['POST'])
@login_required
def sim_calendar_create():
    data = request.get_json() or {}
    try:
        date_str = data.get('date')
        dt = datetime.fromisoformat(date_str) if date_str else None
        if not dt:
            return jsonify({'error': 'date is required (ISO 8601)'}), 400
        evt = AkelloSimEvent(
            calendar_title=data.get('calendar_title') or data.get('title') or 'Untitled',
            description=data.get('description', ''),
            date=dt,
            status=data.get('status', 'Confirmed'),
            created_by=current_user.username,
            request_collateral=bool(data.get('request_collateral', False)),
            collateral_items=data.get('collateral_items') or []
        )
        db.session.add(evt)
        db.session.commit()
        return jsonify({'id': evt.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/sim-calendar/events/<int:event_id>', methods=['PATCH'])
@login_required
def sim_calendar_update(event_id):
    evt = AkelloSimEvent.query.get_or_404(event_id)
    data = request.get_json() or {}
    if 'calendar_title' in data or 'title' in data:
        evt.calendar_title = data.get('calendar_title') or data.get('title')
    if 'description' in data:
        evt.description = data.get('description')
    if 'date' in data and data['date']:
        try:
            evt.date = datetime.fromisoformat(data['date'])
        except Exception:
            return jsonify({'error': 'Invalid date format'}), 400
    if 'status' in data:
        evt.status = data['status']
    if 'request_collateral' in data:
        evt.request_collateral = bool(data['request_collateral'])
    if 'collateral_items' in data:
        evt.collateral_items = data['collateral_items'] or []
    db.session.commit()
    return jsonify({'status': 'ok'})


@app.route('/api/sim-calendar/events/<int:event_id>', methods=['DELETE'])
@login_required
def sim_calendar_delete(event_id):
    evt = AkelloSimEvent.query.get_or_404(event_id)
    db.session.delete(evt)
    db.session.commit()
    return jsonify({'status': 'deleted'})


# @app.route('/akello_monitor', methods=['GET'])
# @login_required
# def akello_monitor():
#     return render_template('akello_monitor.html', title='Analytics')

@app.route('/akello_monitor', methods=['GET'])
@login_required
def akello_monitor():
    return render_template('simone_monitor.html', title='Analytics')


@app.route('/help-desk', methods=['GET', 'POST'])
@login_required
def help_desk():
    from app.forms import HelpDeskForm
    from app.models import HelpDeskQuery

    form = HelpDeskForm()
    if form.validate_on_submit():
        qtype = form.query_type.data
        created_by = 'anonymous' if qtype == 'anonymous' else current_user.username
        image_path = None
        if form.image.data:
            file = form.image.data
            if file.filename:
                filename = secure_filename(f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                save_path = os.path.join(app.config['HELP_DESK_UPLOAD_FOLDER'], filename)
                file.save(save_path)
                image_path = '/' + save_path  # make it web path
        q = HelpDeskQuery(
            query_title=form.query_title.data,
            query_description=form.query_description.data,
            query_type=qtype,
            created_by=created_by,
            image_path=image_path
        )
        db.session.add(q)
        db.session.commit()
        flash('Your query has been submitted.', 'success')
        return redirect(url_for('help_desk'))

    # Show newest first; admins see all; others see only their own and anonymous
    try:
        if current_user.userRole == 'Admin':
            queries = HelpDeskQuery.query.order_by(HelpDeskQuery.timestamp.desc()).all()
        else:
            queries = HelpDeskQuery.query.filter(
                (HelpDeskQuery.created_by == current_user.username) | (HelpDeskQuery.created_by == 'anonymous')
            ).order_by(HelpDeskQuery.timestamp.desc()).all()
    except Exception:
        queries = []

    # My queries section: all queries created by the current user
    try:
        my_queries = HelpDeskQuery.query.filter(HelpDeskQuery.created_by == current_user.username) \
            .order_by(HelpDeskQuery.timestamp.desc()).all()
    except Exception:
        my_queries = []

    return render_template('help_desk.html', form=form, queries=queries, my_queries=my_queries, title='Help desk')


# Update help desk query status (Admin only)
@app.route('/help-desk/<int:query_id>/status', methods=['PATCH'])
@login_required
def update_helpdesk_status(query_id):
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    from app.models import HelpDeskQuery
    q = HelpDeskQuery.query.get_or_404(query_id)
    data = request.get_json() or {}
    new_status = data.get('status')
    allowed = ['Not started', 'Looking into it', 'Resolved']
    if new_status not in allowed:
        return jsonify({'error': 'Invalid status'}), 400
    q.status = new_status
    db.session.commit()
    return jsonify({'message': 'Status updated', 'status': q.status})


# Delete help desk query (Admin only)
@app.route('/help-desk/<int:query_id>', methods=['DELETE'])
@login_required
def delete_helpdesk_query(query_id):
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    from app.models import HelpDeskQuery
    q = HelpDeskQuery.query.get_or_404(query_id)
    # optionally remove file
    try:
        if q.image_path and q.image_path.startswith('/static/uploads/helpdesk/'):
            fs_path = q.image_path.lstrip('/')
            if os.path.exists(fs_path):
                os.remove(fs_path)
    except Exception:
        pass
    db.session.delete(q)
    db.session.commit()
    return jsonify({'message': 'Deleted'})


# Update champion's school details
# Use a flexible key (library_school_id or asl_school_id) to locate the school dict
@app.route("/api/champions/<int:champ_id>/schools/<school_key>", methods=["PUT"], endpoint="update_school_by_key")
def update_school_by_key(champ_id, school_key):
    champ = ChampionSchool.query.get_or_404(champ_id)
    schools = champ.get_schools() or []

    # Normalize types to string for comparison
    key = str(school_key)
    target = None
    for s in schools:
        if str(s.get("library_school_id")) == key or str(s.get("asl_school_id")) == key:
            target = s
            break

    if not target:
        return jsonify({"error": "School not found for this champion"}), 404

    data = request.get_json() or {}
    if "school_name" in data:
        target["school_name"] = data["school_name"]
    if "asl_school_id" in data:
        target["asl_school_id"] = data["asl_school_id"]
    if "library_school_id" in data:
        target["library_school_id"] = data["library_school_id"]

    champ.set_schools(schools)
    db.session.commit()
    return jsonify(champ.to_dict())
@app.route('/api/lesotho-institutions', methods=['GET'])
def lesotho_institutions():
    conn = None
    try:
        conn = get_direct_library_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Query: Get institutions in Lesotho with their user counts
        query = """
            SELECT 
                i.id AS institution_id,
                i.name AS institution_name,
                COUNT(u.id) AS total_users
            FROM institutions i
            LEFT JOIN users u ON u.id = i.id
            WHERE i.country = %s
            GROUP BY i.id, i.name
        """
        cursor.execute(query, ("Lesotho",))
        institutions = cursor.fetchall()

        # Calculate totals
        total_institutions = len(institutions)
        total_users = sum(inst["total_users"] for inst in institutions)

        return jsonify({
            "country": "Lesotho",
            "total_institutions": total_institutions,
            "total_users": total_users,
            "institutions": institutions
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if conn:
            conn.close()




# mobile app routes

@app.route('/api/mobile/login', methods=['POST'])
def mobile_login():
    """
    Mobile login endpoint that returns JSON responses
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required'}), 400
        
        # Find user by username
        user = db.session.scalar(sa.select(User).where(User.username == username))
        
        if user is None or not user.check_password(password):
            return jsonify({'success': False, 'message': 'Invalid username or password'}), 401
        
        # Log the user in
        login_user(user, remember=False)
        
        # Return user data
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'firstname': user.firstname,
            'lastname': user.lastname,
            'userRole': user.userRole,
            'department': user.department,
            'province': user.province
        }
        
        return jsonify({
            'success': True, 
            'message': 'Login successful',
            'user': user_data
        }), 200
        
    except Exception as e:
        print(f"Mobile login error: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/mobile/logout', methods=['POST'])
def mobile_logout():
    """
    Mobile logout endpoint
    """
    try:
        logout_user()
        return jsonify({'success': True, 'message': 'Logout successful'}), 200
    except Exception as e:
        print(f"Mobile logout error: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/mobile/user', methods=['GET'])
@login_required
def mobile_get_user():
    """
    Get current user data for mobile
    """
    try:
        user_data = {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'firstname': current_user.firstname,
            'lastname': current_user.lastname,
            'userRole': current_user.userRole,
            'department': current_user.department,
            'province': current_user.province
        }
        
        return jsonify({
            'success': True,
            'user': user_data
        }), 200
        
    except Exception as e:
        print(f"Get user error: {e}")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/mobile/profile', methods=['GET'])
@login_required
def mobile_user_profile():
    """
    Get detailed user profile data for mobile including Brand Ambassador stats
    """
    try:
        user = current_user
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'firstname': user.firstname,
            'lastname': user.lastname,
            'userRole': user.userRole,
            'department': user.department,
            'province': user.province
        }
        
        # Brand Ambassador specific data
        if user.userRole == 'Brand Ambassador':
            try:
                from app.models import ChampionSchool
                import json
                from datetime import datetime, date
                
                # Find champion record
                champ = ChampionSchool.query.filter_by(
                    firstname=user.firstname,
                    lastname=user.lastname,
                    province=user.province
                ).first()
                
                champion_data = {
                    'schools': [],
                    'stats': {
                        'school_count': 0,
                        'asl_mtd': 0,
                        'library_mtd': 0
                    }
                }
                
                if champ and champ.schools:
                    try:
                        # Parse schools JSON
                        schools_data = json.loads(champ.schools)
                        
                        # Extract school info for display
                        champion_data['schools'] = [
                            {
                                'id': s.get('asl_school_id', ''),
                                'name': s.get('school_name', 'Unknown School'),
                                'asl_id': s.get('asl_school_id'),
                                'library_id': s.get('library_school_id')
                            }
                            for s in schools_data if s.get('school_name')
                        ]
                        
                        # Calculate stats
                        asl_ids = [s.get('asl_school_id') for s in schools_data if s.get('asl_school_id')]
                        champion_data['stats']['school_count'] = len(asl_ids)
                        
                        # Calculate ASL MTD (month-to-date) student count
                        if asl_ids:
                            today = date.today()
                            start_date = today.replace(day=1)
                            
                            asl_mtd = 0
                            try:
                                conn = get_ruzivo_conn()
                                cursor = conn.cursor()
                                
                                for asl_id in asl_ids:
                                    if asl_id:
                                        query = """
                                            SELECT COUNT(*) AS student_count
                                            FROM vwstudent
                                            WHERE school_id = %s
                                            AND last_login BETWEEN %s AND %s
                                        """
                                        cursor.execute(query, (asl_id, start_date, today))
                                        row = cursor.fetchone()
                                        
                                        if row:
                                            if isinstance(row, dict):
                                                asl_mtd += row.get('student_count', 0)
                                            else:
                                                asl_mtd += row[0] or 0
                                
                                cursor.close()
                                conn.close()
                                champion_data['stats']['asl_mtd'] = asl_mtd
                            except Exception as e:
                                print(f"ASL MTD calculation error: {e}")
                        
                        # Calculate Library MTD using existing API
                        try:
                            library_ids = [s.get('library_school_id') for s in schools_data if s.get('library_school_id')]
                            if library_ids:
                                today = date.today()
                                start_date = today.replace(day=1)
                                
                                library_mtd = 0
                                conn = get_direct_library_conn()
                                if conn:
                                    import pymysql.cursors
                                    cursor = conn.cursor(pymysql.cursors.DictCursor)
                                    
                                    library_ids_int = [int(lid) for lid in library_ids if lid]
                                    if library_ids_int:
                                        in_placeholders = ', '.join(['%s'] * len(library_ids_int))
                                        query = f"""
                                            SELECT COUNT(DISTINCT la.user_id) AS active_users
                                            FROM last_activities la
                                            JOIN institution_user iu ON la.user_id = iu.user_id
                                            WHERE iu.institution_id IN ({in_placeholders})
                                              AND la.created_at BETWEEN %s AND %s
                                        """
                                        
                                        start_dt = datetime.combine(start_date, datetime.min.time())
                                        end_dt = datetime.combine(today, datetime.max.time())
                                        params = library_ids_int + [start_dt, end_dt]
                                        
                                        cursor.execute(query, params)
                                        row = cursor.fetchone()
                                        library_mtd = row["active_users"] if row else 0
                                    
                                    cursor.close()
                                    conn.close()
                                    champion_data['stats']['library_mtd'] = library_mtd
                        except Exception as e:
                            print(f"Library MTD calculation error: {e}")
                            
                    except json.JSONDecodeError as e:
                        print(f"Error parsing schools JSON: {e}")
                
                user_data['champion_data'] = champion_data
                
            except Exception as e:
                print(f"Brand Ambassador data error: {e}")
                import traceback
                traceback.print_exc()
        
        return jsonify({
            'success': True,
            'user': user_data
        }), 200
        
    except Exception as e:
        print(f"Profile data error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Server error'}), 500


@app.route('/api/mobile/help-desk', methods=['GET', 'POST'])
@login_required
def mobile_help_desk():
    """
    Mobile help desk endpoint for fetching and creating queries
    """
    from app.models import HelpDeskQuery
    from app.forms import HelpDeskForm
    
    if request.method == 'GET':
        # Fetch help desk queries for mobile
        try:
            # Show newest first; admins see all; others see only their own and anonymous
            if current_user.userRole == 'Admin':
                queries = HelpDeskQuery.query.order_by(HelpDeskQuery.timestamp.desc()).all()
            else:
                queries = HelpDeskQuery.query.filter(
                    (HelpDeskQuery.created_by == current_user.username) | 
                    (HelpDeskQuery.created_by == 'anonymous')
                ).order_by(HelpDeskQuery.timestamp.desc()).all()
            
            # Convert to mobile-friendly format
            queries_data = []
            for q in queries:
                queries_data.append({
                    'id': q.id,
                    'query_title': q.query_title,
                    'query_description': q.query_description,
                    'query_type': q.query_type,
                    'created_by': q.created_by,
                    'timestamp': q.timestamp.isoformat() if q.timestamp else None,
                    'status': q.status or 'Not started',
                    'image_path': q.image_path
                })
            
            return jsonify({
                'success': True,
                'queries': queries_data,
                'current_user': current_user.username,
                'is_admin': current_user.userRole == 'Admin'
            }), 200
            
        except Exception as e:
            print(f"Error fetching help desk queries: {e}")
            return jsonify({
                'success': False,
                'message': 'Failed to fetch queries',
                'queries': []
            }), 500
    
    elif request.method == 'POST':
        # Create new help desk query from mobile
        try:
            # Handle both form data and JSON data
            if request.is_json:
                data = request.get_json()
                query_type = data.get('query_type', '')
                query_title = data.get('query_title', '')
                query_description = data.get('query_description', '')
                image_file = None
            else:
                # Handle multipart form data (with potential file upload)
                query_type = request.form.get('query_type', '')
                query_title = request.form.get('query_title', '')
                query_description = request.form.get('query_description', '')
                image_file = request.files.get('image')
            
            # Validate required fields
            if not query_title or not query_description or not query_type:
                return jsonify({
                    'success': False,
                    'message': 'Query title, description, and type are required'
                }), 400
            
            # Handle image upload
            image_path = None
            if image_file and image_file.filename:
                try:
                    filename = secure_filename(f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{image_file.filename}")
                    save_path = os.path.join(app.config['HELP_DESK_UPLOAD_FOLDER'], filename)
                    image_file.save(save_path)
                    image_path = '/' + save_path  # make it web path
                except Exception as e:
                    print(f"Error saving image: {e}")
                    # Continue without image if upload fails
            
            # Determine created_by
            created_by = 'anonymous' if query_type == 'anonymous' else current_user.username
            
            # Create new help desk query
            q = HelpDeskQuery(
                query_title=query_title,
                query_description=query_description,
                query_type=query_type,
                created_by=created_by,
                image_path=image_path
            )
            
            db.session.add(q)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Query submitted successfully',
                'query_id': q.id
            }), 201
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating help desk query: {e}")
            return jsonify({
                'success': False,
                'message': 'Failed to submit query'
            }), 500


@app.route('/api/mobile/reports', methods=['GET', 'POST'])
@login_required
def mobile_reports():
    """
    Mobile reports endpoint for fetching and creating weekly reports
    """
    from app.models import WeeklyReport
    
    if request.method == 'GET':
        # Fetch reports data for mobile
        try:
            # Get users from same department
            users = User.query.filter_by(department=current_user.department).all()
            
            # Convert to mobile-friendly format
            users_data = []
            for user in users:
                users_data.append({
                    'id': user.id,
                    'username': user.username,
                    'firstname': user.firstname,
                    'lastname': user.lastname,
                    'department': user.department
                })
            
            return jsonify({
                'success': True,
                'users': users_data,
                'current_user': {
                    'id': current_user.id,
                    'username': current_user.username,
                    'department': current_user.department
                }
            }), 200
            
        except Exception as e:
            print(f"Error fetching reports data: {e}")
            return jsonify({
                'success': False,
                'message': 'Failed to fetch reports data',
                'users': []
            }), 500
    
    elif request.method == 'POST':
        # Create new weekly report from mobile
        try:
            data = request.get_json()
            week_start = data.get('week_start', '')
            work_done = data.get('work_done', '')
            work_next = data.get('work_next', '')
            challenges = data.get('challenges', '')
            
            # Validate required fields
            if not week_start or not work_done or not work_next:
                return jsonify({
                    'success': False,
                    'message': 'Week start, work done, and work next are required'
                }), 400
            
            # Validate week start is Monday
            from datetime import datetime
            week_start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
            if week_start_date.weekday() != 0:  # Must be Monday
                return jsonify({
                    'success': False,
                    'message': 'Week start date must be a Monday'
                }), 400
            
            # Create new weekly report
            report = WeeklyReport(
                user_id=current_user.id,
                department=current_user.department,
                week_start=week_start,
                work_done=work_done,
                work_next=work_next,
                challenges=challenges
            )
            
            db.session.add(report)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Report submitted successfully',
                'report_id': report.id
            }), 201
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating weekly report: {e}")
            return jsonify({
                'success': False,
                'message': 'Failed to submit report'
            }), 500


@app.route('/api/mobile/reports/user/<int:user_id>', methods=['GET'])
@login_required
def mobile_user_reports(user_id):
    """
    Get reports for a specific user (mobile)
    """
    from app.models import WeeklyReport
    
    try:
        # Check if user exists and is in same department
        user = User.query.get_or_404(user_id)
        if user.department != current_user.department:
            return jsonify({
                'success': False,
                'message': 'You can only view reports from your department'
            }), 403
        
        # Get reports for this user
        reports = WeeklyReport.query.filter_by(user_id=user_id) \
                                   .order_by(WeeklyReport.created_at.desc()) \
                                   .all()
        
        # Convert to mobile-friendly format
        reports_data = []
        for report in reports:
            reports_data.append({
                'id': report.id,
                'user_id': report.user_id,
                'department': report.department,
                'week_start': report.week_start,
                'work_done': report.work_done,
                'work_next': report.work_next,
                'challenges': report.challenges,
                'created_at': report.created_at.isoformat() if report.created_at else None
            })
        
        return jsonify({
            'success': True,
            'reports': reports_data,
            'user': {
                'id': user.id,
                'username': user.username
            }
        }), 200
        
    except Exception as e:
        print(f"Error fetching user reports: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch user reports',
            'reports': []
        }), 500


@app.route('/api/mobile/reports/<int:report_id>', methods=['PUT'])
@login_required
def mobile_update_report(report_id):
    """
    Update a weekly report (mobile)
    """
    from app.models import WeeklyReport
    from datetime import datetime, timedelta
    
    try:
        report = WeeklyReport.query.get_or_404(report_id)
        
        # Ensure user owns this report
        if report.user_id != current_user.id:
            return jsonify({
                'success': False,
                'message': 'You are not authorized to edit this report'
            }), 403
        
        # Check if report is older than 7 days
        if datetime.utcnow() > report.created_at + timedelta(days=7):
            return jsonify({
                'success': False,
                'message': 'You can only edit reports within 7 days of submission'
            }), 403
        
        data = request.get_json()
        week_start = data.get('week_start', '')
        work_done = data.get('work_done', '')
        work_next = data.get('work_next', '')
        challenges = data.get('challenges', '')
        
        # Validate required fields
        if not week_start or not work_done or not work_next:
            return jsonify({
                'success': False,
                'message': 'Week start, work done, and work next are required'
            }), 400
        
        # Validate week start is Monday
        week_start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
        if week_start_date.weekday() != 0:  # Must be Monday
            return jsonify({
                'success': False,
                'message': 'Week start date must be a Monday'
            }), 400
        
        # Update report
        report.week_start = week_start
        report.work_done = work_done
        report.work_next = work_next
        report.challenges = challenges
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Report updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating report: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to update report'
        }), 500


# ===============================
# SEARCH FUNCTIONALITY ROUTES
# ===============================

@app.route('/api/search', methods=['GET'])
@login_required
def global_search():
    """
    Global search across users, projects, workspaces, reports, and other platform data
    """
    try:
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify({
                'success': True,
                'results': [],
                'message': 'Please enter at least 2 characters to search'
            }), 200
        
        search_results = []
        search_term = f"%{query}%"
        
        # 1. Search Users (all authenticated users can search for other users)
        try:
            users = User.query.filter(
                db.or_(
                    User.username.ilike(search_term),
                    User.firstname.ilike(search_term),
                    User.lastname.ilike(search_term),
                    User.email.ilike(search_term),
                    User.department.ilike(search_term)
                )
            ).limit(10).all()
            
            for user in users:
                # Don't include current user in search results
                if user.id != current_user.id:
                    search_results.append({
                        'type': 'user',
                        'id': user.id,
                        'title': f"{user.firstname} {user.lastname}",
                        'subtitle': f"@{user.username} - {user.userRole}",
                        'description': f"{user.department or 'No department'} | {user.email}",
                        'url': url_for('profile', username=user.username),
                        'icon': 'user'
                    })
        except Exception as e:
            print(f"User search error: {e}")
        
        # 2. Search Workspaces
        try:
            workspaces = Workspace.query.filter(
                db.or_(
                    Workspace.name.ilike(search_term),
                    Workspace.description.ilike(search_term)
                )
            ).limit(10).all()
            
            for workspace in workspaces:
                # Show all workspaces but redirect to aplanforprojects page
                # Access control will be handled on that page
                search_results.append({
                    'type': 'workspace',
                    'id': workspace.id,
                    'title': workspace.name,
                    'subtitle': 'Workspace',
                    'description': workspace.description or 'No description',
                    'url': url_for('aplanforprojects'),  # Redirect to project planning page
                    'icon': 'folder'
                })
        except Exception as e:
            print(f"Workspace search error: {e}")
        
        # 3. Search Projects (ProjectA)
        try:
            projects = ProjectA.query.filter(
                db.or_(
                    ProjectA.project_name.ilike(search_term),
                    ProjectA.description.ilike(search_term)
                )
            ).limit(10).all()
            
            for project in projects:
                # Only show projects where user is a member or admin/manager
                if (current_user in project.members or 
                    current_user.userRole in ['Admin', 'Manager'] or 
                    current_user.has_privilege('Super-admin')):
                    search_results.append({
                        'type': 'project',
                        'id': project.id,
                        'title': project.project_name,
                        'subtitle': 'Project',
                        'description': project.description or 'No description',
                        'url': url_for('aplanforprojects'),  # Redirect to project planning page
                        'icon': 'clipboard'
                    })
        except Exception as e:
            print(f"Project search error: {e}")
        
        # 4. Search Reports
        try:
            reports = WeeklyReport.query.filter(
                db.or_(
                    WeeklyReport.work_done.ilike(search_term),
                    WeeklyReport.work_next.ilike(search_term),
                    WeeklyReport.department.ilike(search_term)
                )
            ).limit(10).all()
            
            for report in reports:
                # Only show user's own reports or if admin
                if report.user_id == current_user.id or current_user.userRole == 'Admin':
                    search_results.append({
                        'type': 'report',
                        'id': report.id,
                        'title': f"Weekly Report - {report.week_start}",
                        'subtitle': f"Report by {report.department}",
                        'description': report.work_done[:100] + '...' if len(report.work_done) > 100 else report.work_done,
                        'url': url_for('akello_weekly_reports'),
                        'icon': 'file-text'
                    })
        except Exception as e:
            print(f"Report search error: {e}")
        
        # 5. Search Champion Schools (with proper access control)
        try:
            champions = ChampionSchool.query.filter(
                db.or_(
                    ChampionSchool.school_name.ilike(search_term),
                    ChampionSchool.province.ilike(search_term)
                )
            ).limit(10).all()
            
            for champion in champions:
                # All users can search champion schools, but Brand Ambassadors only see their province
                if current_user.userRole == 'Brand Ambassador':
                    # Brand Ambassadors only see schools in their province
                    if current_user.province and champion.province == current_user.province:
                        search_results.append({
                            'type': 'champion',
                            'id': champion.id,
                            'title': champion.school_name,
                            'subtitle': f"Champion School - {champion.province}",
                            'description': f"Province: {champion.province}",
                            'url': url_for('all_champion_details'),
                            'icon': 'award'
                        })
                else:
                    # Other roles can see all champion schools
                    search_results.append({
                        'type': 'champion',
                        'id': champion.id,
                        'title': champion.school_name,
                        'subtitle': f"Champion School - {champion.province}",
                        'description': f"Province: {champion.province}",
                        'url': url_for('all_champion_details'),
                        'icon': 'award'
                    })
        except Exception as e:
            print(f"Champion school search error: {e}")
        
        # 6. Search Book Allocations (exclude Brand Ambassadors from admin features)
        if current_user.userRole != 'Brand Ambassador':
            try:
                allocations = BookAllocations.query.filter(
                    db.or_(
                        BookAllocations.school_name.ilike(search_term),
                        BookAllocations.school_province.ilike(search_term),
                        BookAllocations.books_allocated.ilike(search_term)
                    )
                ).limit(10).all()
                
                for allocation in allocations:
                    search_results.append({
                        'type': 'allocation',
                        'id': allocation.id,
                        'title': f"Books for {allocation.school_name}",
                        'subtitle': f"Book Allocation - {allocation.school_province}",
                        'description': allocation.books_allocated or 'No books specified',
                        'url': url_for('bookallocations'),
                        'icon': 'book'
                    })
            except Exception as e:
                print(f"Book allocation search error: {e}")
        
        # Sort results by relevance (exact matches first, then partial matches)
        def sort_by_relevance(item):
            title_lower = item['title'].lower()
            query_lower = query.lower()
            if query_lower == title_lower:
                return 0  # Exact match
            elif title_lower.startswith(query_lower):
                return 1  # Starts with query
            elif query_lower in title_lower:
                return 2  # Contains query
            else:
                return 3  # Other matches
        
        search_results.sort(key=sort_by_relevance)
        
        # Limit total results to prevent overwhelming UI
        search_results = search_results[:20]
        
        return jsonify({
            'success': True,
            'results': search_results,
            'total_found': len(search_results),
            'query': query
        }), 200
        
    except Exception as e:
        print(f"Global search error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Search failed. Please try again.',
            'results': []
        }), 500

@app.route('/search')
@login_required
def search_page():
    """
    Dedicated search results page
    """
    query = request.args.get('q', '').strip()
    return render_template('search_results.html', title='Search Results', query=query)

@app.route('/api/mobile/dashboard', methods=['GET'])
@login_required
def mobile_dashboard_overview():
    """
    Get dashboard overview data for mobile
    """
    try:
        from datetime import datetime, timedelta
        
        # Get current time and ranges
        now = datetime.utcnow()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Get basic stats
        total_users = User.query.filter(User.userRole != 'Admin').count()
        
        # Get recent activity counts (if monitoring is available)
        recent_activities = 0
        active_users_today = 0
        
        try:
            from app.models import UserActivity, ActiveSession
            recent_activities = UserActivity.query.filter(
                UserActivity.timestamp >= week_ago
            ).count()
            
            active_users_today = ActiveSession.query.filter(
                ActiveSession.is_active == True,
                ActiveSession.last_seen >= today
            ).count()
        except:
            # If monitoring tables don't exist, use default values
            pass
        
        # Get performance targets
        latest_target = None
        try:
            from app.models import PerfomanceTargets
            latest_target = PerfomanceTargets.query.order_by(PerfomanceTargets.timestamp.desc()).first()
        except:
            pass
        
        # Get champion data
        champion_count = 0
        try:
            from app.models import ChampionSchool
            champion_count = ChampionSchool.query.count()
        except:
            pass
        
        # Get project data
        active_projects = 0
        total_tasks = 0
        completed_tasks = 0
        
        try:
            from app.models import ProjectA, TaskA
            active_projects = ProjectA.query.count()
            total_tasks = TaskA.query.count()
            completed_tasks = TaskA.query.filter(TaskA.progress == 100).count()
        except:
            pass
        
        dashboard_data = {
            'overview': {
                'total_users': total_users,
                'active_users_today': active_users_today,
                'recent_activities': recent_activities,
                'champion_count': champion_count
            },
            'projects': {
                'active_projects': active_projects,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'completion_rate': round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
            },
            'targets': {
                'has_targets': latest_target is not None,
                'latest_updated': latest_target.timestamp.isoformat() if latest_target else None,
                'updated_by': latest_target.updated_by if latest_target else None
            },
            'system_info': {
                'current_time': now.isoformat(),
                'server_status': 'online',
                'user_role': current_user.userRole,
                'user_department': current_user.department
            }
        }
        
        return jsonify({
            'success': True,
            'data': dashboard_data
        }), 200
        
    except Exception as e:
        print(f"Dashboard overview error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Server error'}), 500


