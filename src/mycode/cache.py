import sqlite3
import json
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
from rich.console import Console

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
conn = sqlite3.connect(str(SQLITE_DB))
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS trajectories (
        id TEXT PRIMARY KEY,
        prompt TEXT,
        response TEXT,
        tool_calls TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

def check_cache(prompt: str, similarity_threshold: float = 0.92) -> dict | None:
    """
    Intercepts user prompt. Searches ChromaDB for semantic matches.
    Returns cached trajectory if match > threshold, else None.
    """
    # Query ChromaDB for the closest match
    # FIX 1: Added "distances" to include array so ChromaDB actually returns them
    results = collection.query(
        query_texts=[prompt],
        n_results=1,
        include=["metadatas", "documents", "distances"]
    )
    
    # FIX 2: Robust checking to prevent IndexError on empty collections and TypeError on None
    if (results and 
        results.get('distances') is not None and 
        len(results['distances']) > 0 and 
        len(results['distances'][0]) > 0):
        
        distance = results['distances'][0][0]
        similarity = 1.0 - distance # ChromaDB returns cosine distance, convert to similarity
        
        if similarity >= similarity_threshold:
            cached_id = results['ids'][0][0]
            
            # Fetch full relational data from SQLite
            cursor.execute("SELECT response, tool_calls FROM trajectories WHERE id = ?", (cached_id,))
            row = cursor.fetchone()
            
            if row:
                console.print(f"\n[bold green]⚡ Cache Hit ({similarity:.2f} similarity): Bypassing LLM API![/bold green]\n")
                return {
                    "response": row[0],
                    "tool_calls": json.loads(row[1]) if row[1] else []
                }
    return None

def save_to_cache(prompt: str, response: str, tool_calls: list):
    """
    Post-execution hook. Saves the successful trajectory to both ChromaDB and SQLite.
    """
    import uuid
    traj_id = str(uuid.uuid4())
    
    # Save vector to ChromaDB
    collection.add(
        ids=[traj_id],
        documents=[prompt],
        metadatas=[{"source": "cli"}]
    )
    
    # Save metadata to SQLite
    cursor.execute(
        "INSERT INTO trajectories (id, prompt, response, tool_calls) VALUES (?, ?, ?, ?)",
        (traj_id, prompt, response, json.dumps(tool_calls))
    )
    conn.commit()
