# Contributing to Agent Firewall

## Development Setup

```bash
# 1. Clone and enter directory
cd extensions/agent-firewall

# 2. Setup Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"

# 3. Setup Frontend
cd frontend
npm install
cd ..

# 4. Install git hooks (from repo root)
cd ../..
./scripts/setup-hooks.sh
```

## Commit Message Convention

We use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### Types

| Type       | Description                                   |
| ---------- | --------------------------------------------- |
| `feat`     | A new feature                                 |
| `fix`      | A bug fix                                     |
| `docs`     | Documentation only changes                    |
| `style`    | Code style changes (formatting, semicolons)   |
| `refactor` | Code change that neither fixes a bug nor adds |
| `perf`     | A code change that improves performance       |
| `test`     | Adding or updating tests                      |
| `build`    | Changes to build process or dependencies      |
| `ci`       | CI/CD configuration changes                   |
| `chore`    | Other changes that don't modify src or tests  |
| `revert`   | Reverts a previous commit                     |

### Scope (optional)

- `backend` - Python FastAPI backend
- `frontend` - Vue.js dashboard
- `gateway` - Gateway integration
- `api` - API endpoints
- `docs` - Documentation

### Examples

```bash
# Feature
feat(backend): add pattern-based rule matching

# Bug fix
fix(frontend): correct traffic chart data binding

# Documentation
docs: update API reference

# Refactor
refactor(backend): extract rule validation logic

# Breaking change (add ! after type)
feat(api)!: change rule response format
```

## Code Quality Checks

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`:

1. **Python**: ruff lint + format
2. **TypeScript/Vue**: ESLint
3. **Commit Message**: Conventional Commits validation

### Manual Checks

```bash
# Backend (Python)
cd extensions/agent-firewall
source .venv/bin/activate
ruff check src tests      # Lint
ruff format src tests     # Format
pytest                    # Tests

# Frontend (Vue/TypeScript)
cd frontend
npm run lint             # ESLint fix
npm run lint:check       # ESLint check only
npm run typecheck        # TypeScript check
```

### Run All Checks

```bash
# From repo root
prek run --all-files
```

## Testing

```bash
# Backend
cd extensions/agent-firewall
source .venv/bin/activate
pytest                          # All tests
pytest tests/test_rules.py      # Specific file
pytest -v                       # Verbose
pytest --cov=src               # With coverage

# Frontend
cd frontend
npm run typecheck              # Type check
```

## Pull Request Process

1. Create feature branch: `git checkout -b feat/your-feature`
2. Make changes with proper commit messages
3. Run all checks before push
4. Create PR with clear description
5. Address review feedback

## Directory Structure

```
extensions/agent-firewall/
├── src/                    # Backend source
│   ├── main.py            # FastAPI app
│   ├── rule_engine.py     # Rule processing
│   └── protocol.py        # WebSocket protocol
├── tests/                  # Backend tests
├── frontend/              # Vue.js dashboard
│   ├── src/
│   │   ├── components/    # Vue components
│   │   └── App.vue        # Root component
│   └── eslint.config.js   # ESLint config
├── scripts/               # Utility scripts
│   ├── start-all.sh       # Start all services
│   └── stop-all.sh        # Stop all services
├── pyproject.toml         # Python project config
└── requirements.txt       # Python dependencies
```
