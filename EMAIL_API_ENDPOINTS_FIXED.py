# Updated Email API Endpoints with Better Outlook Support
# Replace the get_email_queries function in your routes.py with this version

import imaplib
import email
import smtplib
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json
import ssl

# ===== Email Query Storage =====
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


@app.route('/api/email-queries', methods=['GET'])
@login_required
def get_email_queries():
    """Fetch emails from configured Outlook account with better error handling"""
    try:
        # Get email configuration from environment
        imap_server = os.getenv('EMAIL_IMAP_SERVER', 'outlook.office365.com')
        imap_port = int(os.getenv('EMAIL_IMAP_PORT', '993'))
        email_address = os.getenv('EMAIL_ADDRESS')
        email_password = os.getenv('EMAIL_APP_PASSWORD')
        sender_filter = os.getenv('EMAIL_SENDER_FILTER', '')
        
        if not email_address or not email_password:
            return jsonify({'error': 'Email configuration not set. Please check .env file.'}), 500
        
        # Create SSL context
        context = ssl.create_default_context()
        
        # Connect to IMAP server with better error handling
        try:
            print(f"Attempting to connect to {imap_server}:{imap_port}")
            mail = imaplib.IMAP4_SSL(imap_server, imap_port, ssl_context=context)
            
            print(f"Attempting login for {email_address}")
            # Try to login
            mail.login(email_address, email_password)
            print("Login successful!")
            
        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            print(f"IMAP Error: {error_msg}")
            
            # Provide helpful error messages
            if 'LOGIN failed' in error_msg or 'AUTHENTICATE failed' in error_msg:
                return jsonify({
                    'error': 'Authentication failed. Please check:\n1. IMAP is enabled in Outlook settings\n2. Email and password are correct\n3. You may need to use regular password instead of app password\n4. Your organization may require OAuth2 (contact IT)',
                    'details': error_msg
                }), 401
            else:
                return jsonify({'error': f'IMAP connection error: {error_msg}'}), 500
        
        except Exception as e:
            print(f"Connection error: {str(e)}")
            return jsonify({
                'error': f'Cannot connect to {imap_server}. Please check your internet connection and server address.',
                'details': str(e)
            }), 500
        
        # Select inbox
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
        print(f"Unexpected error fetching emails: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


# Keep all other endpoints the same (status update, send email, convert, etc.)
