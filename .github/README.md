# GitHub Workflows

This directory contains GitHub Actions workflows for CI/CD.

## ci.yml - Continuous Integration Workflow

The CI workflow runs on all branches and pull requests to:

1. **Lint** - Run Ruff linter with auto-fix
2. **Test** - Run pytest with coverage reporting
3. **Version Check** - Compare current version with TestPyPI
4. **Build** - Build Python package (only if version changed)
5. **Publish** - Publish to TestPyPI (only on main branch with version bump)

### Key Features

- **Automatic version detection**: Compares `pyproject.toml` version with TestPyPI
- **Conditional publishing**: Only publishes when:
  - Version has changed
  - Push event (not PR)
  - Main branch
- **Trusted publishing**: Uses GitHub OIDC for secure authentication (no API tokens needed)

### TestPyPI Trusted Publisher Setup

⚠️ **Important**: Before the workflow can publish, you must configure a trusted publisher on TestPyPI.

See [../docs/testpypi-setup.md](../docs/testpypi-setup.md) for detailed setup instructions.

**Quick setup**:
1. Go to https://test.pypi.org/manage/account/publishing/
2. Add pending publisher with:
   - Repository: `jslorrma/litellm-codex-oauth-provider`
   - Workflow: `.github/workflows/ci.yml`
   - Environment: `testpypi`

### Workflow Behavior

| Event | Branch | Lint | Test | Build | Publish |
|-------|--------|------|------|-------|---------|
| Pull Request | Any | ✅ | ✅ | Only if version bump | ❌ |
| Push | Non-main | ✅ | ✅ | Only if version bump | ❌ |
| Push | Main | ✅ | ✅ | Only if version bump | ✅ If version bump |

### Required Repository Secrets

None! The workflow uses OIDC trusted publishing, which doesn't require storing secrets.

### Required Repository Environments

The workflow automatically creates the `testpypi` environment. You can optionally pre-create it in:

- Repository Settings → Environments → New environment → `testpypi`

### Publishing a New Version

1. Bump version in `src/litellm_codex_oauth_provider/_version.py`
2. Commit and push to main:
   ```bash
   git add src/litellm_codex_oauth_provider/_version.py
   git commit -m "Bump version to X.Y.Z"
   git push origin main
   ```
3. Watch the workflow run at: https://github.com/jslorrma/litellm-codex-oauth-provider/actions

The package will be available at: https://test.pypi.org/project/litellm-codex-oauth-provider/
