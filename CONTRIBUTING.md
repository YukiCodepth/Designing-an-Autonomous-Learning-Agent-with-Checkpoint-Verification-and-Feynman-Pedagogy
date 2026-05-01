# Contributing

Thank you for contributing to this project. This repository documents a Group 2 internship project from the Infosys Springboard AIML program, so the goal is to keep contributions practical, respectful of the existing architecture, and easy for future contributors to follow.

## Getting Started

1. Fork the repository.
2. Clone your fork locally.
3. Create a branch for your work.

```bash
git clone https://github.com/YukiCodepth/Designing-an-Autonomous-Learning-Agent-with-Checkpoint-Verification-and-Feynman-Pedagogy.git
cd Designing-an-Autonomous-Learning-Agent-with-Checkpoint-Verification-and-Feynman-Pedagogy
git checkout -b feature/short-description
```

## Development Workflow

Choose one local run path:

### Docker

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

### Local `uv`

```bash
cp .env.example .env
uv sync --python 3.11
uv run langgraph dev --host 127.0.0.1 --port 8000 --allow-blocking
```

## Contribution Guidelines

- Keep `.env` local and never commit secrets.
- Preserve existing LangGraph assistant names unless the change intentionally updates `langgraph.json`.
- If you add or change notebooks, update the README tutorial list.
- If you change agent behavior, explain the workflow impact in your pull request.
- Keep edits focused. Small, well-scoped pull requests are easier to review and merge.

## Suggested Areas to Improve

- Research quality and prompt design
- Checkpoint evaluation and feedback quality
- Feynman-style remediation flow
- Documentation, onboarding, and examples
- Workflow visualization and project usability

## Before Opening a Pull Request

- Run the project in Docker or local mode.
- Verify the docs endpoint still loads at `http://127.0.0.1:8000/docs`.
- Confirm your change does not require committing secrets or machine-specific paths.
- Write a clear commit message and pull request summary.

## Pull Request Notes

When opening a pull request, include:

- what changed
- why it changed
- how you tested it
- any follow-up work still remaining
