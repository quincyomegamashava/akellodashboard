# Email Integration Setup Guide

## Overview
This guide helps you set up email integration to fetch emails from `mashavaquincy@gmail.com` to your work email `quincy.mashava@akello.co` and display them as queries in the help desk.

## Required Information

### 1. Outlook App Password (for quincy.mashava@akello.co)
Since you're using Outlook/Office 365, you'll need to create an **App Password**.

**Steps to create Outlook App Password:**
1. Go to your Microsoft Account: https://account.microsoft.com/security
2. Navigate to **Security** → **Advanced security options**
3. Under **App passwords**, click **Create a new app password**
4. Copy the generated password (format: xxxx-xxxx-xxxx-xxxx)
5. Use this password for IMAP access

**Note:** If you don't see "App passwords", your organization may use different authentication. Contact your IT admin for IMAP credentials.

### 2. Email Configuration for Receiving Work Emails

You have two options:

#### Option A: Forward emails from mashavaquincy@gmail.com to quincy.mashava@akello.co
This is the simplest option:
1. In Gmail (mashavaquincy@gmail.com):
   - Go to Settings → See all settings
   - Click on "Forwarding and POP/IMAP"
   - Click "Add a forwarding address"
   - Enter: quincy.mashava@akello.co
   - Verify the forwarding address (check quincy.mashava@akello.co for verification email)
   - Set up a filter to forward specific emails automatically

#### Option B: Direct IMAP Access to Work Email
If your company uses Google Workspace/Microsoft 365, you'll need:
- IMAP server address (usually imap.gmail.com for Google Workspace)
- Port: 993 (SSL)
- Your work email: quincy.mashava@akello.co
- App password for your work email account

### 3. For This Implementation
Since you want to receive emails **AT** `quincy.mashava@akello.co` **FROM** `mashavaquincy@gmail.com`, we'll fetch from your work email account.

**You'll need:**
- IMAP Server: outlook.office365.com (for Outlook/Office 365)
- IMAP Port: 993
- SMTP Server: smtp.office365.com (for sending emails)
- SMTP Port: 587
- Email: quincy.mashava@akello.co
- App Password for quincy.mashava@akello.co

## Environment Variables Setup

Add these to your `.env` file:

```bash
# Email Configuration for Help Desk (Outlook)
EMAIL_IMAP_SERVER=outlook.office365.com
EMAIL_IMAP_PORT=993
EMAIL_SMTP_SERVER=smtp.office365.com
EMAIL_SMTP_PORT=587
EMAIL_ADDRESS=quincy.mashava@akello.co
EMAIL_APP_PASSWORD=your-app-password-here
EMAIL_SENDER_FILTER=mashavaquincy@gmail.com
```

## Backend Implementation

I've created the backend API endpoints. Add them to your `routes.py` file:

```python
import imaplib
import email
from email.header import decode_header
from datetime import datetime

@app.route('/api/email-queries', methods=['GET'])
@login_required
def get_email_queries():
    """Fetch emails from configured email account"""
    try:
        # Get email configuration from environment
        imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
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
        
        # Fetch last 50 emails
        for email_id in email_ids[-50:]:
            try:
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])
                
                # Decode subject
                subject = decode_header(msg['Subject'])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()
                
                # Get sender
                from_header = msg.get('From', '')
                
                # Get date
                date_str = msg.get('Date', '')
                
                # Get body
                body = ''
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            break
                else:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                
                emails.append({
                    'id': email_id.decode(),
                    'subject': subject,
                    'from': from_header,
                    'date': date_str,
                    'preview': body[:200] if body else '',
                    'body': body
                })
            except Exception as e:
                print(f"Error processing email {email_id}: {str(e)}")
                continue
        
        mail.close()
        mail.logout()
        
        return jsonify({'emails': emails}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/email-queries/<email_id>', methods=['GET'])
@login_required
def get_email_query_details(email_id):
    """Get details of a specific email"""
    try:
        imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
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
        subject = decode_header(msg['Subject'])[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()
        
        # Get body
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
        else:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        
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


@app.route('/api/email-queries/<email_id>/convert', methods=['POST'])
@login_required
def convert_email_to_query(email_id):
    """Convert an email to a help desk query"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Fetch the email
        imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
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
        subject = decode_header(msg['Subject'])[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()
        
        # Get body
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
        else:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        # Get sender email
        from_header = msg.get('From', '')
        
        mail.close()
        mail.logout()
        
        # Create a help desk query from the email
        from app.models import HelpDeskQuery  # Import your HelpDeskQuery model
        
        query = HelpDeskQuery(
            query_title=subject or 'Email Query',
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
```

## Testing Steps

1. **Set up environment variables** in your `.env` file
2. **Restart your Flask application**
3. **Test the connection:**
   - Go to Help Desk page
   - Click on "Email Queries" card
   - Click "Refresh Emails" button
   - You should see emails from mashavaquincy@gmail.com

## Troubleshooting

### Common Issues:

1. **"Email configuration not set"**
   - Make sure `.env` file has all required variables
   - Restart Flask app after updating `.env`

2. **Authentication failed**
   - Double-check app password (no spaces)
   - Make sure 2-Step Verification is enabled
   - Generate a new app password if needed

3. **No emails showing**
   - Check if `EMAIL_SENDER_FILTER` is set correctly
   - Verify emails exist in inbox from that sender
   - Check Flask console for error messages

4. **Connection timeout**
   - Check firewall settings
   - Verify IMAP server and port are correct
   - For corporate email, contact IT department

## Next Steps

Once emails are fetching correctly:
- Admin can view email details
- Admin can convert emails to queries with one click
- Converted queries appear in "Recent Queries"
- You can respond to queries through the normal help desk workflow

## Security Notes

- Never commit `.env` file to version control
- App passwords are more secure than regular passwords
- Consider implementing rate limiting for email fetching
- Set up logging for email access attempts
