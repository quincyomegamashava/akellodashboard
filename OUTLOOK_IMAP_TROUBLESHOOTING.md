# Troubleshooting: Outlook IMAP "LOGIN failed" Error

## Error: `b'LOGIN failed.'`

This error means the IMAP server rejected your login credentials. Here's how to fix it:

---

## ✅ Step-by-Step Fixes

### 1. **Enable IMAP in Outlook (MOST COMMON FIX)**

Outlook disables IMAP by default. You MUST enable it:

**For Outlook.com / Hotmail:**
1. Go to: https://outlook.live.com/mail/
2. Click Settings (gear icon) → View all Outlook settings
3. Go to **Mail** → **Sync email**
4. Check if **IMAP** is turned ON
5. If OFF, turn it ON and Save

**For Office 365 (Work/School Account):**
1. Go to: https://outlook.office365.com/mail/
2. Click Settings (gear icon) → View all Outlook settings
3. Go to **Mail** → **Sync email**
4. Look for "POP and IMAP" settings
5. Enable IMAP access
6. **IMPORTANT:** Your IT admin might have disabled IMAP. If you don't see this option, contact IT.

---

### 2. **Check Your Credentials**

Verify your `.env` file has correct values:

```bash
EMAIL_ADDRESS=quincy.mashava@akello.co
EMAIL_APP_PASSWORD=your-password-here
```

**Common mistakes:**
- ❌ Extra spaces in the password
- ❌ Wrong email address
- ❌ Old/expired app password

---

### 3. **Try Your Regular Password First**

Many Outlook accounts don't support app passwords. Try using your **regular Outlook password** instead:

```bash
EMAIL_APP_PASSWORD=your-regular-outlook-password
```

**Test this temporarily** to see if it works. If it does, your account doesn't use app passwords.

---

### 4. **Check Account Type**

Different Outlook account types have different requirements:

#### **Personal Account (outlook.com, hotmail.com, live.com):**
- Uses regular password
- App passwords only if 2FA is enabled
- IMAP server: `outlook.office365.com`

#### **Work/School Account (Office 365):**
- Controlled by your organization
- May require Modern Authentication (OAuth2)
- IMAP might be disabled by IT policy
- **Contact your IT department** if issues persist

---

### 5. **Alternative: Use Gmail Forwarding Instead**

If Outlook IMAP doesn't work (often due to IT restrictions), use this workaround:

**Setup:**
1. Set up email forwarding in mashavaquincy@gmail.com:
   - Gmail Settings → Forwarding and POP/IMAP
   - Forward a copy to: quincy.mashava@akello.co
   
2. Then fetch from Gmail instead:
   ```bash
   EMAIL_IMAP_SERVER=imap.gmail.com
   EMAIL_ADDRESS=mashavaquincy@gmail.com
   EMAIL_APP_PASSWORD=gmail-app-password
   ```

3. Create Gmail app password:
   - Go to: https://myaccount.google.com/apppasswords
   - Generate password for "Mail"

This way, emails go to Outlook but you fetch from Gmail.

---

## 🔍 Diagnostic Steps

### Check 1: Verify Email Configuration

Check your Flask console output when you click "Refresh Emails". Look for these lines:

```
Attempting to connect to outlook.office365.com:993
Attempting login for quincy.mashava@akello.co
```

If you see "Login successful!" - Great! The issue is elsewhere.
If you see "IMAP Error: LOGIN failed" - Continue troubleshooting.

### Check 2: Test with Python

Create a test file `test_imap.py`:

```python
import imaplib

server = "outlook.office365.com"
email = "quincy.mashava@akello.co"
password = "your-password-here"

try:
    mail = imaplib.IMAP4_SSL(server, 993)
    mail.login(email, password)
    print("✅ Login successful!")
    mail.logout()
except Exception as e:
    print(f"❌ Error: {e}")
```

Run: `python test_imap.py`

This will tell you if the issue is with Python/IMAP or your Flask app.

---

## 🔐 Security Considerations

### If Your Organization Blocks IMAP:

Some organizations disable IMAP for security. Alternative solutions:

1. **Microsoft Graph API** (Advanced)
   - Uses OAuth2 instead of IMAP
   - Requires app registration in Azure
   - More secure but more complex

2. **Email Forwarding to Gmail** (Recommended)
   - Easier to set up
   - Gmail has better IMAP support
   - See step 5 above

3. **Manual Import**
   - Export emails as .eml files
   - Upload manually to dashboard
   - Not automated but works

---

## 📋 Checklist

Before asking for help, verify:

- [ ] IMAP is enabled in Outlook settings
- [ ] Email address is correct in `.env`
- [ ] Password is correct (try regular password)
- [ ] No extra spaces in `.env` file
- [ ] Flask server restarted after `.env` changes
- [ ] You're not behind a firewall blocking port 993
- [ ] Tested with the Python test script above

---

## 🆘 Still Not Working?

### Contact Your IT Department

Ask them:
1. "Is IMAP enabled for my account quincy.mashava@akello.co?"
2. "Does our organization allow IMAP connections?"
3. "Do I need to use Modern Authentication / OAuth2?"
4. "Can you enable IMAP access for my account?"

### Use Gmail Instead

If IT says no to IMAP, use the Gmail forwarding method (Step 5 above). This is often the easiest solution for Office 365 accounts with strict IT policies.

---

## 💡 Recommended Solution

For most Office 365 work accounts with IT restrictions:

**Use Gmail as intermediary:**
1. Forward mashavaquincy@gmail.com → quincy.mashava@akello.co (you still receive them)
2. Fetch from mashavaquincy@gmail.com via IMAP (easier to configure)
3. Reply from quincy.mashava@akello.co via SMTP (works fine)

This gives you the best of both worlds!
