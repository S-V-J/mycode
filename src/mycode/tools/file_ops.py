from pathlib import Path

def read_file(path: str) -> str:
    """Reads a file from the local filesystem."""
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Error: File not found at {p}"
        return p.read_text()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(path: str, content: str) -> str:
    """Writes content to a file, creating directories if necessary."""
    try:
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Successfully wrote to {p}"
    except Exception as e:
        return f"Error writing file: {str(e)}"
