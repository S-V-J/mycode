from pathlib import Path
import difflib
import glob as glob_module
import re

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

def edit_file(path: str, old_str: str, new_str: str) -> str:
    """
    Performs a surgical edit on a file by replacing old_str with new_str.
    This is more precise than rewriting the entire file.

    Args:
        path: Path to the file to edit
        old_str: The exact string to search for and replace
        new_str: The string to replace it with

    Returns:
        Success or error message
    """
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Error: File not found at {p}"

        content = p.read_text()

        if old_str not in content:
            # Try to find similar content for better error message
            lines = content.split('\n')
            old_lines = old_str.split('\n')
            best_match = 0
            best_idx = -1

            for i in range(len(lines) - len(old_lines) + 1):
                match = sum(1 for a, b in zip(lines[i:i+len(old_lines)], old_lines) if a == b)
                if match > best_match:
                    best_match = match
                    best_idx = i

            if best_idx >= 0 and best_match > len(old_lines) * 0.5:
                return f"Error: Could not find exact match for old_str. Closest match at line {best_idx + 1} (similarity: {best_match}/{len(old_lines)} lines)"
            else:
                return f"Error: Could not find old_str in file. The text to replace was not found exactly."

        # Count occurrences
        count = content.count(old_str)
        if count > 1:
            return f"Error: Found {count} occurrences of old_str. Please provide more context to make the match unique."

        # Perform the replacement
        new_content = content.replace(old_str, new_str)
        p.write_text(new_content)

        # Generate a diff for display
        diff = list(difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{p.name}",
            tofile=f"b/{p.name}",
            n=3
        ))

        diff_output = ''.join(diff) if diff else "No changes made."
        return f"Successfully edited {p}\n\nDiff:\n```diff\n{diff_output}\n```"
    except Exception as e:
        return f"Error editing file: {str(e)}"


def glob_tool(pattern: str, path: str = ".") -> str:
    """
    Find files matching a glob pattern.

    Args:
        pattern: The glob pattern to match (e.g., '**/*.py', 'src/**/*.js')
        path: The directory to search in (default: current working directory)

    Returns:
        List of matching file paths
    """
    try:
        search_path = Path(path).expanduser().resolve()
        if not search_path.exists():
            return f"Error: Path not found: {path}"

        # Use glob with recursive=True for ** patterns
        matches = list(search_path.rglob(pattern)) if "**" in pattern else list(search_path.glob(pattern))

        if not matches:
            return f"No files found matching pattern: {pattern}"

        # Return relative paths from the search directory
        relative_matches = [str(m.relative_to(search_path)) for m in matches]
        return f"Found {len(matches)} file(s):\n" + "\n".join(sorted(relative_matches))
    except Exception as e:
        return f"Error running glob: {str(e)}"


def grep_tool(pattern: str, path: str = ".", include: str = None) -> str:
    """
    Search for a pattern in files.

    Args:
        pattern: The regex pattern to search for
        path: The directory to search in (default: current working directory)
        include: File pattern to include (e.g., '*.py', '*.js')

    Returns:
        Matching lines with file paths and line numbers
    """
    try:
        search_path = Path(path).expanduser().resolve()
        if not search_path.exists():
            return f"Error: Path not found: {path}"

        # Compile regex
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        # Determine files to search
        if include:
            files = list(search_path.rglob(include))
        else:
            files = [f for f in search_path.rglob("*") if f.is_file()]

        matches = []
        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                for line_num, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(search_path)
                        matches.append(f"{rel_path}:{line_num}: {line.strip()}")
            except Exception:
                continue  # Skip binary/unreadable files

        if not matches:
            return f"No matches found for pattern: {pattern}"

        return f"Found {len(matches)} match(es):\n" + "\n".join(matches[:100]) + ("\n... (truncated)" if len(matches) > 100 else "")
    except Exception as e:
        return f"Error running grep: {str(e)}"
