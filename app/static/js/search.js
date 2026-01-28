document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('globalSearchInput');
    const searchForm = document.getElementById('searchForm');
    const searchSuggestions = document.getElementById('searchSuggestions');
    const suggestionsList = document.getElementById('suggestionsList');

    let searchTimeout = null;
    let currentQuery = '';
    let selectedIndex = -1;
    let suggestions = [];

    // Only initialize if search elements exist (for pages that have the search bar)
    if (!searchInput || !searchSuggestions) return;

    // Search input event listeners
    searchInput.addEventListener('input', handleSearchInput);
    searchInput.addEventListener('focus', handleSearchFocus);
    searchInput.addEventListener('blur', handleSearchBlur);
    searchInput.addEventListener('keydown', handleKeyNavigation);

    // Form submission
    if (searchForm) {
        searchForm.addEventListener('submit', handleSearchSubmit);
    }

    // Click outside to close suggestions
    document.addEventListener('click', function (e) {
        const container = document.getElementById('searchContainer');
        if (container && !container.contains(e.target)) {
            hideSuggestions();
        }
    });

    function handleSearchInput(e) {
        const query = e.target.value.trim();
        currentQuery = query;
        selectedIndex = -1;

        // Clear previous timeout
        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }

        if (query.length >= 2) {
            // Debounce search to avoid too many API calls
            searchTimeout = setTimeout(() => {
                if (currentQuery === query) { // Only search if query hasn't changed
                    performLiveSearch(query);
                }
            }, 300);
        } else {
            hideSuggestions();
        }
    }

    function handleSearchFocus(e) {
        const query = e.target.value.trim();
        if (query.length >= 2 && suggestions.length > 0) {
            showSuggestions();
        }
    }

    function handleSearchBlur(e) {
        // Delay hiding suggestions to allow clicking on them
        setTimeout(() => {
            hideSuggestions();
        }, 200);
    }

    function handleKeyNavigation(e) {
        if (!suggestions.length) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
                updateSelectedSuggestion();
                break;
            case 'ArrowUp':
                e.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, -1);
                updateSelectedSuggestion();
                break;
            case 'Enter':
                if (selectedIndex >= 0) {
                    e.preventDefault();
                    navigateToSuggestion(suggestions[selectedIndex]);
                }
                break;
            case 'Escape':
                hideSuggestions();
                searchInput.blur();
                break;
        }
    }

    function handleSearchSubmit(e) {
        const query = searchInput.value.trim();
        if (query.length < 2) {
            e.preventDefault();
            // Optional: Implement a toast or alert here
            console.log('Please enter at least 2 characters to search');
            return;
        }
        // Let the form submit naturally to the search page
    }

    function performLiveSearch(query) {
        showLoadingSuggestions();

        fetch(`/api/search?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.results) {
                    suggestions = data.results.slice(0, 8); // Limit to 8 suggestions
                    displaySuggestions(suggestions, query);
                    if (suggestions.length > 0) {
                        showSuggestions();
                    } else {
                        showNoSuggestions();
                    }
                } else {
                    showErrorSuggestions();
                }
            })
            .catch(error => {
                console.error('Live search error:', error);
                showErrorSuggestions();
            });
    }

    function displaySuggestions(results, query) {
        if (!results || results.length === 0) {
            showNoSuggestions();
            return;
        }

        let html = '';
        results.forEach((result, index) => {
            const icon = getSearchIcon(result.icon);
            const isSelected = index === selectedIndex;

            html += `
            <div class="search-suggestion-item px-4 py-3 hover:bg-slate-50 cursor-pointer border-b border-slate-100 last:border-b-0 ${isSelected ? 'bg-indigo-50' : ''
                }" 
                 data-index="${index}" 
                 onclick="navigateToSuggestion(suggestions[${index}])">
                <div class="flex items-center gap-3">
                    <div class="flex-shrink-0">
                        <i class="${icon} text-slate-500"></i>
                    </div>
                    <div class="flex-grow min-w-0">
                        <div class="font-medium text-slate-900 truncate">
                            ${highlightSearchText(result.title, query)}
                        </div>
                        <div class="text-sm text-slate-500 truncate">
                            ${result.subtitle}
                        </div>
                    </div>
                    <div class="flex-shrink-0">
                        <i class="fas fa-arrow-right text-slate-300 text-xs"></i>
                    </div>
                </div>
            </div>
        `;
        });

        // Add "View all results" option
        html += `
        <div class="search-suggestion-item px-4 py-3 hover:bg-slate-50 cursor-pointer border-t border-slate-200 bg-slate-25" 
             onclick="document.getElementById('searchForm').submit()">
            <div class="flex items-center gap-3 text-indigo-600">
                <div class="flex-shrink-0">
                    <i class="fas fa-search"></i>
                </div>
                <div class="flex-grow">
                    <div class="font-medium">View all results for "${query}"</div>
                </div>
                <div class="flex-shrink-0">
                    <i class="fas fa-external-link-alt text-xs"></i>
                </div>
            </div>
        </div>
    `;

        suggestionsList.innerHTML = html;

        // Re-attach event listeners to new elements if needed, 
        // but onclick attributes handle it here.
    }

    function showLoadingSuggestions() {
        suggestionsList.innerHTML = `
        <div class="px-4 py-3 text-center">
            <i class="fas fa-spinner fa-spin text-slate-400"></i>
            <span class="ml-2 text-sm text-slate-500">Searching...</span>
        </div>
    `;
        showSuggestions();
    }

    function showNoSuggestions() {
        suggestionsList.innerHTML = `
        <div class="px-4 py-3 text-center text-sm text-slate-500">
            <i class="fas fa-search-minus text-slate-400"></i>
            <span class="ml-2">No results found</span>
        </div>
    `;
        showSuggestions();
    }

    function showErrorSuggestions() {
        suggestionsList.innerHTML = `
        <div class="px-4 py-3 text-center text-sm text-red-500">
            <i class="fas fa-exclamation-triangle text-red-400"></i>
            <span class="ml-2">Search error. Please try again.</span>
        </div>
    `;
        showSuggestions();
    }

    function showSuggestions() {
        searchSuggestions.classList.remove('hidden');
    }

    function hideSuggestions() {
        searchSuggestions.classList.add('hidden');
        selectedIndex = -1;
    }

    function updateSelectedSuggestion() {
        const items = suggestionsList.querySelectorAll('.search-suggestion-item');
        items.forEach((item, index) => {
            if (index === selectedIndex) {
                item.classList.add('bg-indigo-50');
            } else {
                item.classList.remove('bg-indigo-50');
            }
        });
    }

    function getSearchIcon(iconName) {
        const iconMap = {
            'user': 'fas fa-user',
            'folder': 'fas fa-folder',
            'clipboard': 'fas fa-clipboard-list',
            'file-text': 'fas fa-file-alt',
            'award': 'fas fa-award',
            'book': 'fas fa-book'
        };
        return iconMap[iconName] || 'fas fa-circle';
    }

    function highlightSearchText(text, query) {
        if (!text || !query) return text;

        const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
        return text.replace(regex, '<mark class="bg-yellow-200 px-1 rounded">$1</mark>');
    }

    function escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // Make suggestions available globally for onclick handlers
    window.suggestions = suggestions;
    window.navigateToSuggestion = function (suggestion) {
        if (suggestion && suggestion.url) {
            window.location.href = suggestion.url;
        }
    };
});
