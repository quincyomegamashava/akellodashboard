# Duplicate ID Checker Feature

## Overview
This feature allows administrators to quickly identify duplicate ASL School IDs and Library School IDs in the Champion Schools database. IDs with value `0` are excluded from duplicate detection as they typically represent "not applicable" or unassigned values.

## Location
The Duplicate Checker is located in the **Administration** page alongside the Users and Champion Schools sections.

## How to Use

### 1. Access the Duplicate Checker
- Navigate to the **Administration** page
- Click on the **"Duplicate Checker"** orange card
- The Duplicate Checker modal will open

### 2. Check for Duplicates
- Click the **"Check for Duplicates"** button
- The system will scan all Champion School records
- Results will be displayed in seconds

### 3. Review Results

#### If No Duplicates Found:
- A green success message will appear
- Confirmation that all ASL and Library IDs are unique

#### If Duplicates Found:
- **Red Alert Sections** appear showing:
  - Number of duplicate IDs found
  - Detailed table for each duplicate type (ASL and/or Library)

- **Each duplicate entry shows:**
  - The duplicate ID value
  - Count (how many times it appears)
  - List of Champions using that ID
  - List of Schools associated with that ID
  - Provinces where duplicates occur

- **Visual Highlighting:**
  - Duplicate IDs are highlighted in **red** with a pink background in the results table
  - Duplicate IDs are also highlighted in the main **Champion Schools table** for easy cross-reference

### 4. Fix Duplicates
After identifying duplicates:
1. Close the Duplicate Checker modal
2. Open the Champion Schools modal
3. The duplicate IDs will be highlighted in red
4. Edit the conflicting records to resolve duplicates
5. Click "Save" to update each record
6. Re-run the duplicate checker to verify fixes

## Features

### Separate Tracking
- **ASL ID Duplicates** and **Library ID Duplicates** are checked independently
- Each type has its own section in the results

### Smart Filtering
- IDs with value `0` are automatically excluded
- Empty/null IDs are ignored
- Only meaningful duplicates are reported

### Visual Highlighting
- Duplicate cells in the Champion Schools table are:
  - Background: Light red (`#fee2e2`)
  - Text: Bold and red (`#dc2626`)
- Easy to spot at a glance

### Detailed Information
For each duplicate, you can see:
- Which champions have the duplicate ID
- Which schools are affected
- Geographic distribution (provinces)

## Use Cases

1. **Data Quality Checks**
   - Regular audits to ensure data integrity
   - Validate bulk uploads didn't create duplicates

2. **Merge Detection**
   - Identify records that might need to be merged
   - Find potential data entry errors

3. **School ID Management**
   - Ensure each school has unique identifiers
   - Prevent conflicts in external system integrations

4. **Before Reporting**
   - Clean data before generating reports
   - Ensure accurate analytics

## Technical Details

### How It Works
1. Scans all Champion School records in the DOM
2. Builds maps of ASL and Library IDs
3. Identifies IDs appearing more than once
4. Highlights cells in the main table
5. Displays detailed breakdown in modal

### Performance
- Client-side processing (instant results)
- No server calls required
- Works with any number of records

### Data Safety
- Read-only operation
- Does not modify any data
- Safe to run multiple times

## Best Practices

1. **Run regularly** after:
   - Bulk CSV uploads
   - Manual data entry sessions
   - Data migrations

2. **Document duplicates** before fixing:
   - Take note of which records have duplicates
   - Determine the correct ID to keep

3. **Verify after fixing**:
   - Always re-run the checker after corrections
   - Confirm no new duplicates were introduced

4. **Use with Champion Schools modal**:
   - Keep both modals handy
   - Checker identifies, Champion Schools modal fixes

## Notes

- Highlights persist until the Champion Schools modal is closed and reopened
- Re-running the checker clears previous highlights
- IDs equal to `0` are intentionally ignored
- The feature works entirely in the browser (no database queries)
