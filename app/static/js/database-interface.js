/**
 * Database Interface JavaScript
 * Handles SQL Editor, Visual Query Builder, Schema Explorer, and Results Display
 */

class DatabaseInterface {
    constructor() {
        this.currentDatabase = null;
        this.databaseSchema = null;
        this.sqlEditor = null;
        this.currentResults = null;
        this.visualQueryConfig = {
            tables: [],
            columns: [],
            joins: [],
            conditions: [],
            order_by: [],
            limit: 1000
        };
        
        this.init();
    }
    
    init() {
        this.initializeComponents();
        this.setupEventListeners();
        this.loadAvailableDatabases();
    }
    
    initializeComponents() {
        // Initialize SQL Editor with Ace
        this.initializeSqlEditor();
        
        // Initialize tabs
        this.initializeTabs();
        
        // Initialize modals
        this.initializeModals();
        
        // Initialize schema tree
        this.initializeSchemaTree();
    }
    
    initializeSqlEditor() {
        try {
            // Check if Ace Editor is available
            if (typeof ace === 'undefined') {
                throw new Error('Ace Editor library not loaded');
            }
            
            // Check if the editor element exists
            const editorElement = document.getElementById('sqlEditor');
            if (!editorElement) {
                throw new Error('SQL Editor element not found');
            }
            
            console.log('Initializing Ace Editor...');
            this.sqlEditor = ace.edit("sqlEditor");
            
            // Set theme and mode
            this.sqlEditor.setTheme("ace/theme/github");
            this.sqlEditor.session.setMode("ace/mode/sql");
            
            // Configure editor options
            this.sqlEditor.setOptions({
                enableBasicAutocompletion: true,
                enableLiveAutocompletion: true,
                enableSnippets: true,
                showPrintMargin: false,
                fontSize: 14,
                wrap: true
            });
            
            // Set default query
            this.sqlEditor.setValue(`-- Welcome to the Database Query Interface
-- Select a database and write your SQL queries here
-- Example:
SELECT * FROM users LIMIT 10;`, -1);
            
            console.log('SQL Editor initialized successfully');
            
        } catch (error) {
            console.error('Error initializing SQL editor:', error);
            
            // Show detailed error message
            const errorMsg = `SQL Editor initialization failed: ${error.message}`;
            this.showNotification(errorMsg, 'error');
            
            // Create a fallback textarea if Ace Editor fails
            this.createFallbackEditor();
        }
    }
    
    initializeTabs() {
        const tabButtons = document.querySelectorAll('.tab-button');
        const tabContents = document.querySelectorAll('.tab-content');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabId = button.getAttribute('data-tab');
                
                // Update active tab
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));
                
                button.classList.add('active');
                document.getElementById(tabId).classList.add('active');
                
                // Resize editor if SQL tab is activated
                if (tabId === 'sql-editor' && this.sqlEditor) {
                    setTimeout(() => this.sqlEditor.resize(), 100);
                }
            });
        });
    }
    
    initializeModals() {
        // Close modals when clicking outside or on close button
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal.id);
                }
            });
        });
        
        document.querySelectorAll('.close-modal').forEach(button => {
            button.addEventListener('click', (e) => {
                const modal = e.target.closest('.modal');
                if (modal) {
                    this.closeModal(modal.id);
                }
            });
        });
    }
    
    initializeSchemaTree() {
        // Schema tree will be initialized when database is connected
        this.schemaTreeData = [];
    }
    
    setupEventListeners() {
        // Database connection
        document.getElementById('connectBtn').addEventListener('click', () => this.connectToDatabase());
        document.getElementById('databaseSelector').addEventListener('change', (e) => {
            const connectBtn = document.getElementById('connectBtn');
            const selectedValue = e.target.value;
            
            // Enable connect button if a database is selected and not disabled
            connectBtn.disabled = !selectedValue;
            
            // Update connect button text based on selection
            if (selectedValue) {
                const selectedOption = e.target.options[e.target.selectedIndex];
                if (selectedOption.textContent.includes('Demo Mode')) {
                    connectBtn.textContent = 'Enable Demo Mode';
                } else if (selectedOption.textContent.includes('Disconnected')) {
                    connectBtn.textContent = 'Retry Connection';
                } else {
                    connectBtn.textContent = 'Connect';
                }
            } else {
                connectBtn.textContent = 'Connect';
            }
        });
        
        // Schema refresh
        document.getElementById('refreshSchemaBtn').addEventListener('click', () => this.refreshSchema());
        
        // SQL Editor actions
        document.getElementById('executeBtn').addEventListener('click', () => this.executeQuery());
        document.getElementById('formatBtn').addEventListener('click', () => this.formatQuery());
        document.getElementById('saveQueryBtn').addEventListener('click', () => this.showSaveQueryModal());
        
        // Visual Query Builder actions
        document.getElementById('buildQueryBtn').addEventListener('click', () => this.buildVisualQuery());
        document.getElementById('executeBuiltBtn').addEventListener('click', () => this.executeVisualQuery());
        document.getElementById('clearBuilderBtn').addEventListener('click', () => this.clearVisualBuilder());
        
        // Enhanced Builder controls
        document.getElementById('addJoinBtn').addEventListener('click', () => this.addJoin());
        document.getElementById('addConditionBtn').addEventListener('click', () => this.addCondition());
        document.getElementById('addOrderBtn').addEventListener('click', () => this.addOrderBy());
        document.getElementById('addAggregationBtn').addEventListener('click', () => this.addAggregation());
        
        // Column selection controls
        document.getElementById('selectAllColumnsBtn').addEventListener('click', () => this.selectAllColumns());
        document.getElementById('clearColumnsBtn').addEventListener('click', () => this.clearColumnSelection());
        
        // Results actions
        document.getElementById('exportCsvBtn').addEventListener('click', () => this.exportResults());
        document.getElementById('copyResultsBtn').addEventListener('click', () => this.copyResults());
        
        // Save query modal
        document.getElementById('confirmSaveBtn').addEventListener('click', () => this.saveQuery());
        document.getElementById('cancelSaveBtn').addEventListener('click', () => this.closeModal('saveQueryModal'));
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.executeQuery();
                } else if (e.key === 's') {
                    e.preventDefault();
                    this.showSaveQueryModal();
                }
            }
        });
    }
    
    async loadAvailableDatabases() {
        try {
            this.showConnectionStatus('loading', 'Loading databases...');
            
            const response = await fetch('/api/databases/list');
            const data = await response.json();
            
            if (data.success) {
                this.populateDatabaseSelector(data.databases);
                this.showConnectionStatus('disconnected', 'Select a database');
            } else {
                throw new Error(data.error || 'Failed to load databases');
            }
            
        } catch (error) {
            console.error('Error loading databases:', error);
            this.showNotification('Error loading databases: ' + error.message, 'error');
            this.showConnectionStatus('disconnected', 'Error loading databases');
        }
    }
    
    populateDatabaseSelector(databases) {
        const selector = document.getElementById('databaseSelector');
        selector.innerHTML = '<option value="">Select Database...</option>';
        
        // Count connected databases
        const connectedDbs = Object.values(databases).filter(db => db.status === 'connected');
        const totalDbs = Object.values(databases).length;
        
        if (connectedDbs.length === 0) {
            const noDbOption = document.createElement('option');
            noDbOption.value = '';
            noDbOption.textContent = 'No databases available';
            noDbOption.disabled = true;
            selector.appendChild(noDbOption);
            
            // Show help message
            this.showNotification(
                'No database connections available. Check your database configuration.',
                'warning'
            );
        }
        
        Object.values(databases).forEach(db => {
            const option = document.createElement('option');
            option.value = db.key;
            
            // Create descriptive text based on status
            let statusText = '';
            switch(db.status) {
                case 'connected':
                    statusText = '✓ Connected';
                    break;
                case 'disconnected':
                    statusText = '✗ Disconnected';
                    break;
                case 'connection_error':
                    statusText = '⚠ Connection Error';
                    break;
                case 'demo':
                    statusText = '🔧 Demo Mode';
                    break;
                default:
                    statusText = db.status;
            }
            
            option.textContent = `${db.name} - ${statusText}`;
            
            // Only disable if it's truly unavailable (not demo mode)
            option.disabled = (db.status === 'disconnected' || db.status === 'connection_error');
            
            // Add tooltip with more info
            if (db.host && db.database) {
                option.title = `Host: ${db.host}, Database: ${db.database}`;
            } else if (db.status === 'demo') {
                option.title = 'Demo mode - configure database connections to use real databases';
            }
            
            selector.appendChild(option);
        });
        
        // Update connection count in status
        if (connectedDbs.length > 0) {
            this.showConnectionStatus('disconnected', `${connectedDbs.length}/${totalDbs} databases available`);
        }
    }
    
    async connectToDatabase() {
        const selectedDb = document.getElementById('databaseSelector').value;
        if (!selectedDb) {
            this.showNotification('Please select a database', 'warning');
            return;
        }
        
        try {
            this.showConnectionStatus('connecting', 'Connecting...');
            
            // Handle demo mode differently
            if (selectedDb === 'demo') {
                this.currentDatabase = selectedDb;
                this.showConnectionStatus('demo', 'Demo Mode Active');
                this.setupDemoMode();
                this.showNotification('Demo mode activated - limited functionality available', 'info');
                return;
            }
            
            // Test connection for real databases
            const response = await fetch(`/api/databases/${selectedDb}/test`);
            const data = await response.json();
            
            if (data.success) {
                this.currentDatabase = selectedDb;
                this.showConnectionStatus('connected', `Connected to ${selectedDb}`);
                await this.loadDatabaseSchema();
                this.showNotification('Connected successfully', 'success');
            } else {
                throw new Error(data.message || 'Connection failed');
            }
            
        } catch (error) {
            console.error('Connection error:', error);
            this.showNotification('Connection failed: ' + error.message, 'error');
            this.showConnectionStatus('disconnected', 'Connection failed');
        }
    }
    
    async loadDatabaseSchema() {
        if (!this.currentDatabase) return;
        
        try {
            console.log('Loading schema for database:', this.currentDatabase);
            const response = await fetch(`/api/databases/${this.currentDatabase}/tables`);
            const data = await response.json();
            
            console.log('Schema response:', data);
            
            if (data.success) {
                this.databaseSchema = data.tables;
                console.log('Schema loaded successfully:', this.databaseSchema?.length, 'tables');
                this.buildSchemaTree();
                this.populateVisualBuilder();
                this.updateSqlEditorAutocompletion();
            } else {
                throw new Error(data.error || 'Failed to load schema');
            }
            
        } catch (error) {
            console.error('Error loading schema:', error);
            this.showNotification('Error loading schema: ' + error.message, 'error');
        }
    }
    
    buildSchemaTree() {
        const treeContainer = document.getElementById('schemaTree');
        
        if (!this.databaseSchema || this.databaseSchema.length === 0) {
            treeContainer.innerHTML = '<div class="empty-state"><p>No tables found</p></div>';
            return;
        }
        
        // Build tree data
        const treeData = this.databaseSchema.map(table => ({
            id: table.name,
            text: `${table.name} (${table.row_count} rows)`,
            icon: 'fas fa-table',
            data: { type: 'table', table: table },
            children: table.columns.map(column => ({
                id: `${table.name}.${column.name}`,
                text: `${column.name} (${column.type})`,
                icon: column.primary_key ? 'fas fa-key' : 'fas fa-columns',
                data: { type: 'column', table: table.name, column: column }
            }))
        }));
        
        // Initialize or update jsTree
        if (treeContainer.classList.contains('jstree')) {
            $(treeContainer).jstree('destroy');
        }
        
        $(treeContainer).jstree({
            core: {
                data: treeData,
                themes: {
                    name: 'default',
                    responsive: true
                }
            },
            plugins: ['themes', 'types']
        });
        
        // Handle tree events
        $(treeContainer).on('dblclick.jstree', (e, data) => {
            const node = $(treeContainer).jstree('get_node', e.target);
            if (node && node.data && node.data.type === 'table') {
                this.previewTable(node.data.table.name);
            }
        });
    }
    
    showEmptyTablesContainer() {
        const tablesContainer = document.getElementById('tablesContainer');
        tablesContainer.innerHTML = '<div class="empty-state"><i class="fas fa-database"></i><p>Connect to database to select tables</p></div>';
        
        const columnsContainer = document.getElementById('columnsContainer');
        columnsContainer.innerHTML = '<div class="empty-state"><i class="fas fa-columns"></i><p>Select tables first</p></div>';
    }
    
    populateVisualBuilder() {
        if (!this.databaseSchema) {
            this.showEmptyTablesContainer();
            return;
        }
        
        console.log('Populating visual builder with schema:', this.databaseSchema);
        
        const tablesContainer = document.getElementById('tablesContainer');
        tablesContainer.innerHTML = '';
        
        // Create modern table cards
        this.databaseSchema.forEach(table => {
            const tableCard = document.createElement('div');
            tableCard.className = 'table-card';
            tableCard.setAttribute('data-table', table.name);
            tableCard.innerHTML = `
                <div class="table-header">
                    <i class="fas fa-table"></i>
                    <strong>${table.name}</strong>
                </div>
                <div class="table-meta">
                    <small>${table.row_count || 0} rows • ${table.columns.length} columns</small>
                </div>
            `;
            
            // Add click event to toggle selection
            tableCard.onclick = () => this.toggleTableSelection(table.name);
            
            tablesContainer.appendChild(tableCard);
        });
        
        // Initialize columns container
        this.updateColumnsContainer();
        
        // Update date filters and join suggestions
        this.updateDateFilters();
        this.generateJoinSuggestions();
    }
    
    toggleTableSelection(tableName) {
        console.log('Toggling table selection:', tableName);
        
        const tableCard = document.querySelector(`[data-table="${tableName}"]`);
        if (!tableCard) {
            console.error('Table card not found:', tableName);
            return;
        }
        
        tableCard.classList.toggle('selected');
        
        if (tableCard.classList.contains('selected')) {
            if (!this.visualQueryConfig.tables.includes(tableName)) {
                this.visualQueryConfig.tables.push(tableName);
                this.showNotification(`Added table: ${tableName}`, 'success');
            }
        } else {
            this.visualQueryConfig.tables = this.visualQueryConfig.tables.filter(t => t !== tableName);
            this.showNotification(`Removed table: ${tableName}`, 'info');
        }
        
        // Update dependent components
        this.updateColumnsContainer();
        this.updateDateFilters();
        this.generateJoinSuggestions();
        this.updatePreview();
    }
    
    updateColumnsContainer() {
        const columnsContainer = document.getElementById('columnsContainer');
        columnsContainer.innerHTML = '';
        
        if (this.visualQueryConfig.tables.length === 0) {
            columnsContainer.innerHTML = '<div class="empty-state">Select tables first</div>';
            return;
        }
        
        console.log('Updating columns for tables:', this.visualQueryConfig.tables);
        
        // Add "Select All" option
        const selectAllCard = document.createElement('div');
        selectAllCard.className = 'column-card';
        selectAllCard.setAttribute('data-column', '*');
        selectAllCard.innerHTML = `
            <div class="column-name">* (All Columns)</div>
            <div class="column-type">All available columns</div>
        `;
        selectAllCard.onclick = () => this.toggleColumnSelection('*');
        columnsContainer.appendChild(selectAllCard);
        
        // Add columns from selected tables with modern cards
        this.visualQueryConfig.tables.forEach(tableName => {
            const table = this.databaseSchema.find(t => t.name === tableName);
            if (table) {
                table.columns.forEach(column => {
                    const columnCard = document.createElement('div');
                    columnCard.className = 'column-card';
                    const fullColumnName = `${tableName}.${column.name}`;
                    columnCard.setAttribute('data-column', fullColumnName);
                    
                    // Add icons for primary keys and other special columns
                    let icon = 'fas fa-columns';
                    if (column.primary_key) {
                        icon = 'fas fa-key';
                    } else if (column.type.toLowerCase().includes('date') || column.type.toLowerCase().includes('time')) {
                        icon = 'fas fa-calendar';
                    } else if (column.type.toLowerCase().includes('text') || column.type.toLowerCase().includes('varchar')) {
                        icon = 'fas fa-font';
                    } else if (column.type.toLowerCase().includes('int') || column.type.toLowerCase().includes('decimal')) {
                        icon = 'fas fa-hashtag';
                    }
                    
                    columnCard.innerHTML = `
                        <div class="column-name">
                            <i class="${icon}"></i>
                            ${column.name}
                        </div>
                        <div class="column-type">${column.type}${!column.nullable ? ' NOT NULL' : ''}</div>
                    `;
                    
                    columnCard.onclick = () => this.toggleColumnSelection(fullColumnName);
                    columnsContainer.appendChild(columnCard);
                });
            }
        });
    }
    
    toggleColumnSelection(columnName) {
        console.log('Toggling column selection:', columnName);
        
        const columnCard = document.querySelector(`[data-column="${columnName}"]`);
        if (!columnCard) {
            console.error('Column card not found:', columnName);
            return;
        }
        
        columnCard.classList.toggle('selected');
        
        if (columnCard.classList.contains('selected')) {
            // If selecting all columns, clear other selections first
            if (columnName === '*') {
                this.visualQueryConfig.columns = ['*'];
                // Remove selected class from other column cards
                document.querySelectorAll('.column-card[data-column]:not([data-column="*"])').forEach(card => {
                    card.classList.remove('selected');
                });
                this.showNotification('Selected all columns', 'success');
            } else {
                // If selecting specific column and * is selected, remove * first
                if (this.visualQueryConfig.columns.includes('*')) {
                    this.visualQueryConfig.columns = [];
                    document.querySelector('.column-card[data-column="*"]')?.classList.remove('selected');
                }
                if (!this.visualQueryConfig.columns.includes(columnName)) {
                    this.visualQueryConfig.columns.push(columnName);
                    this.showNotification(`Added column: ${columnName}`, 'success');
                }
            }
        } else {
            this.visualQueryConfig.columns = this.visualQueryConfig.columns.filter(c => c !== columnName);
            this.showNotification(`Removed column: ${columnName}`, 'info');
        }
        
        this.updatePreview();
    }
    
    addJoin() {
        const joinsContainer = document.getElementById('joinsContainer');
        const joinItem = document.createElement('div');
        joinItem.className = 'join-item';
        
        joinItem.innerHTML = `
            <select class="join-type">
                <option value="INNER">INNER JOIN</option>
                <option value="LEFT">LEFT JOIN</option>
                <option value="RIGHT">RIGHT JOIN</option>
                <option value="FULL">FULL JOIN</option>
            </select>
            <select class="join-table">
                <option value="">Select table...</option>
                ${this.databaseSchema.map(t => `<option value="${t.name}">${t.name}</option>`).join('')}
            </select>
            <span>ON</span>
            <input type="text" class="join-condition" placeholder="table1.id = table2.id">
            <button class="btn-danger btn-small" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        joinsContainer.appendChild(joinItem);
    }
    
    addCondition() {
        const conditionsContainer = document.getElementById('conditionsContainer');
        const conditionItem = document.createElement('div');
        conditionItem.className = 'condition-item';
        
        conditionItem.innerHTML = `
            <input type="text" class="condition-column" placeholder="Column name">
            <select class="condition-operator">
                <option value="=">=</option>
                <option value="!="!=</option>
                <option value=">">></option>
                <option value="<"><</option>
                <option value=">=">>=</option>
                <option value="<="><=</option>
                <option value="LIKE">LIKE</option>
                <option value="IN">IN</option>
                <option value="IS NULL">IS NULL</option>
                <option value="IS NOT NULL">IS NOT NULL</option>
            </select>
            <input type="text" class="condition-value" placeholder="Value">
            <button class="btn-danger btn-small" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        conditionsContainer.appendChild(conditionItem);
    }
    
    addOrderBy() {
        const orderContainer = document.getElementById('orderbyContainer');
        const orderItem = document.createElement('div');
        orderItem.className = 'order-item';
        
        orderItem.innerHTML = `
            <input type="text" class="order-column" placeholder="Column name">
            <select class="order-direction">
                <option value="ASC">ASC</option>
                <option value="DESC">DESC</option>
            </select>
            <button class="btn-danger btn-small" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        orderContainer.appendChild(orderItem);
    }
    
    async buildVisualQuery() {
        try {
            const queryConfig = this.collectVisualQueryConfig();
            
            const response = await fetch(`/api/databases/${this.currentDatabase}/build-query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(queryConfig)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Switch to SQL editor and show generated query
                document.querySelector('[data-tab="sql-editor"]').click();
                this.sqlEditor.setValue(data.query, -1);
                this.showNotification('Query generated successfully', 'success');
            } else {
                throw new Error(data.error || 'Failed to build query');
            }
            
        } catch (error) {
            console.error('Error building query:', error);
            this.showNotification('Error building query: ' + error.message, 'error');
        }
    }
    
    collectVisualQueryConfig() {
        const config = {
            type: 'SELECT',
            tables: this.visualQueryConfig.tables,
            columns: this.visualQueryConfig.columns.length > 0 ? this.visualQueryConfig.columns : ['*'],
            joins: [],
            conditions: [],
            order_by: [],
            limit: parseInt(document.getElementById('queryLimit').value) || 1000
        };
        
        // Collect joins
        document.querySelectorAll('.join-item').forEach(item => {
            const type = item.querySelector('.join-type').value;
            const table = item.querySelector('.join-table').value;
            const condition = item.querySelector('.join-condition').value;
            
            if (table && condition) {
                config.joins.push({ type, table, condition });
            }
        });
        
        // Collect conditions
        document.querySelectorAll('.condition-item').forEach(item => {
            const column = item.querySelector('.condition-column').value;
            const operator = item.querySelector('.condition-operator').value;
            const value = item.querySelector('.condition-value').value;
            
            if (column && (value || operator.includes('NULL'))) {
                config.conditions.push({ column, operator, value });
            }
        });
        
        // Collect order by
        document.querySelectorAll('.order-item').forEach(item => {
            const column = item.querySelector('.order-column').value;
            const direction = item.querySelector('.order-direction').value;
            
            if (column) {
                config.order_by.push({ column, direction });
            }
        });
        
        return config;
    }
    
    async executeVisualQuery() {
        try {
            const queryConfig = this.collectVisualQueryConfig();
            
            const response = await fetch(`/api/databases/${this.currentDatabase}/execute-built-query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(queryConfig)
            });
            
            const data = await response.json();
            this.handleQueryResults(data);
            
            if (data.success && data.generated_query) {
                // Show generated query in SQL editor
                this.sqlEditor.setValue(data.generated_query, -1);
            }
            
        } catch (error) {
            console.error('Error executing visual query:', error);
            this.showNotification('Error executing query: ' + error.message, 'error');
        }
    }
    
    clearVisualBuilder() {
        this.visualQueryConfig = {
            tables: [],
            columns: [],
            joins: [],
            conditions: [],
            order_by: [],
            limit: 1000
        };
        
        // Clear UI
        document.querySelectorAll('.table-item, .column-item').forEach(item => {
            item.classList.remove('selected');
        });
        
        document.getElementById('joinsContainer').innerHTML = `
            <button id="addJoinBtn" class="btn-secondary">
                <i class="fas fa-plus"></i> Add Join
            </button>
        `;
        
        document.getElementById('conditionsContainer').innerHTML = `
            <button id="addConditionBtn" class="btn-secondary">
                <i class="fas fa-plus"></i> Add Condition
            </button>
        `;
        
        document.getElementById('orderbyContainer').innerHTML = `
            <button id="addOrderBtn" class="btn-secondary">
                <i class="fas fa-plus"></i> Add Order
            </button>
        `;
        
        // Re-bind events
        document.getElementById('addJoinBtn').addEventListener('click', () => this.addJoin());
        document.getElementById('addConditionBtn').addEventListener('click', () => this.addCondition());
        document.getElementById('addOrderBtn').addEventListener('click', () => this.addOrderBy());
        
        this.updateColumnsContainer();
    }
    
    async executeQuery() {
        if (!this.currentDatabase) {
            this.showNotification('Please connect to a database first', 'warning');
            return;
        }
        
        const query = this.sqlEditor.getValue().trim();
        if (!query) {
            this.showNotification('Please enter a query', 'warning');
            return;
        }
        
        try {
            // Handle demo mode with mock data
            if (this.currentDatabase === 'demo') {
                this.handleDemoQuery(query);
                return;
            }
            
            const allowModifications = document.getElementById('allowModifications').checked;
            const limit = parseInt(document.getElementById('queryLimit').value) || 1000;
            
            const response = await fetch(`/api/databases/${this.currentDatabase}/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query,
                    allow_modifications: allowModifications,
                    limit
                })
            });
            
            const data = await response.json();
            this.handleQueryResults(data);
            
        } catch (error) {
            console.error('Error executing query:', error);
            this.showNotification('Error executing query: ' + error.message, 'error');
        }
    }
    
    handleQueryResults(data) {
        console.log('Handling query results:', data);
        
        // Switch to results tab
        document.querySelector('[data-tab="results"]').click();
        
        const resultsContainer = document.getElementById('resultsContainer');
        const resultsInfo = document.getElementById('resultsInfo');
        const exportBtn = document.getElementById('exportCsvBtn');
        const copyBtn = document.getElementById('copyResultsBtn');
        
        if (data.success) {
            this.currentResults = data;
            
            if (data.type === 'select') {
                resultsInfo.textContent = data.message;
                this.displayTableResults(data, resultsContainer);
                exportBtn.disabled = false;
                copyBtn.disabled = false;
            } else {
                resultsInfo.textContent = data.message;
                resultsContainer.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-check-circle fa-3x" style="color: #27ae60;"></i>
                        <p>${data.message}</p>
                    </div>
                `;
                exportBtn.disabled = true;
                copyBtn.disabled = true;
            }
            
            this.showNotification(data.message, 'success');
            
        } else {
            resultsInfo.textContent = 'Error';
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-exclamation-triangle fa-3x" style="color: #e74c3c;"></i>
                    <p>Query Error</p>
                    <pre style="text-align: left; background: #f8f9fa; padding: 1rem; border-radius: 4px; margin-top: 1rem;">${data.error || data.message}</pre>
                </div>
            `;
            exportBtn.disabled = true;
            copyBtn.disabled = true;
            
            this.showNotification('Query failed: ' + (data.error || data.message), 'error');
        }
    }
    
    displayTableResults(data, container) {
        console.log('Displaying table results:', {
            columns: data.columns,
            dataLength: data.data ? data.data.length : 0,
            firstRow: data.data && data.data.length > 0 ? data.data[0] : null
        });
        
        if (!data.columns || !data.data || data.data.length === 0) {
            console.log('No results to display');
            container.innerHTML = '<div class="empty-state"><p>No results found</p></div>';
            return;
        }
        
        const table = document.createElement('table');
        table.className = 'results-table';
        
        // Create header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        
        data.columns.forEach(column => {
            const th = document.createElement('th');
            th.textContent = column;
            headerRow.appendChild(th);
        });
        
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Create body
        const tbody = document.createElement('tbody');
        
        data.data.forEach(row => {
            const tr = document.createElement('tr');
            
            data.columns.forEach(column => {
                const td = document.createElement('td');
                const value = row[column];
                td.textContent = value !== null ? value : 'NULL';
                if (value === null) {
                    td.style.fontStyle = 'italic';
                    td.style.color = '#999';
                }
                tr.appendChild(td);
            });
            
            tbody.appendChild(tr);
        });
        
        table.appendChild(tbody);
        container.innerHTML = '';
        container.appendChild(table);
    }
    
    async previewTable(tableName) {
        try {
            const response = await fetch(`/api/databases/${this.currentDatabase}/tables/${tableName}/sample?limit=100`);
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('tablePreviewTitle').textContent = `Table Preview: ${tableName}`;
                const content = document.getElementById('tablePreviewContent');
                this.displayTableResults(data, content);
                this.showModal('tablePreviewModal');
            } else {
                throw new Error(data.error || 'Failed to load table preview');
            }
            
        } catch (error) {
            console.error('Error loading table preview:', error);
            this.showNotification('Error loading table preview: ' + error.message, 'error');
        }
    }
    
    formatQuery() {
        if (!this.sqlEditor) return;
        
        // Simple SQL formatting
        let query = this.sqlEditor.getValue();
        query = query
            .replace(/\bSELECT\b/gi, 'SELECT')
            .replace(/\bFROM\b/gi, '\nFROM')
            .replace(/\bWHERE\b/gi, '\nWHERE')
            .replace(/\bJOIN\b/gi, '\nJOIN')
            .replace(/\bINNER JOIN\b/gi, '\nINNER JOIN')
            .replace(/\bLEFT JOIN\b/gi, '\nLEFT JOIN')
            .replace(/\bRIGHT JOIN\b/gi, '\nRIGHT JOIN')
            .replace(/\bORDER BY\b/gi, '\nORDER BY')
            .replace(/\bGROUP BY\b/gi, '\nGROUP BY')
            .replace(/\bHAVING\b/gi, '\nHAVING')
            .replace(/\bLIMIT\b/gi, '\nLIMIT');
        
        this.sqlEditor.setValue(query, -1);
        this.showNotification('Query formatted', 'success');
    }
    
    showSaveQueryModal() {
        document.getElementById('queryName').value = '';
        document.getElementById('queryDescription').value = '';
        this.showModal('saveQueryModal');
    }
    
    async saveQuery() {
        const name = document.getElementById('queryName').value.trim();
        const description = document.getElementById('queryDescription').value.trim();
        const query = this.sqlEditor.getValue().trim();
        
        if (!name || !query) {
            this.showNotification('Please provide a name and query', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/databases/save-query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name,
                    description,
                    query,
                    database: this.currentDatabase
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification('Query saved successfully', 'success');
                this.closeModal('saveQueryModal');
            } else {
                throw new Error(data.error || 'Failed to save query');
            }
            
        } catch (error) {
            console.error('Error saving query:', error);
            this.showNotification('Error saving query: ' + error.message, 'error');
        }
    }
    
    async exportResults() {
        if (!this.currentResults || this.currentResults.type !== 'select') {
            this.showNotification('No results to export', 'warning');
            return;
        }
        
        try {
            const response = await fetch(`/api/databases/${this.currentDatabase}/export`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    results: this.currentResults
                })
            });
            
            if (response.ok) {
                // Handle file download
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = response.headers.get('content-disposition')?.split('filename=')[1] || 'query_results.csv';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                this.showNotification('Results exported successfully', 'success');
            } else {
                const data = await response.json();
                throw new Error(data.error || 'Export failed');
            }
            
        } catch (error) {
            console.error('Error exporting results:', error);
            this.showNotification('Error exporting results: ' + error.message, 'error');
        }
    }
    
    copyResults() {
        if (!this.currentResults || this.currentResults.type !== 'select') {
            this.showNotification('No results to copy', 'warning');
            return;
        }
        
        try {
            // Create CSV format
            const csvContent = [
                this.currentResults.columns.join('\t'),
                ...this.currentResults.data.map(row => 
                    this.currentResults.columns.map(col => row[col] || '').join('\t')
                )
            ].join('\n');
            
            // Copy to clipboard
            navigator.clipboard.writeText(csvContent).then(() => {
                this.showNotification('Results copied to clipboard', 'success');
            });
            
        } catch (error) {
            console.error('Error copying results:', error);
            this.showNotification('Error copying results', 'error');
        }
    }
    
    async refreshSchema() {
        if (!this.currentDatabase) return;
        
        try {
            await this.loadDatabaseSchema();
            this.showNotification('Schema refreshed', 'success');
        } catch (error) {
            console.error('Error refreshing schema:', error);
            this.showNotification('Error refreshing schema', 'error');
        }
    }
    
    setupDemoMode() {
        // Create demo schema data
        this.databaseSchema = [
            {
                name: 'users',
                columns: [
                    { name: 'id', type: 'INT', nullable: false, primary_key: true },
                    { name: 'username', type: 'VARCHAR(50)', nullable: false, primary_key: false },
                    { name: 'email', type: 'VARCHAR(100)', nullable: false, primary_key: false },
                    { name: 'created_at', type: 'DATETIME', nullable: false, primary_key: false }
                ],
                primary_keys: ['id'],
                foreign_keys: [],
                row_count: 1000
            },
            {
                name: 'posts',
                columns: [
                    { name: 'id', type: 'INT', nullable: false, primary_key: true },
                    { name: 'title', type: 'VARCHAR(200)', nullable: false, primary_key: false },
                    { name: 'content', type: 'TEXT', nullable: true, primary_key: false },
                    { name: 'user_id', type: 'INT', nullable: false, primary_key: false },
                    { name: 'created_at', type: 'DATETIME', nullable: false, primary_key: false }
                ],
                primary_keys: ['id'],
                foreign_keys: [{ column: 'user_id', references: 'users.id' }],
                row_count: 2500
            }
        ];
        
        this.buildSchemaTree();
        this.populateVisualBuilder();
        this.updateSqlEditorAutocompletion();
        
        // Update SQL editor with demo query
        if (this.sqlEditor && this.sqlEditor.setValue) {
            this.sqlEditor.setValue(`-- Demo Mode Active - Sample Database Schema
-- Tables available: users, posts
-- Try these example queries:

SELECT * FROM users LIMIT 10;

-- Join example:
SELECT u.username, p.title 
FROM users u 
JOIN posts p ON u.id = p.user_id 
LIMIT 5;`, -1);
        }
    }
    
    updateSqlEditorAutocompletion() {
        if (!this.sqlEditor || !this.databaseSchema) return;
        
        try {
            const completions = [];
            
            // Add table names
            this.databaseSchema.forEach(table => {
                completions.push({
                    name: table.name,
                    value: table.name,
                    score: 1000,
                    meta: 'table'
                });
                
                // Add column names
                table.columns.forEach(column => {
                    completions.push({
                        name: `${table.name}.${column.name}`,
                        value: `${table.name}.${column.name}`,
                        score: 900,
                        meta: 'column'
                    });
                    
                    completions.push({
                        name: column.name,
                        value: column.name,
                        score: 800,
                        meta: 'column'
                    });
                });
            });
            
            // Add custom completer
            const customCompleter = {
                getCompletions: function(editor, session, pos, prefix, callback) {
                    callback(null, completions);
                }
            };
            
            this.sqlEditor.completers = [customCompleter];
            
        } catch (error) {
            console.error('Error updating autocompletion:', error);
        }
    }
    
    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
        }
    }
    
    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
        }
    }
    
    showConnectionStatus(status, message) {
        const statusElement = document.getElementById('connectionStatus');
        statusElement.className = `connection-status ${status}`;
        statusElement.textContent = message;
    }
    
    createFallbackEditor() {
        try {
            const editorContainer = document.querySelector('.sql-editor-container');
            if (editorContainer) {
                editorContainer.innerHTML = `
                    <textarea id="sqlEditorFallback" class="sql-editor-fallback" 
                              placeholder="-- Welcome to the Database Query Interface\n-- Select a database and write your SQL queries here\n-- Example:\nSELECT * FROM users LIMIT 10;"></textarea>
                `;
                
                // Style the fallback editor
                const fallbackEditor = document.getElementById('sqlEditorFallback');
                fallbackEditor.style.cssText = `
                    width: 100%;
                    height: 100%;
                    min-height: 400px;
                    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                    font-size: 14px;
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    resize: none;
                    outline: none;
                `;
                
                // Create a simple interface for the fallback
                this.sqlEditor = {
                    getValue: () => fallbackEditor.value,
                    setValue: (value) => { fallbackEditor.value = value; },
                    resize: () => {}
                };
                
                console.log('Fallback editor created');
            }
        } catch (error) {
            console.error('Failed to create fallback editor:', error);
        }
    }
    
    handleDemoQuery(query) {
        // Simple demo query handler - generates mock results
        const queryLower = query.toLowerCase().trim();
        
        // Generate demo results based on query
        let mockResults;
        
        if (queryLower.includes('select') && queryLower.includes('users')) {
            mockResults = {
                success: true,
                type: 'select',
                columns: ['id', 'username', 'email', 'created_at'],
                data: [
                    { id: 1, username: 'john_doe', email: 'john@example.com', created_at: '2024-01-15 10:30:00' },
                    { id: 2, username: 'jane_smith', email: 'jane@example.com', created_at: '2024-01-16 14:22:00' },
                    { id: 3, username: 'admin_user', email: 'admin@example.com', created_at: '2024-01-10 09:15:00' }
                ],
                row_count: 3,
                execution_time: 0.001,
                message: 'Demo query returned 3 rows in 0.001 seconds'
            };
        } else if (queryLower.includes('select') && queryLower.includes('posts')) {
            mockResults = {
                success: true,
                type: 'select',
                columns: ['id', 'title', 'content', 'user_id', 'created_at'],
                data: [
                    { id: 1, title: 'First Post', content: 'This is the content of the first post.', user_id: 1, created_at: '2024-01-17 12:00:00' },
                    { id: 2, title: 'Second Post', content: 'Content of the second post.', user_id: 2, created_at: '2024-01-18 15:30:00' }
                ],
                row_count: 2,
                execution_time: 0.002,
                message: 'Demo query returned 2 rows in 0.002 seconds'
            };
        } else if (queryLower.includes('join')) {
            mockResults = {
                success: true,
                type: 'select',
                columns: ['username', 'title'],
                data: [
                    { username: 'john_doe', title: 'First Post' },
                    { username: 'jane_smith', title: 'Second Post' }
                ],
                row_count: 2,
                execution_time: 0.003,
                message: 'Demo join query returned 2 rows in 0.003 seconds'
            };
        } else {
            mockResults = {
                success: false,
                error: 'Demo mode: Only SELECT queries on users and posts tables are supported. Try: SELECT * FROM users LIMIT 10;',
                message: 'Query not supported in demo mode'
            };
        }
        
        // Simulate network delay
        setTimeout(() => {
            this.handleQueryResults(mockResults);
        }, 100);
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <span>${message}</span>
            <button onclick="this.parentElement.remove()" style="background: none; border: none; color: inherit; margin-left: 1rem; cursor: pointer;">&times;</button>
        `;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Position notification
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 1.5rem;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 10000;
            max-width: 400px;
            animation: slideInRight 0.3s ease;
        `;
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }
}

// Add CSS for notifications animation
const notificationStyle = document.createElement('style');
notificationStyle.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .notification {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .notification.success {
        background: #27ae60;
        color: white;
    }
    
    .notification.error {
        background: #e74c3c;
        color: white;
    }
    
    .notification.warning {
        background: #f39c12;
        color: white;
    }
    
    .notification.info {
        background: #3498db;
        color: white;
    }
`;
document.head.appendChild(notificationStyle);

// Initialize the interface when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.databaseInterface = new DatabaseInterface();
});
// Enhanced Visual Query Builder Methods
DatabaseInterface.prototype.selectAllColumns = function() {
    if (!this.databaseSchema) return;
    
    this.visualQueryConfig.columns = [];
    this.visualQueryConfig.tables.forEach(tableName => {
        const table = this.databaseSchema.find(t => t.name === tableName);
        if (table) {
            table.columns.forEach(col => {
                this.visualQueryConfig.columns.push({
                    table: tableName,
                    column: col.name,
                    type: col.type
                });
            });
        }
    });
    
    this.renderColumns();
    this.updatePreview();
};

DatabaseInterface.prototype.clearColumnSelection = function() {
    this.visualQueryConfig.columns = [];
    this.renderColumns();
    this.updatePreview();
};

DatabaseInterface.prototype.addAggregation = function() {
    const container = document.getElementById('aggregationsContainer');
    const aggregationId = 'agg_' + Date.now();
    
    const aggregationHtml = `
        <div class="aggregation-item" id="${aggregationId}">
            <select class="aggregation-function">
                <option value="COUNT">COUNT</option>
                <option value="SUM">SUM</option>
                <option value="AVG">AVG</option>
                <option value="MIN">MIN</option>
                <option value="MAX">MAX</option>
            </select>
            <span>(</span>
            <select class="aggregation-column">
                <option value="*">*</option>
                ${this.getAvailableColumns().map(col => 
                    `<option value="${col.table}.${col.column}">${col.table}.${col.column}</option>`
                ).join('')}
            </select>
            <span>)</span>
            <input type="text" placeholder="Alias (optional)" class="aggregation-alias">
            <button onclick="dbInterface.removeAggregation('${aggregationId}')" class="btn-sm btn-danger">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    const addButton = document.getElementById('addAggregationBtn');
    addButton.insertAdjacentHTML('beforebegin', aggregationHtml);
    
    this.updatePreview();
};

DatabaseInterface.prototype.removeAggregation = function(aggregationId) {
    const element = document.getElementById(aggregationId);
    if (element) {
        element.remove();
        this.updatePreview();
    }
};

DatabaseInterface.prototype.generateJoinSuggestions = function() {
    const container = document.getElementById('joinSuggestions');
    if (!this.databaseSchema || this.visualQueryConfig.tables.length < 2) {
        container.innerHTML = '<div class="empty-state">Select multiple tables to see join suggestions</div>';
        return;
    }
    
    let suggestions = [];
    const selectedTables = this.visualQueryConfig.tables;
    
    // Generate join suggestions based on foreign keys and common column names
    for (let i = 0; i < selectedTables.length - 1; i++) {
        for (let j = i + 1; j < selectedTables.length; j++) {
            const table1 = this.databaseSchema.find(t => t.name === selectedTables[i]);
            const table2 = this.databaseSchema.find(t => t.name === selectedTables[j]);
            
            if (table1 && table2) {
                // Look for common column names
                table1.columns.forEach(col1 => {
                    table2.columns.forEach(col2 => {
                        if (col1.name === col2.name || 
                            col1.name === `${table2.name}_id` ||
                            col2.name === `${table1.name}_id`) {
                            suggestions.push({
                                table1: table1.name,
                                table2: table2.name,
                                column1: col1.name,
                                column2: col2.name,
                                type: 'INNER'
                            });
                        }
                    });
                });
            }
        }
    }
    
    if (suggestions.length === 0) {
        container.innerHTML = '<div class="empty-state">No automatic join suggestions found</div>';
        return;
    }
    
    const suggestionsHtml = suggestions.map(suggestion => `
        <div class="join-suggestion" onclick="dbInterface.applyJoinSuggestion('${suggestion.table1}', '${suggestion.table2}', '${suggestion.column1}', '${suggestion.column2}', '${suggestion.type}')">
            <span>${suggestion.table1}.${suggestion.column1} = ${suggestion.table2}.${suggestion.column2}</span>
            <button class="btn-sm btn-primary">Apply</button>
        </div>
    `).join('');
    
    container.innerHTML = suggestionsHtml;
};

DatabaseInterface.prototype.applyJoinSuggestion = function(table1, table2, column1, column2, joinType) {
    this.visualQueryConfig.joins.push({
        type: joinType,
        table: table2,
        condition: `${table1}.${column1} = ${table2}.${column2}`
    });
    
    this.renderJoins();
    this.updatePreview();
};

DatabaseInterface.prototype.updateDateFilters = function() {
    const dateFiltersSection = document.getElementById('dateFiltersSection');
    const container = document.getElementById('dateFiltersContainer');
    
    // Find date/datetime columns in selected tables
    let dateColumns = [];
    this.visualQueryConfig.tables.forEach(tableName => {
        const table = this.databaseSchema.find(t => t.name === tableName);
        if (table) {
            table.columns.forEach(col => {
                if (col.type.toLowerCase().includes('date') || 
                    col.type.toLowerCase().includes('time') || 
                    col.type.toLowerCase().includes('timestamp')) {
                    dateColumns.push({
                        table: tableName,
                        column: col.name,
                        type: col.type
                    });
                }
            });
        }
    });
    
    if (dateColumns.length === 0) {
        dateFiltersSection.style.display = 'none';
        return;
    }
    
    dateFiltersSection.style.display = 'block';
    
    const dateFiltersHtml = dateColumns.map((dateCol, index) => `
        <div class="date-filter-item" id="dateFilter_${index}">
            <label>${dateCol.table}.${dateCol.column}:</label>
            <select class="date-filter-operator" onchange="dbInterface.updateDateFilterInputs(${index})">
                <option value="between">Between</option>
                <option value=">=">On or After</option>
                <option value="<=">On or Before</option>
                <option value="=">Exactly</option>
            </select>
            <div class="date-inputs" id="dateInputs_${index}">
                <input type="date" class="date-from" placeholder="From date">
                <input type="date" class="date-to" placeholder="To date">
            </div>
            <button onclick="dbInterface.applyDateFilter(${index}, '${dateCol.table}', '${dateCol.column}')" class="btn-sm btn-primary">
                Apply Filter
            </button>
        </div>
    `).join('');
    
    container.innerHTML = dateFiltersHtml;
};

DatabaseInterface.prototype.updateDateFilterInputs = function(index) {
    const operator = document.querySelector(`#dateFilter_${index} .date-filter-operator`).value;
    const inputsContainer = document.getElementById(`dateInputs_${index}`);
    
    if (operator === 'between') {
        inputsContainer.innerHTML = `
            <input type="date" class="date-from" placeholder="From date">
            <span>to</span>
            <input type="date" class="date-to" placeholder="To date">
        `;
    } else {
        inputsContainer.innerHTML = `
            <input type="date" class="date-single" placeholder="Select date">
        `;
    }
};

DatabaseInterface.prototype.applyDateFilter = function(index, table, column) {
    const filterItem = document.getElementById(`dateFilter_${index}`);
    const operator = filterItem.querySelector('.date-filter-operator').value;
    
    let condition = '';
    if (operator === 'between') {
        const fromDate = filterItem.querySelector('.date-from').value;
        const toDate = filterItem.querySelector('.date-to').value;
        if (fromDate && toDate) {
            condition = `${table}.${column} BETWEEN '${fromDate}' AND '${toDate}'`;
        }
    } else {
        const date = filterItem.querySelector('.date-single').value;
        if (date) {
            condition = `${table}.${column} ${operator} '${date}'`;
        }
    }
    
    if (condition) {
        this.visualQueryConfig.conditions.push({
            column: `${table}.${column}`,
            operator: operator === 'between' ? 'BETWEEN' : operator,
            value: operator === 'between' ? 
                `'${filterItem.querySelector('.date-from').value}' AND '${filterItem.querySelector('.date-to').value}'` :
                `'${filterItem.querySelector('.date-single').value}'`,
            type: 'date'
        });
        
        this.renderConditions();
        this.updatePreview();
        this.showNotification(`Date filter applied for ${table}.${column}`, 'success');
    }
};

DatabaseInterface.prototype.addQuickCondition = function(type) {
    const availableColumns = this.getAvailableColumns();
    if (availableColumns.length === 0) {
        this.showNotification('Please select tables first', 'error');
        return;
    }
    
    let condition = {
        column: availableColumns[0].table + '.' + availableColumns[0].column,
        operator: '=',
        value: '',
        type: type
    };
    
    switch (type) {
        case 'equals':
            condition.operator = '=';
            condition.value = '';
            break;
        case 'like':
            condition.operator = 'LIKE';
            condition.value = '%value%';
            break;
        case 'between':
            condition.operator = 'BETWEEN';
            condition.value = 'value1 AND value2';
            break;
        case 'in':
            condition.operator = 'IN';
            condition.value = "('value1', 'value2')";
            break;
    }
    
    this.visualQueryConfig.conditions.push(condition);
    this.renderConditions();
    this.updatePreview();
};

DatabaseInterface.prototype.updatePreview = function() {
    // Create or update the preview panel
    let previewPanel = document.querySelector('.builder-preview');
    if (!previewPanel) {
        previewPanel = document.createElement('div');
        previewPanel.className = 'builder-preview';
        document.querySelector('.query-builder').appendChild(previewPanel);
    }
    
    const query = this.buildQueryFromConfig();
    const stats = this.getQueryStats();
    
    previewPanel.innerHTML = `
        <h5><i class="fas fa-eye"></i> Query Preview</h5>
        <pre>${query}</pre>
        <div class="quick-stats">
            <span><i class="fas fa-table"></i> ${stats.tables} tables</span>
            <span><i class="fas fa-columns"></i> ${stats.columns} columns</span>
            <span><i class="fas fa-filter"></i> ${stats.conditions} conditions</span>
            <span><i class="fas fa-link"></i> ${stats.joins} joins</span>
        </div>
    `;
};

DatabaseInterface.prototype.getAvailableColumns = function() {
    if (!this.databaseSchema) return [];
    
    let columns = [];
    this.visualQueryConfig.tables.forEach(tableName => {
        const table = this.databaseSchema.find(t => t.name === tableName);
        if (table) {
            table.columns.forEach(col => {
                columns.push({
                    table: tableName,
                    column: col.name,
                    type: col.type,
                    fullName: `${tableName}.${col.name}`
                });
            });
        }
    });
    
    return columns;
};

DatabaseInterface.prototype.buildQueryFromConfig = function() {
    const config = this.visualQueryConfig;
    
    if (config.tables.length === 0) {
        return 'SELECT * FROM your_table LIMIT 10;';
    }
    
    // Build SELECT clause
    let selectClause = 'SELECT ';
    if (config.columns.length === 0 || config.columns.includes('*')) {
        selectClause += '*';
    } else {
        selectClause += config.columns.join(', ');
    }
    
    // Build FROM clause
    let fromClause = ' FROM ' + config.tables[0];
    
    // Add JOINs
    if (config.joins && config.joins.length > 0) {
        config.joins.forEach(join => {
            fromClause += ` ${join.type || 'INNER'} JOIN ${join.table} ON ${join.condition}`;
        });
    }
    
    // Build WHERE clause
    let whereClause = '';
    if (config.conditions && config.conditions.length > 0) {
        const conditions = config.conditions.map(cond => {
            return `${cond.column} ${cond.operator} ${cond.value}`;
        }).join(' AND ');
        whereClause = ' WHERE ' + conditions;
    }
    
    // Build ORDER BY clause
    let orderClause = '';
    if (config.order_by && config.order_by.length > 0) {
        const orderItems = config.order_by.map(order => {
            return `${order.column} ${order.direction || 'ASC'}`;
        }).join(', ');
        orderClause = ' ORDER BY ' + orderItems;
    }
    
    // Build LIMIT clause
    let limitClause = '';
    if (config.limit && config.limit > 0) {
        limitClause = ` LIMIT ${config.limit}`;
    }
    
    return selectClause + fromClause + whereClause + orderClause + limitClause + ';';
};

DatabaseInterface.prototype.getQueryStats = function() {
    return {
        tables: this.visualQueryConfig.tables.length,
        columns: this.visualQueryConfig.columns.length,
        conditions: this.visualQueryConfig.conditions.length,
        joins: this.visualQueryConfig.joins.length
    };
};
