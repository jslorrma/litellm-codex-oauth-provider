# Contributing to This Project

Welcome! This guide explains how to contribute code, documentation, or ideas to this repository.

## How to Contribute

We use a **fork-and-pull-request** workflow. All contributions are made via pull requests from your own fork to the `main` branch of the original repository.

### Quick Start

1. **Fork the repository** on GitHub.
2. **Clone your fork** to your local machine.
3. **Create a new branch** for your feature or fix (e.g., `feature/add-new-provider`).
4. **Set up your development environment** (see [Getting Started](development/getting-started.md)).
5. **Make your changes** and commit them, following our commit message conventions.
6. **Push your branch** to your fork.
7. **Open a pull request** to the `main` branch of the upstream repository.
8. **Address review feedback** and update your PR until it is approved and merged.
9. **Celebrate your contribution!** 🎉

## Code Style and Clean Code Principles

- Write code that is easy to understand, modify, and test.
- Follow PEP8 and Google's Python Style Guide.
- Use modern Python features: type hints, dataclasses, comprehensions, f-strings, pattern matching, context managers.
- Document all functions, classes, and modules using NumPy docstring format.
- Keep documentation close to the code and favor Markdown and Mermaid for diagrams.
- See the [Getting Started Guide](development/getting-started.md) for examples and style details.

## Branching and Commit Conventions

- **Branch from `main`** for all features and fixes.
- **Branch names:**
  - Use descriptive names: `feature/<description>`, `bugfix/<description>`, `docs/<description>`, etc.
  - Use hyphens for readability (e.g., `feature/add-api-endpoint`).
  - Use only alphanumeric lowercase characters and hyphens.
- **Commit messages:**
  - Use [conventional commits][conventionalcommits]:
    - `feat:` for new features
    - `fix:` for bug fixes
    - `docs:`, `style:`, `refactor:`, `ci:`, `chore:` etc. for other changes
  - Write in imperative mood (e.g., "Add feature", not "Added feature").
  - Reference issues (e.g., `docs: add installation instructions (#1)`).
  - Begin with a short summary (up to 50 characters), separated from the body by a blank line.
  - Example:

    ```text
    feat: add user authentication (#42)
    ```

## Testing and Quality Assurance

- Write tests for new features and bug fixes using `pytest`.
- Run tests before submitting a PR:

  ```bash
  pixi run test
  pixi run test-with-coverage
  ```

- Use assertions and descriptive test names.
- Test results and coverage are checked in CI/CD pipelines.
- See the [Getting Started Guide](development/getting-started.md) for more on test conventions.

## Review and Collaboration

- All contributions are made via pull requests and require review by at least one maintainer.
- Use clear PR titles and descriptions, reference issues, and communicate openly in PR comments.
- Use @-mentions to notify reviewers or contributors.
- Address review feedback promptly and keep discussions constructive.

## Issue Reporting and Feature Requests

- Check existing issues before creating a new one.
- Use clear, descriptive titles and provide detailed information (steps to reproduce, expected/actual behavior, environment info).
- For feature requests, explain the motivation and desired outcome.
- Include screenshots or GIFs if helpful.

### Issue Reporting Guidelines

- **Check Existing Issues**: Before creating a new issue, check existing issues to avoid duplicates. If an issue already exists for your problem or suggestion, add any additional information in the comments.
- **Use a Clear and Descriptive Title**: Issue titles should be descriptive and give a clear idea of what the issue is about.
- **Describe the Issue in Detail**: Include as much relevant information as possible:
  - For bugs: Steps to reproduce, expected behavior, and actual behavior
  - For feature requests: What you're trying to achieve and why
- **Include System Information**: For bugs, include information about your environment (OS, browser version, and any other relevant software versions).
- **Use Labels Appropriately**: If possible, use labels to categorize your issue to help maintainers and other contributors identify and prioritize issues.

## Documentation Contributions

- Keep documentation close to the code and up-to-date.
- Use Markdown and Mermaid for diagrams.
- Favor code examples over analytical descriptions.
- Update `README.md`, `docs/`, and docstrings as needed.

## Need Help?

- For questions, contact maintainers listed in `README.md` via issues or PRs.
- For environment setup and development workflow, see [Getting Started](development/getting-started.md).

[conventionalcommits]: https://www.conventionalcommits.org/en/v1.0.0/
