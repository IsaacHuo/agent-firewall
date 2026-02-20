#!/usr/bin/env bash
#
# Install git hooks for development
# Run from repository root: ./scripts/setup-hooks.sh

set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
HOOKS_DIR="$ROOT_DIR/git-hooks"
GIT_HOOKS_DIR="$ROOT_DIR/.git/hooks"

echo "🔧 Installing git hooks..."

# Create .git/hooks if not exists
mkdir -p "$GIT_HOOKS_DIR"

# Install pre-commit hook
if [[ -f "$HOOKS_DIR/pre-commit" ]]; then
  ln -sf "$HOOKS_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit"
  chmod +x "$GIT_HOOKS_DIR/pre-commit"
  echo "  ✅ pre-commit hook installed"
else
  echo "  ⚠️  pre-commit hook not found"
fi

# Install commit-msg hook
if [[ -f "$HOOKS_DIR/commit-msg" ]]; then
  ln -sf "$HOOKS_DIR/commit-msg" "$GIT_HOOKS_DIR/commit-msg"
  chmod +x "$GIT_HOOKS_DIR/commit-msg"
  echo "  ✅ commit-msg hook installed"
else
  echo "  ⚠️  commit-msg hook not found"
fi

# Check for pre-commit tool (prek)
if command -v prek &> /dev/null; then
  echo ""
  echo "📦 Installing pre-commit hooks via prek..."
  prek install
  echo "  ✅ prek hooks installed"
else
  echo ""
  echo "💡 Tip: Install 'prek' for additional checks:"
  echo "   pip install pre-commit"
  echo "   prek install"
fi

echo ""
echo "✅ Git hooks setup complete!"
echo ""
echo "Hooks installed:"
echo "  - pre-commit: Code linting and formatting"
echo "  - commit-msg: Conventional Commits validation"
echo ""
echo "Commit message format: <type>(<scope>): <subject>"
echo "Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore"
