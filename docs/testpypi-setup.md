# TestPyPI Trusted Publisher Configuration

This document explains how to configure PyPI/TestPyPI trusted publishing for this repository.

## Problem

The CI pipeline was failing with the following error when trying to publish to TestPyPI:

```
Trusted publishing exchange failure:
Token request failed: the server refused the request for the following reasons:

* `invalid-publisher`: valid token, but no corresponding publisher (Publisher with matching claims was not found)
```

## Root Cause

The error occurs because:

1. The GitHub Actions workflow uses **OpenID Connect (OIDC) trusted publishing** to authenticate with TestPyPI
2. TestPyPI needs to have a **trusted publisher** configured that matches the GitHub repository and workflow
3. The trusted publisher was either not configured or configured with incorrect settings

## Solution: Configure Trusted Publisher on TestPyPI

### Step 1: Create TestPyPI Account (if needed)

1. Go to [https://test.pypi.org/](https://test.pypi.org/)
2. Register for an account or log in

### Step 2: Reserve Package Name (First Time Only)

Before configuring trusted publishing, you need to either:

- **Option A**: Upload an initial version manually using API tokens (traditional method)
- **Option B**: Use the "Pending Publisher" feature (recommended)

For **Option B** (Pending Publisher):

1. Go to [https://test.pypi.org/manage/account/publishing/](https://test.pypi.org/manage/account/publishing/)
2. Scroll to "Pending publishers"
3. Click "Add a new pending publisher"
4. Fill in the form with the details below (see Step 3)

### Step 3: Configure Trusted Publisher

Whether using Option A or B above, configure the trusted publisher with these **exact** settings:

| Field | Value |
|-------|-------|
| **PyPI Project Name** | `litellm-codex-oauth-provider` |
| **Owner** | `jslorrma` |
| **Repository name** | `litellm-codex-oauth-provider` |
| **Workflow filename** | `.github/workflows/ci.yml` |
| **Environment name** | `testpypi` |

### Step 4: Understanding the Workflow

The CI workflow (`.github/workflows/ci.yml`) is configured to:

1. **Run linting and tests** on all branches and PRs
2. **Build the package** only when version is bumped (compared to TestPyPI)
3. **Publish to TestPyPI** only when:
   - Version has changed
   - Event is a `push` (not a pull request)
   - Branch is `main`

This prevents publishing from pull requests, which would fail with trusted publishing.

### Step 5: OIDC Token Claims

When the workflow runs on the main branch, GitHub generates an OIDC token with these claims:

```yaml
sub: repo:jslorrma/litellm-codex-oauth-provider:environment:testpypi
repository: jslorrma/litellm-codex-oauth-provider
repository_owner: jslorrma
repository_owner_id: 47713663
workflow_ref: jslorrma/litellm-codex-oauth-provider/.github/workflows/ci.yml@refs/heads/main
job_workflow_ref: jslorrma/litellm-codex-oauth-provider/.github/workflows/ci.yml@refs/heads/main
ref: refs/heads/main
environment: testpypi
```

TestPyPI validates these claims against your trusted publisher configuration.

## Testing the Setup

1. Make a version bump in `src/litellm_codex_oauth_provider/_version.py`
2. Commit and push to main branch:
   ```bash
   git add src/litellm_codex_oauth_provider/_version.py
   git commit -m "Bump version to trigger release"
   git push origin main
   ```
3. Watch the GitHub Actions workflow at: [https://github.com/jslorrma/litellm-codex-oauth-provider/actions](https://github.com/jslorrma/litellm-codex-oauth-provider/actions)

## Publishing to Production PyPI

When ready to publish to production PyPI:

1. Configure a similar trusted publisher on [https://pypi.org/](https://pypi.org/)
2. Create a new environment in `.github/workflows/ci.yml` (e.g., `pypi`)
3. Add a new job `publish-to-pypi` similar to `publish-to-testpypi`
4. Consider gating production publishing to tags only:
   ```yaml
   if: startsWith(github.ref, 'refs/tags/v')
   ```

## Troubleshooting

### Error: "No corresponding publisher found"

- **Cause**: Trusted publisher not configured or misconfigured
- **Solution**: Double-check all fields in TestPyPI trusted publisher configuration

### Error: "Workflow running on wrong ref"

- **Cause**: Workflow triggered from PR instead of main branch
- **Solution**: Wait for PR to be merged, then workflow will run on main

### Error: "Environment not found"

- **Cause**: GitHub environment `testpypi` not created
- **Solution**: The environment is created automatically when the workflow runs. Optionally, pre-create it in repository settings → Environments

## References

- [PyPI Trusted Publishers Documentation](https://docs.pypi.org/trusted-publishers/)
- [PyPI Trusted Publishers Troubleshooting](https://docs.pypi.org/trusted-publishers/troubleshooting/)
- [GitHub Actions OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
