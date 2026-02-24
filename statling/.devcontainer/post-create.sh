#!/bin/bash
set -e

echo "🚀 Running post-create setup..."

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install package in editable mode with dev dependencies
echo "📦 Installing statling in editable mode with dev dependencies..."
pip install -e ".[dev]"

# Verify installation
echo "✅ Verifying installation..."
python -c "from statling import CharacterRenderer; print('✓ Statling imported successfully')"

# Show installed packages
echo "📋 Installed packages:"
pip list | grep -E "statling|PyYAML|Jinja2|ruff|black|flake8|isort|mypy|pytest"

# Configure git
echo "🔧 Configuring git..."
git config --global --add safe.directory /workspace

# Display Python version
echo "🐍 Python version:"
python --version

# Display pip version
echo "📦 pip version:"
pip --version

# Create output directory if it doesn't exist
mkdir -p /workspace/output

echo "✅ Post-create setup complete!"
echo ""
echo "🎉 Ready to develop! Available commands:"
echo "  • statling --help                    - CLI help"
echo "  • ruff check . && ruff format .      - Fast linting & formatting"
echo "  • black . && isort . && flake8 .     - Traditional tools"
echo "  • mypy .                             - Type checking"
echo "  • pytest -v                          - Run tests"
