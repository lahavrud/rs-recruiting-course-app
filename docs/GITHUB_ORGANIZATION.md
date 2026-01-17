# 📋 GitHub Organization Guide

This document outlines the GitHub organization structure and best practices for the RS Recruitment project.

---

## 🏷️ Label System

### Priority Labels
- **P1** (High/Critical Priority) - Urgent issues, blocking bugs, security issues
- **P2** (Medium/High Priority) - Important features, non-blocking bugs
- **P3** (Low/Normal Priority) - Nice-to-have features, minor improvements

### Type Labels
- **feat** - New feature or request
- **fix** - Bug fix
- **chore** - Routine work or maintenance
- **refactor** - Code refactoring
- **test** - Testing, test coverage, or test improvements
- **docs** - Documentation improvements
- **security** - Security-related changes

### Scope Labels
- **backend** - Core server and data management
- **infra** - Infrastructure, DevOps, system-level changes
- **frontend** - Frontend/UI changes (when applicable)
- **api** - API endpoints and contracts
- **config** - Configuration files or settings

### Status Labels
- **bug** - Something isn't working
- **duplicate** - Issue or PR already exists
- **invalid** - Doesn't seem right
- **wontfix** - Will not be worked on
- **question** - Further information requested
- **help wanted** - Extra attention needed
- **good first issue** - Good for newcomers

---

## 📝 Issue Templates

### Task / Feature (`task.md`)
Use for planned work items, features, and development tasks.
- Includes Goal, Scope, Tasks checklist, and Definition of Done
- Default labels: Based on type (feat/chore/etc) + priority

### Bug Report (`bug_report.md`)
Use for reporting bugs or unexpected behavior.
- Includes reproduction steps, expected vs actual behavior
- Default labels: `bug, P2`

### Feature Request (`feature_request.md`)
Use for suggesting new features or enhancements.
- Includes motivation, proposed solution, acceptance criteria
- Default labels: `feat, P3`

### Infrastructure (`infrastructure.md`)
Use for infrastructure, DevOps, or system-level changes.
- Includes technical details, environment scope, breaking changes
- Default labels: `infra, P2`

---

## 🔄 Workflow Best Practices

### Issue Creation
1. **Always use an issue template** - Choose the appropriate template
2. **Set priority** - Add P1/P2/P3 label based on urgency
3. **Add scope labels** - backend, infra, frontend, etc.
4. **Link to project** - Assign to "RS Recruitment - MVP" project
5. **Assign yourself** - Use `--assignee "@me"` when creating via CLI

### Branch Naming
- Features: `feat/short-description`
- Fixes: `fix/short-description`
- Chores: `chore/short-description`
- Docs: `docs/short-description`
- Refactor: `refactor/short-description`

### Pull Request Process
1. **Link to issue** - Reference related issue in PR description
2. **Use PR template** - Fill out Summary, Why, Changes, How to Test
3. **Wait for CI** - Never merge until CI passes
4. **Keep PRs small** - Focus on one feature/fix per PR
5. **Update documentation** - If behavior changes, update docs

### Commit Messages
Use **Conventional Commits** format:
- `feat(scope): description`
- `fix(scope): description`
- `chore(infra): description`
- `refactor(scope): description`
- `docs(scope): description`

---

## 📊 Project Board Organization

### Project: "RS Recruitment - MVP"

The project has multiple views for different purposes:

**View 1: Project Board (Board Layout)**
- **Columns:**
  1. **Backlog** - New issues, not yet prioritized
  2. **To Do** - Prioritized and ready to start
  3. **In Progress** - Currently being worked on
  4. **In Review** - PR created, awaiting review/CI
  5. **Done** - Merged and deployed

- **Automation Rules:**
  - When issue is assigned → Move to "To Do"
  - When PR is created → Move to "In Review"
  - When PR is merged → Move to "Done"

**View 2: Roadmap (Roadmap Layout)**
- **Purpose:** Visual timeline view showing when work is planned and how milestones align
- **Status:** Created (can be recreated via CLI if needed)
- **Configuration:** See [Roadmap Setup Guide](./ROADMAP_SETUP.md) for detailed instructions

---

## 🎯 Milestones

Milestones are used to track progress against roadmap phases. Each milestone aligns with a major development phase from `docs/ROADMAP.md`.

### Available Milestones

1. **Infrastructure Phase** - All infrastructure tasks (infra1-infra8)
   - Repo setup, CI/CD, email service, file storage, frontend architecture, CORS

2. **Company Slice** - Company onboarding and admin approval (feat1-feat2)
   - Company registration, authentication, and admin approval workflow

3. **Job Slice** - Job posting and public job board (feat3-feat4)
   - Job CRUD operations and public job board

4. **Candidate Slice** - Public application form and shadow profile (feat5-feat6)
   - Candidate application submission and shadow profile creation

5. **Match Slice** - Admin dashboard and notifications (feat7-feat8)
   - Admin matching dashboard and notification system

6. **Frontend** - Frontend structure and pages (frontend1-frontend3)
   - Frontend setup, public pages, and admin/company dashboards

7. **Deployment** - Database backup, dev/staging/prod deployment (devops1-deploy1)
   - Backup strategy and deployment to all environments

### Using Milestones

**Assign to Issues:**
- When creating an issue, assign it to the appropriate milestone
- Issues can be filtered by milestone to track progress per phase
- Milestones can be closed when all related issues are completed

**Assign to Pull Requests:**
- PRs automatically inherit milestones from linked issues (via `assign-milestone.yml` workflow)
- If a PR links to an issue with a milestone (e.g., "Closes #123"), the PR will automatically get the same milestone
- You can also manually assign milestones to PRs if needed

**Best Practices:**
- Assign issues to milestones when creating them
- Link PRs to issues using "Closes #123" to automatically inherit milestones
- Update milestone descriptions if scope changes
- Close milestones when the phase is complete
- Use milestones to track progress against roadmap timeline

---

## 🎯 Issue Prioritization Guidelines

### P1 (Critical)
- Security vulnerabilities
- Production bugs blocking core functionality
- Infrastructure failures
- Data loss or corruption risks

### P2 (High)
- Non-blocking bugs
- Important features from roadmap
- Performance issues
- Infrastructure improvements

### P3 (Normal)
- Nice-to-have features
- Minor improvements
- Documentation updates
- Code quality improvements

---

## ⚙️ Repository Settings

### Merge Settings
- **Squash Merge**: Enabled (recommended for trunk-based development)
- **Merge Commit**: Enabled
- **Rebase Merge**: Enabled
- **Default Merge Method**: Set to squash merge (aligns with trunk-based development workflow)
- **Auto-delete Merged Branches**: Enabled - Merged PR branches are automatically deleted to keep repository clean

### Branch Protection
- Protected via Repository Ruleset on `main` branch
- Required: CI checks (`lint`, `test`) must pass
- Required: Branch must be up to date before merging
- Required: Pull requests required (no direct pushes)
- **No bypass**: Even administrators cannot bypass rules

---

## 🔍 Repository Metadata

### Description
"Specialized CRM for boutique recruitment agency - MVP. FastAPI backend with vertical slices architecture."

### Topics
- `fastapi`
- `python`
- `recruitment`
- `crm`
- `mvp`
- `postgresql`
- `docker`

### README
- Keep README.md up to date with current status
- Link to detailed documentation in `docs/`
- Include CI badge and quick start guide

---

## 📚 Documentation Structure

- **`docs/CONTEXT.md`** - Core philosophy, domain model, coding standards
- **`docs/ARCHITECTURE.md`** - System design, infrastructure decisions
- **`docs/ROADMAP.md`** - Product roadmap and timeline
- **`docs/ROADMAP_SETUP.md`** - GitHub Projects roadmap view setup guide
- **`docs/ROADMAP_STEP_BY_STEP.md`** - Detailed step-by-step roadmap configuration (buttons, dates)
- **`docs/API_DESIGN.md`** - API endpoints and contracts (when implemented)
- **`docs/GITHUB_ORGANIZATION.md`** - This file

---

## ✅ Checklist for New Issues

- [ ] Used appropriate issue template
- [ ] Added priority label (P1/P2/P3)
- [ ] Added type label (feat/fix/chore/etc)
- [ ] Added scope label (backend/infra/etc)
- [ ] Assigned to project "RS Recruitment - MVP"
- [ ] Assigned milestone (Infrastructure Phase | Company Slice | Job Slice | Candidate Slice | Match Slice | Frontend | Deployment)
- [ ] Assigned to yourself (if working on it)
- [ ] Linked related issues/PRs
- [ ] Filled out all relevant sections

---

## 🚀 Quick Reference Commands

### Create Issue
```bash
gh issue create \
  --title "feat(scope): description" \
  --body-file .github/ISSUE_TEMPLATE/task.md \
  --assignee "@me" \
  --project "RS Recruitment - MVP" \
  --label "feat,P2,backend" \
  --milestone "Company Slice"
```

### Create PR
```bash
gh pr create \
  --title "feat(scope): description" \
  --body "Closes #123" \
  --assignee "@me" \
  --base main \
  --milestone "Company Slice"
```

**Note:** PRs will automatically inherit the milestone from linked issues via the `assign-milestone.yml` workflow. You can still set it manually if needed.

### List Issues by Priority
```bash
gh issue list --label "P1"
gh issue list --label "P2"
gh issue list --label "P3"
```

### Milestone Management
```bash
# List all milestones
gh api repos/lahavrud/rs-recruitment/milestones

# Create issue with milestone
gh issue create \
  --title "feat(scope): description" \
  --body-file .github/ISSUE_TEMPLATE/task.md \
  --assignee "@me" \
  --project "RS Recruitment - MVP" \
  --label "feat,P2,backend" \
  --milestone "Company Slice"

# List issues by milestone
gh issue list --milestone "Infrastructure Phase"

# Update issue milestone
gh issue edit <issue-number> --milestone "Job Slice"
```

---

## 📖 Additional Resources

- [GitHub Issues Best Practices](https://docs.github.com/en/issues/tracking-your-work-with-issues/about-issues)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Project Documentation](../docs/CONTEXT.md)
