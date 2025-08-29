// A2A Learning Lab Dashboard JavaScript

// Settings panel functions
function toggleSettingsPanel() {
    const panel = document.getElementById('settings-panel');
    const isVisible = panel.style.display !== 'none';
    panel.style.display = isVisible ? 'none' : 'block';
    
    // Load current token status when opening
    if (!isVisible) {
        updateTokenStatus();
    }
}

function saveGitHubTokenSetting() {
    const input = document.getElementById('github-token-setting');
    const token = input.value.trim();
    
    if (!token) {
        showTokenStatus('Please enter a token', 'error');
        return;
    }
    
    if (!token.startsWith('ghp_') && !token.startsWith('github_pat_')) {
        if (!confirm('This doesn\'t look like a valid GitHub token. Continue anyway?')) {
            return;
        }
    }
    
    // Store token in sessionStorage
    sessionStorage.setItem('github_token', token);
    
    // Clear input for security
    input.value = '';
    
    showTokenStatus('Token saved successfully! 🎉', 'success');
    updateTokenStatus();
}

function clearGitHubTokenSetting() {
    sessionStorage.removeItem('github_token');
    document.getElementById('github-token-setting').value = '';
    showTokenStatus('Token cleared', 'info');
    updateTokenStatus();
}

function showTokenStatus(message, type) {
    const statusEl = document.getElementById('token-status');
    statusEl.textContent = message;
    statusEl.className = `token-status ${type}`;
    
    // Clear status after 3 seconds
    setTimeout(() => {
        statusEl.textContent = '';
        statusEl.className = 'token-status';
    }, 3000);
}

function updateTokenStatus() {
    const hasToken = sessionStorage.getItem('github_token');
    const settingsBtn = document.querySelector('.settings-btn');
    
    if (hasToken) {
        settingsBtn.innerHTML = '🔓 Settings';
        settingsBtn.title = 'GitHub token configured';
    } else {
        settingsBtn.innerHTML = '🔐 Settings';
        settingsBtn.title = 'No GitHub token configured';
    }
}

// Chat functions
function addUserMessage(form) {
    const input = form.querySelector('input[name="message"]');
    const messageText = input.value.trim();
    
    if (!messageText) return false;
    
    // Create user message HTML
    const timestamp = new Date().toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
    });
    
    const userMessageHTML = `
        <div class="message user-message">
            <div class="message-header">
                <span class="message-sender">👤 You</span>
                <span class="message-time">${timestamp}</span>
            </div>
            <div class="message-content"><p>${messageText}</p></div>
        </div>
    `;
    
    // Add to chat immediately
    const messagesContainer = document.getElementById('chat-messages');
    messagesContainer.insertAdjacentHTML('beforeend', userMessageHTML);
    
    // Clear input immediately
    input.value = '';
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Add typing indicator
    const typingHTML = `
        <div id="typing-temp" class="message assistant-message typing-indicator">
            <div class="message-header">
                <span class="message-sender">🤖 A2A Task Router</span>
                <span class="message-time">thinking...</span>
            </div>
            <div class="message-content">
                <span class="typing-dots">
                    <span>.</span><span>.</span><span>.</span>
                </span>
            </div>
        </div>
    `;
    messagesContainer.insertAdjacentHTML('beforeend', typingHTML);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return true;
}

function removeTypingIndicator() {
    const typingEl = document.getElementById('typing-temp');
    if (typingEl) {
        typingEl.remove();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    updateTokenStatus();
    
    // Handle form submission
    const chatForm = document.querySelector('.chat-form');
    if (chatForm) {
        chatForm.addEventListener('htmx:beforeRequest', function(event) {
            // Add user message immediately before HTMX request
            addUserMessage(this);
        });
        
        chatForm.addEventListener('htmx:afterSettle', function(event) {
            // Remove typing indicator after response
            removeTypingIndicator();
            
            // Scroll to bottom after new content
            const messagesContainer = document.getElementById('chat-messages');
            if (messagesContainer) {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        });
    }
});