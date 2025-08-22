from pathlib import Path
from typing import List, Tuple

def list_repo_files(root: str=".", limit: int=200) -> List[Path]:
    files = []
    for p in Path(root).rglob("*"):
        if p.is_file() and p.suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".toml", ".yaml", ".yml", ".md"}:
            files.append(p)
        if len(files) >= limit:
            break
    return files

def slice_file(path: Path, lines: Tuple[int, int] | None=None, max_chars: int=3000) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    if lines:
        start, end = lines
        all_lines = content.splitlines()
        seg = all_lines[max(0, start-1):min(len(all_lines), end)]
        content = "\n".join(f"{i+start:>4} {line}" for i, line in enumerate(seg))
    else:
        # annotate with line numbers
        content = "\n".join(f"{i+1:>4} {line}" for i, line in enumerate(content.splitlines()))
    return content[:max_chars]

def build_focus_from_trace(tail: str, max_files: int=8) -> list[Path]:
    """
    Pull likely files from a pytest tail.
    """
    import re
    paths = []
    # Handle both Unix and Windows paths
    for m in re.finditer(r"([\w\-/\\\.]+\.py):(\d+)", tail):
        paths.append(Path(m.group(1)))
    
    # Also look for import statements to find related files
    for m in re.finditer(r"from ([\w\.]+) import", tail):
        module_name = m.group(1)
        if not module_name.startswith('.'):
            # Try to find the module file
            module_path = Path(f"{module_name.replace('.', '/')}.py")
            if module_path.exists():
                paths.append(module_path)
            # Also try in sample_project directory
            sample_path = Path(f"sample_project/{module_name.replace('.', '/')}.py")
            if sample_path.exists():
                paths.append(sample_path)
    
    seen = []
    out = []
    for p in paths:
        if p.exists() and str(p) not in seen:
            seen.append(str(p))
            out.append(p)
        if len(out) >= max_files:
            break
    return out

def make_context(failure_brief: str, tail: str) -> tuple[str, str]:
    files = build_focus_from_trace(tail)
    if not files:
        files = list_repo_files(limit=6)
    
    # If we only found test files, try to find the corresponding source files
    if files and all("test" in str(f) for f in files):
        # Look for app_logic.py specifically since that's what the test imports
        app_logic_path = Path("sample_project/app_logic.py")
        if app_logic_path.exists() and app_logic_path not in files:
            files.append(app_logic_path)
        
        # Also add any .py files in the same directory as test files
        for test_file in files:
            if "test" in str(test_file):
                parent_dir = test_file.parent.parent if test_file.parent.name == "tests" else test_file.parent
                for py_file in parent_dir.glob("*.py"):
                    if py_file not in files and "test" not in py_file.name:
                        files.append(py_file)
    
    file_list_str = "\n".join(str(p) for p in files)
    slices = []
    for p in files:
        slices.append(f"--- {p}\n{slice_file(p)}")
    return file_list_str, "\n\n".join(slices)