# Champion Schools Update Fix

## Problem
When editing ASL ID or Library ID for a champion's school in the Administration panel, the user's profile page would show zero schools and the layout would break.

## Root Cause
The issue was in the backend update logic (`/admin/champion_schools/<id>` PATCH endpoint). When trying to match which school entry to update in the JSON array, the matching logic was too simplistic and could fail to find the correct entry, causing:

1. **Failed Matches**: The school entry wasn't found, so a new duplicate entry was added
2. **Data Corruption**: The schools JSON array structure was modified incorrectly
3. **Profile Breakage**: The profile page relies on the schools JSON being properly structured with consistent field names

## What Was Fixed

### Enhanced Matching Logic (routes.py lines 1145-1182)

The update endpoint now uses a **three-strategy matching approach**:

#### Strategy 1: Match by Original IDs (Most Reliable)
- Matches schools by the original ASL and/or Library IDs sent from the frontend
- Handles cases where:
  - Both IDs match
  - One ID matches and the other is empty or "0"
  - This accounts for schools that may only have one type of ID

#### Strategy 2: Match by School Name
- If no ID match is found, tries to match by school name
- Case-insensitive comparison
- Useful when IDs are being added to a school that previously had none

#### Strategy 3: Match by New IDs
- As a fallback, tries to match using the new IDs being set
- Prevents creating duplicate entries

### Improved Update Logic
- **Preserves existing data**: Only updates fields that are actually provided
- **Handles empty values**: Doesn't overwrite existing IDs with empty strings
- **Maintains data structure**: Ensures the JSON array structure remains consistent

## Code Changes

### Before:
```python
# Simple matching that often failed
for idx, s in enumerate(schools):
    if (asl_id_orig and s_asl == asl_id_orig) or (lib_id_orig and s_lib == lib_id_orig):
        match_idx = idx
        break
```

### After:
```python
# Multi-strategy matching with proper handling of edge cases
# Strategy 1: Match by original IDs with flexible logic
if asl_id_orig or lib_id_orig:
    for idx, s in enumerate(schools):
        s_asl = str(s.get('asl_school_id') or '').strip()
        s_lib = str(s.get('library_school_id') or '').strip()
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

# Strategy 2: Match by school name
# Strategy 3: Match by new IDs
```

## Testing the Fix

### Test Case 1: Edit Existing School IDs
1. Go to Administration page
2. Open Champion Schools modal
3. Find a champion with schools
4. Edit the ASL ID or Library ID inline
5. Click "Save"
6. Go to that champion's profile (`/profile/username`)
7. **Expected**: Schools should still display correctly
8. **Expected**: Number of schools should remain the same

### Test Case 2: Add ID to School Without One
1. Find a school entry with only one ID (e.g., only ASL ID, Library ID is empty or 0)
2. Edit to add the missing ID
3. Click "Save"
4. Check profile
5. **Expected**: School should now have both IDs

### Test Case 3: Change Both IDs
1. Find a school with both IDs
2. Change both ASL ID and Library ID
3. Click "Save"
4. Check profile
5. **Expected**: School should have the new IDs, no duplicates

### Test Case 4: Edit School Name
1. Edit only the school name, leave IDs unchanged
2. Click "Save"
3. Check profile
4. **Expected**: School name updated, IDs unchanged

## Data Structure

The `ChampionSchool` model stores schools as JSON:
```json
[
  {
    "school_name": "Test School",
    "asl_school_id": "12345",
    "library_school_id": "67890"
  },
  {
    "school_name": "Another School",
    "asl_school_id": "11111",
    "library_school_id": "22222"
  }
]
```

**Key Points:**
- Each champion has ONE `ChampionSchool` record
- That record contains an array of school dictionaries
- Profile page reads this JSON to display schools
- Administration page flattens this into separate rows for editing

## Frontend (JavaScript)
The JavaScript in administration.html sends:
- `original_asl_school_id`: The ASL ID before editing (from `row.dataset.asl`)
- `original_library_school_id`: The Library ID before editing (from `row.dataset.lib`)
- `asl_school_id`: The new ASL ID
- `library_school_id`: The new Library ID
- `school_name`: The school name

This allows the backend to reliably identify which school entry to update.

## Prevention
This fix prevents:
- ❌ Creating duplicate school entries
- ❌ Losing school data when editing IDs
- ❌ Profile page breakage
- ❌ School count going to zero
- ❌ Layout distortion

## Notes
- No database migration needed (logic-only fix)
- Existing data is not affected
- Works with schools that have:
  - Both IDs
  - Only ASL ID
  - Only Library ID
  - IDs with value "0" (treated as empty)
