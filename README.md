# Shizuku - Document AI Assistant

Shizuku is a powerful document analysis and chat application that allows you to upload PDFs, ask questions about their content, and organize your research in notebooks. Built with Flask and powered by Google's Gemini AI, it provides an intuitive interface for document-based question answering with persistent chat history.

## 🌟 Features

### 📚 Notebook Management
- Create, rename, and delete notebooks
- Organize research by subject or project
- Track sources per notebook

### 📄 PDF Document Processing
- Upload multiple PDFs simultaneously
- Intelligent text extraction from PDF pages
- Source management with renaming and deletion capabilities

### 💬 AI-Powered Chat Interface
- Ask questions about uploaded documents
- Context-aware responses based on selected sources
- Multiple chat sessions per notebook
- Persistent chat history with session management

### 🎨 Rich Text Editor
- Integrated Quill.js editor for note-taking
- Formatting tools for creating detailed notes
- Save chat excerpts directly to notes

### 🏗️ Advanced UI Features
- **Dark Mode**: Modern dark theme with proper contrast
- **Resizable Panels**: Drag to resize all interface columns
- **Chat History Panel**: Separate panel showing all chat sessions (like ChatGPT/DeepSeek)
- **Context Menus**: Right-click functionality for notebooks and chat sessions
- **Responsive Design**: Works on different screen sizes

### 🔄 Session Management
- Multiple chat sessions per notebook
- Automatic session creation and management
- Session renaming and deletion
- Persistent conversation history

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Gemini API key

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd shizuku
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Create a requirements.txt file with:**
```
Flask==2.3.3
Werkzeug==2.3.7
PyPDF2==3.0.1
google-generativeai==0.3.2
markdown==3.4.4
```

4. **Configure API key:**
   - Get a Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Replace the API key in `app.py`:
   ```python
   genai.configure(api_key='YOUR_ACTUAL_API_KEY_HERE')
   ```

5. **Run the application:**
```bash
python app.py
```

6. **Open your browser:**
```
http://localhost:5000
```

## 📁 Project Structure

```
shizuku/
├── app.py                 # Main Flask application
├── templates/
│   ├── base.html         # Base template with layout
│   ├── index.html        # Home page (notebooks list)
│   └── notebook.html     # Notebook interface
├── uploads/              # PDF storage directory
├── notebook_lm.db        # SQLite database (auto-generated)
└── README.md            # This file
```

## 🗄️ Database Schema

The application uses SQLite with the following tables:

- **notebooks**: Stores notebook metadata
- **materials**: Stores uploaded PDF information
- **chats**: Stores chat messages with session tracking
- **notes**: Stores rich text notes
- **chat_sessions**: Manages separate chat conversations

## 🎯 Usage Guide

### 1. Creating a Notebook
- From the home page, enter a notebook name and click the "+" button
- Notebooks appear in the sidebar with source counts

### 2. Uploading PDFs
- Open a notebook
- Click "Add PDFs" or drag files to the upload area in Sources panel
- Select which sources to include in queries using checkboxes

### 3. Chatting with Documents
- Type questions in the chat input at the bottom
- AI responses are based only on selected sources
- Responses are formatted with markdown for better readability

### 4. Managing Chat History
- Use the "New Chat" button to start fresh conversations
- Switch between different chat sessions in the Chat History panel
- Rename or delete chat sessions using the action buttons

### 5. Taking Notes
- Use the Studio panel to create rich text notes
- Save excerpts from AI responses directly to notes
- Organize notes within each notebook

### 6. Resizing Panels
- Drag the edges of any panel to resize it
- Panel widths are saved between sessions

## 🛠️ Development

### Database Reset
For development purposes, you can reset the database by visiting:
```
http://localhost:5000/reset_db
```

This will:
- Clear all data from the database
- Remove uploaded PDF files
- Reinitialize the schema

### API Integration
The application uses Google's Gemini 2.5 Flash model for generating responses. The AI is instructed to:
- Only use information from the provided document context
- Format responses with proper markdown
- Admit when information cannot be found

## 🔧 Configuration

### Environment Variables
While not currently implemented, you can extend the app to use environment variables:
```python
import os
genai.configure(api_key=os.getenv('GEMINI_API_KEY', 'your-default-key'))
```

### File Upload Settings
- Maximum file size: Limited by Flask's default (16MB)
- Allowed extensions: .pdf only
- Storage: Files are stored in the `uploads/` directory

## 🚨 Security Notes

1. **API Keys**: Always keep your Gemini API key secure. Consider using environment variables in production.
2. **File Uploads**: The app uses `secure_filename()` to sanitize uploaded filenames.
3. **Database**: Uses SQLite with proper foreign key constraints.
4. **Session Management**: Flask's session is used with a secret key.

## 📱 Browser Compatibility

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Google Gemini AI](https://ai.google.dev/) for the AI capabilities
- [Flask](https://flask.palletsprojects.com/) web framework
- [Quill.js](https://quilljs.com/) rich text editor
- [Bootstrap](https://getbootstrap.com/) for UI components
- [Font Awesome](https://fontawesome.com/) for icons

## 🐛 Troubleshooting

### Common Issues

1. **PDF upload fails:**
   - Ensure files are actual PDFs
   - Check file size limits
   - Verify write permissions in the uploads directory

2. **AI responses not working:**
   - Verify your Gemini API key is correct
   - Check internet connectivity
   - Ensure at least one PDF is uploaded and selected

3. **Database issues:**
   - Delete `notebook_lm.db` and restart the app
   - Ensure SQLite write permissions

4. **Chat sessions not saving:**
   - Check browser localStorage settings
   - Ensure JavaScript is enabled

### Getting Help
Create an issue in the GitHub repository with:
- Steps to reproduce the problem
- Expected vs actual behavior
- Screenshots if applicable
- Your environment details

## 🌐 Deployment

### For Production:
1. Use a production WSGI server (Gunicorn, uWSGI)
2. Set up a reverse proxy (Nginx, Apache)
3. Use environment variables for sensitive data
4. Implement proper logging
5. Set up regular backups of the database and uploads directory

Example with Gunicorn:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

---

**Shizuku** - Your intelligent document companion for research and analysis. 📚✨
