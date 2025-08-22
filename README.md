# Repo Doctor

Repo Doctor is a GitHub Action and CLI that reads failing test logs, asks GLM 4.5 for a minimal unified diff, and posts the patch as a PR comment. It runs GLM 4.5 in thinking mode by default and hides the model's internal reasoning in public outputs.

## Features

- Runs your tests in CI, captures the error log, and builds a short failure brief
- Sends that brief plus small code slices to GLM 4.5
- Receives a unified diff and a short summary
- Posts both to the PR as a single comment
- Optional local command to apply the patch and re-run tests

## Setup

### Requirements

- Python 3.11 or newer
- One API key in env named `OPENROUTER_API_KEY`
- GitHub secret named `OPENROUTER_API_KEY` for CI

### Installation

```bash
pip install -e .
```

## Usage

### Quick Start

The simplest way to use Repo Doctor is with the one-step fix command:

```bash
repo-doctor fix
```

This will:
1. Run your tests to detect failures
2. Analyze the failures and generate a fix
3. Apply the fix automatically
4. Re-run tests to verify the fix worked

### Step-by-Step Usage

For more control, you can use the individual commands:

#### 1. Run tests and capture failures

```bash
repo-doctor run-tests
```

This runs pytest and saves the output to `pytest.log`. The command always exits with code 0 to continue the pipeline even if tests fail.

#### 2. Analyze failures and propose a fix

```bash
repo-doctor propose
```

This will:
- Parse the test logs from `pytest.log` or `report.xml`
- Build context by finding relevant source files
- Send the failure details to GLM 4.5
- Print a unified diff that should fix the failing tests
- Save the proposal to `repo_doctor_output.md`

You can optionally specify a project name:
```bash
repo-doctor propose --project-name "My Project"
```

#### 3. Apply the proposed fix

```bash
repo-doctor apply
```

This will:
- Look for the most recent patch from `repo_doctor_output.md`
- Apply the patch using git apply with multiple fallback strategies
- Show "Applied" on success or error details on failure

For verbose output showing which patch strategy was used:
```bash
repo-doctor apply --verbose
```

### Alternative Workflows

#### Pipe propose output directly to apply

```bash
repo-doctor propose | repo-doctor apply
```

### Command Reference

| Command | Description | Options |
|---------|-------------|---------|
| `repo-doctor run-tests` | Run tests and save logs | Custom pytest command |
| `repo-doctor propose` | Analyze failures and generate fix | `--project-name`, `-p` |
| `repo-doctor apply` | Apply the proposed patch | `--verbose`, `-v` |
| `repo-doctor fix` | One-step: run tests, propose, apply, verify | `--verbose`, `-v` |
| `repo-doctor ci-run` | CI mode: run workflow and post PR comment | `--project-name`, `-p` |

### Examples

#### Fix a failing test suite

```bash
# One command does everything
repo-doctor fix

# Or step by step
repo-doctor run-tests
repo-doctor propose
repo-doctor apply
```

#### Test on the included sample project

```bash
cd my_test
python -m pytest  # See the failures
cd ..
repo-doctor fix   # Let repo-doctor fix them
cd my_test
python -m pytest  # Verify fixes worked
```

#### Custom test command

```bash
repo-doctor run-tests "python -m pytest tests/ -v --tb=short"
repo-doctor propose --project-name "My Custom Project"
repo-doctor apply
```

### As a GitHub Action

The GitHub Action is automatically triggered on pull requests. It will:

1. Run your tests
2. If tests fail, call GLM 4.5 to propose a fix
3. Post the proposed fix as a comment on the PR

To use it, make sure you have the `OPENROUTER_API_KEY` secret set in your repository.

## Sample Project

A sample project is included in the `sample_project` directory. You can test Repo Doctor with it:

```bash
cd sample_project
pytest -q || true
python -m repo_doctor.cli run-tests
python -m repo_doctor.cli propose > repo_doctor_output.md
cat repo_doctor_output.md
```

## Configuration

### Environment Variables

- `OPENROUTER_API_KEY`: Your OpenRouter API key (required)
- `REPO_DOCTOR_MODEL`: The model to use (default: `z-ai/glm-4.5`)
- `GITHUB_TOKEN`: GitHub token (automatically provided in GitHub Actions)

### Model Configuration

Repo Doctor uses GLM 4.5 with thinking mode enabled by default. The thinking mode is configured to:

- Enable reasoning on OpenRouter and exclude it from responses
- Enable thinking type on Z.ai for compatibility

## Cost Estimation

Repo Doctor includes cost estimation for API calls. The default rates for `z-ai/glm-4.5` are:
- $0.20 per million input tokens
- $0.80 per million output tokens

## How It Works

1. **Test Execution**: Runs your tests and captures the output
2. **Log Parsing**: Extracts key information from failing tests
3. **Context Building**: Identifies relevant files and code sections
4. **API Call**: Sends the context to GLM 4.5 with a carefully crafted prompt
5. **Diff Extraction**: Parses the response to extract the unified diff
6. **PR Comment**: Posts the diff as a comment on the PR (in CI mode)

## Future Plans

- **PyPI Distribution**: Planning to publish Repo Doctor on PyPI for easy installation via `pip install repo-doctor`
- **IDE Integration**: VS Code extension and other IDE plugins
- **Advanced Patch Strategies**: More sophisticated diff generation and application methods

## License

This project is open source and available under the MIT License.