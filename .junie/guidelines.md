# Junie Development Guidelines

## General
- Prefer simple, readable code over clever code.
- Keep business logic separate from CLI/input-output handling.
- Use small, focused functions.

## Python
- Use Python 3.12 features where appropriate.
- Follow existing project conventions.
- Keep modules modular and easy to test.

## Testing
- Write unit tests before implementation in the Test Driven Development style a done by Kent Beck: no code should be written until there 
is a failing test first.  Then write the minimum amount of code to make the test pass. And continue to refactor and 
improve the code until it is clean and efficient.
- Use pytest.
- Cover error handling paths, not only happy paths.
- Code coverage should be at least 80%.

## Package Management
- Use uv for dependency management.
- Do not use pip, poetry, or conda unless explicitly requested.

## Output/API
- Keep JSON schemas stable and versioned.
- Ensure command-line tools write machine-readable output to stdout and human-readable errors to stderr.