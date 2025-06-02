from fastapi import FastAPI, Request, HTTPException, Depends, status, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Generator
from werkzeug.security import generate_password_hash, check_password_hash  
import psycopg2
from psycopg2.extras import RealDictCursor
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



app = FastAPI()

# Add session middleware (equivalent to Flask-Session)
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-here")

# Add CORS middleware (equivalent to Flask-CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DATABASE_URL = os.getenv("DATABASE_URL") 

def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    try:
        db = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor  
        )
        yield db
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection failed"
        )
    finally:
        if 'db' in locals():
            db.close()


# Pydantic models for request validation
class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str


@app.middleware("http")
async def close_db_connection(request: Request, call_next):
    """Middleware to ensure database connections are closed after each request"""
    response = await call_next(request)
    
    # Close database connection if it exists
    if hasattr(request.state, 'db'):
        request.state.db.close()
    
    return response

# Authentication dependency (replaces @login_required decorator)
async def login_required(request: Request):
    """
    Dependency to check if user is authenticated.
    Raises HTTPException if not authenticated.
    """
    if 'user_id' not in request.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return request.session['user_id']

# Optional: Dependency to get current user info
async def get_current_user(request: Request, user_id: str = Depends(login_required),db: psycopg2.extensions.connection = Depends(get_db_connection)):

    cursor = db.cursor()
    
    cursor.execute(
        "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
    )
    user = cursor.fetchone()
    
    if not user:
        # Clear invalid session
        request.session.pop('user_id', None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
    
    return user

# Routes for authentication
@app.post('/api/signup', response_model=Dict[str, Any], status_code=201)
async def signup(request: Request, signup_data: SignupRequest,db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """User registration endpoint"""
    
    # Input validation is handled by Pydantic automatically
    # But you can add additional validation if needed
    if not signup_data.name.strip() or not signup_data.email.strip() or not signup_data.password.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name, email and password are required"
        )

    cursor = db.cursor()
    
    # Check if user already exists
    cursor.execute(
        "SELECT id FROM users WHERE email = ?", (signup_data.email,)
    )
    existing_user = cursor.fetchone()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create new user
    user_id = str(uuid.uuid4())
    hashed_password = generate_password_hash(signup_data.password)
    
    try:
        cursor.execute(
            "INSERT INTO users (id, name, email, password) VALUES (?, ?, ?, ?)",
            (user_id, signup_data.name, signup_data.email, hashed_password)
        )
        db.commit()
        
        # Create session
        request.session['user_id'] = user_id
        
        return {
            "message": "User registered successfully",
            "user": {
                "id": user_id,
                "name": signup_data.name,
                "email": signup_data.email
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post('/api/login', response_model=Dict[str, Any])
async def login(request: Request, login_data: LoginRequest,db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """User login endpoint"""

    cursor = db.cursor()

    # Find user
    cursor.execute(
        "SELECT id, name, email, password FROM users WHERE email = ?", (login_data.email,)
    )
    user = cursor.fetchone()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check password
    if not check_password_hash(user['password'], login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create session
    request.session['user_id'] = user['id']

    return {
        "message": "Login successful",
        "user": {
            "id": user['id'],
            "name": user['name'],
            "email": user['email']
        }
    }

@app.post('/api/logout', response_model=Dict[str, str])
async def logout(request: Request):
    """User logout endpoint"""
    request.session.pop('user_id', None)
    return {"message": "Logout successful"}

@app.get('/api/session', response_model=Dict[str, Any])
async def get_session(request: Request, db: psycopg2.extensions.connection = Depends(get_db_connection)):
    """Get current session information"""
    
    print(request.session)  # Debug print (same as Flask version)

    if 'user_id' not in request.session:
        return {"authenticated": False}

    cursor = db.cursor()

    cursor.execute(
        "SELECT id, name, email FROM users WHERE id = ?", (request.session['user_id'],)
    )
    user = cursor.fetchone()
    
    if not user:
        request.session.pop('user_id', None)
        return {"authenticated": False}
    
    return {
        "authenticated": True,
        "user": {
            "id": user['id'],
            "name": user['name'],
            "email": user['email']
        }
    }



class ConversationResponse(BaseModel):
    id: str
    title: str

class ConversationsListResponse(BaseModel):
    conversations: list[ConversationResponse]

class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"

class CreateConversationResponse(BaseModel):
    id: str
    title: str

# Conversations & Messages routes
@app.get('/api/conversations', response_model=ConversationsListResponse)
async def get_conversations(
    request: Request,
    user_id: str = Depends(login_required),
    db: psycopg2.extensions.connection = Depends(get_db_connection)
):
    """Get all conversations for the authenticated user"""
    
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

    return {"conversations": result}

@app.post('/api/conversations', response_model=CreateConversationResponse)
async def create_conversation(
    request: Request,
    conversation_data: CreateConversationRequest,
    user_id: str = Depends(login_required),
    db: psycopg2.extensions.connection = Depends(get_db_connection)
):
    """Create a new conversation or return existing 'new' conversation"""
    
    # The title might be provided, but we prioritize finding an existing new conversation
    requested_title = conversation_data.title
    
    cursor = db.cursor()

    # Check if an existing 'new' conversation exists for this user
    cursor.execute(
        "SELECT id, title FROM conversations WHERE user_id = ? AND is_new = TRUE LIMIT 1",
        (user_id,)
    )
    existing_new_conversation = cursor.fetchone()

    print(existing_new_conversation)

    if existing_new_conversation:
        # If a 'new' conversation exists, return it with 200 OK status
        return CreateConversationResponse(
            id=existing_new_conversation['id'],
            title=existing_new_conversation['title']
        )

    # If no 'new' conversation exists, create a new one
    conversation_id = str(uuid.uuid4())
    title_to_use = requested_title  # Use the requested title or default

    try:
        cursor.execute(
            "INSERT INTO conversations (id, user_id, title, is_new) VALUES (?, ?, ?, TRUE)",
            (conversation_id, user_id, title_to_use)
        )
        db.commit()  # Commit the new conversation

        # Return with 201 Created status (FastAPI automatically uses 201 for POST)
        return CreateConversationResponse(
            id=conversation_id,
            title=title_to_use
        )
    except Exception as e:
        db.rollback()  # Rollback changes if something goes wrong
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

class ConversationResponse(BaseModel):
    id: str
    title: str

class ConversationsListResponse(BaseModel):
    conversations: list[ConversationResponse]

class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"

class CreateConversationResponse(BaseModel):
    id: str
    title: str

# Conversations & Messages routes
@app.get('/api/conversations', response_model=ConversationsListResponse)
async def get_conversations(
    request: Request,
    user_id: str = Depends(login_required),
    db: psycopg2.extensions.connection = Depends(get_db_connection)
):
    """Get all conversations for the authenticated user"""
    
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

    return {"conversations": result}

@app.post('/api/conversations', response_model=CreateConversationResponse)
async def create_conversation(
    request: Request,
    conversation_data: CreateConversationRequest,
    user_id: str = Depends(login_required),
    db: psycopg2.extensions.connection = Depends(get_db_connection)
):
    """Create a new conversation or return existing 'new' conversation"""
    
    # The title might be provided, but we prioritize finding an existing new conversation
    requested_title = conversation_data.title
    
    cursor = db.cursor()

    # Check if an existing 'new' conversation exists for this user
    cursor.execute(
        "SELECT id, title FROM conversations WHERE user_id = ? AND is_new = TRUE LIMIT 1",
        (user_id,)
    )
    existing_new_conversation = cursor.fetchone()

    print(existing_new_conversation)

    if existing_new_conversation:
        # If a 'new' conversation exists, return it with 200 OK status
        return CreateConversationResponse(
            id=existing_new_conversation['id'],
            title=existing_new_conversation['title']
        )

    # If no 'new' conversation exists, create a new one
    conversation_id = str(uuid.uuid4())
    title_to_use = requested_title  # Use the requested title or default

    try:
        cursor.execute(
            "INSERT INTO conversations (id, user_id, title, is_new) VALUES (?, ?, ?, TRUE)",
            (conversation_id, user_id, title_to_use)
        )
        db.commit()  # Commit the new conversation

        # Return with 201 Created status (FastAPI automatically uses 201 for POST)
        return CreateConversationResponse(
            id=conversation_id,
            title=title_to_use
        )
    except Exception as e:
        db.rollback()  # Rollback changes if something goes wrong
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Additional Pydantic models for messages
class MessageResponse(BaseModel):
    id: str
    is_user: bool
    content: str
    created_at: str  # or datetime if you prefer

class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    messages: list[MessageResponse]

# Get specific conversation with messages
@app.get('/api/conversations/{conversation_id}', response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    request: Request,
    user_id: str = Depends(login_required),
    db: psycopg2.extensions.connection = Depends(get_db_connection)
):
    """Get a specific conversation with all its messages"""
    
    cursor = db.cursor()

    # Verify conversation belongs to user
    cursor.execute(
        "SELECT id, title FROM conversations WHERE id = ? AND user_id = ?",
        (conversation_id, user_id)
    )
    conversation = cursor.fetchone()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
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
            "is_user": bool(msg['is_user']),
            "content": msg['content'],
            "created_at": str(msg['created_at'])  # Convert to string for JSON serialization
        })
    
    return ConversationDetailResponse(
        id=conversation['id'],
        title=conversation['title'],
        messages=messages_list
    )


class MessageRequest(BaseModel):
    message: str

class SaveMessageResponse(BaseModel):
    success: bool
    message: str

# Import your RAG components (adjust import path as needed)
# from rag.agent import model, build_prompt

@app.post('/api/stream-answer/{conversation_id}/messages')
async def stream_answer(
    conversation_id: str,
    message_data: MessageRequest,
    request: Request,
    user_id: str = Depends(login_required),
    db: psycopg2.extensions.connection = Depends(get_db_connection)
):
    """Stream AI response for a conversation message"""
    
    from rag.agent import model, build_prompt  # Import your RAG components
    
    message = message_data.message
    
    if not message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content is required"
        )

    cursor = db.cursor()

    # Validate conversation ownership
    cursor.execute(
        "SELECT id, is_new, is_title_changed FROM conversations WHERE id = ? AND user_id = ?", 
        (conversation_id, user_id)
    )
    conversation = cursor.fetchone()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Handle new conversation logic
    if bool(conversation['is_new']) == True:
        # If the conversation is new, set is_new to False
        cursor.execute(
            "UPDATE conversations SET is_new = FALSE WHERE id = ?",
            (conversation_id,)
        )
        db.commit()  # Commit the update

    # Handle title generation logic
    if bool(conversation['is_title_changed']) == False:
        new_title = classify_and_generate_title(message)  # You'll need to implement this
        
        if new_title:
            # If the title has not been changed, update it to the first message
            cursor.execute(
                "UPDATE conversations SET title = ?, is_title_changed = TRUE WHERE id = ?",
                (new_title, conversation_id)
            )
            db.commit()

    # Add user message to database
    message_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO messages (id, conversation_id, is_user, content) VALUES (?, ?, ?, ?)",
        (message_id, conversation_id, True, message)
    )
    db.commit()  # Commit user message

    # Build conversation history
    cursor.execute("""
        SELECT is_user, content FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
        LIMIT ?
    """, (conversation_id, MEMORY_SIZE * 2))  # You'll need to define MEMORY_SIZE
    
    history = cursor.fetchall()
    conversation_history = [
        (history[i]['content'], history[i + 1]['content'])
        for i in range(0, len(history) - 1, 2)
        if history[i]['is_user'] and not history[i + 1]['is_user']
    ]

    # Retrieve relevant chunks and build prompt
    chunks = retrieve_relevant_chunks(store, message, top_k=5)  # You'll need to implement this
    prompt = build_prompt(chunks, message, conversation_history)

    def generate() -> Generator[str, None, None]:
        """Generator function for streaming response"""
        try:
            for chunk in model.generate_content(prompt, stream=True):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"Error: {str(e)}"

    # Return streaming response
    return StreamingResponse(
        generate(),
        media_type='text/plain',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }
    )

@app.post('/api/stream-answer/{conversation_id}/ai-message', response_model=SaveMessageResponse)
async def save_ai_answer(
    conversation_id: str,
    message_data: MessageRequest,
    request: Request,
    user_id: str = Depends(login_required),
    db: psycopg2.extensions.connection = Depends(get_db_connection)
):
    """Save AI response message to database"""
    
    message = message_data.message
    
    if not message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content is required"
        )

    cursor = db.cursor()

    # Validate conversation ownership
    cursor.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ?", 
        (conversation_id, user_id)
    )
    conversation = cursor.fetchone()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Add AI message to database
    message_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO messages (id, conversation_id, is_user, content) VALUES (?, ?, ?, ?)",
        (message_id, conversation_id, False, message)
    )
    db.commit()  # Commit AI message

    return SaveMessageResponse(
        success=True,
        message="AI message inserted in db successfully"
    )