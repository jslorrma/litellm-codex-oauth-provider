# TestPyPI Publishing Setup - Quick Start Guide

## 🎯 Problem Solved

Your CI pipeline was failing with this error:
```
Trusted publishing exchange failure:
* `invalid-publisher`: valid token, but no corresponding publisher
```

This happened because the GitHub Actions workflow was trying to publish to TestPyPI using OIDC trusted publishing, but TestPyPI wasn't configured to accept tokens from your repository.

## ✅ What Has Been Fixed

1. **Created `.github/workflows/ci.yml`** - A complete CI/CD workflow that:
   - ✅ Runs linting with Ruff
   - ✅ Runs tests with pytest and coverage
   - ✅ Automatically detects version bumps
   - ✅ Builds Python package
   - ✅ **Publishes to TestPyPI ONLY from main branch** (not from PRs)

2. **Added comprehensive documentation**:
   - `docs/testpypi-setup.md` - Detailed setup guide
   - `.github/README.md` - Quick workflow reference

## ⚠️ Action Required: Configure TestPyPI

You must configure a **Trusted Publisher** on TestPyPI before the workflow can publish packages.

### Steps (5 minutes):

1. **Go to TestPyPI**: https://test.pypi.org/manage/account/publishing/

2. **Add a new pending publisher** with these EXACT values:

   | Field | Value |
   |-------|-------|
   | PyPI Project Name | `litellm-codex-oauth-provider` |
   | Owner | `jslorrma` |
   | Repository name | `litellm-codex-oauth-provider` |
   | Workflow filename | `.github/workflows/ci.yml` |
   | Environment name | `testpypi` |

3. **Save** - TestPyPI will now accept OIDC tokens from your workflow!

### Why These Values?

These values match what GitHub Actions sends in the OIDC token when the workflow runs on the main branch:

```yaml
repository: jslorrma/litellm-codex-oauth-provider
workflow_ref: jslorrma/litellm-codex-oauth-provider/.github/workflows/ci.yml@refs/heads/main
environment: testpypi
```

## 🚀 Testing the Setup

Once you've configured the trusted publisher on TestPyPI:

1. **Merge this PR** to the main branch

2. **The workflow will run automatically** and should complete successfully (lint, test)

3. **To trigger a publish**, bump the version:
   ```bash
   # Edit src/litellm_codex_oauth_provider/_version.py
   # Change: __version__ = "0.1.0"
   # To:     __version__ = "0.1.1"
   
   git add src/litellm_codex_oauth_provider/_version.py
   git commit -m "Bump version to 0.1.1"
   git push origin main
   ```

4. **Watch the workflow**: https://github.com/jslorrma/litellm-codex-oauth-provider/actions

5. **Check TestPyPI**: https://test.pypi.org/project/litellm-codex-oauth-provider/

## 🔒 Security Benefits

The new setup uses **OpenID Connect (OIDC)** trusted publishing instead of API tokens:

- ✅ No secrets to store or rotate
- ✅ Automatic token generation per workflow run
- ✅ Tokens work only for your specific repository and workflow
- ✅ Reduces security risks

## 📚 More Information

- **Detailed setup guide**: `docs/testpypi-setup.md`
- **Workflow reference**: `.github/README.md`
- **PyPI documentation**: https://docs.pypi.org/trusted-publishers/

## ❓ Common Questions

**Q: Why didn't it work from the PR?**
A: Trusted publishing only accepts tokens from stable refs (main branch or tags), not from PR merge refs. This is a security feature.

**Q: Do I need to configure this again for production PyPI?**
A: Yes, you'll need to configure a separate trusted publisher on https://pypi.org/ when you're ready for production releases.

**Q: Can I test this on a PR first?**
A: The lint and test steps will run on PRs. Publishing only happens from main branch after version bump.

## 🐛 Troubleshooting

If publishing still fails after configuration:

1. **Double-check** all fields in TestPyPI match exactly
2. **Wait** 1-2 minutes after saving configuration
3. **Ensure** you're pushing to main branch, not a PR
4. **Verify** version was bumped (different from TestPyPI)

---

**Need help?** See `docs/testpypi-setup.md` for detailed troubleshooting steps.
