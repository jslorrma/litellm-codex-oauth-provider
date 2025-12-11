# Commit Message Instructions

Given a git diff, analyze the changes and generate an appropriate commit message in the specified format.

---

## Conventional Commits Format

```
<type>[optional scope]: <description>
[optional body]
[optional footer(s)]
```

---

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

---

### Scope Guidelines

- Use parentheses: `feat(api):`, `fix(ui):`
- Common scopes: `api`, `ui`, `auth`, `db`, `config`, `deps`, `docs`
- For monorepos: package or module names
- Scope should be concise and lowercase

---

### Description Rules

- Use imperative mood ("add" not "added" or "adds")
- Start with lowercase letter
- No period at the end
- Maximum 50 characters
- Be concise but descriptive
- Wrap all file names in backticks for clarity

---

### Body Guidelines (Optional)

- Start one blank line after description
- Explain "what" and "why", not "how"
- Wrap at 72 characters per line
- Use for complex changes requiring explanation

---

### Footer Guidelines (Optional)

- Start one blank line after body
- **Breaking Changes**: `BREAKING CHANGE: description`
- Issue references, e.g., `Closes #123`

---

## Analysis Instructions

When analyzing staged changes:

1. Determine Primary Type based on the nature of changes
2. Identify Scope from modified directories or modules
3. Craft Description focusing on the most significant change
4. Determine if there are Breaking Changes
5. For complex changes, include a detailed body explaining what and why
6. Add appropriate footers for issue references or breaking changes

---

**Return ONLY the commit message in the conventional format.**
