import subprocess
import tempfile
from typing import Tuple

def normalize_unified_diff(diff_text: str) -> str:
    """
    Normalize unified diff headers and path separators to maximize git apply compatibility:
    - Convert Windows backslashes to forward slashes in header paths
    - Ensure headers have a/ and b/ prefixes (git-style)
    - Insert 'diff --git a/... b/...' header if missing
    - Ensure trailing newline
    """
    import re

    text = diff_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    out: list[str] = []
    a_path = None
    b_path = None

    for line in lines:
        if line.startswith("--- ") or line.startswith("+++ "):
            m = re.match(r"^(---|\+\+\+)\s+(.*)$", line)
            if m:
                typ, path = m.groups()
                p = path.strip()
                # Normalize Windows backslashes
                p = p.replace("\\", "/")
                # Add git-style prefixes if missing and not /dev/null
                if not (p.startswith("a/") or p.startswith("b/") or p.startswith("/dev/null")):
                    prefix = "a/" if typ == "---" else "b/"
                    if p.startswith("./"):
                        p = p[2:]
                    p = prefix + p

                if typ == "---" and p != "/dev/null" and a_path is None:
                    a_path = p
                if typ == "+++" and p != "/dev/null" and b_path is None:
                    b_path = p

                line = f"{typ} {p}"
        out.append(line)

    normalized = "\n".join(out)
    # Prepend a diff --git header if absent
    if a_path and b_path:
        stripped = normalized.lstrip()
        if not stripped.startswith("diff --git "):
            normalized = f"diff --git {a_path} {b_path}\n" + normalized

    if not normalized.endswith("\n"):
        normalized += "\n"
    return normalized
def extract_diff_block(markdown: str) -> str:
    """
    Find a single fenced ```diff or ```patch code block.
    If none found, return the whole string.
    """
    import re
    m = re.search(r"```(?:diff|patch)\s*\n([\s\S]*?)```", markdown)
    if m:
        diff_content = m.group(1).rstrip()
        # Ensure proper line endings
        lines = diff_content.split('\n')
        # Remove any empty lines at the end
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines)
    return markdown.strip()

def fallback_apply_by_search_replace(diff_text: str) -> Tuple[bool, str]:
    """
    Fallback patch application: parse unified diff hunks and apply changes by
    search-and-replace using context and +/- lines. Handles small patches that
    lack full context or have minor header inconsistencies.
    """
    import re
    from pathlib import Path

    text = diff_text.replace("\r\n", "\n").replace("\r", "\n")

    # Determine target file from +++ header
    m = re.search(r'^\+\+\+\s+([^\n]+)', text, flags=re.M)
    if not m:
        return False, "Fallback: no +++ header found"
    b_path = m.group(1).strip()
    # Normalize paths
    b_path = b_path.replace("\\", "/")
    if b_path.startswith("b/") or b_path.startswith("a/"):
        b_path = b_path[2:]
    if b_path.startswith("./"):
        b_path = b_path[2:]

    p = Path(b_path)
    if not p.exists():
        return False, f"Fallback: target file not found: {b_path}"

    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Fallback: cannot read file {b_path}: {e}"

    changed = 0

    # Iterate hunks and apply
    for hm in re.finditer(r'^@@.*?@@\s*\n(?P<body>(?:[ \t\+\-].*\n)+)', text, flags=re.M):
        body = hm.group('body').rstrip("\n").split("\n")
        # Build pattern (context + removals) and replacement (context + additions)
        pattern_lines = []
        replacement_lines = []
        for line in body:
            if line.startswith(" ") or line.startswith("\t"):
                # context
                t = line[1:]
                pattern_lines.append(t)
                replacement_lines.append(t)
            elif line.startswith("-") and not line.startswith("---"):
                pattern_lines.append(line[1:])
            elif line.startswith("+") and not line.startswith("+++"):
                replacement_lines.append(line[1:])

        pattern = "\n".join(pattern_lines)
        replacement = "\n".join(replacement_lines)

        applied = False
        if pattern and pattern in content:
            content = content.replace(pattern, replacement, 1)
            applied = True
        else:
            # Try removal-only block replacement
            removed = [l[1:] for l in body if l.startswith("-") and not l.startswith("---")]
            added = [l[1:] for l in body if l.startswith("+") and not l.startswith("+++")]
            if removed:
                rem_block = "\n".join(removed)
                add_block = "\n".join(added)
                if rem_block and rem_block in content:
                    content = content.replace(rem_block, add_block, 1)
                    applied = True
                elif removed[0] in content:
                    content = content.replace(removed[0], add_block, 1)
                    applied = True

        if applied:
            changed += 1
        else:
            return False, "Fallback: unable to match hunk to file content"

    try:
        p.write_text(content, encoding="utf-8")
    except Exception as e:
        return False, f"Fallback: write failed: {e}"

    if changed > 0:
        return True, f"Fallback applied {changed} hunk(s)"
    return False, "Fallback: no changes applied"


def apply_patch(diff_text: str) -> Tuple[bool, str]:
    """
    Apply the patch using git apply with normalization and multiple fallbacks.
    """
    import os

    # Clean up and normalize
    diff_text = diff_text.strip()
    if not diff_text:
        return False, "Empty diff content"
    diff_text = normalize_unified_diff(diff_text)

    with tempfile.NamedTemporaryFile("w+", suffix=".patch", delete=False, newline="") as f:
        f.write(diff_text)
        f.flush()
        patch_path = f.name

    try:
        # Try multiple strategies
        cmds = [
            ["git", "apply", "--whitespace=fix", patch_path],
            ["git", "apply", "--ignore-whitespace", patch_path],
            ["git", "apply", "-p0", patch_path],
            ["git", "apply", "-p1", patch_path],
            ["git", "apply", "--reject", patch_path],
        ]
        for cmd in cmds:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True, f"Patch applied successfully ({' '.join(cmd[1:])})"

        # Fallback: try search-replace application
        ok, msg = fallback_apply_by_search_replace(diff_text)
        if ok:
            return True, f"Patch applied via fallback: {msg}"

        return False, f"git apply failed: {result.stderr or result.stdout}; {msg}"
    except Exception as e:
        return False, f"Error applying patch: {str(e)}"
    finally:
        try:
            os.unlink(patch_path)
        except:
            pass