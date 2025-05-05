// EchoMind Code Assistant JavaScript

// Global variables
let conversationId = null;
let settings = {
    model: 'claude-3-sonnet-20240229',
    temperature: 0.7,
    executeCode: false,
    userId: 'user_123',
    apiKey: ''
};

// DOM Elements
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const uploadButton = document.getElementById('uploadButton');
const fileInput = document.getElementById('fileInput');
const settingsButton = document.getElementById('settingsButton');
const settingsPanel = document.getElementById('settingsPanel');
const modelSelect = document.getElementById('modelSelect');
const temperatureSlider = document.getElementById('temperatureSlider');
const temperatureValue = document.getElementById('temperatureValue');
const executeCodeCheckbox = document.getElementById('executeCodeCheckbox');
const userIdInput = document.getElementById('userIdInput');
const apiKeyInput = document.getElementById('apiKeyInput');
const saveSettingsButton = document.getElementById('saveSettingsButton');
const cancelSettingsButton = document.getElementById('cancelSettingsButton');
const codeExecutionPanel = document.getElementById('codeExecutionPanel');
const codeExecutionOutput = document.getElementById('codeExecutionOutput');
const closeExecutionPanelButton = document.getElementById('closeExecutionPanelButton');
const tooltip = document.getElementById('tooltip');
const tooltipContent = document.getElementById('tooltipContent');

// Initialize the application
function init() {
    // Load settings from localStorage
    loadSettings();
    
    // Initialize syntax highlighting
    hljs.configure({
        ignoreUnescapedHTML: true
    });
    
    // Initialize marked.js
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true
    });
    
    // Set up event listeners
    setupEventListeners();
}

// Set up event listeners
function setupEventListeners() {
    // Send message when send button is clicked
    sendButton.addEventListener('click', sendMessage);
    
    // Send message when Enter key is pressed (Shift+Enter for new line)
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Handle file upload
    uploadButton.addEventListener('click', () => {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', handleFileUpload);
    
    // Settings panel
    settingsButton.addEventListener('click', toggleSettingsPanel);
    saveSettingsButton.addEventListener('click', saveSettings);
    cancelSettingsButton.addEventListener('click', () => {
        loadSettings();
        toggleSettingsPanel();
    });
    
    // Update temperature value display when slider is moved
    temperatureSlider.addEventListener('input', () => {
        temperatureValue.textContent = temperatureSlider.value;
    });
    
    // Code execution panel
    closeExecutionPanelButton.addEventListener('click', () => {
        codeExecutionPanel.classList.remove('visible');
    });
    
    // Tooltip for copy code functionality
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.tooltip')) {
            tooltip.classList.remove('visible');
        }
    });
}

// Send a message to Claude
async function sendMessage() {
    const prompt = messageInput.value.trim();
    if (!prompt) return;
    
    // Check if API key is set
    if (!settings.apiKey) {
        showTooltip(sendButton, 'Please set your API key in the settings', 2000);
        settingsPanel.classList.add('visible');
        return;
    }
    
    // Add user message to chat
    addMessage(prompt, 'user');
    
    // Clear input
    messageInput.value = '';
    
    // Disable send button while processing
    sendButton.disabled = true;
    
    // Add loading indicator
    const loadingElement = addLoadingIndicator();
    
    try {
        let response;
        
        if (conversationId) {
            // Continue conversation
            response = await continueConversation(prompt, conversationId);
        } else {
            // Start new conversation
            response = await executeCodeAssistant(prompt);
        }
        
        // Remove loading indicator
        loadingElement.remove();
        
        // Process the response
        processAIResponse(response);
        
        // Re-enable send button
        sendButton.disabled = false;
        
        // Scroll to bottom
        scrollToBottom();
    } catch (error) {
        // Remove loading indicator
        loadingElement.remove();
        
        // Add error message
        addMessage(`Error: ${error.message}`, 'system');
        
        // Re-enable send button
        sendButton.disabled = false;
    }
}

// Add a message to the chat
function addMessage(content, role) {
    const messageElement = document.createElement('div');
    messageElement.className = `message ${role}`;
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    if (role === 'assistant') {
        // Process markdown and code blocks
        messageContent.innerHTML = parseMarkdown(content);
        
        // Add syntax highlighting
        messageContent.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
            addCodeActions(block);
        });
    } else {
        // Simple text for user messages
        messageContent.textContent = content;
    }
    
    messageElement.appendChild(messageContent);
    chatMessages.appendChild(messageElement);
    
    // Scroll to the bottom
    scrollToBottom();
    
    return messageElement;
}

// Add loading indicator
function addLoadingIndicator() {
    const loadingElement = document.createElement('div');
    loadingElement.className = 'message assistant';
    
    const loadingContent = document.createElement('div');
    loadingContent.className = 'loading';
    
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.className = 'loading-dot';
        loadingContent.appendChild(dot);
    }
    
    loadingElement.appendChild(loadingContent);
    chatMessages.appendChild(loadingElement);
    
    scrollToBottom();
    
    return loadingElement;
}

// Parse markdown content
function parseMarkdown(content) {
    return marked.parse(content);
}

// Add code actions (copy, run) to code blocks
function addCodeActions(codeBlock) {
    const language = codeBlock.className.replace('language-', '');
    
    // Create code actions container
    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'code-actions';
    
    // Copy button
    const copyButton = document.createElement('button');
    copyButton.className = 'code-action-button';
    copyButton.textContent = 'Copy';
    copyButton.addEventListener('click', (e) => {
        e.preventDefault();
        
        // Copy code to clipboard
        navigator.clipboard.writeText(codeBlock.textContent)
            .then(() => {
                showTooltip(copyButton, 'Copied!', 1000);
            })
            .catch((err) => {
                showTooltip(copyButton, 'Failed to copy', 1000);
                console.error('Failed to copy: ', err);
            });
    });
    
    actionsContainer.appendChild(copyButton);
    
    // Run button for Python code
    if (language === 'python' && settings.executeCode) {
        const runButton = document.createElement('button');
        runButton.className = 'code-action-button';
        runButton.textContent = 'Run';
        runButton.addEventListener('click', (e) => {
            e.preventDefault();
            executeCodeLocally(codeBlock.textContent, language);
        });
        
        actionsContainer.appendChild(runButton);
    }
    
    // Insert actions before the code block
    codeBlock.parentNode.insertBefore(actionsContainer, codeBlock);
}

// Show tooltip
function showTooltip(element, message, duration = 2000) {
    tooltipContent.textContent = message;
    
    const rect = element.getBoundingClientRect();
    tooltip.style.top = `${rect.top - 40}px`;
    tooltip.style.left = `${rect.left + (rect.width / 2) - 50}px`;
    
    tooltip.classList.add('visible');
    
    setTimeout(() => {
        tooltip.classList.remove('visible');
    }, duration);
}

// Execute EchoMind Code Assistant API
async function executeCodeAssistant(prompt) {
    const url = '/claude-code/execute';
    
    const requestBody = {
        user_id: settings.userId,
        prompt: prompt,
        model: settings.model,
        temperature: parseFloat(settings.temperature)
    };
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Key': settings.apiKey
        },
        body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to connect to EchoMind Code Assistant API');
    }
    
    return await response.json();
}

// Continue conversation
async function continueConversation(prompt, conversationId) {
    const url = `/claude-code/conversation/${conversationId}`;
    
    const requestBody = {
        prompt: prompt,
        user_id: settings.userId,
        model: settings.model,
        temperature: parseFloat(settings.temperature)
    };
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Key': settings.apiKey
        },
        body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to continue conversation');
    }
    
    return await response.json();
}

// Process AI response
function processAIResponse(response) {
    // Update conversation ID
    conversationId = response.conversation_id;
    
    // Get EchoMind's response content
    const aiResponse = response.response;
    
    // Format the response for display
    let formattedContent = '';
    
    if (aiResponse.content) {
        for (const contentItem of aiResponse.content) {
            if (contentItem.type === 'text') {
                formattedContent += contentItem.text + '\n\n';
            } else if (contentItem.type === 'code') {
                // Format as markdown code block
                const language = 'python';  // Default to Python
                formattedContent += '```' + language + '\n' + contentItem.text + '\n```\n\n';
                
                // Execute code if setting is enabled
                if (settings.executeCode && language === 'python') {
                    executeCodeLocally(contentItem.text, language);
                }
            }
        }
    } else {
        formattedContent = 'No content in the response';
    }
    
    // Add message to chat
    addMessage(formattedContent.trim(), 'assistant');
}

// Execute code locally
function executeCodeLocally(code, language) {
    if (language !== 'python') {
        showTooltip(sendButton, 'Only Python execution is supported', 2000);
        return;
    }
    
    // Show code execution panel
    codeExecutionPanel.classList.add('visible');
    codeExecutionOutput.textContent = 'Executing code...';
    
    // Execute code on server
    executeCodeOnServer(code)
        .then((result) => {
            let output = '';
            
            if (result.stdout) {
                output += result.stdout;
            }
            
            if (result.stderr) {
                output += '\n\nError:\n' + result.stderr;
            }
            
            if (result.exception) {
                output += '\n\nException:\n' + result.exception.message;
                if (result.exception.traceback) {
                    output += '\n' + result.exception.traceback;
                }
            }
            
            codeExecutionOutput.textContent = output || 'No output';
        })
        .catch((error) => {
            codeExecutionOutput.textContent = `Error executing code: ${error.message}`;
        });
}

// Execute code on server
async function executeCodeOnServer(code) {
    const url = '/code/execute';
    
    const requestBody = {
        user_id: settings.userId,
        code: code,
        language: 'python'
    };
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Key': settings.apiKey
        },
        body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to execute code');
    }
    
    const result = await response.json();
    return result.result;
}

// Handle file upload
function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    
    reader.onload = (event) => {
        const content = event.target.result;
        
        // Create a prompt with the file content
        const prompt = `I have the following code from ${file.name}. Please analyze it, suggest improvements, and explain what it does:\n\n\`\`\`\n${content}\n\`\`\``;
        
        // Set as message input
        messageInput.value = prompt;
        
        // Focus and resize textarea
        messageInput.focus();
    };
    
    reader.readAsText(file);
    
    // Reset file input
    fileInput.value = '';
}

// Toggle settings panel
function toggleSettingsPanel() {
    settingsPanel.classList.toggle('visible');
}

// Save settings
function saveSettings() {
    settings.model = modelSelect.value;
    settings.temperature = temperatureSlider.value;
    settings.executeCode = executeCodeCheckbox.checked;
    settings.userId = userIdInput.value;
    settings.apiKey = apiKeyInput.value;
    
    // Save to localStorage
    localStorage.setItem('claudeCodeSettings', JSON.stringify({
        model: settings.model,
        temperature: settings.temperature,
        executeCode: settings.executeCode,
        userId: settings.userId
        // Not saving API key for security reasons
    }));
    
    toggleSettingsPanel();
}

// Load settings
function loadSettings() {
    // Try to load from localStorage
    const savedSettings = JSON.parse(localStorage.getItem('claudeCodeSettings') || '{}');
    
    if (savedSettings.model) settings.model = savedSettings.model;
    if (savedSettings.temperature) settings.temperature = savedSettings.temperature;
    if (savedSettings.executeCode !== undefined) settings.executeCode = savedSettings.executeCode;
    if (savedSettings.userId) settings.userId = savedSettings.userId;
    
    // Update UI
    modelSelect.value = settings.model;
    temperatureSlider.value = settings.temperature;
    temperatureValue.textContent = settings.temperature;
    executeCodeCheckbox.checked = settings.executeCode;
    userIdInput.value = settings.userId;
}

// Scroll to bottom of chat
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', init);