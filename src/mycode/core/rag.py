import os
import hashlib
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
from rich.console import Console
import threading

console = Console()

# Define local persistent storage paths for RAG
MYCODE_DIR = Path.home() / ".mycode"
RAG_DIR = MYCODE_DIR / "rag_data"
RAG_DIR.mkdir(parents=True, exist_ok=True)

# Initialize ChromaDB specifically for codebase chunks
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
rag_client = chromadb.PersistentClient(path=str(RAG_DIR))
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
codebase_collection = rag_client.get_or_create_collection(
    name="codebase_index",
    embedding_function=embedding_func,
    metadata={"hnsw:space": "cosine"}
)

# --- TREE-SITTER INITIALIZATION ---
TREE_SITTER_AVAILABLE = False
PY_LANGUAGE = None
JS_LANGUAGE = None
TS_LANGUAGE = None

try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
    from tree_sitter import Language, Parser

    PY_LANGUAGE = Language(tspython.language())
    JS_LANGUAGE = Language(tsjavascript.language())

    # Handle API variations in tree-sitter-typescript
    try:
        TS_LANGUAGE = Language(tstypescript.language_typescript())
    except AttributeError:
        TS_LANGUAGE = Language(tstypescript.language())

    TREE_SITTER_AVAILABLE = True
except Exception as e:
    console.print(f"[yellow]Warning: Tree-sitter failed to load ({e}). Falling back to basic text chunking.[/yellow]")

def get_parser(language):
    """Safely initializes a Tree-sitter parser across different package versions."""
    try:
        return Parser(language) # New API (>= 0.21)
    except TypeError:
        p = Parser()            # Old API (<= 0.20)
        p.set_language(language)
        return p

def chunk_code(code: str, file_path: str, language: str) -> list[dict]:
    """Parses code into logical AST chunks using Tree-sitter."""
    chunks = []
    lang_map = {'python': PY_LANGUAGE, 'javascript': JS_LANGUAGE, 'typescript': TS_LANGUAGE}
    target_lang = lang_map.get(language)

    if TREE_SITTER_AVAILABLE and target_lang:
        parser = get_parser(target_lang)
        tree = parser.parse(bytes(code, "utf8"))

        def traverse(node):
            # Target logical boundaries across Python, JS, and TS
            if node.type in [
                'function_definition', 'class_definition', # Python
                'function_declaration', 'class_declaration', 'method_definition', # JS/TS
                'export_statement', 'lexical_declaration' # JS/TS consts/lets
            ]:
                chunk_code_str = code[node.start_byte:node.end_byte]
                name_node = node.child_by_field_name('name')
                name = code[name_node.start_byte:name_node.end_byte] if name_node else "anonymous"

                chunks.append({
                    "content": chunk_code_str,
                    "metadata": {
                        "file": file_path,
                        "type": node.type,
                        "name": name,
                        "hash": hashlib.md5(chunk_code_str.encode()).hexdigest()
                    }
                })
            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return chunks

    # Fallback: Basic chunking by lines if tree-sitter fails or unsupported language
    lines = code.split('\n')
    chunk_size = 50
    for i in range(0, len(lines), chunk_size):
        chunk_str = '\n'.join(lines[i:i+chunk_size])
        chunks.append({
            "content": chunk_str,
            "metadata": {
                "file": file_path,
                "type": "text_chunk",
                "name": f"lines_{i}-{i+chunk_size}",
                "hash": hashlib.md5(chunk_str.encode()).hexdigest()
            }
        })
    return chunks

def index_file(file_path: Path):
    """Indexes a single file into the ChromaDB codebase collection."""
    ext = file_path.suffix.lower()
    lang_map = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript'}
    if ext not in lang_map: return

    try:
        code = file_path.read_text(encoding='utf-8')
    except Exception:
        return

    chunks = chunk_code(code, str(file_path), lang_map[ext])
    if not chunks: return

    # Generate unique IDs based on file path and chunk name
    ids = [f"{file_path}_{c['metadata']['name']}_{i}" for i, c in enumerate(chunks)]
    documents = [c['content'] for c in chunks]
    metadatas = [c['metadata'] for c in chunks]

    # Upsert handles both new files and modified files seamlessly
    codebase_collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

def index_directory(directory: Path):
    """Scans and indexes all supported files in the directory, ignoring virtual environments."""
    ignore_dirs = {'venv', '.venv', 'env', 'node_modules', '.git', '__pycache__', '.mycode', 'chroma_data', 'rag_data'}

    files_to_index = []
    for root, dirs, files in os.walk(directory):
        # Prune ignored directories from the walk
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for file in files:
            if file.endswith(('.py', '.js', '.ts')):
                files_to_index.append(Path(root) / file)

    if not files_to_index: return

    console.print(f"[dim]🔍 Indexing {len(files_to_index)} files for RAG context...[/dim]")
    for f in files_to_index:
        index_file(f)
    console.print(f"[bold green]✓ Codebase indexed successfully.[/bold green]")

def retrieve_context(query: str, n_results: int = 5) -> str:
    """Searches the codebase index and returns formatted context for the system prompt."""
    results = codebase_collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas"]
    )

    if not results or not results['documents'][0]:
        return ""

    context_str = "RELEVANT CODEBASE CONTEXT:\n"
    for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
        file_info = meta.get('file', 'unknown')
        type_info = meta.get('type', 'unknown')
        name_info = meta.get('name', 'unknown')
        context_str += f"\n--- File: {file_info} ({type_info}: {name_info}) ---\n"
        context_str += doc + "\n"

    return context_str

# --- WATCHDOG BACKGROUND WORKER ---
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    class CodeHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if not event.is_directory and event.src_path.endswith(('.py', '.js', '.ts')):
                file_path = Path(event.src_path)
                index_file(file_path)
                # Invalidate cache for this file
                from mycode.core.cache import invalidate_cache_for_file
                invalidate_cache_for_file(str(file_path))

        def on_created(self, event):
            self.on_modified(event)

        def on_deleted(self, event):
            if not event.is_directory and event.src_path.endswith(('.py', '.js', '.ts')):
                # Invalidate cache for deleted file
                from mycode.core.cache import invalidate_cache_for_file
                invalidate_cache_for_file(event.src_path)

    def start_watcher(directory: Path):
        """Starts a daemon thread to monitor file changes and update the RAG index."""
        observer = Observer()
        observer.schedule(CodeHandler(), str(directory), recursive=True)
        observer.daemon = True
        observer.start()
        console.print(f"[dim]👁️ Background file watcher started on {directory}[/dim]")

except ImportError:
    def start_watcher(directory: Path):
        console.print("[yellow]Warning: watchdog not installed. Background indexing disabled.[/yellow]")
