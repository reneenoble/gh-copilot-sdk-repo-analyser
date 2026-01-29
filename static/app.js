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

document.getElementById('analyseForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submitBtn');
    const result = document.getElementById('result');
    
    btn.disabled = true;
    btn.textContent = 'Analysing...';
    result.className = 'show';
    result.innerHTML = '<div class="loading"><span class="spinner"></span>Starting analysis...</div>';
    
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
        
        // Use SSE for streaming
        const params = new URLSearchParams({ owner, repo, issue_number });
        const eventSource = new EventSource(`/analyse/stream?${params}`);
        
        let content = '';
        let toolCalls = [];
        
        // Show initial header
        result.innerHTML = `<p><strong>Repository:</strong> ${owner}/${repo} | <strong>Issue:</strong> #${issue_number}</p><div id="tools-status"></div><div id="analysis-content"></div>`;
        
        eventSource.addEventListener('message', (e) => {
            const data = JSON.parse(e.data);
            content += data.content;
            document.getElementById('analysis-content').innerHTML = marked.parse(content);
        });
        
        eventSource.addEventListener('tool_call', (e) => {
            const data = JSON.parse(e.data);
            toolCalls.push(data.name);
            document.getElementById('tools-status').innerHTML = 
                `<div class="tool-indicator">🔧 Using: ${data.name}...</div>`;
        });
        
        eventSource.addEventListener('done', (e) => {
            eventSource.close();
            const data = JSON.parse(e.data);
            if (data.tools_used && data.tools_used.length > 0) {
                document.getElementById('tools-status').innerHTML = 
                    `<div class="tools-summary">Tools used: ${data.tools_used.join(', ')}</div>`;
            } else {
                document.getElementById('tools-status').innerHTML = '';
            }
            btn.disabled = false;
            btn.textContent = 'Analyse Issue';
        });
        
        eventSource.addEventListener('error', (e) => {
            eventSource.close();
            result.innerHTML = `<div class="error"><strong>Error:</strong> Connection lost or analysis failed</div>`;
            btn.disabled = false;
            btn.textContent = 'Analyse Issue';
        });
        
    } catch (err) {
        result.innerHTML = `<div class="error"><strong>Error:</strong> ${err.message}</div>`;
        btn.disabled = false;
        btn.textContent = 'Analyse Issue';
    }
});
