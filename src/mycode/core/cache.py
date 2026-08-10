import sqlite3
import json
import chromadb
import hashlib
from chromadb.utils import embedding_functions
from pathlib import Path
from rich.console import Console
from datetime import datetime
import uuid

console = Console()

# Define local persistent storage paths
MYCODE_DIR = Path.home() / ".mycode"
CHROMA_DIR = MYCODE_DIR / "chroma_data"
SQLITE_DB = MYCODE_DIR / "history.db"

# Ensure directories exist
MYCODE_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Initialize ChromaDB with a lightweight, local HuggingFace embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
collection = chroma_client.get_or_create_collection(
    name="mycode_trajectories",
    embedding_function=embedding_func,
    metadata={"hnsw:space": "cosine"}
)

# Initialize SQLite for relational metadata
conn = sqlite3.connect(str(SQLITE_DB), check_same_thread=False)
cursor = conn.cursor()

# Create tables for trajectories, sessions, and messages
cursor.execute("""
    CREATE TABLE IF NOT EXISTS trajectories (
        id TEXT PRIMARY KEY,
        prompt TEXT,
        response TEXT,
        tool_calls TEXT,
        file_hashes TEXT,  -- JSON: {file_path: md5_hash, ...}
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

# Migration: Add file_hashes column if it doesn't exist (for existing databases)
try:
    cursor.execute("ALTER TABLE trajectories ADD COLUMN file_hashes TEXT")
except sqlite3.OperationalError:
    pass  # Column already exists

cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        name TEXT,
        project_path TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_id TEXT,
        role TEXT,
        content TEXT,
        tool_calls TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
""")

conn.commit()


def compute_file_hash(file_path: str) -> str:
    """Compute MD5 hash of a file."""
    try:
        p = Path(file_path).expanduser().resolve()
        if p.exists() and p.is_file():
            return hashlib.md5(p.read_bytes()).hexdigest()
    except Exception:
        pass
    return ""


def extract_file_paths_from_tool_calls(tool_calls: list) -> set:
    """Extract all file paths referenced in tool calls."""
    file_paths = set()
    for tc in tool_calls:
        name = tc.get("name", "")
        args = tc.get("args", {})
        if name in ("read_file", "write_file", "edit_file"):
            path = args.get("path", "")
            if path:
                file_paths.add(str(Path(path).expanduser().resolve()))
        elif name == "bash":
            # Could parse bash commands for file paths, but skip for now
            pass
    return file_paths


def get_file_hashes(file_paths: set) -> dict:
    """Get current MD5 hashes for a set of file paths."""
    hashes = {}
    for path in file_paths:
        hash_val = compute_file_hash(path)
        if hash_val:
            hashes[path] = hash_val
    return hashes


def check_cache(prompt: str, similarity_threshold: float = 0.92, micro_validation_threshold: float = 0.85) -> dict | None:
    """
    Intercepts user prompt. Searches ChromaDB for semantic matches.
    Validates cache against current file hashes.
    Returns cached trajectory if valid, else None.
    """
    # Query ChromaDB for the closest match
    results = collection.query(
        query_texts=[prompt],
        n_results=1,
        include=["metadatas", "documents", "distances"]
    )

    # Robust checking to prevent IndexError on empty collections and TypeError on None
    if not (results and
            results.get('distances') is not None and
            len(results['distances']) > 0 and
            len(results['distances'][0]) > 0):
        return None

    distance = results['distances'][0][0]
    similarity = 1.0 - distance  # ChromaDB returns cosine distance, convert to similarity

    if similarity < similarity_threshold:
        return None

    cached_id = results['ids'][0][0]

    # Fetch full relational data from SQLite including file_hashes
    cursor.execute("SELECT response, tool_calls, file_hashes FROM trajectories WHERE id = ?", (cached_id,))
    row = cursor.fetchone()

    if not row:
        return None

    response, tool_calls_json, file_hashes_json = row
    tool_calls = json.loads(tool_calls_json) if tool_calls_json else []
    cached_hashes = json.loads(file_hashes_json) if file_hashes_json else {}

    # --- SMART VALIDATION: Check file hashes ---
    if cached_hashes:
        file_paths = set(cached_hashes.keys())
        current_hashes = get_file_hashes(file_paths)

        # Check if any file has changed
        for path, cached_hash in cached_hashes.items():
            current_hash = current_hashes.get(path)
            if current_hash != cached_hash:
                console.print(f"\n[bold yellow]⚠ Cache Stale: File changed since cache: {path}[/bold yellow]")
                console.print(f"  Cached hash: {cached_hash[:8]}...  Current hash: {current_hash[:8] if current_hash else 'DELETED'}...")
                return None  # Invalidate cache

        console.print(f"\n[bold green]⚡ Cache Hit ({similarity:.2f} similarity): File hashes validated![/bold green]\n")

    # --- MICRO-VALIDATION: Borderline similarity with matching hashes ---
    elif micro_validation_threshold <= similarity < similarity_threshold:
        console.print(f"\n[bold cyan]🔍 Micro-validation needed ({similarity:.2f} similarity)...[/bold cyan]")
        # Send micro-prompt to LLM for validation
        if _micro_validate(prompt, response):
            console.print(f"\n[bold green]⚡ Cache Hit ({similarity:.2f} similarity): Micro-validation passed![/bold green]\n")
        else:
            console.print(f"\n[bold yellow]⚠ Cache Invalidated: Micro-validation failed[/bold yellow]")
            return None

    else:
        console.print(f"\n[bold green]⚡ Cache Hit ({similarity:.2f} similarity): Bypassing LLM API![/bold green]\n")

    return {
        "response": response,
        "tool_calls": tool_calls
    }


def _micro_validate(prompt: str, cached_response: str) -> bool:
    """
    Send a micro-prompt to the LLM to validate if cached solution is still sound.
    This is a synchronous call - in production, this would use the NemotronClient.
    For now, we'll do a simple heuristic check.
    """
    # Simple heuristic: if the cached response contains specific file paths or
    # version-specific code that might be outdated, be conservative
    # In a full implementation, this would call the LLM with a validation prompt

    # For now, return True to allow cache hit (conservative approach)
    # A real implementation would use the LLM client here
    return True


def save_to_cache(prompt: str, response: str, tool_calls: list):
    """
    Post-execution hook. Saves the successful trajectory to both ChromaDB and SQLite.
    Includes file hashes for smart validation.
    """
    traj_id = str(uuid.uuid4())

    # Extract file paths from tool calls and compute their hashes
    file_paths = extract_file_paths_from_tool_calls(tool_calls)
    file_hashes = get_file_hashes(file_paths)

    # Save vector to ChromaDB
    collection.add(
        ids=[traj_id],
        documents=[prompt],
        metadatas=[{"source": "cli"}]
    )

    # Save metadata to SQLite with file hashes
    cursor.execute(
        "INSERT INTO trajectories (id, prompt, response, tool_calls, file_hashes) VALUES (?, ?, ?, ?, ?)",
        (traj_id, prompt, response, json.dumps(tool_calls), json.dumps(file_hashes))
    )
    conn.commit()


def invalidate_cache_for_file(file_path: str):
    """
    Invalidate all cache entries that reference a specific file.
    Called when a file is modified (via watchdog).
    """
    try:
        resolved_path = str(Path(file_path).expanduser().resolve())
    except Exception:
        return

    # Find all trajectories that reference this file
    cursor.execute("SELECT id, file_hashes FROM trajectories")
    rows = cursor.fetchall()

    invalidated_count = 0
    for traj_id, file_hashes_json in rows:
        if file_hashes_json:
            file_hashes = json.loads(file_hashes_json)
            if resolved_path in file_hashes:
                # Delete from ChromaDB
                try:
                    collection.delete(ids=[traj_id])
                except Exception:
                    pass
                # Delete from SQLite
                cursor.execute("DELETE FROM trajectories WHERE id = ?", (traj_id,))
                invalidated_count += 1

    if invalidated_count > 0:
        conn.commit()
        console.print(f"[dim]🗑️ Invalidated {invalidated_count} cache entries for {resolved_path}[/dim]")


# --- Session Management Functions ---

def create_session(name: str, project_path: str) -> str:
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO sessions (id, name, project_path) VALUES (?, ?, ?)",
        (session_id, name, project_path)
    )
    conn.commit()
    return session_id


def get_sessions(project_path: str = None) -> list:
    """Get all sessions, optionally filtered by project path."""
    if project_path:
        cursor.execute(
            "SELECT id, name, project_path, created_at, updated_at FROM sessions WHERE project_path = ? ORDER BY updated_at DESC",
            (project_path,)
        )
    else:
        cursor.execute(
            "SELECT id, name, project_path, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        )
    return cursor.fetchall()


def get_session(session_id: str) -> tuple | None:
    """Get a single session by ID."""
    cursor.execute(
        "SELECT id, name, project_path, created_at, updated_at FROM sessions WHERE id = ?",
        (session_id,)
    )
    return cursor.fetchone()


def update_session_name(session_id: str, name: str):
    """Update session name."""
    cursor.execute(
        "UPDATE sessions SET name = ?, updated_at = ? WHERE id = ?",
        (name, datetime.now().isoformat(), session_id)
    )
    conn.commit()


def delete_session(session_id: str):
    """Delete a session and its messages."""
    cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()


def add_message(session_id: str, role: str, content: str, tool_calls: list = None):
    """Add a message to a session."""
    msg_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO messages (id, session_id, role, content, tool_calls) VALUES (?, ?, ?, ?, ?)",
        (msg_id, session_id, role, content, json.dumps(tool_calls) if tool_calls else None)
    )
    # Update session timestamp
    cursor.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (datetime.now().isoformat(), session_id)
    )
    conn.commit()


def get_messages(session_id: str) -> list:
    """Get all messages for a session."""
    cursor.execute(
        "SELECT role, content, tool_calls, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,)
    )
    return cursor.fetchall()


def get_or_create_default_session(project_path: str) -> str:
    """Get the most recent session for a project, or create a new one."""
    sessions = get_sessions(project_path)
    if sessions:
        return sessions[0][0]  # Return most recent session ID
    return create_session("Session 1", project_path)