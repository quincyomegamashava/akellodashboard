# Add this to your Flask app's routes.py file
# Mobile Help Desk API endpoints

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