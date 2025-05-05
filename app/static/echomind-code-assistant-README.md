# EchoMind Code Assistant UI

This is a simple web-based chat interface for interacting with the EchoMind Code Assistant. It allows you to have conversations with the AI assistant and get help with programming tasks, code reviews, debugging, and more.

## How to Access the Chat UI

1. Start the EchoMind API server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. Open your browser and go to:
   ```
   http://localhost:8000/static/echomind-code-assistant.html
   ```

## Usage

### Basic Operations
- Type your message in the text area at the bottom of the screen and click "Send" or press Enter to send it to the assistant.
- Use Shift+Enter to add a new line in the message input without sending.
- Click the paperclip icon to upload a code file for the assistant to analyze.

### Settings
Click the gear icon (⚙️) in the top-right corner to access settings:

1. **Model**: Choose between different AI models with varying capabilities.
2. **Temperature**: Adjust the creativity of the assistant's responses (0.0 to 1.0).
3. **Execute Code**: Toggle whether Python code should be executed automatically.
4. **User ID**: Your user identifier (used for tracking conversations).
5. **API Key**: Your API key for authentication (required).

### Code Execution
When the assistant generates Python code, you can:
- Click "Copy" to copy the code to your clipboard.
- Click "Run" to execute the code and see the output (if code execution is enabled).

### Conversation Management
- Each conversation with the assistant is preserved in a session.
- To start a new conversation, refresh the page.

## Security Notes
- Your API key is stored in memory only and not saved to localStorage.
- Code execution happens on the server side in a controlled environment.
- Be cautious about uploading sensitive code files.

## Troubleshooting
- If you encounter authentication errors, make sure your API key is correctly set in the settings.
- If code execution fails, check the error message for details.
- For other issues, check the browser console for error messages.