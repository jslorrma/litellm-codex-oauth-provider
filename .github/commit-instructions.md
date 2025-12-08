# Commit Message Instructions

Given a git diff, analyze the changes and generate an appropriate commit message in the specified format.

## Conventional Commits Format

```text
<type>[optional scope]: <description>
[optional body]
[optional footer(s)]
```

### Notes

- Ensure that all file names in the description are wrapped in backticks for clarity.
- Focus on clarity and brevity in both the title and descriptions.

### Core Types (Required)

- **feat**: New feature or functionality (MINOR version bump)
- **fix**: Bug fix or error correction (PATCH version bump)

### Additional Types (Extended)

- **docs**: Documentation changes only
- **style**: Code style changes (whitespace, formatting, semicolons, etc.)
- **refactor**: Code refactoring without feature changes or bug fixes
- **perf**: Performance improvements
- **test**: Adding or fixing tests
- **build**: Build system or external dependency changes
- **ci**: CI/CD configuration changes
- **chore**: Maintenance tasks, tooling changes
- **revert**: Reverting previous commits

### Scope Guidelines

- Use parentheses: `feat(api):`, `fix(ui):`
- Common scopes: `api`, `ui`, `auth`, `db`, `config`, `deps`, `docs`
- For monorepos: package or module names
- Keep scope concise and lowercase

### Description Rules

- Use imperative mood ("add" not "added" or "adds")
- Start with lowercase letter
- No period at the end
- Maximum 50 characters
- Be concise but descriptive

### Body Guidelines (Optional)

- Start one blank line after description
- Explain the "what" and "why", not the "how"
- Wrap at 72 characters per line
- Use for complex changes requiring explanation

### Footer Guidelines (Optional)

- Start one blank line after body
- **Breaking Changes**: `BREAKING CHANGE: description`

## Analysis Instructions

When analyzing staged changes:

1. Determine Primary Type based on the nature of changes
2. Identify Scope from modified directories or modules
3. Craft Description focusing on the most significant change
4. Determine if there are Breaking Changes
5. For complex changes, include a detailed body explaining what and why
6. Add appropriate footers for issue references or breaking changes

For significant changes, include a detailed body explaining the changes.

Return ONLY the commit message in the conventional format, nothing else.
