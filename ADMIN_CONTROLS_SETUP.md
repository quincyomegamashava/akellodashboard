# Admin Controls for ASL MTD Filtering - Setup Instructions

## What's Been Completed

✅ **Backend Components:**
1. `AppSetting` model added to `app/models.py` with helper methods
2. Profile route updated to check admin settings before filtering schools
3. API endpoints created in `app/routes_asl_settings.py`

✅ **UI Components:**
1. Settings modal HTML created in `app/templates/asl_settings_modal.html`
2. JavaScript handlers for loading and saving settings

✅ **Database Migration:**
1. Migration script created: `create_app_settings_table.py`

---

## Setup Steps

### Step 1: Run Database Migration

```bash
cd c:\Users\quincy.mashava\Desktop\Akello\akellodashboard
python create_app_settings_table.py
```

This will:
- Create the `app_settings` table
- Initialize default settings (both filters enabled)

### Step 2: Add Settings Card to Administration Page

Open `app/templates/administration.html` and add this card after line 204 (after the "System State" card):

```html
      <div class="minimal-card p-6" style="cursor: pointer;" onclick="document.getElementById('aslSettingsModal').style.display='block';">
        <div class="kpi-icon-minimal bg-purple-50 text-purple-600 mb-4">
          <i class="fas fa-sliders-h"></i>
        </div>
        <div class="text-2xl font-black text-slate-800">ASL MTD</div>
        <div class="text-xs font-bold text-slate-400 uppercase tracking-widest mt-1">Filter Settings</div>
      </div>
```

### Step 3: Include Settings Modal in Administration Page

At the end of `app/templates/administration.html` (before the closing `{% endblock %}` tag), add:

```html
{% include 'asl_settings_modal.html' %}
```

### Step 4: Import Routes in __init__.py

Add this line after line 31 in `app/__init__.py`:

```python
from app import routes_asl_settings
```

### Step 5: Restart Flask Server

The Flask server should automatically reload. If not, restart it manually.

---

## Testing

1. **Access Admin Page:** Navigate to `/administration` (admin users only)
2. **Click ASL MTD Card:** Click the new "ASL MTD Filter Settings" card
3. **Toggle Settings:** Try different combinations:
   - Both enabled (default)
   - Only 12+ months enabled
   - Only 1+ year enabled
   - Both disabled
4. **Verify Profile Page:** Visit a Brand Ambassador profile and check that the ASL MTD count changes based on settings

---

## How It Works

### Default Behavior (Both Enabled)
- Excludes schools with total months >= 12 since Jan 2025
- Excludes schools where first awarded > 1 year ago
- This is the current behavior you requested

### Flexible Configuration
Admins can now:
- Disable 12-month filter (include long-term scholarships)
- Disable 1-year filter (include old scholarships)
- Disable both (include all schools)
- Enable both (strictest filtering)

### Settings Storage
- Stored in `app_settings` table
- Persists across server restarts
- Tracks who made changes and when

---

## Files Modified/Created

**Modified:**
- `app/models.py` - Added AppSetting model
- `app/routes.py` - Updated profile route filtering logic

**Created:**
- `app/routes_asl_settings.py` - API endpoints
- `app/templates/asl_settings_modal.html` - UI modal
- `create_app_settings_table.py` - Database migration

**To Modify:**
- `app/templates/administration.html` - Add settings card and include modal
- `app/__init__.py` - Import new routes

---

## API Endpoints

**GET** `/api/settings/asl-mtd-filters`
- Returns current filter settings
- Response: `{"success": true, "settings": {"exclude_12_months": true, "exclude_1_year": true}}`

**POST** `/api/settings/asl-mtd-filters`
- Updates filter settings (admin only)
- Body: `{"exclude_12_months": true, "exclude_1_year": false}`
- Response: `{"success": true, "message": "Settings updated successfully"}`

---

## Troubleshooting

**Modal doesn't open:**
- Check browser console for JavaScript errors
- Verify `asl_settings_modal.html` is included in administration.html

**Settings don't save:**
- Check that you're logged in as an admin
- Verify API endpoints are accessible
- Check Flask logs for errors

**ASL MTD count doesn't change:**
- Settings only affect future profile page loads
- Refresh the profile page after changing settings
- Verify settings were saved (check database or use GET endpoint)
