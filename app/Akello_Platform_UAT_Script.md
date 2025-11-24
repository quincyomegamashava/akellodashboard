# Akello Platform - User Acceptance Test (UAT) Script

## Document Information
- **Platform**: Akello Educational Dashboard
- **Version**: Current
- **Test Environment**: [To be filled by tester]
- **Tester**: [To be filled]
- **Date**: [To be filled]
- **Status**: [Pass/Fail/Pending]

---

## Test Overview
This UAT script covers all major functionality areas of the Akello Platform including:
1. Authentication & User Management
2. Dashboard Analytics & Reporting
3. Project Management & Planning
4. Educational Monitoring & Tracking
5. Administrative Functions
6. Data Export & Reporting

---

## Test Prerequisites
- [ ] Platform is deployed and accessible
- [ ] Test user accounts are available with different privilege levels
- [ ] Database connections are active (Ruzivo & Akello Library)
- [ ] Test data is available for analytics features
- [ ] Browser developer tools accessible for debugging

---

## UAT Test Cases

### 1. Authentication & User Management

#### Test 1.1: User Login
**Test ID**: UAT-001  
**Objective**: Verify user can login with valid credentials  
**Priority**: High  

**Test Steps**:
1. Navigate to login page
2. Enter valid username and password
3. Click login button
4. Verify successful login and redirect to dashboard

**Expected Result**: User should be logged in and redirected to the overview dashboard  
**Test Data**: Valid username/password combinations  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 1.2: Invalid Login
**Test ID**: UAT-002  
**Objective**: Verify error handling for invalid credentials  
**Priority**: High  

**Test Steps**:
1. Navigate to login page
2. Enter invalid username/password
3. Click login button
4. Verify error message is displayed

**Expected Result**: Error message displayed, user remains on login page  
**Test Data**: Invalid credentials  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 1.3: Password Reset
**Test ID**: UAT-003  
**Objective**: Verify password reset functionality  
**Priority**: Medium  

**Test Steps**:
1. Navigate to "Forgot Password" link
2. Enter valid email address
3. Submit password reset request
4. Check email for reset link
5. Follow reset process

**Expected Result**: Password reset email sent, user can reset password  
**Test Data**: Valid user email  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 1.4: User Registration
**Test ID**: UAT-004  
**Objective**: Verify new user registration  
**Priority**: Medium  

**Test Steps**:
1. Navigate to registration page
2. Fill in all required fields (username, email, password, firstname, lastname, role)
3. Submit registration form
4. Verify successful registration

**Expected Result**: User account created successfully  
**Test Data**: New user information  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 1.5: User Logout
**Test ID**: UAT-005  
**Objective**: Verify user logout functionality  
**Priority**: Medium  

**Test Steps**:
1. Login as valid user
2. Click logout button/link
3. Verify session is terminated
4. Attempt to access protected pages

**Expected Result**: User logged out, redirected to login page  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

### 2. Dashboard Analytics & Reporting

#### Test 2.1: Overview Dashboard Load
**Test ID**: UAT-006  
**Objective**: Verify overview dashboard loads with charts  
**Priority**: High  

**Test Steps**:
1. Login as authorized user
2. Navigate to overview page
3. Verify page loads completely
4. Check that line chart and bar chart are displayed
5. Verify data is populated in charts

**Expected Result**: Dashboard loads with visible line and bar charts showing platform usage data  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 2.2: Analytics Data API
**Test ID**: UAT-007  
**Objective**: Verify analytics API returns correct data  
**Priority**: High  

**Test Steps**:
1. Open browser developer tools
2. Navigate to overview dashboard
3. Check Network tab for API call to `/api/platforms_overall_yearly`
4. Verify API returns JSON data
5. Check response structure includes monthly_usage, yearly_totals, year

**Expected Result**: API returns properly formatted JSON data  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 2.3: Akello Analytics Page
**Test ID**: UAT-008  
**Objective**: Verify Akello Analytics page functionality  
**Priority**: Medium  

**Test Steps**:
1. Navigate to Akello Analytics page
2. Verify page loads without errors
3. Check data visualization elements
4. Test any interactive features

**Expected Result**: Analytics page displays relevant educational data  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 2.4: Province Statistics
**Test ID**: UAT-009  
**Objective**: Verify province-level statistics display  
**Priority**: Medium  

**Test Steps**:
1. Navigate to province statistics page
2. Verify province data loads
3. Check data accuracy and formatting
4. Test filtering/selection features if available

**Expected Result**: Province statistics display correctly with accurate data  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 2.5: School Profile Usage
**Test ID**: UAT-010  
**Objective**: Verify school-specific usage analytics  
**Priority**: Medium  

**Test Steps**:
1. Navigate to school profile usage page
2. Select a specific school
3. Verify usage data displays
4. Check data completeness and accuracy

**Expected Result**: School-specific usage data displays correctly  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

### 3. Project Management & Planning

#### Test 3.1: Create New Workspace
**Test ID**: UAT-011  
**Objective**: Verify workspace creation functionality  
**Priority**: High  

**Test Steps**:
1. Navigate to workspaces page
2. Click "Create New Workspace"
3. Fill in workspace details (name, description)
4. Submit workspace creation form
5. Verify workspace appears in list

**Expected Result**: New workspace created and visible in workspace list  
**Test Data**: Workspace name and description  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 3.2: Project Planning Tool
**Test ID**: UAT-012  
**Objective**: Verify project planning functionality  
**Priority**: High  

**Test Steps**:
1. Navigate to "A Plan for Projects" page
2. Create new project within workspace
3. Add project details (title, description, dates)
4. Add team members to project
5. Verify project is saved correctly

**Expected Result**: Project created with all details saved  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 3.3: Task Management
**Test ID**: UAT-013  
**Objective**: Verify task creation and management  
**Priority**: High  

**Test Steps**:
1. Open existing project
2. Create new task within project
3. Assign task to team member
4. Set task status and due date
5. Update task status
6. Verify all changes are saved

**Expected Result**: Tasks can be created, assigned, and updated successfully  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 3.4: Workspace Collaboration
**Test ID**: UAT-014  
**Objective**: Verify team collaboration features  
**Priority**: Medium  

**Test Steps**:
1. Create workspace as one user
2. Add team members to workspace
3. Login as different team member
4. Verify access to shared workspace
5. Test collaborative editing capabilities

**Expected Result**: Team members can collaborate on shared workspaces  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

### 4. Educational Monitoring & Tracking

#### Test 4.1: Monitoring Dashboard
**Test ID**: UAT-015  
**Objective**: Verify educational monitoring dashboard  
**Priority**: High  

**Test Steps**:
1. Navigate to monitoring dashboard
2. Verify real-time data displays
3. Check student activity metrics
4. Verify platform usage statistics
5. Test data refresh functionality

**Expected Result**: Monitoring dashboard shows current educational platform activity  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 4.2: Champion Schools Tracking
**Test ID**: UAT-016  
**Objective**: Verify champion schools data management  
**Priority**: Medium  

**Test Steps**:
1. Navigate to champion schools section
2. Add new champion school data
3. Update existing school information
4. Verify data validation rules
5. Export champion school data

**Expected Result**: Champion school data can be managed and exported  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 4.3: Student Activity Tracking
**Test ID**: UAT-017  
**Objective**: Verify student activity monitoring  
**Priority**: High  

**Test Steps**:
1. Access student activity reports
2. Filter by date range
3. Filter by school/province
4. Verify activity data accuracy
5. Export activity reports

**Expected Result**: Student activity data displays accurately with filtering options  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 4.4: Library Usage Analytics
**Test ID**: UAT-018  
**Objective**: Verify Akello Library usage tracking  
**Priority**: Medium  

**Test Steps**:
1. Navigate to library analytics
2. Check book allocation reports
3. Verify usage statistics
4. Test filtering and sorting options
5. Export library usage data

**Expected Result**: Library usage data displays with export capabilities  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

### 5. Administrative Functions

#### Test 5.1: User Management (Admin)
**Test ID**: UAT-019  
**Objective**: Verify admin user management capabilities  
**Priority**: High  

**Test Steps**:
1. Login as admin user
2. Navigate to user management section
3. View list of all users
4. Edit user privileges
5. Deactivate/activate user account
6. Delete test user account

**Expected Result**: Admin can manage all user accounts and privileges  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 5.2: Privilege Management
**Test ID**: UAT-020  
**Objective**: Verify role-based access control  
**Priority**: High  

**Test Steps**:
1. Login as user with different privilege levels
2. Attempt to access admin-only features
3. Verify proper access restrictions
4. Test privilege escalation prevention
5. Verify privilege inheritance

**Expected Result**: Users can only access features appropriate to their privilege level  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 5.3: System Settings
**Test ID**: UAT-021  
**Objective**: Verify system configuration options  
**Priority**: Medium  

**Test Steps**:
1. Navigate to settings page
2. Update configuration parameters
3. Save changes
4. Verify changes take effect
5. Test settings validation

**Expected Result**: System settings can be updated and saved  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 5.4: Database Management
**Test ID**: UAT-022  
**Objective**: Verify database interface functionality  
**Priority**: Medium  

**Test Steps**:
1. Access database interface page
2. Test database connectivity status
3. Verify data synchronization
4. Check error handling for connection issues
5. Test database query execution

**Expected Result**: Database interface shows connection status and allows basic management  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

### 6. Data Export & Reporting

#### Test 6.1: Weekly Reports Generation
**Test ID**: UAT-023  
**Objective**: Verify weekly report creation and export  
**Priority**: Medium  

**Test Steps**:
1. Navigate to weekly reports section
2. Create new weekly report
3. Fill in report details (work done, next week, challenges)
4. Submit report
5. Export report to PDF/Excel format

**Expected Result**: Weekly reports can be created and exported  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 6.2: CSV Data Upload
**Test ID**: UAT-024  
**Objective**: Verify CSV upload functionality  
**Priority**: Medium  

**Test Steps**:
1. Navigate to CSV upload feature
2. Select properly formatted CSV file
3. Upload file and verify data processing
4. Check for data validation errors
5. Verify imported data appears in system

**Expected Result**: CSV data uploads successfully with proper validation  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 6.3: Analytics Export
**Test ID**: UAT-025  
**Objective**: Verify analytics data export capabilities  
**Priority**: Medium  

**Test Steps**:
1. Generate analytics report
2. Select export format (CSV, Excel, PDF)
3. Download exported file
4. Verify data completeness in export
5. Check file formatting and readability

**Expected Result**: Analytics data can be exported in multiple formats  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 6.4: Performance Targets Reporting
**Test ID**: UAT-026  
**Objective**: Verify performance targets functionality  
**Priority**: Medium  

**Test Steps**:
1. Navigate to performance targets section
2. Set new performance targets
3. Update existing targets
4. Generate performance reports
5. Export targets data

**Expected Result**: Performance targets can be managed and reported  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

### 7. Browser Compatibility & Performance

#### Test 7.1: Cross-Browser Compatibility
**Test ID**: UAT-027  
**Objective**: Verify platform works across different browsers  
**Priority**: Medium  

**Test Steps**:
1. Test core functionality in Chrome
2. Test core functionality in Firefox
3. Test core functionality in Safari
4. Test core functionality in Edge
5. Document any browser-specific issues

**Expected Result**: Platform functions consistently across major browsers  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 7.2: Mobile Responsiveness
**Test ID**: UAT-028  
**Objective**: Verify mobile device compatibility  
**Priority**: Medium  

**Test Steps**:
1. Access platform on mobile device
2. Test navigation and menu functionality
3. Verify chart and graph display on mobile
4. Test form input capabilities
5. Check responsive layout behavior

**Expected Result**: Platform is usable and functional on mobile devices  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 7.3: Performance Load Testing
**Test ID**: UAT-029  
**Objective**: Verify platform performance under load  
**Priority**: Low  

**Test Steps**:
1. Simulate multiple concurrent users
2. Monitor page load times
3. Check database query performance
4. Verify chart rendering speed
5. Test API response times

**Expected Result**: Platform maintains acceptable performance under normal load  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

### 8. Security & Error Handling

#### Test 8.1: SQL Injection Prevention
**Test ID**: UAT-030  
**Objective**: Verify protection against SQL injection  
**Priority**: High  

**Test Steps**:
1. Attempt SQL injection in login forms
2. Try SQL injection in search fields
3. Test SQL injection in data input forms
4. Verify error handling doesn't expose sensitive info
5. Check parameterized query usage

**Expected Result**: Platform prevents SQL injection attempts  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 8.2: Session Management
**Test ID**: UAT-031  
**Objective**: Verify proper session handling  
**Priority**: High  

**Test Steps**:
1. Login and verify session creation
2. Test session timeout functionality
3. Verify session invalidation on logout
4. Test concurrent session handling
5. Check session security measures

**Expected Result**: Sessions are managed securely with proper timeouts  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

#### Test 8.3: Error Page Handling
**Test ID**: UAT-032  
**Objective**: Verify proper error page display  
**Priority**: Medium  

**Test Steps**:
1. Navigate to non-existent pages (404 errors)
2. Trigger server errors (500 errors)
3. Test database connection errors
4. Verify error messages are user-friendly
5. Check error logging functionality

**Expected Result**: Errors are handled gracefully with appropriate user messages  
**Status**: [ ] Pass [ ] Fail [ ] N/A  
**Comments**: _____________________

---

## Test Summary

### Overall Test Results
- **Total Test Cases**: 32
- **Passed**: ___
- **Failed**: ___
- **Not Applicable**: ___
- **Pending**: ___

### Critical Issues Found
1. _________________________________
2. _________________________________
3. _________________________________

### Recommendations
1. _________________________________
2. _________________________________
3. _________________________________

### Sign-off
**Tester Name**: ________________________  
**Tester Signature**: ___________________  
**Date**: _______________________________  

**Development Team Lead**: ______________  
**Signature**: ___________________________  
**Date**: _______________________________  

**Project Manager**: ____________________  
**Signature**: ___________________________  
**Date**: _______________________________  

---

## Appendix

### Test Data Requirements
- Admin user credentials
- Standard user credentials
- Test school/province data
- Sample CSV files for upload
- Performance targets test data

### Known Issues Log
| Issue ID | Description | Severity | Status | Date Found |
|----------|-------------|----------|--------|------------|
| | | | | |
| | | | | |
| | | | | |

### Environment Details
- **Server Environment**: _______________
- **Database Version**: __________________
- **Python Version**: ____________________
- **Flask Version**: ______________________
- **Browser Versions Tested**: ___________

---

*This UAT script should be executed by the development team before each release to ensure platform stability and functionality.*