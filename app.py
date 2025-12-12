# app.py - Updated with chat history features
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import PyPDF2
import google.generativeai as genai
import markdown
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'change_this_in_production_123'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Replace with your real Gemini API key
genai.configure(api_key='GEMINI_API_KEY_HERE')

DB_NAME = 'notebook_lm.db'


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        # Create tables if they don't exist
        c.execute('''CREATE TABLE IF NOT EXISTS notebooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            created_at TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notebook_id INTEGER,
            pdf_path TEXT,
            file_name TEXT,
            uploaded_at TIMESTAMP,
            FOREIGN KEY (notebook_id) REFERENCES notebooks (id) ON DELETE CASCADE
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notebook_id INTEGER,
            session_id TEXT,
            message TEXT,
            is_user BOOLEAN,
            created_at TIMESTAMP,
            FOREIGN KEY (notebook_id) REFERENCES notebooks (id) ON DELETE CASCADE
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notebook_id INTEGER,
            title TEXT,
            content TEXT,
            created_at TIMESTAMP,
            FOREIGN KEY (notebook_id) REFERENCES notebooks (id) ON DELETE CASCADE
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notebook_id INTEGER,
            session_id TEXT UNIQUE,
            title TEXT,
            created_at TIMESTAMP,
            last_activity TIMESTAMP,
            FOREIGN KEY (notebook_id) REFERENCES notebooks (id) ON DELETE CASCADE
        )''')

        # Check if session_id column exists in chats table
        c.execute("PRAGMA table_info(chats)")
        columns = [column[1] for column in c.fetchall()]
        if 'session_id' not in columns:
            print("Adding session_id column to chats table...")
            try:
                c.execute("ALTER TABLE chats ADD COLUMN session_id TEXT")
                # Set default session_id for existing chats
                c.execute(
                    "UPDATE chats SET session_id = 'default' WHERE session_id IS NULL")
            except:
                pass

        # Check if file_name column exists, if not add it (without default)
        c.execute("PRAGMA table_info(materials)")
        columns = [column[1] for column in c.fetchall()]
        if 'file_name' not in columns:
            print("Adding file_name column to materials table...")
            try:
                c.execute("ALTER TABLE materials ADD COLUMN file_name TEXT")
            except:
                pass

        # Check if created_at columns exist (add without default first)
        c.execute("PRAGMA table_info(notebooks)")
        notebook_columns = [column[1] for column in c.fetchall()]
        if 'created_at' not in notebook_columns:
            print("Adding created_at column to notebooks table...")
            try:
                c.execute(
                    "ALTER TABLE notebooks ADD COLUMN created_at TIMESTAMP")
                # Update existing rows with current timestamp
                c.execute(
                    "UPDATE notebooks SET created_at = datetime('now') WHERE created_at IS NULL")
            except:
                pass

        c.execute("PRAGMA table_info(chats)")
        chat_columns = [column[1] for column in c.fetchall()]
        if 'created_at' not in chat_columns:
            print("Adding created_at column to chats table...")
            try:
                c.execute("ALTER TABLE chats ADD COLUMN created_at TIMESTAMP")
                # Update existing rows with current timestamp
                c.execute(
                    "UPDATE chats SET created_at = datetime('now') WHERE created_at IS NULL")
            except:
                pass

        # Also check uploaded_at for materials
        c.execute("PRAGMA table_info(materials)")
        material_columns = [column[1] for column in c.fetchall()]
        if 'uploaded_at' not in material_columns:
            print("Adding uploaded_at column to materials table...")
            try:
                c.execute(
                    "ALTER TABLE materials ADD COLUMN uploaded_at TIMESTAMP")
                # Update existing rows with current timestamp
                c.execute(
                    "UPDATE materials SET uploaded_at = datetime('now') WHERE uploaded_at IS NULL")
            except:
                pass

        conn.commit()


init_db()


def format_ai_response(text):
    """Format AI response with better markdown styling"""
    # Convert markdown to HTML
    html = markdown.markdown(text, extensions=['fenced_code', 'tables'])

    # Add custom classes for better styling
    html = html.replace('<h1>', '<h1 class="ai-heading-1">')
    html = html.replace('<h2>', '<h2 class="ai-heading-2">')
    html = html.replace('<h3>', '<h3 class="ai-heading-3">')
    html = html.replace('<ul>', '<ul class="ai-list">')
    html = html.replace('<ol>', '<ol class="ai-list">')
    html = html.replace('<li>', '<li class="ai-list-item">')
    html = html.replace('<p>', '<p class="ai-paragraph">')
    html = html.replace('<code>', '<code class="ai-code">')
    html = html.replace('<blockquote>', '<blockquote class="ai-quote">')

    return html


def parse_selected_sources(selected_sources_str):
    """Parse selected sources from string to list of integers"""
    if not selected_sources_str:
        return []

    # If it's already a list, return it as is
    if isinstance(selected_sources_str, list):
        return [int(x) for x in selected_sources_str if x]

    # If it's a comma-separated string, split it
    if isinstance(selected_sources_str, str):
        if ',' in selected_sources_str:
            return [int(x.strip()) for x in selected_sources_str.split(',') if x.strip()]
        elif selected_sources_str:
            return [int(selected_sources_str)]

    return []


def get_or_create_session(notebook_id, session_id=None):
    """Get existing session or create a new one"""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        if session_id:
            # Check if session exists
            c.execute('SELECT * FROM chat_sessions WHERE session_id = ? AND notebook_id = ?',
                      (session_id, notebook_id))
            session = c.fetchone()
            if session:
                # Update last activity
                c.execute('UPDATE chat_sessions SET last_activity = datetime("now") WHERE id = ?',
                          (session['id'],))
                conn.commit()
                return session_id

        # Create new session
        new_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        c.execute('''INSERT INTO chat_sessions 
                    (notebook_id, session_id, title, created_at, last_activity) 
                    VALUES (?, ?, ?, datetime("now"), datetime("now"))''',
                  (notebook_id, new_session_id, "New Chat"))
        conn.commit()
        return new_session_id


def get_chat_sessions(notebook_id):
    """Get all chat sessions for a notebook"""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''SELECT session_id, title, created_at, last_activity 
                    FROM chat_sessions 
                    WHERE notebook_id = ? 
                    ORDER BY last_activity DESC''', (notebook_id,))
        return c.fetchall()


def get_chat_messages(notebook_id, session_id):
    """Get chat messages for a specific session"""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''SELECT message, is_user, created_at 
                    FROM chats 
                    WHERE notebook_id = ? AND session_id = ? 
                    ORDER BY created_at''', (notebook_id, session_id))
        return c.fetchall()


@app.route('/')
def index():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            'SELECT id, subject, created_at FROM notebooks ORDER BY created_at DESC')
        notebooks = c.fetchall()
        notebooks_with_counts = []
        for nb in notebooks:
            c.execute(
                'SELECT COUNT(*) FROM materials WHERE notebook_id = ?', (nb['id'],))
            count = c.fetchone()[0]
            d = dict(nb)
            d['material_count'] = count
            notebooks_with_counts.append(d)
    return render_template('index.html', notebooks=notebooks_with_counts)


@app.route('/create_notebook', methods=['POST'])
def create_notebook():
    subject = request.form['subject'].strip()
    if subject:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO notebooks (subject, created_at) VALUES (?, datetime("now"))', (subject,))
            conn.commit()
            flash(f'Notebook "{subject}" created!', 'success')
    else:
        flash('Name cannot be empty!', 'error')
    return redirect(url_for('index'))


@app.route('/rename_notebook/<int:nb_id>', methods=['POST'])
def rename_notebook(nb_id):
    new_name = request.form.get('name', '').strip()
    if new_name:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute('UPDATE notebooks SET subject = ? WHERE id = ?',
                      (new_name, nb_id))
            conn.commit()
    return '', 204


@app.route('/delete_notebook/<int:nb_id>', methods=['POST'])
def delete_notebook(nb_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM notebooks WHERE id = ?', (nb_id,))
        conn.commit()
    return '', 204


@app.route('/delete_material/<int:mat_id>', methods=['POST'])
def delete_material(mat_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # Get the pdf_path first to delete the file
        c.execute('SELECT pdf_path FROM materials WHERE id = ?', (mat_id,))
        result = c.fetchone()
        if result:
            pdf_path = result[0]
            try:
                # Delete the file from uploads folder
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        c.execute('DELETE FROM materials WHERE id = ?', (mat_id,))
        conn.commit()
    return '', 204


@app.route('/delete_note/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM notes WHERE id = ?', (note_id,))
        conn.commit()
        return '', 204


@app.route('/rename_material/<int:mat_id>', methods=['POST'])
def rename_material(mat_id):
    data = request.json or {}
    new_filename = data.get('filename', '').strip()

    if not new_filename:
        return jsonify({'error': 'Filename cannot be empty'}), 400

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('UPDATE materials SET file_name = ? WHERE id = ?',
                  (new_filename, mat_id))
        conn.commit()
        return '', 204


@app.route('/save_note/<int:nb_id>', methods=['POST'])
def save_note(nb_id):
    data = request.json or {}
    title = data.get('title') or 'Untitled Note'
    content = data.get('content') or ''
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(
            'INSERT INTO notes (notebook_id, title, content, created_at) VALUES (?, ?, ?, datetime("now"))',
            (nb_id, title, content))
        conn.commit()
        note_id = c.lastrowid

        # read back the created_at timestamp so we can return it to the client
        c.execute('SELECT created_at FROM notes WHERE id = ?', (note_id,))
        row = c.fetchone()
        created_at = row[0] if row else None

    return jsonify({
        'id': note_id,
        'title': title,
        'content': content,
        'created_at': created_at
    }), 200


@app.route('/notes_list/<int:nb_id>', methods=['GET'])
def notes_list(nb_id):
    """
    Return JSON list of notes for a notebook, ordered by created_at desc.
    """
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            'SELECT id, title, created_at FROM notes WHERE notebook_id = ? ORDER BY created_at DESC',
            (nb_id,))
        rows = c.fetchall()
        notes = []
        for r in rows:
            notes.append({
                'id': r['id'],
                'title': r['title'],
                'created_at': r['created_at'],
            })
    return jsonify(notes), 200


@app.route('/update_note/<int:note_id>', methods=['POST'])
def update_note(note_id):
    data = request.json
    title = data.get('title')
    content = data.get('content')
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('UPDATE notes SET title = ?, content = ? WHERE id = ?',
                  (title, content, note_id))
        conn.commit()
    return '', 204


@app.route('/get_note/<int:note_id>', methods=['GET'])
def get_note(note_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT title, content FROM notes WHERE id = ?', (note_id,))
        note = c.fetchone()
        if note:
            return jsonify({'title': note['title'], 'content': note['content']})
        else:
            return jsonify({'error': 'Note not found'}), 404


@app.route('/new_chat_session/<int:nb_id>', methods=['POST'])
def new_chat_session(nb_id):
    """Create a new chat session"""
    session_id = get_or_create_session(nb_id)
    return jsonify({'session_id': session_id}), 200


@app.route('/get_chat_sessions/<int:nb_id>', methods=['GET'])
def get_chat_sessions_route(nb_id):
    """Get all chat sessions for a notebook"""
    sessions = get_chat_sessions(nb_id)
    sessions_list = []
    for session in sessions:
        sessions_list.append({
            'session_id': session['session_id'],
            'title': session['title'],
            'created_at': session['created_at'],
            'last_activity': session['last_activity']
        })
    return jsonify(sessions_list), 200


@app.route('/delete_chat_session/<int:nb_id>/<session_id>', methods=['DELETE'])
def delete_chat_session(nb_id, session_id):
    """Delete a chat session and its messages"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # Delete chat messages first
        c.execute(
            'DELETE FROM chats WHERE notebook_id = ? AND session_id = ?', (nb_id, session_id))
        # Delete the session
        c.execute(
            'DELETE FROM chat_sessions WHERE notebook_id = ? AND session_id = ?', (nb_id, session_id))
        conn.commit()
    return '', 204


@app.route('/rename_chat_session/<int:nb_id>/<session_id>', methods=['POST'])
def rename_chat_session(nb_id, session_id):
    """Rename a chat session"""
    data = request.json or {}
    new_title = data.get('title', '').strip()

    if not new_title:
        return jsonify({'error': 'Title cannot be empty'}), 400

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('UPDATE chat_sessions SET title = ? WHERE notebook_id = ? AND session_id = ?',
                  (new_title, nb_id, session_id))
        conn.commit()
    return '', 204


@app.route('/notebook/<int:nb_id>', methods=['GET', 'POST'])
def notebook(nb_id):
    session_id = request.args.get(
        'session_id') or request.form.get('session_id')

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('SELECT subject FROM notebooks WHERE id = ?', (nb_id,))
        nb = c.fetchone()
        if not nb:
            flash('Notebook not found', 'error')
            return redirect(url_for('index'))

        # Get or create session
        current_session_id = get_or_create_session(nb_id, session_id)

        # Get materials
        try:
            c.execute(
                'SELECT id, pdf_path, file_name FROM materials WHERE notebook_id = ? ORDER BY uploaded_at DESC', (nb_id,))
            materials = c.fetchall()
        except sqlite3.OperationalError:
            # If query fails due to missing columns, use simpler query
            c.execute(
                'SELECT id, pdf_path FROM materials WHERE notebook_id = ? ORDER BY id DESC', (nb_id,))
            rows = c.fetchall()
            materials = []
            for row in rows:
                mat_id, pdf_path = row
                # Try to get file_name if it exists
                c.execute("PRAGMA table_info(materials)")
                columns = [col[1] for col in c.fetchall()]
                if 'file_name' in columns:
                    c.execute(
                        'SELECT file_name FROM materials WHERE id = ?', (mat_id,))
                    file_name_result = c.fetchone()
                    file_name = file_name_result[0] if file_name_result else pdf_path
                else:
                    file_name = pdf_path
                materials.append(
                    {'id': mat_id, 'pdf_path': pdf_path, 'file_name': file_name})

        # Get chat messages for current session
        c.execute('''SELECT message, is_user, created_at 
                    FROM chats 
                    WHERE notebook_id = ? AND session_id = ? 
                    ORDER BY created_at''', (nb_id, current_session_id))

        chat_history = []
        for row in c.fetchall():
            if row['is_user']:
                chat_history.append((row['message'], True))
            else:
                formatted_message = format_ai_response(row['message'])
                chat_history.append((formatted_message, False))

        # Get chat sessions
        chat_sessions = get_chat_sessions(nb_id)

        # Get notes
        c.execute(
            'SELECT id, title, created_at FROM notes WHERE notebook_id = ? ORDER BY created_at DESC', (nb_id,))
        notes = c.fetchall()

        # Handle selected sources properly
        selected_sources_param = request.form.get(
            'selected_sources') or request.args.get('selected_sources')
        selected_ids = parse_selected_sources(selected_sources_param)

        # If no sources selected in request, use all materials
        if not selected_ids and materials:
            selected_ids = [m['id'] for m in materials]

        if request.method == 'POST':
            if 'pdf' in request.files:
                files = request.files.getlist('pdf')
                for file in files:
                    if file and file.filename.lower().endswith('.pdf'):
                        fn = secure_filename(file.filename)
                        file.save(os.path.join(
                            app.config['UPLOAD_FOLDER'], fn))
                        c.execute(
                            'INSERT INTO materials (notebook_id, pdf_path, file_name, uploaded_at) VALUES (?, ?, ?, datetime("now"))',
                            (nb_id, fn, file.filename))
                conn.commit()
                flash('PDFs uploaded!', 'success')
                return redirect(url_for('notebook', nb_id=nb_id, session_id=current_session_id))

            elif 'message' in request.form:
                user_msg = request.form['message'].strip()
                if user_msg:
                    # Save user message
                    c.execute(
                        'INSERT INTO chats (notebook_id, session_id, message, is_user, created_at) VALUES (?, ?, ?, 1, datetime("now"))',
                        (nb_id, current_session_id, user_msg))

                    # Update session title if it's the first user message in this session
                    c.execute('''SELECT COUNT(*) FROM chats 
                                WHERE notebook_id = ? AND session_id = ? AND is_user = 1''',
                              (nb_id, current_session_id))
                    user_message_count = c.fetchone()[0]

                    if user_message_count == 1:
                        # Use first user message as session title (truncated if too long)
                        title = user_msg[:50] + \
                            ('...' if len(user_msg) > 50 else '')
                        c.execute('''UPDATE chat_sessions SET title = ?, last_activity = datetime("now") 
                                    WHERE notebook_id = ? AND session_id = ?''',
                                  (title, nb_id, current_session_id))
                    else:
                        # Just update last activity
                        c.execute('''UPDATE chat_sessions SET last_activity = datetime("now") 
                                    WHERE notebook_id = ? AND session_id = ?''',
                                  (nb_id, current_session_id))

                    conn.commit()

                    context = ""
                    if selected_ids:
                        placeholders = ','.join('?' for _ in selected_ids)
                        c.execute(
                            f'SELECT pdf_path FROM materials WHERE id IN ({placeholders})', selected_ids)
                    else:
                        c.execute(
                            'SELECT pdf_path FROM materials WHERE notebook_id = ?', (nb_id,))
                    files_to_search = c.fetchall()

                    for row in files_to_search:
                        path = os.path.join(
                            app.config['UPLOAD_FOLDER'], row['pdf_path'])
                        try:
                            with open(path, 'rb') as f:
                                reader = PyPDF2.PdfReader(f)
                                for page in reader.pages:
                                    text = page.extract_text() or ""
                                    context += text + "\n"
                        except:
                            continue

                    try:
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        prompt = f"""You are a helpful assistant analyzing documents. Use ONLY the following context to answer. 
                        If the answer cannot be found in the context, say "Based on the provided documents, I cannot find information about this."
                        
                        Format your answer professionally using markdown with:
                        - Clear headings (## for main sections, ### for subsections)
                        - Bullet points for lists
                        - Bold for important terms
                        - Tables when comparing information
                        - Code blocks with language specification for technical content
                        
                        Context:
                        {context}
                        
                        Question: {user_msg}
                        
                        Provide a comprehensive, well-formatted answer:"""
                        response = model.generate_content(prompt)
                        ai_reply = response.text
                    except Exception as e:
                        ai_reply = f"Error generating response: {str(e)}"

                    # Save AI response
                    c.execute(
                        'INSERT INTO chats (notebook_id, session_id, message, is_user, created_at) VALUES (?, ?, ?, 0, datetime("now"))',
                        (nb_id, current_session_id, ai_reply))
                    conn.commit()

                    # Pass selected sources and session_id as query parameters
                    selected_sources_str = ','.join(
                        str(x) for x in selected_ids)
                    return redirect(url_for('notebook',
                                            nb_id=nb_id,
                                            session_id=current_session_id,
                                            selected_sources=selected_sources_str) + '#chatHistory')

        # Sidebar
        c.execute('SELECT id, subject FROM notebooks ORDER BY id DESC')
        all_nbs = c.fetchall()
        notebooks_with_counts = []
        for n in all_nbs:
            c.execute(
                'SELECT COUNT(*) FROM materials WHERE notebook_id = ?', (n['id'],))
            cnt = c.fetchone()[0]
            d = dict(n)
            d['material_count'] = cnt
            notebooks_with_counts.append(d)

    return render_template('notebook.html',
                           nb_id=nb_id,
                           subject=nb['subject'],
                           materials=materials,
                           chat_history=chat_history,
                           chat_sessions=chat_sessions,
                           current_session_id=current_session_id,
                           notebooks=notebooks_with_counts,
                           selected_sources=selected_ids,
                           notes=notes)


@app.route('/reset_db')
def reset_db():
    """Reset database - for development only"""
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    # Also clean up uploads folder
    for file in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

    init_db()
    flash('Database and uploads reset successfully!', 'success')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
