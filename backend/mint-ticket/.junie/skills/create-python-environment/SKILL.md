---
name: create-python-environment
description: Scaffolds a new Python environment and project structure with uv, src-layout, CLI entry point, test setup, and PEP 735 dependency groups.
---

### Create Python Environment Skill

Use this skill whenever setting up a new Python project, package, or microservice. This standardizes environment creation, optimizes developer velocity, prevents configuration discrepancies, and enforces consistent architecture across services.

---

### Step-by-Step Procedure

#### 1. Prompt for Project Location and Program Name
- Prompt the user for the target path of the Python program starting from the project root (e.g., `backend/ticket-issuer` or `services/pdf-processor`).
- Extract the `<program_name>` as the terminal directory name in the path (e.g., `ticket-issuer`).
- Derive the Python module/package name `<module_name>` by converting any dashes (`-`) in `<program_name>` to underscores (`_`) and ensuring lowercase snake_case (e.g., `ticket-issuer` -> `ticket_issuer`).

#### 2. Create Target Directory
- Create the target directory at the specified path if it does not already exist:
  ```bash
  mkdir -p <target_path>
  ```
- Change working directory or target commands to this path.

#### 3. Initialize with uv
- Run `uv init` with the converted module name:
  ```bash
  uv init <module_name>
  ```
- Alternatively, when inside the directory:
  ```bash
  uv init --name <module_name>
  ```
- Ensure Python version constraint in `pyproject.toml` targets Python 3.12+ (e.g., `requires-python = ">=3.12"`).

#### 4. Establish src Layout and Test Directory Structure
- Create the package module directory under `src/` and the `tests/` directory:
  ```bash
  mkdir -p src/<module_name>
  mkdir -p tests
  ```
- Add `__init__.py` to both directories:
  ```bash
  touch src/<module_name>/__init__.py
  touch tests/__init__.py
  ```
- If `uv init` generated a top-level `hello.py` or `main.py`, remove it or move its logic into `src/<module_name>/cli.py`.
- Create a minimal CLI entry point at `src/<module_name>/cli.py`:
  ```python
  def main() -> None:
      print("<program_name> CLI initialized")


  if __name__ == "__main__":
      main()
  ```
- Create a starter test at `tests/test_cli.py`:
  ```python
  from <module_name>.cli import main

  def test_main(capsys) -> None:
      main()
      captured = capsys.readouterr()
      assert "<program_name>" in captured.out
  ```

#### 5. Configure `pyproject.toml`
Adjust `pyproject.toml` to include:
1. **CLI Entry Point (`[project.scripts]`)**:
   Register the CLI executable command named `<program_name>` pointing to `<module_name>.cli:main`:
   ```toml
   [project.scripts]
   <program_name> = "<module_name>.cli:main"
   ```
2. **Hatch Wheel Build Targets (`[tool.hatch.build.targets.wheel]`)**:
   Direct the Hatchling build backend to package from the `src` layout:
   ```toml
   [tool.hatch.build.targets.wheel]
   packages = ["src/<module_name>"]
   ```
3. **PEP 735 Dependency Groups (`[dependency-groups]`)**:
   Isolate development, testing, and linting dependencies from production runtime dependencies:
   ```toml
   [dependency-groups]
   dev = [
       "pytest>=8.0.0",
       "pytest-cov>=5.0.0",
       "pytest-mock>=3.14.0",
       "ruff>=0.5.0",
   ]
   ```
4. **Pytest and Tooling Configurations**:
   ```toml
   [tool.uv]
   package = true

   [tool.ruff]
   line-length = 100
   target-version = "py312"

   [tool.pytest.ini_options]
   testpaths = ["tests"]
   ```

---

### Example `pyproject.toml`

For a project located at `backend/ticket-issuer` (`<program_name>` = `ticket-issuer`, `<module_name>` = `ticket_issuer`):

```toml
[project]
name = "ticket-issuer"
version = "0.1.0"
description = "Ticket Issuer Service"
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
ticket-issuer = "ticket_issuer.cli:main"

[tool.uv]
package = true

[tool.hatch.build.targets.wheel]
packages = ["src/ticket_issuer"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.pytest.ini_options]
testpaths = ["tests"]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=5.0.0",
    "pytest-mock>=3.14.0",
    "ruff>=0.5.0",
]
```

---

### Verification and Sanity Checklist

After running the setup steps:
1. Run `uv sync` to install dependencies and configure the virtual environment.
2. Run `uv run pytest` to verify the test suite executes successfully against the `src` layout.
3. Test CLI execution via `uv run <program_name>`.
