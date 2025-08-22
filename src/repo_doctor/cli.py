import subprocess
import sys
import json
from pathlib import Path
import typer
from rich.console import Console
from .logs import read_text, parse_pytest_log, format_failure_brief
from .context import make_context
from .api import call_glm_45, build_user_prompt
from .diff_utils import extract_diff_block, apply_patch
from .github import post_pr_comment
from .cost import estimate_cost

app = typer.Typer()
con = Console()

@app.command()
def run_tests(cmd: str = "pytest -q --disable-warnings --junitxml=report.xml"):
    """
    Run tests and save logs to pytest.log. Always returns exit code 0 to continue the pipeline.
    """
    con.print(f"[bold]Running[/bold] {cmd}")
    with open("pytest.log", "w", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            print(line, end="")
            f.write(line)
        p.wait()
    # do not exit nonzero here
    con.print("[green]Tests finished[/green]")

@app.command()
def propose(project_name: str = typer.Option("Sample Project", "--project-name", "-p")):
    """
    Parse logs, build context, call GLM 4.5, and print the diff.
    """
    log = read_text("pytest.log") or read_text("report.xml")
    # Ensure we have fresh failing logs; if not, run tests to capture failures
    if not log or ("FAILED" not in log and "ERROR" not in log and "AssertionError" not in log):
        con.print("[yellow]No failing logs found; running tests to capture failures...[/yellow]")
        run_tests()
        log = read_text("pytest.log") or read_text("report.xml")
    brief_obj = parse_pytest_log(log)
    brief = format_failure_brief(brief_obj)
    file_list, slices = make_context(brief, brief_obj.get("tail", ""))

    prompt = build_user_prompt(project_name, brief, file_list, slices)
    content, meta = call_glm_45(prompt)

    diff = extract_diff_block(content)
    usage = meta.get("usage", {})
    cost = estimate_cost(usage)
    summary = f"Repo Doctor suggestion\n\n{cost}\n\n```diff\n{diff}\n```"
    print(summary)
    # Persist latest proposal so `apply` can pick it up without re-running propose
    Path("repo_doctor_output.md").write_text(summary, encoding="utf-8")

@app.command()
def apply(verbose: bool = typer.Option(False, "--verbose", "-v")):
    """
    Apply last suggested patch found in repo_doctor_output.md or from stdin.
    """
    text = ""

    # Prefer stdin if piped
    try:
        if not sys.stdin.isatty():
            stdin_data = sys.stdin.read()
            if stdin_data and stdin_data.strip():
                text = stdin_data
    except Exception:
        pass

    # Look for repo_doctor_output.md
    md = Path("repo_doctor_output.md")
    if not text and md.exists():
        text = md.read_text(encoding="utf-8")
    
    # If still no text, try to run propose automatically
    if not text:
        con.print("[yellow]No patch found, running propose first...[/yellow]")
        log = read_text("pytest.log") or read_text("report.xml")
        if not log:
            con.print("[red]No test logs found. Run 'repo-doctor run-tests' first.[/red]")
            return
        
        brief_obj = parse_pytest_log(log)
        brief = format_failure_brief(brief_obj)
        file_list, slices = make_context(brief, brief_obj.get("tail", ""))
        
        prompt = build_user_prompt("Sample Project", brief, file_list, slices)
        content, meta = call_glm_45(prompt)
        text = content
    
    diff = extract_diff_block(text)
    if not diff or diff.strip() == "":
        con.print("[red]No valid diff found to apply[/red]")
        return
        
    ok, msg = apply_patch(diff)
    if ok:
        if verbose:
            con.print(f"[bold]Applied[/bold] {msg}")
        else:
            con.print(f"[bold]Applied[/bold]")
    else:
        con.print(f"[bold]Failed[/bold] {msg}")

@app.command()
def ci_run(project_name: str = typer.Option("Repository", "--project-name", "-p")):
    """
    CI entrypoint. Run tests, propose a patch, post a PR comment.
    """
    run_tests()
    log = read_text("pytest.log")
    brief_obj = parse_pytest_log(log)
    brief = format_failure_brief(brief_obj)
    file_list, slices = make_context(brief, brief_obj.get("tail", ""))

    prompt = build_user_prompt(project_name, brief, file_list, slices)
    content, meta = call_glm_45(prompt)
    diff = extract_diff_block(content)
    usage = meta.get("usage", {})
    cost = estimate_cost(usage)

    body = f"### Repo Doctor\n{cost}\n\n<details>\n<summary>Proposed patch</summary>\n\n```diff\n{diff}\n```\n\n</details>"
    post_pr_comment(body)
    # Save to artifact
    Path("repo_doctor_output.md").write_text(body, encoding="utf-8")
    print(body)

@app.command()
def fix(verbose: bool = typer.Option(False, "--verbose", "-v")):
    """
    Run tests, propose a patch, and apply it automatically.
    """
    # Run tests first
    run_tests()
    
    # Parse logs and propose fix
    log = read_text("pytest.log") or read_text("report.xml")
    if not log:
        con.print("[red]No test logs found[/red]")
        return
        
    brief_obj = parse_pytest_log(log)
    brief = format_failure_brief(brief_obj)
    
    # Check if there are any failures
    if not brief_obj.get("test") and not brief_obj.get("error_type"):
        con.print("[green]No test failures found - nothing to fix![/green]")
        return
    
    file_list, slices = make_context(brief, brief_obj.get("tail", ""))
    
    con.print("[yellow]Analyzing failure and generating fix...[/yellow]")
    prompt = build_user_prompt("Sample Project", brief, file_list, slices)
    content, meta = call_glm_45(prompt)
    
    diff = extract_diff_block(content)
    usage = meta.get("usage", {})
    cost = estimate_cost(usage)
    
    if not diff or diff.strip() == "":
        con.print("[red]Could not generate a valid fix[/red]")
        return
    
    con.print(f"[blue]Generated fix ({cost})[/blue]")
    con.print(f"```diff\n{diff}\n```")
    
    # Apply the fix
    ok, msg = apply_patch(diff)
    if ok:
        if verbose:
            con.print(f"[bold]Applied[/bold] {msg}")
        else:
            con.print(f"[bold]Applied[/bold]")
        con.print("[green]Fix applied! Re-running tests to verify...[/green]")
        run_tests()
    else:
        con.print(f"[bold]Failed[/bold] {msg}")

if __name__ == "__main__":
    app()