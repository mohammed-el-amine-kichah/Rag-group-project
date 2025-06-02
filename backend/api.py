from flask import Flask, request, jsonify, session, Response,stream_with_context , g
from flask_cors import CORS
from flask_session import Session
from functools import wraps
import os
import uuid
import datetime
import sqlite3 # Import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from rag.main import build_or_update_store
from rag.vector_store import VectorStore
from rag.retriever import retrieve_relevant_chunks
from rag.agent import generate_answer
from rag.settings import MEMORY_SIZE
import google.generativeai as genai
from rag.settings import GEMINI_API_KEY


store = VectorStore.load("vector_store")

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel('gemini-1.5-flash')

def classify_and_generate_title(user_msg: str):
    """
    Ask Gemini:
     - If this is only a greeting/pleasantry, respond with exactly SKIP
     - Otherwise, respond with up to 5 words that summarize the request.
    """
    prompt = f"""
أنت مساعد ذكي ودقيق.
إذا كانت رسالة المستخدم التالية مجرد تحية أو كلام عابر، فأجب تمامًا بالكلمة:
SKIP

وإلا، قم بكتابة عنوان موجز جداً (لا يتجاوز 5 كلمات) يصف طلب المستخدم باختصار شديد، ويجب أن يكون العنوان باللغة العربية فقط.

رسالة المستخدم:
\"\"\"{user_msg}\"\"\"
"""
    response = model.generate_content(prompt)
    out = response.text.strip() if hasattr(response, 'text') else response.generations[0].text.strip()
    return None if out == "SKIP" else out


# Initialize Flask
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = "bbe40792-2cb6-4d7a-b466-2f2c5ce16a34"  # Change in production
app.config['SESSION_TYPE'] = 'filesystem'  # Using filesystem-based sessions
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=7)  # Session expires after 7 days
app.config['UPLOAD_FOLDER'] = 'data'

# Setup CORS for React frontend
CORS(app, supports_credentials=True, origins=[
    "http://localhost:5173",  # Development React server
    "http://localhost:5000",  # Production server if served from Flask
    # Add your production domain here
])

# Initialize session
Session(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# SQLite Database Configuration
DATABASE_PATH = 'database.db' # Define your SQLite database file

def initialize_database(db):
    """Initializes the database tables if they do not already exist."""
    cursor = db.cursor()
    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create conversations table - Added is_new column
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY NOT NULL,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        is_title_changed BOOLEAN DEFAULT FALSE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        is_new BOOLEAN DEFAULT TRUE, -- Added is_new column with default TRUE
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Create messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY NOT NULL,
        conversation_id TEXT NOT NULL,
        is_user BOOLEAN NOT NULL,
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
    )
    """)
    db.commit() # Commit changes after creating tables


# --- SQLite Database Helper Functions ---
def get_db():
    """Establishes a database connection if not already present for the current request."""
    # Check if the database connection is already in the request context
    if 'db' not in g:
        # Check if the database file exists. If not, initialize it.
        # This ensures initialization happens on the first DB access,
        # regardless of how the app is started (dev server, gunicorn, etc.).
        db_exists = os.path.exists(DATABASE_PATH)

        g.db = sqlite3.connect(
            DATABASE_PATH,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row # Allows accessing columns by name

        # If the database file did not exist, initialize the tables
        if not db_exists:
            print("Database file not found. Initializing database tables.")
            initialize_database(g.db) # Pass the connection

    return g.db


@app.teardown_appcontext
def close_db(e=None):
    """Closes the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()
# --- End SQLite Database Helper Functions ---

# Load (or create) the vector store at startup

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

# Routes for authentication
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    
    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required"}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Check if user already exists
    cursor.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    )
    existing_user = cursor.fetchone()
    
    if existing_user:
        return jsonify({"error": "User with this email already exists"}), 400
    
    # Create new user
    user_id = str(uuid.uuid4())
    hashed_password = generate_password_hash(password)
    
    try:
        cursor.execute(
            "INSERT INTO users (id, name, email, password) VALUES (?, ?, ?, ?)",
            (user_id, name, email, hashed_password)
        )
        db.commit() # Commit the new user
        
        # Create session
        session['user_id'] = user_id
        
        return jsonify({
            "message": "User registered successfully",
            "user": {
                "id": user_id,
                "name": name,
                "email": email
            }
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    
    db = get_db()
    cursor = db.cursor()

    # Find user
    cursor.execute(
        "SELECT id, name, email, password FROM users WHERE email = ?", (email,)
    )
    user = cursor.fetchone() # Use fetchone() for single row

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401
    
    # Check password (user[3] is the 'password' column)
    if not check_password_hash(user['password'], password):
        return jsonify({"error": "Invalid email or password"}), 401
    
    # Create session (user[0] is 'id', user[1] is 'name', user[2] is 'email')
    
    session['user_id'] = user['id']


    return jsonify({
        "message": "Login successful",
        "user": {
            "id": user['id'],
            "name": user['name'],
            "email": user['email']
        }
    }), 200

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({"message": "Logout successful"}), 200

@app.route('/api/session', methods=['GET'])
def get_session():

    print(session)

    if 'user_id' not in session:
        return jsonify({"authenticated": False}), 200
    
    
    db = get_db()
    cursor = db.cursor()


    cursor.execute(
        "SELECT id, name, email FROM users WHERE id = ?", (session['user_id'],)
    )
    user = cursor.fetchone()
    
    if not user:
        session.pop('user_id', None)
        return jsonify({"authenticated": False}), 200
    
    return jsonify({
        "authenticated": True,
        "user": {
            "id": user['id'],
            "name": user['name'],
            "email": user['email']
        }
    }), 200

# Conversations & Messages routes
@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor()

    # Include is_new in the select statement
    cursor.execute(
        """
        SELECT id, title, created_at, updated_at, is_new
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (user_id,)
        
    )
    conversations = cursor.fetchall()

    result = []
    for conv in conversations:
        result.append({
            "id": conv['id'],
            "title": conv['title'],
        })

    return jsonify({"conversations": result}), 200

@app.route('/api/conversations', methods=['POST'])
@login_required
def create_conversation():
    # The title might be provided, but we prioritize finding an existing new conversation
    data = request.get_json()
    requested_title = data.get('title', 'New Conversation')

    user_id = session['user_id']
    db = get_db()
    cursor = db.cursor()

    # Check if an existing 'new' conversation exists for this user
    cursor.execute(
        "SELECT id, title FROM conversations WHERE user_id = ? AND is_new = TRUE LIMIT 1",
        (user_id,)
    )
    existing_new_conversation = cursor.fetchone()

    print(existing_new_conversation)

    if existing_new_conversation:
        # If a 'new' conversation exists, return it
        return jsonify({
                "id": existing_new_conversation['id'],
                "title": existing_new_conversation['title']
        }), 200 # Use 200 OK as we are not creating a new resource

    # If no 'new' conversation exists, create a new one
    conversation_id = str(uuid.uuid4())
    title_to_use = requested_title # Use the requested title or default

    try:
        cursor.execute(
            "INSERT INTO conversations (id, user_id, title, is_new) VALUES (?, ?, ?, TRUE)",
            (conversation_id, user_id, title_to_use)
        )
        db.commit() # Commit the new conversation

        return jsonify({
            "id": conversation_id,
            "title": title_to_use
        }), 201 # Use 201 Created as a new resource was made
    except Exception as e:
        db.rollback() # Rollback changes if something goes wrong
        return jsonify({"error": str(e)}), 500


@app.route('/api/conversations/<conversation_id>', methods=['GET'])
@login_required
def get_conversation(conversation_id):
    user_id = session['user_id']
    
    db = get_db()
    cursor = db.cursor()

    # Verify conversation belongs to user
    cursor.execute(
        "SELECT id, title FROM conversations WHERE id = ? AND user_id = ?",
        (conversation_id, user_id)
    )
    conversation = cursor.fetchone()
    
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404
    
    # Get messages
    cursor.execute(
        """
        SELECT id, is_user, content, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at DESC
        """,
        (conversation_id,)
    )
    messages = cursor.fetchall()
    
    messages_list = []
    for msg in messages:
        messages_list.append({
            "id": msg['id'],
            "is_user": bool(msg['is_user'] ),
            "content": msg['content'],
            "created_at": msg['created_at']
        })
    
    return jsonify({
            "id": conversation['id'],
            "title": conversation['title'],
            "messages": messages_list
    }), 200

# @app.route('/api/conversations/<conversation_id>/messages', methods=['POST'])
# @login_required
# def send_message(conversation_id):
#     user_id = session['user_id']
#     data = request.get_json()
#     message = data.get('message')
    
#     if not message:
#         return jsonify({"error": "Message content is required"}), 400
    
#     db = get_db()
#     cursor = db.cursor()

#     # Verify conversation belongs to user
#     cursor.execute(
#         "SELECT id , is_new , is_title_changed FROM conversations WHERE id = ? AND user_id = ?",
#         (conversation_id, user_id)
#     )
#     conversation = cursor.fetchone()
    
#     if not conversation:
#         return jsonify({"error": "Conversation not found"}), 404

#     if bool(conversation['is_new']) == True:
#         # If the conversation is new, set is_new to False
#         cursor.execute(
#             "UPDATE conversations SET is_new = FALSE WHERE id = ?",
#             (conversation_id,)
#         )
#         db.commit() # Commit the update

    

#     message_id = str(uuid.uuid4())

#     if bool(conversation['is_title_changed']) == False:
        
#         new_title = classify_and_generate_title(message)
        
#         if new_title:

#         # If the title has not been changed, update it to the first message
#             cursor.execute(
#                 "UPDATE conversations SET title = ?, is_title_changed = TRUE WHERE id = ?",
#                 (new_title, conversation_id)
#             )
#             db.commit()
    
#     # Add user message to database
#     cursor.execute(
#         "INSERT INTO messages (id, conversation_id, is_user, content) VALUES (?, ?, ?, ?)",
#         (message_id, conversation_id, True, message)
#     )
    
#     db.commit() # Commit user message and conversation update
    
#     # Get conversation history for context
#     cursor.execute(
#         """
#         SELECT is_user, content FROM messages
#         WHERE conversation_id = ?
#         ORDER BY created_at ASC
#         LIMIT ?
#         """,
#         (conversation_id, MEMORY_SIZE * 2)  # Get enough for context
#     )
#     history = cursor.fetchall()
    
#     conversation_history = []
#     for i in range(0, len(history), 2):
#         if i + 1 < len(history):
#             # Create pairs of (user_message, assistant_response)
#             if history[i]['is_user'] and not history[i+1]['is_user']:  # If user then assistant
#                 conversation_history.append((history[i]['content'], history[i+1]['content']))
    
#     # Use RAG to generate response
#     print(conversation_history)
#     chunks = retrieve_relevant_chunks(store, message, top_k=5)
#     answer = generate_answer(chunks, message, conversation_history)
    
#     # Add assistant response to database
#     assistant_message_id = str(uuid.uuid4())
#     cursor.execute(
#         "INSERT INTO messages (id, conversation_id, is_user, content) VALUES (?, ?, ?, ?)",
#         (assistant_message_id, conversation_id, False, answer)
#     )
#     db.commit() # Commit assistant message
    
#     return jsonify({
#             "id": assistant_message_id,
#             "is_user": False,
#             "content": answer
#     }), 200

@app.route('/api/stream-answer/<conversation_id>/messages', methods=['POST'])
@login_required
def stream_answer(conversation_id):
    from rag.agent import model, build_prompt  # we'll add build_prompt below

    user_id = session['user_id']
    data = request.get_json()
    message = data.get('message')

    if not message:
        return jsonify({"error": "Message content is required"}), 400

    db = get_db()
    cursor = db.cursor()

    # Validate conversation ownership
    cursor.execute("SELECT id , is_new, is_title_changed FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
    conversation = cursor.fetchone()
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404

    if bool(conversation['is_new']) == True:
        # If the conversation is new, set is_new to False
        cursor.execute(
            "UPDATE conversations SET is_new = FALSE WHERE id = ?",
            (conversation_id,)
        )
        db.commit() # Commit the update

    if bool(conversation['is_title_changed']) == False:
        
        new_title = classify_and_generate_title(message)
        
        if new_title:

        # If the title has not been changed, update it to the first message
            cursor.execute(
                "UPDATE conversations SET title = ?, is_title_changed = TRUE WHERE id = ?",
                (new_title, conversation_id)
            )
            db.commit()

    message_id = str(uuid.uuid4())
    # Add user message to database
    cursor.execute(
        "INSERT INTO messages (id, conversation_id, is_user, content) VALUES (?, ?, ?, ?)",
        (message_id, conversation_id, True, message)
    )
    
    db.commit() # Commit user message

    # Build history
    cursor.execute("""
        SELECT is_user, content FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
        LIMIT ?
    """, (conversation_id, MEMORY_SIZE * 2))
    history = cursor.fetchall()
    conversation_history = [
        (history[i]['content'], history[i + 1]['content'])
        for i in range(0, len(history) - 1, 2)
        if history[i]['is_user'] and not history[i + 1]['is_user']
    ]

    chunks = retrieve_relevant_chunks(store, message, top_k=5)
    prompt = build_prompt(chunks, message, conversation_history)

    def generate():
        for chunk in model.generate_content(prompt, stream=True):
            if chunk.text:
                yield chunk.text

    return Response(stream_with_context(generate()), mimetype='text/plain')


@app.route('/api/stream-answer/<conversation_id>/ai-message', methods=['POST'])
@login_required
def save_ai_answer(conversation_id):
    user_id = session['user_id']
    data = request.get_json()
    message = data.get('message')

    if not message:
        return jsonify({"error": "Message content is required"}), 400

    db = get_db()
    cursor = db.cursor()

    # Validate conversation ownership
    cursor.execute("SELECT id FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
    conversation = cursor.fetchone()
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404


    message_id = str(uuid.uuid4())
    # Add user message to database
    cursor.execute(
        "INSERT INTO messages (id, conversation_id, is_user, content) VALUES (?, ?, ?, ?)",
        (message_id, conversation_id, False, message)
    )
    
    db.commit() # Commit user message

    
    return jsonify({ "success" : True, "message" : "Ai message inserted in db successfully"}),200



# Document upload route
@app.route('/api/upload', methods=['POST'])
@login_required
def upload():
    """Upload a new DOCX/TXT file; triggers incremental indexing."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Update store incrementally
    # Assuming build_or_update_store and VectorStore.load still work as expected
    # and do not directly interact with the database (only local files).
    build_or_update_store({filename}, "vector_store/index.faiss")
    
    return jsonify({"status": "indexed", "file": filename}), 200



if __name__ == '__main__':
    # It's good practice to initialize the DB once when the app starts
    # if you're sure it hasn't been initialized before, 
    # or let the /api/initialize endpoint handle it.
    # For a simple dev setup, you might call initialize_database() directly here.
    # However, for a Flask app, it's often better to let the teardown context 
    # manage the connection lifecycle.
    # To ensure the DB file is created if not exists, `get_db()` will create it.
    # Then, the `initialize_database()` function needs to be called to create tables.
    
    # You could call initialize_database() here for first-time setup
    # with proper error handling or let the /api/initialize endpoint be the trigger.
    # For demonstration purposes, calling it on startup might be desired
    # if you don't want to manually hit the /api/initialize endpoint.
    try:
        with app.app_context():
            initialize_database()
            print("Database tables initialized if not existing.")
    except Exception as e:
        print(f"Error initializing database on startup: {e}")


    app.run(debug=True)