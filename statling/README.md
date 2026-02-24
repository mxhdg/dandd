# Statling

A D&D 5e character sheet renderer that converts YAML character data into formatted Markdown character sheets using Jinja2 templates.

## Quick Start

### Using Dev Container (Recommended)

The easiest way to get started is using the provided dev container:

1. Install [VS Code](https://code.visualstudio.com/) and the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open the `statling` folder in VS Code
3. Press `F1` → "Dev Containers: Reopen in Container"
4. Wait for setup to complete - everything is configured automatically!

See [.devcontainer/README.md](.devcontainer/README.md) for more details.

### Using GitHub Codespaces

Click the "Code" button on GitHub → "Codespaces" → "Create codespace" for instant setup.

## Installation

### From Source

```bash
# Clone or navigate to the repository
cd statling

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Using pip (future)

```bash
pip install statling
```

### After Installation

Once installed, you can use the `statling` command:

```bash
# Render to stdout
statling characters/character.yaml

# Render to file
statling characters/character.yaml -o output.md

# Use custom template
statling characters/character.yaml -t custom.j2 -o output.md
```

## Usage

### Command Line

From the project root:

```bash
# Render to stdout
python statling/render.py characters/2014_elowen_turnerleaf.yaml

# Render to file
python statling/render.py characters/2014_elowen_turnerleaf.yaml -o output.md

# Use custom template
python statling/render.py characters/character.yaml -t custom_template.j2 -o output.md
```

Or as a Python module:

```bash
python -m statling.render characters/2014_elowen_turnerleaf.yaml -o output.md
```

### As a Library

```python
from statling import CharacterRenderer

# Initialize renderer
renderer = CharacterRenderer()

# Render to string
rendered = renderer.render('characters/character.yaml')
print(rendered)

# Render to file
renderer.render_to_file(
    'characters/character.yaml',
    'output.md',
    template_name='character_sheet_5e_2014.j2'
)
```

## YAML Format

Character data should be structured as YAML with the following main sections:

- `name`, `race`, `alignment`, `background` - Basic info
- `classes` - Array of class/level/subclass
- `ability_scores` - Scores and modifiers for all abilities
- `saving_throws` - Proficiencies and bonuses
- `skills` - Proficiencies and bonuses for all skills
- `combat` - AC, HP, initiative, hit dice, etc.
- `weapons` - Attack bonuses, damage, range
- `features` - Racial traits, class features, etc.
- `equipment` - Carried items and currency
- `personality` - Traits, ideals, bonds, flaws
- `companion` - Optional companion stats
- `appearance` - Physical description
- `advancement` - Leveling options

See `characters/2014_elowen_turnerleaf.yaml` for a complete example.

## Templates

Templates are stored in `statling/templates/` and use Jinja2 syntax.

### Available Templates

- `character_sheet_5e_2014.j2` - Standard D&D 5e (2014) character sheet format

### Creating Custom Templates

Create a new `.j2` file in the templates directory. The template has access to all fields from the YAML character data as variables.

Example:

```jinja
# {{ name }}

**Level {{ total_level }} {{ race }} {{ classes[0].name }}**

## Ability Scores
Strength: {{ ability_scores.strength.score }} ({{ '%+d' | format(ability_scores.strength.modifier) }})
...
```

## Requirements

- Python 3.14+
- PyYAML >= 6.0
- Jinja2 >= 3.1.0

Install dependencies:

```bash
pip install -r requirements.txt
```

Or install in development mode with code quality tools:

```bash
pip install -e ".[dev]"
```

## Code Quality

This project follows PEP 8 standards and uses modern Python 3.14 type hints.

### Available Tools

The project includes multiple code quality tools:

- **Ruff**: Fast all-in-one linter and formatter (recommended)
- **Black**: Code formatter
- **isort**: Import statement organizer
- **flake8**: Linting
- **mypy**: Static type checking

### Run Code Quality Checks

**Using Ruff (recommended - fastest):**

```bash
ruff check .            # Lint
ruff format .           # Format
ruff check --fix .      # Auto-fix issues
```

**Using traditional tools:**

```bash
# Format code
black .
isort .

# Lint code
flake8 .

# Type check
mypy .
```

**Run all checks:**

```bash
# Format and lint
black . && isort . && flake8 . && mypy .
```

### Using Make

A Makefile is provided for convenience:

```bash
make help           # Show all available targets
make dev-install    # Install with dev dependencies
make format         # Format code (uses Ruff by default)
make lint           # Lint code (uses Ruff by default)
make type-check     # Type check with mypy
make test           # Run tests
make check          # Run all checks (fast with Ruff)
make all            # Format, lint, type-check, and test
make clean          # Clean build artifacts

# Using traditional tools
make format-trad    # Format with Black and isort
make lint-trad      # Lint with Flake8
make check-trad     # All checks with traditional tools
```

**Note**: Ruff is recommended as it's significantly faster and provides all functionality of Black, isort, and Flake8 in one tool. Traditional tools are included for compatibility.

## Building and Distribution

Build the package:

```bash
# Install build tools
pip install build

# Build source and wheel distributions
python -m build

# This creates files in dist/:
# - statling-0.1.0.tar.gz (source distribution)
# - statling-0.1.0-py3-none-any.whl (wheel)
```

Install from local build:

```bash
pip install dist/statling-0.1.0-py3-none-any.whl
```

## Package Structure

```
statling/
├── .editorconfig                    # Editor configuration
├── .gitignore                       # Git ignore rules
├── LICENSE                          # MIT License
├── MANIFEST.in                      # Package manifest
├── README.md                        # This file
├── pyproject.toml                   # Modern Python packaging config
├── setup.py                         # Legacy setup script
├── requirements.txt                 # Dependencies
├── __init__.py                      # Package init
├── __main__.py                      # Module entry point  
├── py.typed                         # PEP 561 type hints marker
├── render.py                        # Main rendering logic
└── templates/
    └── character_sheet_5e_2014.j2  # Jinja2 template
```
