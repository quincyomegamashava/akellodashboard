# Collateral Request Feature

## Overview
This feature allows users to request collateral items that are marked as "available" and enables admins/managers to approve or decline these requests with reasons.

## Database Migration
Run the SQL migration to create the `collateral_requests` table:

```bash
# Apply the migration to your database
mysql -u your_user -p your_database < migrations_sql/add_collateral_requests_table.sql
```

## Features

### For All Users (Branding Tracker Tab):

1. **View Collateral Items**
   - Click "View Collateral" button
   - See all collateral items and their availability status
   - Items marked as "available" will show a "Request" button

2. **Request Collateral**
   - Click "Request" button on any available item
   - Fill in:
     - Event Details/Reason for request
     - Date needed by
   - Submit the request

3. **View My Requests**
   - Click "My Requests" button
   - See all your collateral requests
   - View request status (Pending, Approved, Declined)
   - If declined, see the decline reason

### For Admins/Managers (Brand Manager Tab):

1. **Manage Collateral Items**
   - Add new collateral items
   - Toggle item status between available/unavailable
   - Delete collateral items

2. **Manage Collateral Requests**
   - Click "Manage Requests" button
   - View all pending requests from users
   - See requester, collateral item, event details, and needed-by date
   
3. **Approve Requests**
   - Click "Approve" button on pending requests
   - Request status changes to "Approved"
   - User can see approval status

4. **Decline Requests**
   - Click "Decline" button on pending requests
   - Enter a reason for declining
   - Request status changes to "Declined"
   - User can see decline reason

## API Endpoints

### Get Collateral Requests
```
GET /api/collateral/requests
Returns: List of requests (all for admins, own for users)
```

### Create Collateral Request
```
POST /api/collateral/requests
Body: {
  "collateral_item_id": 1,
  "event_details": "School event at...",
  "needed_by_date": "2025-12-01"
}
```

### Approve Request
```
POST /api/collateral/requests/<request_id>/approve
```

### Decline Request
```
POST /api/collateral/requests/<request_id>/decline
Body: {
  "decline_reason": "Item already allocated..."
}
```

## Workflow

1. **User requests collateral**
   - User browses available collateral items
   - Submits request with event details and date
   - Request status: **Pending**

2. **Admin reviews request**
   - Admin sees all pending requests
   - Reviews event details and date needed

3. **Admin approves/declines**
   - **Approve**: Request status → **Approved**, user notified
   - **Decline**: Must provide reason, status → **Declined**, reason shown to user

4. **User checks status**
   - User views their requests
   - Sees approval status or decline reason

## Permissions

- **All authenticated users**: Can request available collateral items and view their own requests
- **Admin/Manager users**: Can manage collateral items, approve/decline requests, and view all requests

## Notes

- Only collateral items with status "available" can be requested
- Decline reason is mandatory when declining a request
- Users can only see their own requests (unless they're admins)
- Admins can see all requests from all users
