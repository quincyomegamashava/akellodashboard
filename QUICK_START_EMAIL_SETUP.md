# Quick Start: Email Integration Setup

## ✅ What's Already Done
- ✅ Frontend updated with modals (Recent Queries, My Queries, Email Queries)
- ✅ Status tracking column added to Email Queries table
- ✅ Email notification prompt when marking as "Resolved"
- ✅ All JavaScript functions implemented

## 🔧 What You Need To Do

### 1. Get Outlook App Password (5 minutes)

Since quincy.mashava@akello.co is an Outlook email:

1. Go to: https://account.microsoft.com/security
2. Click "Security" → "Advanced security options"
3. Under "App passwords", click "Create a new app password"
4. Copy the password (looks like: xxxx-xxxx-xxxx-xxxx)

**Note:** If you don't see "App passwords", contact your IT admin - your organization might use different authentication.

### 2. Update `.env` File (2 minutes)

Add these lines to your `.env` file in the project root:

```bash
# Email Configuration for Help Desk
EMAIL_IMAP_SERVER=outlook.office365.com
EMAIL_IMAP_PORT=993
EMAIL_SMTP_SERVER=smtp.office365.com
EMAIL_SMTP_PORT=587
EMAIL_ADDRESS=quincy.mashava@akello.co
EMAIL_APP_PASSWORD=paste-your-app-password-here
EMAIL_SENDER_FILTER=mashavaquincy@gmail.com
```

### 3. Add Backend Code (10 minutes)

Open `app/routes.py` and:

**A. Add imports at the top:**
```python
import imaplib
import email
import smtplib
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
```

**B. Copy all the code from `EMAIL_API_ENDPOINTS.py` to the bottom of your routes.py file**

The file includes:
- Helper functions (`load_email_statuses`, `save_email_status`)
- 5 API endpoints for email management

### 4. Restart Flask (1 minute)

```bash
# Stop the Flask server (Ctrl+C)
# Start it again
python run.py
```

### 5. Test (5 minutes)

1. Open the Help Desk page
2. Click the "Email Queries" card (purple one)
3. Click "Refresh Emails" button
4. You should see emails from mashavaquincy@gmail.com

5. Test status change:
   - Change status dropdown to "Resolved"
   - A prompt will appear asking for a message
   - Enter your message and click OK
   - Email will be sent to the customer!

## 🎯 How It Works

### Email Flow:
1. Customer sends email from `mashavaquincy@gmail.com`
2. Email arrives at `quincy.mashava@akello.co`
3. Dashboard fetches emails via IMAP
4. Admin can view, track status, and respond

### Status Workflow:
- **Not started** (Grey) → Initial state
- **Looking into it** (Orange) → Working on it
- **Resolved** (Green) → Done! → Triggers email notification

### Email Notification:
When you mark as "Resolved":
1. Prompt appears with default message
2. You can customize the message
3. Professional HTML email sent via SMTP
4. Includes Akello branding and contact info

## 🔍 Troubleshooting

### "Email configuration not set"
- Check `.env` file has all variables
- Restart Flask after updating `.env`

### "Authentication failed"
- Verify app password (no spaces/dashes)
- Try generating new app password
- Check email address is correct

### "No emails showing"
- Verify emails exist in inbox from mashavaquincy@gmail.com
- Check `EMAIL_SENDER_FILTER` value
- Look at Flask console for error messages

### "Cannot send email"
- Verify SMTP settings in `.env`
- Check app password works for SMTP
- Ensure port 587 is not blocked by firewall

## 📝 Files Reference

- `help_desk.html` - Frontend (already updated ✅)
- `EMAIL_API_ENDPOINTS.py` - Backend code to add
- `EMAIL_INTEGRATION_SETUP.md` - Detailed documentation
- `.env` - Configuration file (you need to update)

## 🚀 Next Steps

After setup works:
1. Test with a real email from mashavaquincy@gmail.com
2. Practice changing statuses
3. Send test resolution email
4. Consider adding more status options if needed

## 💡 Tips

- Email statuses are stored in `email_query_statuses.json`
- You can customize the email template in the `send_resolution_email` function
- The system fetches the last 50 emails by default
- Email addresses are extracted from "Name <email@example.com>" format automatically

## 🆘 Need Help?

Check the detailed documentation in:
- `EMAIL_INTEGRATION_SETUP.md` - Full setup guide
- `HELP_DESK_CHANGES_SUMMARY.md` - Overview of changes

The frontend is ready - you just need to add backend code and configuration!
