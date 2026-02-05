// State
let BOOTSTRAP = { collaborators: [], workspaces: [] };
let SELECTED_WORKSPACE = null;
let WORKSPACES_DATA = [];
let LESSON_MODE = 'structured';

// Elements
const wsFiles = document.getElementById('wsFiles');
const wsFileList = document.getElementById('wsFileList');
const workspaceForm = document.getElementById('workspaceForm');
const collaboratorsSelect = document.getElementById('wsCollaboratorsSelect');
const workspaceSelector = document.getElementById('workspaceSelector');
const lsModelSelect = document.getElementById('lsModelSelect');
const aqModelSelect = document.getElementById('aqModelSelect');
const lsWorkspaceDisplay = document.getElementById('lsWorkspaceDisplay');
const aqWorkspaceDisplay = document.getElementById('aqWorkspaceDisplay');

// Load initial data
document.addEventListener('DOMContentLoaded', async () => {
    await bootstrapContentDev();
    await loadWorkspaces();
    await loadOllamaModels();
});

async function bootstrapContentDev() {
    try {
        const r = await fetch('/api/content-dev/bootstrap');
        if (!r.ok) throw new Error('Failed bootstrap');
        BOOTSTRAP = await r.json();
        paintCollaborators();
        paintWorkspaceSelector();
    } catch (e) { console.error(e); }
}

async function loadOllamaModels() {
    // Load for lesson script model selector
    lsModelSelect.innerHTML = '';
    aqModelSelect.innerHTML = '';
    try {
        const r = await fetch('/api/ollama/models');
        const data = await r.json();
        const models = data.models || [];
        models.forEach(name => {
            const opt1 = document.createElement('option');
            opt1.value = name;
            opt1.textContent = name;
            lsModelSelect.appendChild(opt1);

            const opt2 = document.createElement('option');
            opt2.value = name;
            opt2.textContent = name;
            aqModelSelect.appendChild(opt2);
        });
        const defaultModel = (models.includes('llama3.1') ? 'llama3.1' : models[0]) || 'llama3.1';
        if (lsModelSelect.options.length) {
            lsModelSelect.value = defaultModel;
            aqModelSelect.value = defaultModel;
        } else {
            const opt1 = document.createElement('option');
            opt1.value = 'llama3.1';
            opt1.textContent = 'llama3.1';
            lsModelSelect.appendChild(opt1);
            const opt2 = document.createElement('option');
            opt2.value = 'llama3.1';
            opt2.textContent = 'llama3.1';
            aqModelSelect.appendChild(opt2);
        }
    } catch (e) {
        const opt1 = document.createElement('option');
        opt1.value = 'llama3.1';
        opt1.textContent = 'llama3.1';
        lsModelSelect.appendChild(opt1);
        const opt2 = document.createElement('option');
        opt2.value = 'llama3.1';
        opt2.textContent = 'llama3.1';
        aqModelSelect.appendChild(opt2);
    }
}

function paintCollaborators() {
    collaboratorsSelect.innerHTML = '';
    BOOTSTRAP.collaborators.forEach(u => {
        const opt = document.createElement('option');
        opt.value = u.id;
        opt.textContent = `${u.name} (${u.username})`;
        collaboratorsSelect.appendChild(opt);
    });
}

function paintWorkspaceSelector() {
    workspaceSelector.innerHTML = '<option value="">-- Select a workspace --</option>';
    BOOTSTRAP.workspaces.forEach(w => {
        const opt = document.createElement('option');
        opt.value = w.id;
        opt.textContent = w.name;
        workspaceSelector.appendChild(opt);
    });
}

// Workspace selection handler
workspaceSelector.addEventListener('change', (e) => {
    const wsId = e.target.value;
    if (!wsId) {
        SELECTED_WORKSPACE = null;
        document.getElementById('workspaceContentSection').classList.add('cd-hidden');
        document.getElementById('selectedWorkspaceInfo').classList.add('cd-hidden');
        return;
    }

    const ws = WORKSPACES_DATA.find(w => w.id == wsId);
    if (ws) {
        SELECTED_WORKSPACE = ws;
        document.getElementById('wsInfoName').textContent = ws.name;
        document.getElementById('wsInfoDescription').textContent = ws.description || '';
        document.getElementById('selectedWorkspaceInfo').classList.remove('cd-hidden');
        document.getElementById('workspaceContentSection').classList.remove('cd-hidden');
        lsWorkspaceDisplay.value = ws.name;
        aqWorkspaceDisplay.value = ws.name;

        // Load lessons for this workspace
        loadWorkspaceLessons(ws);
        loadWorkspaceActivityQuestions(ws);
        loadWorkspaceLessonsForSelect(ws);

        // Open first tab
        openTab('lessonTab');
    }
});

async function loadWorkspaces() {
    try {
        const r = await fetch('/api/workspaces/mine');
        if (!r.ok) throw new Error('Failed to load workspaces');
        const data = await r.json();
        WORKSPACES_DATA = data.workspaces || [];
        BOOTSTRAP.workspaces = WORKSPACES_DATA.map(w => ({ id: w.id, name: w.name }));
        paintWorkspaceSelector();
    } catch (e) { console.error(e); }
}

function loadWorkspaceLessons(ws) {
    const list = document.getElementById('workspaceLessonsList');
    if (!ws.lessons || ws.lessons.length === 0) {
        list.innerHTML = '<li class="w3-padding-small w3-text-gray">No lessons yet</li>';
        return;
    }
    list.innerHTML = ws.lessons.map(l => `
    <li class="w3-padding-small">
        <b>${escapeHtml(l.topic)}</b>
        <span class="w3-text-gray w3-tiny"> (Age ${escapeHtml(l.age || '')})</span>
        <button class="w3-button w3-tiny w3-round w3-light-gray w3-right" type="button" onclick="viewLesson(${l.id})">View</button>
    </li>
    `).join('');
}

function loadWorkspaceActivityQuestions(ws) {
    const list = document.getElementById('workspaceActivityQuestionsList');
    if (!ws.activity_questions || ws.activity_questions.length === 0) {
        list.innerHTML = '<li class="w3-padding-small w3-text-gray">No activity questions yet</li>';
        return;
    }
    list.innerHTML = ws.activity_questions.map(aq => `
    <li class="w3-padding-small">
        <b>${escapeHtml(aq.topic)}</b>
        <span class="w3-text-gray w3-tiny"> (${escapeHtml(aq.question_type)}, ${escapeHtml(aq.num_questions)} questions)</span>
        <button class="w3-button w3-tiny w3-round w3-light-gray w3-right" type="button" onclick="viewActivityQuestion(${aq.id})">View</button>
    </li>
    `).join('');
}

function loadWorkspaceLessonsForSelect(ws) {
    const select = document.getElementById('aqLessonSelect');
    select.innerHTML = '<option value="">-- None --</option>';
    if (ws.lessons && ws.lessons.length > 0) {
        ws.lessons.forEach(l => {
            const opt = document.createElement('option');
            opt.value = l.id;
            opt.textContent = l.topic;
            select.appendChild(opt);
        });
    }
}

// Tab switching
function openTab(tabName) {
    const tabs = ['lessonTab', 'activityTab', 'contentTab'];
    tabs.forEach(tab => {
        const el = document.getElementById(tab);
        const btn = document.getElementById(tab + 'Btn');
        if (tab === tabName) {
            el.classList.remove('cd-hidden');
            if (btn) btn.classList.add('active');
        } else {
            el.classList.add('cd-hidden');
            if (btn) btn.classList.remove('active');
        }
    });
}

// File list
wsFiles.addEventListener('change', () => {
    const names = Array.from(wsFiles.files).map(f => `• ${f.name}`).join('\n');
    wsFileList.textContent = names || '';
});

async function testOllama() {
    const status = document.getElementById('ollamaStatus');
    status.textContent = 'Checking...';
    try {
        const r = await fetch('/api/ollama/models');
        const data = await r.json();
        if ((data.models || []).length) {
            status.textContent = `OK: ${(data.models || []).join(', ')}`;
            status.className = 'cd-text-sm cd-text-success'; // Modern class
        } else {
            status.textContent = 'No models found';
            status.className = 'cd-text-sm cd-text-muted'; // Modern class
        }
    } catch (e) {
        status.textContent = 'Not reachable';
        status.className = 'cd-text-sm cd-text-muted'; // Modern class
    }
}

// Modal controls
function openWsModal() { document.getElementById('wsCreateModal').style.display = 'block'; }
function closeWsModal() { document.getElementById('wsCreateModal').style.display = 'none'; }
window.openWsModal = openWsModal; window.closeWsModal = closeWsModal;

// Tasks with subtasks
function addTask() {
    const input = document.getElementById('taskInput');
    const title = input.value.trim();
    if (!title) return;
    const li = document.createElement('li');
    li.className = 'w3-padding-small';
    li.innerHTML = `
    <div class="w3-row">
        <div class="w3-col s8"><b>${escapeHtml(title)}</b></div>
        <div class="w3-col s4 w3-right-align">
        <button class="w3-button w3-tiny w3-round w3-light-gray" type="button" onclick="this.closest('li').remove()"><i class="fa fa-trash"></i></button>
        </div>
    </div>
    <div class="w3-margin-top">
        <div class="w3-row" style="gap:8px; align-items:center;">
        <input class="w3-input w3-border w3-round-small" style="width:70%; display:inline-block;" placeholder="Add sub-task">
        <button class="w3-button w3-tiny w3-round w3-indigo" type="button">Add</button>
        </div>
        <ul class="w3-ul w3-small w3-margin-top" style="border-left:2px solid #e5e7eb; padding-left:8px;"></ul>
    </div>
    `;
    const taskList = document.getElementById('taskList');
    taskList.appendChild(li);
    const addBtn = li.querySelector('button.w3-indigo');
    const subInput = li.querySelector('input');
    const subList = li.querySelector('ul');
    addBtn.onclick = () => {
        const st = subInput.value.trim();
        if (!st) return;
        const subLi = document.createElement('li');
        subLi.className = 'w3-padding-small';
        subLi.innerHTML = `
        <span>${escapeHtml(st)}</span>
        <button class="w3-button w3-tiny w3-round w3-light-gray w3-right" type="button" onclick="this.closest('li').remove()"><i class="fa fa-times"></i></button>
    `;
        subList.appendChild(subLi);
        subInput.value = '';
    };
    input.value = '';
}

// Create workspace (persist to backend)
workspaceForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const subject = document.getElementById('wsSubject').value.trim();
    const grade = document.getElementById('wsGrade').value.trim();
    const term = document.getElementById('wsTerm').value.trim();
    const description = document.getElementById('wsDescription').value.trim();

    const tasks = Array.from(document.querySelectorAll('#taskList > li')).map(li => ({
        title: li.querySelector('b')?.textContent || '',
        subtasks: Array.from(li.querySelectorAll('ul > li > span')).map(s => s.textContent)
    }));

    const selectedCollabs = Array.from(collaboratorsSelect.selectedOptions).map(o => o.value);

    const fd = new FormData();
    fd.append('subject', subject);
    fd.append('grade', grade);
    fd.append('term', term);
    fd.append('description', description);
    selectedCollabs.forEach(id => fd.append('collaborators', id));
    fd.append('tasks', JSON.stringify(tasks));
    Array.from(wsFiles.files).forEach(f => fd.append('files', f));

    try {
        const r = await fetch('/api/workspaces', { method: 'POST', body: fd });
        if (!r.ok) throw new Error('Failed to create workspace');
        await r.json();
        await loadWorkspaces();
        workspaceForm.reset();
        document.getElementById('taskList').innerHTML = '';
        wsFileList.textContent = '';
        closeWsModal();
    } catch (err) {
        alert('Error creating workspace');
        console.error(err);
    }
});

// Lesson mode switching
function switchLessonMode(mode) {
    LESSON_MODE = mode;
    const structuredMode = document.getElementById('lsStructuredMode');
    const promptMode = document.getElementById('lsPromptMode');
    const structuredBtn = document.getElementById('lsModeStructuredBtn');
    const promptBtn = document.getElementById('lsModePromptBtn');

    if (mode === 'structured') {
        structuredMode.classList.remove('cd-hidden');
        promptMode.classList.add('cd-hidden');
        structuredBtn.classList.add('active');
        promptBtn.classList.remove('active');
    } else {
        structuredMode.classList.add('cd-hidden');
        promptMode.classList.remove('cd-hidden');
        promptBtn.classList.add('active');
        structuredBtn.classList.remove('active');
    }
}
window.switchLessonMode = switchLessonMode;

// Lesson Generator via backend (Ollama)
async function generateLesson() {
    if (!SELECTED_WORKSPACE) {
        alert('Please select a workspace first.');
        return;
    }

    const generateBtn = document.getElementById('lsGenerateBtn');
    const loading = document.getElementById('lsLoading');
    const outputSection = document.getElementById('lsOutputSection');
    const output = document.getElementById('lsOutput');

    let topic, age, subject, customPrompt;
    let objectives = [], aspects = [], activities = [], images = [];

    if (LESSON_MODE === 'prompt') {
        // Single prompt mode
        customPrompt = document.getElementById('lsPrompt').value.trim();
        topic = document.getElementById('lsPromptTopic').value.trim();
        age = document.getElementById('lsPromptAge').value.trim();

        if (!customPrompt || !topic || !age) {
            alert('Please provide a prompt, topic, and age.');
            return;
        }
    } else {
        // Structured input mode
        topic = document.getElementById('lsTopic').value.trim();
        age = document.getElementById('lsAge').value.trim();
        subject = document.getElementById('lsSubject').value.trim();
        objectives = splitLines(document.getElementById('lsObjectives').value);
        aspects = splitLines(document.getElementById('lsAspects').value);
        activities = splitLines(document.getElementById('lsActivities').value);
        images = splitLines(document.getElementById('lsImages').value);

        if (!topic || !age) {
            alert('Please provide both Topic and Age.');
            return;
        }
    }

    const includeQuestions = document.getElementById('lsIncludeQuestions').checked;

    // Show loading state
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Generating...';
    loading.classList.remove('cd-hidden');
    outputSection.classList.add('cd-hidden');
    output.textContent = ''; // Clear previous content

    // Reset progress
    document.getElementById('lsProgressBar').style.width = '0%';
    document.getElementById('lsProgressPercent').textContent = '0%';
    document.getElementById('lsProgressMessage').textContent = 'Generating lesson...';
    document.getElementById('lsProgressText').textContent = 'Initializing...';

    try {
        const requestBody = {
            workspace_id: Number(SELECTED_WORKSPACE.id),
            topic,
            age: Number(age),
            model: lsModelSelect.value || undefined
        };

        if (LESSON_MODE === 'prompt') {
            requestBody.custom_prompt = customPrompt;
            requestBody.subject = subject; // Include subject for formatting
        } else {
            requestBody.subject = subject;
            requestBody.objectives = objectives;
            requestBody.aspects = aspects;
            requestBody.activities = activities;
            requestBody.images = images;
        }

        // Use streaming endpoint
        const response = await fetch('/api/lessons/generate-stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            // Try to get error message
            let errorMsg = 'Failed to generate lesson';
            try {
                const errorText = await response.text();
                try {
                    const errorData = JSON.parse(errorText);
                    errorMsg = errorData.error || errorMsg;
                } catch {
                    errorMsg = errorText || errorMsg;
                }
            } catch {
                errorMsg = `HTTP ${response.status}: ${response.statusText}`;
            }
            throw new Error(errorMsg);
        }

        // Check if response is actually streaming (text/event-stream)
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('text/event-stream') && !contentType.includes('text/plain')) {
            // Fallback: might be regular JSON response
            try {
                const data = await response.json();
                if (data.error) {
                    throw new Error(data.error);
                }
                // If it's a regular response, handle it
                if (data.lesson && data.lesson.content) {
                    output.textContent = data.lesson.content;
                    outputSection.classList.remove('w3-hide');
                    loading.classList.add('w3-hide');
                    return;
                }
            } catch (e) {
                // Not JSON, continue with streaming
            }
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let lessonId = null;
        let fullContent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.type === 'progress') {
                            // Update progress
                            const percentage = data.percentage || 0;
                            document.getElementById('lsProgressBar').style.width = percentage + '%';
                            document.getElementById('lsProgressPercent').textContent = percentage + '%';
                            document.getElementById('lsProgressMessage').textContent = data.message || `Generating... ${percentage}%`;
                            document.getElementById('lsProgressText').textContent = data.message || `Generating... ${percentage}%`;

                            // Append content as it streams
                            if (data.content) {
                                fullContent += data.content;
                                output.textContent = fullContent;
                                output.scrollTop = output.scrollHeight; // Auto-scroll
                            }
                        } else if (data.type === 'complete') {
                            // Generation complete
                            document.getElementById('lsProgressBar').style.width = '100%';
                            document.getElementById('lsProgressPercent').textContent = '100%';
                            document.getElementById('lsProgressMessage').textContent = 'Complete!';
                            document.getElementById('lsProgressText').textContent = 'Lesson generation complete!';

                            fullContent = data.content || fullContent;
                            output.textContent = fullContent;
                            lessonId = data.lesson_id;
                            outputSection.classList.remove('cd-hidden');
                            loading.classList.add('cd-hidden');

                            // If include questions is checked, generate questions too
                            if (includeQuestions && lessonId) {
                                await generateActivityQuestionsForLesson(topic, subject, Number(age), lessonId);
                            }

                            // Reload workspace data
                            await loadWorkspaces();
                            if (SELECTED_WORKSPACE) {
                                const ws = WORKSPACES_DATA.find(w => w.id == SELECTED_WORKSPACE.id);
                                if (ws) {
                                    loadWorkspaceLessons(ws);
                                    loadWorkspaceActivityQuestions(ws);
                                    loadWorkspaceLessonsForSelect(ws);
                                }
                            }
                        } else if (data.type === 'error') {
                            // Handle error - might have partial content
                            if (data.partial_content) {
                                output.textContent = data.partial_content;
                                outputSection.classList.remove('cd-hidden');
                                loading.classList.add('cd-hidden');
                                alert('Warning: ' + (data.message || 'Generation was interrupted. Partial content displayed.'));
                                // Still reload workspace if lesson was saved
                                if (data.lesson_id) {
                                    await loadWorkspaces();
                                    if (SELECTED_WORKSPACE) {
                                        const ws = WORKSPACES_DATA.find(w => w.id == SELECTED_WORKSPACE.id);
                                        if (ws) {
                                            loadWorkspaceLessons(ws);
                                            loadWorkspaceActivityQuestions(ws);
                                            loadWorkspaceLessonsForSelect(ws);
                                        }
                                    }
                                }
                            } else {
                                throw new Error(data.message || 'Generation error');
                            }
                        }
                    } catch (e) {
                        // If it's a JSON parse error on a line that doesn't start with 'data: ', skip it
                        if (line.trim() && !line.startsWith('data: ')) {
                            continue; // Skip non-SSE lines (empty lines, comments, etc.)
                        }
                        // If it's actually a parse error on a data line, log it but don't break
                        if (line.startsWith('data: ')) {
                            console.error('Error parsing SSE data:', e, 'Line:', line);
                            // Try to continue - might be malformed but not critical
                        }
                    }
                }
            }
        }
    } catch (err) {
        console.error(err);
        alert('Error generating lesson: ' + (err?.message || 'unknown error'));
        loading.classList.add('cd-hidden');
    } finally {
        // Reset button state
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="fa fa-magic"></i> Generate Lesson';
    }
}
window.generateLesson = generateLesson;

async function generateActivityQuestionsForLesson(topic, subject, age, lessonId) {
    // Generate questions with age range based on lesson age
    const ageRange = { min_age: Math.max(3, age - 2), max_age: Math.min(21, age + 2) };

    try {
        const r = await fetch('/api/activity-questions/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_id: Number(SELECTED_WORKSPACE.id),
                lesson_id: lessonId,
                topic: topic,
                subject: subject || null,
                age_range: ageRange,
                grade_range: null,
                ability_levels: [],
                question_type: 'mixed',
                num_questions: 5,
                model: aqModelSelect.value || undefined
            })
        });
        const data = await r.json();
        if (!r.ok) {
            console.error('Failed to generate activity questions:', data.error);
            return;
        }
    } catch (err) {
        console.error('Error generating activity questions:', err);
    }
}

// Activity Questions Generator
async function generateActivityQuestions() {
    if (!SELECTED_WORKSPACE) {
        alert('Please select a workspace first.');
        return;
    }

    const topic = document.getElementById('aqTopic').value.trim();
    const subject = document.getElementById('aqSubject').value.trim();
    const lessonId = document.getElementById('aqLessonSelect').value;
    const minAge = document.getElementById('aqMinAge').value;
    const maxAge = document.getElementById('aqMaxAge').value;
    const minGrade = document.getElementById('aqMinGrade').value;
    const maxGrade = document.getElementById('aqMaxGrade').value;
    const questionType = document.getElementById('aqQuestionType').value;
    const numQuestions = parseInt(document.getElementById('aqNumQuestions').value) || 5;

    // Get ability levels
    const abilityLevels = [];
    if (document.getElementById('aqAbilityBeginner').checked) abilityLevels.push('beginner');
    if (document.getElementById('aqAbilityIntermediate').checked) abilityLevels.push('intermediate');
    if (document.getElementById('aqAbilityAdvanced').checked) abilityLevels.push('advanced');

    if (!topic) {
        alert('Please provide a topic.');
        return;
    }

    // Validate ranges
    if (minAge && maxAge && parseInt(minAge) > parseInt(maxAge)) {
        alert('Minimum age must be less than or equal to maximum age.');
        return;
    }
    if (minGrade && maxGrade && parseInt(minGrade) > parseInt(maxGrade)) {
        alert('Minimum grade must be less than or equal to maximum grade.');
        return;
    }

    const ageRange = (minAge && maxAge) ? { min_age: parseInt(minAge), max_age: parseInt(maxAge) } : null;
    const gradeRange = (minGrade && maxGrade) ? { min_grade: parseInt(minGrade), max_grade: parseInt(maxGrade) } : null;

    const generateBtn = document.getElementById('aqGenerateBtn');
    const loading = document.getElementById('aqLoading');
    const outputSection = document.getElementById('aqOutputSection');
    const output = document.getElementById('aqOutput');

    // Show loading state
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Generating...';
    loading.classList.remove('cd-hidden');
    outputSection.classList.add('cd-hidden');

    try {
        const r = await fetch('/api/activity-questions/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_id: Number(SELECTED_WORKSPACE.id),
                lesson_id: lessonId || null,
                topic: topic,
                subject: subject || null,
                age_range: ageRange,
                grade_range: gradeRange,
                ability_levels: abilityLevels,
                question_type: questionType,
                num_questions: numQuestions,
                model: aqModelSelect.value || undefined
            })
        });

        const data = await r.json();
        if (!r.ok) {
            throw new Error(data.error || 'Failed to generate activity questions');
        }

        output.textContent = data.activity_question.content || '';
        outputSection.classList.remove('cd-hidden');

        // Reload workspace data
        await loadWorkspaces();
        if (SELECTED_WORKSPACE) {
            const ws = WORKSPACES_DATA.find(w => w.id == SELECTED_WORKSPACE.id);
            if (ws) {
                loadWorkspaceActivityQuestions(ws);
                loadWorkspaceLessonsForSelect(ws);
            }
        }
    } catch (error) {
        console.error('Error generating activity questions:', error);
        alert('Error generating activity questions: ' + (error.message || 'Unknown error'));
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="fa fa-magic"></i> Generate Questions';
        loading.classList.add('cd-hidden');
    }
}

// Lesson view modal
async function viewLesson(lessonId) {
    try {
        const r = await fetch(`/api/lessons/${lessonId}`);
        const data = await r.json();
        if (!r.ok) { throw new Error(data.error || 'Failed'); }
        document.getElementById('lessonModalTitle').textContent = `${data.topic} (Age ${data.age})`;
        document.getElementById('lessonModalBody').textContent = data.content || '';
        document.getElementById('lessonModal').style.display = 'block';
    } catch (e) { alert('Error loading lesson: ' + (e.message || '')); }
}
window.viewLesson = viewLesson;

// Activity Question view modal
async function viewActivityQuestion(questionId) {
    try {
        const r = await fetch(`/api/activity-questions/${questionId}`);
        const data = await r.json();
        if (!r.ok) { throw new Error(data.error || 'Failed'); }
        document.getElementById('activityQuestionModalTitle').textContent = `${data.topic} (${data.question_type}, ${data.num_questions} questions)`;
        document.getElementById('activityQuestionModalBody').textContent = data.content || '';
        document.getElementById('activityQuestionModal').style.display = 'block';
    } catch (e) { alert('Error loading activity questions: ' + (e.message || '')); }
}
window.viewActivityQuestion = viewActivityQuestion;

function copyLessonOutput() {
    const output = document.getElementById('lsOutput');
    const text = output.textContent;

    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            const btn = event.target.closest('button');
            const original = btn.innerHTML;
            btn.innerHTML = '<i class="fa fa-check"></i> Copied!';
            // btn.classList.remove('w3-indigo'); // Not used in modern
            btn.classList.add('cd-text-success'); // Add text success color
            setTimeout(() => {
                btn.innerHTML = original;
                btn.classList.remove('cd-text-success');
                // btn.classList.add('w3-indigo');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy text: ', err);
            fallbackCopyLesson(text);
        });
    } else {
        fallbackCopyLesson(text);
    }
}

function fallbackCopyLesson(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        document.execCommand('copy');
        alert('Lesson copied to clipboard!');
    } catch (err) {
        console.error('Fallback copy failed: ', err);
        alert('Failed to copy. Please select the text manually.');
    }
    document.body.removeChild(textArea);
}

function downloadLessonOutput() {
    const output = document.getElementById('lsOutput');
    const text = output.textContent;
    const topic = LESSON_MODE === 'prompt'
        ? document.getElementById('lsPromptTopic').value.trim()
        : document.getElementById('lsTopic').value.trim();
    const filename = topic ? `${topic.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()}_lesson.txt` : 'lesson.txt';

    const blob = new Blob([text], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

function copyActivityQuestions() {
    const output = document.getElementById('aqOutput');
    const text = output.textContent;

    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            const btn = event.target.closest('button');
            const original = btn.innerHTML;
            btn.innerHTML = '<i class="fa fa-check"></i> Copied!';
            // btn.classList.remove('w3-indigo');
            btn.classList.add('cd-text-success');
            setTimeout(() => {
                btn.innerHTML = original;
                btn.classList.remove('cd-text-success');
                // btn.classList.add('w3-indigo');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy text: ', err);
            fallbackCopyActivityQuestions(text);
        });
    } else {
        fallbackCopyActivityQuestions(text);
    }
}

function fallbackCopyActivityQuestions(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        document.execCommand('copy');
        alert('Activity questions copied to clipboard!');
    } catch (err) {
        console.error('Fallback copy failed: ', err);
        alert('Failed to copy. Please select the text manually.');
    }
    document.body.removeChild(textArea);
}

function downloadActivityQuestions() {
    const output = document.getElementById('aqOutput');
    const text = output.textContent;
    const topic = document.getElementById('aqTopic').value.trim() || 'activity_questions';

    const blob = new Blob([text], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = `${topic.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()}_activity_questions.txt`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

function copyActivityQuestionModal() {
    const text = document.getElementById('activityQuestionModalBody').textContent;
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            alert('Copied to clipboard!');
        }).catch(err => {
            console.error('Failed to copy:', err);
            alert('Failed to copy. Please select the text manually.');
        });
    } else {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy');
            alert('Copied to clipboard!');
        } catch (err) {
            alert('Failed to copy. Please select the text manually.');
        }
        document.body.removeChild(textArea);
    }
}

// Helpers
function splitLines(v) {
    return v.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
}
function formatDate(d) {
    const date = (d instanceof Date) ? d : new Date(d);
    return date.toLocaleString();
}
function escapeHtml(s) {
    return String(s).replace(/[&<>"]+/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] || c));
}
