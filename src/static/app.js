let activeTab = 'url';

function switchTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`.tab[data-tab="${tab}"]`).classList.add('active');
    document.getElementById(`${tab}-tab`).classList.add('active');
}

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
});

function parseGitHubUrl(url) {
    const match = url.match(/github\.com\/([^/]+)\/([^/]+)\/issues\/(\d+)/);
    if (!match) throw new Error('Invalid GitHub issue URL');
    return { owner: match[1], repo: match[2], issue_number: parseInt(match[3]) };
}

function addChatMessage(container, emoji, content, type = 'assistant') {
    const msg = document.createElement('div');
    msg.className = `chat-message chat-${type}`;
    msg.innerHTML = `
        <div class="chat-avatar">${emoji}</div>
        <div class="chat-bubble">
            <div class="chat-content">${content}</div>
        </div>
    `;
    container.appendChild(msg);
    msg.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    return msg.querySelector('.chat-content');
}

function describeToolCall(toolName, args) {
    const toolEmojis = {
        'get_github_issue': '📋',
        'get_repo_structure': '📂',
        'search_code_in_repo': '🔍',
        'get_file_content': '📄',
        'report_intent': '📝'
    };
    const emoji = toolEmojis[toolName] || '🔧';

    let detail = '';
    if (args) {
        switch (toolName) {
            case 'get_github_issue':
                if (args.owner && args.repo && args.issue_number)
                    detail = `<code>${args.owner}/${args.repo}#${args.issue_number}</code>`;
                break;
            case 'get_repo_structure':
                detail = args.path
                    ? `<code>${args.path}</code>`
                    : '<code>/</code> (root)';
                break;
            case 'search_code_in_repo':
                if (args.query) detail = `"${args.query}"`;
                break;
            case 'get_file_content':
                if (args.path) detail = `<code>${args.path}</code>`;
                break;
            case 'report_intent':
                if (args.intent) detail = args.intent;
                break;
        }
    }

    const label = toolName.replace(/_/g, ' ');
    const description = detail ? `${label} &mdash; ${detail}` : label;
    return { emoji, description };
}

function addToolMessage(container, toolName, args) {
    const { emoji, description } = describeToolCall(toolName, args);
    const msg = document.createElement('div');
    msg.className = 'chat-message chat-tool';
    msg.innerHTML = `
        <div class="chat-avatar">${emoji}</div>
        <div class="chat-tool-status">
            <span class="tool-spinner"></span>
            <span class="tool-label">Fetching:</span> <strong>${description}</strong>
        </div>
    `;
    container.appendChild(msg);
    msg.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    return msg;
}

document.getElementById('analyseForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submitBtn');
    const result = document.getElementById('result');
    
    btn.disabled = true;
    btn.textContent = 'Analysing...';
    result.className = 'show';
    
    try {
        let owner, repo, issue_number;
        
        if (activeTab === 'url') {
            const url = document.getElementById('url').value;
            ({ owner, repo, issue_number } = parseGitHubUrl(url));
        } else {
            owner = document.getElementById('owner').value;
            repo = document.getElementById('repo').value;
            issue_number = parseInt(document.getElementById('issue_number').value);
        }
        
        // Set up chat container
        result.innerHTML = `
            <div class="chat-header">
                <span class="repo-badge">📁 ${owner}/${repo}</span>
                <span class="issue-badge">#${issue_number}</span>
            </div>
            <div id="chat-container"></div>
        `;
        
        const container = document.getElementById('chat-container');
        addChatMessage(container, '🚀', 'Starting analysis...', 'status');
        
        // Use SSE for streaming
        const params = new URLSearchParams({ owner, repo, issue_number });
        const eventSource = new EventSource(`/analyse/stream?${params}`);
        
        let currentBubble = null;
        let currentContent = '';
        let lastToolMsg = null;
        
        eventSource.addEventListener('message', (e) => {
            const data = JSON.parse(e.data);
            
            // Mark previous tool as done
            if (lastToolMsg) {
                lastToolMsg.querySelector('.tool-spinner')?.remove();
                lastToolMsg.querySelector('.chat-tool-status').innerHTML += ' ✓';
                lastToolMsg = null;
            }
            
            // Create new bubble if needed
            if (!currentBubble) {
                currentBubble = addChatMessage(container, '🤖', '', 'assistant');
            }
            
            currentContent += data.content;
            currentBubble.innerHTML = marked.parse(currentContent);
            currentBubble.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
        
        eventSource.addEventListener('tool_call', (e) => {
            const data = JSON.parse(e.data);
            
            // Mark previous tool as done
            if (lastToolMsg) {
                lastToolMsg.querySelector('.tool-spinner')?.remove();
                lastToolMsg.querySelector('.chat-tool-status').innerHTML += ' ✓';
            }
            
            lastToolMsg = addToolMessage(container, data.name, data.args);
            
            // Reset bubble for next message
            currentBubble = null;
            currentContent = '';
        });
        
        eventSource.addEventListener('done', (e) => {
            eventSource.close();
            
            // Mark any pending tool as done
            if (lastToolMsg) {
                lastToolMsg.querySelector('.tool-spinner')?.remove();
                lastToolMsg.querySelector('.chat-tool-status').innerHTML += ' ✓';
            }
            
            addChatMessage(container, '✅', 'Analysis complete!', 'status');
            btn.disabled = false;
            btn.textContent = 'Analyse Issue';
        });
        
        eventSource.addEventListener('error', (e) => {
            eventSource.close();
            addChatMessage(container, '❌', 'Connection lost or analysis failed', 'error');
            btn.disabled = false;
            btn.textContent = 'Analyse Issue';
        });
        
    } catch (err) {
        result.innerHTML = `<div class="error"><strong>Error:</strong> ${err.message}</div>`;
        btn.disabled = false;
        btn.textContent = 'Analyse Issue';
    }
});
