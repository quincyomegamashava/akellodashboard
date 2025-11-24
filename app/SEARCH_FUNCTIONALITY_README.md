# Akello Platform Search Functionality

## Overview
The Akello Platform now includes a comprehensive global search feature that allows users to quickly find content across the entire platform including users, workspaces, projects, reports, champion schools, and book allocations.

## Features

### 🔍 **Global Search Bar**
- Located in the top navigation bar (desktop only)
- Real-time search suggestions as you type
- Keyboard navigation support (arrow keys, Enter, Escape)
- Minimum 2 characters required to trigger search

### 🎯 **Search Categories**
The search functionality covers the following content types:

1. **Users** (All authenticated users)
   - Search by username, first name, last name, email, department
   - Results redirect to user profile pages
   - Excludes current user from search results

2. **Workspaces**
   - Search by workspace name and description
   - All users can find workspaces, redirects to project planning page
   - Access control handled on destination page

3. **Projects**
   - Search by project name and description
   - Only shows projects where user is a member or Admin/Manager
   - Redirects to project planning page

4. **Reports**
   - Search weekly reports by content and department
   - Users see only their own reports (unless Admin)
   - Redirects to reports page

5. **Champion Schools**
   - Search by school name and province
   - Brand Ambassadors see only their province's schools
   - Other roles see all champion schools
   - Redirects to champions page

6. **Book Allocations**
   - Search by school name, province, and allocated books
   - Excluded for Brand Ambassadors (admin feature)
   - Redirects to book allocations page

## How to Use

### 1. **Live Search Suggestions**
- Start typing in the search bar (minimum 2 characters)
- Suggestions appear in a dropdown below the search bar
- Use mouse or keyboard to navigate suggestions
- Click or press Enter to navigate directly to a result

### 2. **Full Search Results Page**
- Press Enter in the search bar or click "View all results"
- Displays comprehensive search results with highlighted matches
- Results are sorted by relevance (exact matches first)
- Each result shows title, type, description, and navigation link

### 3. **Keyboard Shortcuts**
- `↓` / `↑` - Navigate through suggestions
- `Enter` - Select highlighted suggestion or submit search
- `Escape` - Close suggestions dropdown

## Technical Implementation

### Backend (Flask)
- **Route**: `/api/search` - JSON API for live search suggestions
- **Route**: `/search` - Full search results page
- **Security**: Role-based access control for sensitive content
- **Performance**: Debounced search requests (300ms delay)
- **Limits**: Results limited to 20 items to prevent UI overload

### Frontend (JavaScript)
- Real-time search with debouncing to reduce API calls
- Keyboard navigation support
- Responsive dropdown with hover and click interactions
- Error handling for network issues
- Search term highlighting in results

### Database Queries
- Uses SQL `ILIKE` for case-insensitive partial matching
- Searches across multiple fields simultaneously using `OR` conditions
- Results sorted by relevance (exact → starts with → contains → other)

## Security & Privacy

### Access Control
- **Users**: All authenticated users can search for other users
- **Workspaces**: All users can find workspaces, access control at destination
- **Projects**: Limited to projects where user is a team member or Admin/Manager
- **Reports**: Users see only their own reports (Admin sees all)
- **Champion Schools**: Brand Ambassadors see only their province, others see all
- **Book Allocations**: Excluded for Brand Ambassadors (admin-only feature)

### Data Protection
- Search queries are logged for debugging but not stored permanently
- No sensitive information exposed in search results
- All search operations require authentication

## Error Handling

### Client-Side
- Network errors display user-friendly messages
- Invalid queries (< 2 characters) show warning messages
- Loading states provide visual feedback during searches

### Server-Side
- Database connection errors are handled gracefully
- Invalid search parameters return appropriate error responses
- Detailed error logging for debugging purposes

## Performance Considerations

### Optimization Features
- **Debounced Search**: 300ms delay prevents excessive API calls
- **Result Limits**: API returns maximum 8 suggestions, 20 full results
- **Caching**: Browser caches search results temporarily
- **Indexed Queries**: Database queries use existing indexes where possible

### Performance Tips
- Search is most effective with specific terms (2-4 words)
- Results are more relevant when searching exact names or titles
- Use filters on the dedicated search page for refined results

## Troubleshooting

### Common Issues

1. **No Search Suggestions Appearing**
   - Ensure you've typed at least 2 characters
   - Check browser console for JavaScript errors
   - Verify network connectivity

2. **Search Returns No Results**
   - Check spelling and try different keywords
   - Ensure you have access permissions to the content
   - Try broader search terms

3. **Slow Search Performance**
   - Clear browser cache and cookies
   - Check network connection speed
   - Contact admin if database performance issues persist

### Browser Compatibility
- **Supported**: Chrome 70+, Firefox 65+, Safari 12+, Edge 79+
- **Required**: JavaScript enabled
- **Note**: Search bar is hidden on mobile devices (small/medium screens)

## Future Enhancements

### Planned Features
- Advanced search filters (date range, content type, user role)
- Search within specific modules (workspace-only search)
- Recent searches history
- Search analytics and usage statistics
- Mobile-friendly search interface

### Customization Options
- Search result templates can be customized in `templates/search_results.html`
- Search categories can be added/removed in `routes.py` global_search function
- UI styling can be modified in the base.html search styles

## API Documentation

### Search API Endpoint
```
GET /api/search?q=<search_term>

Response:
{
  "success": true,
  "results": [
    {
      "type": "user|workspace|project|report|champion|allocation",
      "id": "unique_identifier",
      "title": "Display title",
      "subtitle": "Content type description", 
      "description": "Additional context",
      "url": "Navigation URL",
      "icon": "icon_name"
    }
  ],
  "total_found": 5,
  "query": "search_term"
}
```

### Error Responses
```
{
  "success": false,
  "message": "Error description",
  "results": []
}
```

---

## Support
For technical support or feature requests related to the search functionality, contact the development team or create an issue in the project repository.

**Last Updated**: October 2024  
**Version**: 1.0.0