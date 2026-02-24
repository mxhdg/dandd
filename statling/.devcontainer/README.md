# Dev Container for Statling

This directory contains the development container configuration for the Statling project.

## Features

- **Python 3.14** (Debian Bookworm base)
- **Pre-installed tools**: git, GitHub CLI, zsh, oh-my-zsh
- **VS Code extensions**:
  - Python & Pylance
  - Ruff (linting & formatting)
  - YAML, TOML, Markdown support
  - Jinja template syntax highlighting
  - GitLens & GitHub integration
- **Auto-setup**: Package installed in editable mode with dev dependencies
- **Character files mounted**: Access to `../characters` directory

## Quick Start

### Using VS Code

1. Install the "Dev Containers" extension
2. Open the `statling` folder in VS Code
3. Press `F1` → "Dev Containers: Reopen in Container"
4. Wait for the container to build and setup to complete

### Using GitHub Codespaces

1. Navigate to the repository on GitHub
2. Click "Code" → "Codespaces" → "Create codespace on main"
3. Wait for the codespace to initialize

## What Gets Installed

The post-create script automatically:

- Upgrades pip to the latest version
- Installs the package in editable mode: `pip install -e ".[dev]"`
- Configures git with safe directory settings
- Creates an `output` directory for rendered character sheets

## Available Commands

Once inside the container:

```bash
# Use the installed statling command
statling --help
statling ../characters/2014_elowen_turnerleaf.yaml -o output/test.md

# Run as a module
python -m statling.render ../characters/2014_elowen_turnerleaf.yaml

# Code quality tools
# Ruff (fast, all-in-one - recommended)
ruff check .          # Lint code
ruff format .         # Format code
ruff check --fix .    # Auto-fix issues

# Traditional tools
black .               # Format with Black
isort .               # Sort imports
flake8 .              # Lint with Flake8
mypy .                # Type check

# Run all checks
black . && isort . && flake8 . && mypy .

# Testing
pytest -v             # Run tests (when added)

# Build package
python -m build
```

## VS Code Tasks

Press `Ctrl+Shift+P` → "Tasks: Run Task" to access:

- **Install Package (Dev)**: Reinstall package with dev dependencies
- **Run Ruff Check**: Lint with Ruff (fast)
- **Run Ruff Format**: Format with Ruff (fast)
- **Run Black**: Format with Black
- **Run isort**: Sort imports
- **Run Flake8**: Lint with Flake8
- **Format All (Black + isort)**: Format code with traditional tools
- **Lint All (Flake8 + MyPy)**: Run all linting checks
- **Check All (Format + Lint)**: Run complete code quality check
- **Run MyPy**: Type check the code
- **Run Tests**: Execute pytest
- **Build Package**: Build distribution packages
- **Render Test Character**: Render Elowen's character sheet

## VS Code Launch Configurations

Press `F5` to debug:

- **Python: Current File**: Debug the currently open file
- **Statling: Render Character**: Debug character rendering
- **Python: Module**: Debug a Python module

## Directory Structure

```
.devcontainer/
├── devcontainer.json         # Main configuration
├── Dockerfile               # Custom container image
├── post-create.sh           # Setup script
├── statling.code-workspace  # VS Code workspace settings
└── README.md               # This file
```

## Customization

### Add VS Code Extensions

Edit `devcontainer.json` → `customizations.vscode.extensions`

### Add System Packages

Edit `Dockerfile` → Add to `apt-get install` list

### Modify Python Setup

Edit `post-create.sh` → Add your setup commands

### Change Python Version

Edit `Dockerfile` → Change the `FROM` line to use different Python version:
```dockerfile
FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm
```

## Environment Variables

The container sets:

- `PYTHONUNBUFFERED=1` - No buffering for stdout/stderr
- `PYTHONDONTWRITEBYTECODE=1` - Don't create `.pyc` files
- `PIP_DISABLE_PIP_VERSION_CHECK=1` - Skip pip version check

## Mounted Directories

The `characters` directory from the parent folder is mounted at `/workspace/characters` for easy access to test YAML files.

## Troubleshooting

### Container won't start

1. Rebuild the container: `F1` → "Dev Containers: Rebuild Container"
2. Check Docker is running
3. Ensure you have enough disk space

### Package not found

Run the "Install Package (Dev)" task or:
```bash
pip install -e ".[dev]"
```

### Git issues

The post-create script should handle this, but if needed:
```bash
git config --global --add safe.directory /workspace
```

## Performance Tips

- The container uses bind mounts for better file sync performance
- Python bytecode writing is disabled to reduce I/O
- Volume caching is set to "cached" for optimal performance

## Resources

- [VS Code Dev Containers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [GitHub Codespaces Documentation](https://docs.github.com/en/codespaces)
- [Dev Container Specification](https://containers.dev/)
