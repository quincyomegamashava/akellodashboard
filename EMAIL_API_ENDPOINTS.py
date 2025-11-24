# Email API Endpoints for Help Desk
# Add these to your routes.py file

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
