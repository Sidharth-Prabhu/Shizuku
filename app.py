# app.py - Simplified version without created_at issues
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import PyPDF2
import google.generativeai as genai
import markdown

app = Flask(__name__)
app.secret_key = 'change_this_in_production'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Gemini API
genai.configure(api_key='AIzaSyAXBGtt1y1pos91QMlzXARLn0lSLknwLXw')

DB_NAME = 'notebook_lm.db'


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS notebooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notebook_id INTEGER,
                pdf_path TEXT,
                FOREIGN KEY (notebook_id) REFERENCES notebooks (id) ON DELETE CASCADE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notebook_id INTEGER,
                message TEXT,
                is_user BOOLEAN,
                FOREIGN KEY (notebook_id) REFERENCES notebooks (id) ON DELETE CASCADE
            )
        ''')
        conn.commit()


init_db()


@app.route('/')
def index():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT id, subject FROM notebooks ORDER BY id DESC')
        notebooks = c.fetchall()

        # Get material counts for each notebook
        notebooks_with_counts = []
        for nb in notebooks:
            c.execute(
                'SELECT COUNT(*) as count FROM materials WHERE notebook_id = ?', (nb['id'],))
            count_result = c.fetchone()
            material_count = count_result['count'] if count_result else 0

            notebook_dict = dict(nb)
            notebook_dict['material_count'] = material_count
            notebooks_with_counts.append(notebook_dict)

    return render_template('index.html', notebooks=notebooks_with_counts)


@app.route('/create_notebook', methods=['POST'])
def create_notebook():
    subject = request.form['subject'].strip()
    if subject:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute('INSERT INTO notebooks (subject) VALUES (?)', (subject,))
            conn.commit()
            flash(f'Notebook "{subject}" created successfully!', 'success')
    else:
        flash('Notebook name cannot be empty!', 'error')
    return redirect(url_for('index'))


@app.route('/notebook/<int:nb_id>', methods=['GET', 'POST'])
def notebook(nb_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get notebook details
        c.execute('SELECT subject FROM notebooks WHERE id = ?', (nb_id,))
        nb = c.fetchone()
        if not nb:
            flash('Notebook not found', 'error')
            return redirect(url_for('index'))

        # Get materials
        c.execute(
            'SELECT pdf_path FROM materials WHERE notebook_id = ? ORDER BY id DESC', (nb_id,))
        materials = [row['pdf_path'] for row in c.fetchall()]

        # Get chat history
        c.execute(
            'SELECT message, is_user FROM chats WHERE notebook_id = ? ORDER BY id', (nb_id,))
        chat_history = [(markdown.markdown(row['message']),
                         row['is_user']) for row in c.fetchall()]

        if request.method == 'POST':
            if 'pdf' in request.files:
                files = request.files.getlist('pdf')
                uploaded_files = []
                for file in files:
                    if file and file.filename.endswith('.pdf'):
                        filename = secure_filename(file.filename)
                        file.save(os.path.join(
                            app.config['UPLOAD_FOLDER'], filename))
                        c.execute(
                            'INSERT INTO materials (notebook_id, pdf_path) VALUES (?, ?)', (nb_id, filename))
                        uploaded_files.append(filename)
                if uploaded_files:
                    conn.commit()
                    flash(
                        f'Successfully uploaded {len(uploaded_files)} PDF(s)', 'success')

            elif 'message' in request.form:
                user_msg = request.form['message'].strip()
                if user_msg:
                    c.execute(
                        'INSERT INTO chats (notebook_id, message, is_user) VALUES (?, ?, 1)', (nb_id, user_msg))
                    conn.commit()

                    context = ""
                    for pdf_file in materials:
                        path = os.path.join(
                            app.config['UPLOAD_FOLDER'], pdf_file)
                        try:
                            with open(path, 'rb') as f:
                                reader = PyPDF2.PdfReader(f)
                                for page in reader.pages:
                                    text = page.extract_text()
                                    if text:
                                        context += text + "\n"
                        except:
                            continue

                    try:
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        prompt = f"""You are a helpful AI assistant for a Notebook LM application. Use ONLY the following context to answer the user's question. 
                        If the answer cannot be found in the context, say "I cannot find that information in the uploaded documents."
                        
                        Context:
                        {context}
                        
                        Question: {user_msg}
                        
                        Provide a helpful, accurate answer based only on the context above. Use markdown formatting for readability."""
                        response = model.generate_content(prompt)
                        ai_reply = response.text
                    except Exception as e:
                        ai_reply = f"**Error generating response:** {str(e)}"

                    c.execute(
                        'INSERT INTO chats (notebook_id, message, is_user) VALUES (?, ?, 0)', (nb_id, ai_reply))
                    conn.commit()

            return redirect(url_for('notebook', nb_id=nb_id))

    # Get all notebooks for sidebar
    c.execute('SELECT id, subject FROM notebooks ORDER BY id DESC')
    all_notebooks = c.fetchall()
    notebooks_with_counts = []
    for nb in all_notebooks:
        c.execute(
            'SELECT COUNT(*) as count FROM materials WHERE notebook_id = ?', (nb['id'],))
        count_result = c.fetchone()
        material_count = count_result['count'] if count_result else 0

        notebook_dict = dict(nb)
        notebook_dict['material_count'] = material_count
        notebooks_with_counts.append(notebook_dict)

    return render_template('notebook.html',
                           nb_id=nb_id,
                           subject=nb['subject'],
                           materials=materials,
                           chat_history=chat_history,
                           notebooks=notebooks_with_counts)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
