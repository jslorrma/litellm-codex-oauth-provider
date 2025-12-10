# Pull Request Instructions

Use these guidelines to create clear and comprehensive pull request descriptions, enabling effective code reviews and collaboration.

---

## Pull Request Description Template

```markdown
# _Pull Request Title_
_The title should be a concise summary of the main change or feature introduced by the pull request and reflect the branch name or issue being addressed._

## Summary
- _Briefly describe the purpose of the pull request, referencing the main problem or goal. Don't be too general, but be clear and specific._
- _Highlight major changes, new features, or bug fixes._
- _Mention any related issues or tickets._

## Changes

### Core Changes
_Test and Documentation changes go in their own sections below._
- _Bullet point summary of changes made, with concise descriptions._
- _Reference specific files or modules affected. Make sure files are quoted using backticks._
- _Add relevant context or rationale for the changes._
- _Include technical details helpful for reviewers._

### Tests
- _Describe new or updated tests, focusing on data scenarios, validation, or model evaluation._
- _Mention important cases that are tested (or untested if relevant)._

### Documentation
- _List any documentation updated, such as README, notebooks, or data dictionaries._
- _Provide important info for maintainers (e.g., migration steps, reproducibility instructions)._

### Dependencies
- **Added** – `package@version` (reason/benefit).
- **Updated** – `package@old -> package@new` (note if security-/bug-fix-related).
- **Removed** – `package@version` (reason).

**Change Summary:**
- Files changed: `<N>`
- Insertions: `+<X>` / Deletions: `-<Y>`

## Breaking Changes or Concerns
_IMPORTANT: Only fill this section if there are breaking changes, significant concerns, or areas needing special attention. Skip if not applicable._
- _Note areas requiring special attention during review._
- _Mention known issues or limitations._
- _Highlight areas where specific feedback is requested._

## Feedback & Review Requested
_IMPORTANT: Only fill this section if you want specific feedback from reviewers. Skip if not applicable._
- _Specific aspects where reviewer input is desired (e.g., pipeline design, feature selection, data handling)._
- _Alternative approaches considered and rationale for current choice._
```

---

## Step-by-Step Instructions

1. **Determine Target Branch**
   - Default to `origin/develop` if not specified.
   - Use `origin/<target_branch>` for comparisons.

2. **Gather Information**
   - _Always perform this step._
   - Extract `<target_branch>` as above.
   - Execute the following commands:
     - `git fetch origin`; fetch latest remote changes.
     - `git log origin/<target_branch>..HEAD --pretty=format:'commit %H%nAuthor: %an <%ae>%nDate: %ad%n%n%s%n%n%b%n---' --no-merges`; get a detailed commit log for the pull request.
     - `git diff origin/<target_branch>...HEAD --stat --name-status`; get a summary of file changes.

3. **Review & Analyze**
   - Understand changes from logs and diffs and the PR's purpose and scope.
   - Identify: Features, fixes, refactors, performance, security, tests, docs, config, deps.
   - Check for breaking changes (schema, API, contracts).

4. **Draft & Format**
   - Use the template above.
   - Fill in all sections with clear and concise information.
   - Group changes logically.
   - Be concise but complete and specific not too general.
