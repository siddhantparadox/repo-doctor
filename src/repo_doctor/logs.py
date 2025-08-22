from pathlib import Path
import re

def read_text(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""

def parse_pytest_log(text: str) -> dict:
    """
    Extract a short failure brief.
    Finds the first FAIL block, test name, error type, message, and a small traceback tail.
    """
    brief = {}
    # Test name
    m = re.search(r"__+ (test[^\s:]+)", text)
    if m:
        brief["test"] = m.group(1)

    # Error line and type
    et = re.search(r"E\s+([A-Za-z_]+Error):\s*(.+)", text)
    if et:
        brief["error_type"] = et.group(1)
        brief["error_msg"] = et.group(2)[:300]

    # Last 20 lines for context
    tail = "\n".join(text.splitlines()[-20:])
    brief["tail"] = tail

    return brief

def format_failure_brief(brief: dict) -> str:
    parts = []
    if "test" in brief:
        parts.append(f"Failing test {brief['test']}")
    if "error_type" in brief:
        parts.append(f"Exception {brief['error_type']}")
    if "error_msg" in brief:
        parts.append(f"Message {brief['error_msg']}")
    parts.append("Trace tail")
    parts.append(brief.get("tail", "")[:2000])
    return "\n".join(parts)