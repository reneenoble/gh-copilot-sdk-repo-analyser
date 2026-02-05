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

function addToolMessage(container, toolName) {
    const toolEmojis = {
        'get_github_issue': '📋',
        'get_repo_structure': '📂',
        'search_code_in_repo': '🔍',
        'get_file_content': '📄'
    };
    const emoji = toolEmojis[toolName] || '🔧';
    const msg = document.createElement('div');
    msg.className = 'chat-message chat-tool';
    msg.innerHTML = `
        <div class="chat-avatar">${emoji}</div>
        <div class="chat-tool-status">
            <span class="tool-spinner"></span>
            Fetching: <strong>${toolName.replace(/_/g, ' ')}</strong>...
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
            
            lastToolMsg = addToolMessage(container, data.name);
            
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
