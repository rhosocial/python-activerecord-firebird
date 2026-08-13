# Version Control Principles for rhosocial-activerecord

## 1. Version Management Principles

### Package Ecosystem Architecture

The project consists of three main package types with distinct versioning strategies:

```
rhosocial-activerecord (Core)
    └── Provides: Base ActiveRecord, interfaces, backend abstraction
    └── Version: Independent semantic versioning
    └── Dependencies: Pydantic only

rhosocial-activerecord-testsuite (Test Suite)
    └── Provides: Standardized test contracts, provider interfaces
    └── Version: Tracks core package for API compatibility
    └── Dependencies: Core package, pytest

rhosocial-activerecord-{backend} (Backend Extensions)
    └── Provides: Database-specific implementations
    └── Version: MAJOR synced with core, MINOR/PATCH independent
    └── Dependencies: Core package, native database drivers
```

### Python Version Support Policy

#### Current Support Matrix

**All Versions**:
- **Supported**: Python 3.11, 3.12, 3.13, 3.14
- **Tested on CI**: All above versions (against Firebird 5 and 6-snapshot)
- **Minimum version**: Python 3.11 (required by the `firebird-driver` dependency, which declares `requires-python >= 3.11`)

#### Support Lifecycle

**Python Version End-of-Life Policy**:

- **Active Support**: Major versions actively maintained by Python core team
- **Security-only Support**: 6 months after Python version reaches EOL
- **Dropped Support**: After security-only period ends, or when the minimum supported Python version is raised

**Current Python EOL Schedule**:

```
Python Version | EOL Date    | rhosocial-activerecord-firebird Support Status
---------------|-------------|-------------------------------------------------
3.8            | 2024-10     | Not supported (firebird-driver requires 3.11+)
3.9            | 2025-10     | Not supported (firebird-driver requires 3.11+)
3.10           | 2026-10     | Not supported (firebird-driver requires 3.11+)
3.11           | 2027-10     | Full support
3.12           | 2028-10     | Full support
3.13           | 2029-10     | Full support
3.14           | 2030-10     | Full support
```

#### Dependency Constraints

- `firebird-driver>=2.0.0`: Requires Python 3.11+
- Python 3.11 is the effective minimum regardless of the core package's own
  minimum, because this backend cannot be installed without the driver.
- The `rhosocial-activerecord` core package supports Python 3.8+; this backend
  is therefore always more restrictive than the core.

#### Upgrade Path

```bash
pip install rhosocial-activerecord-firebird
```

#### Migration Strategy

**For Users on Python < 3.11**:

1. Upgrade to Python 3.11 or newer before installing this backend.
2. The `firebird-driver` package will refuse installation on Python < 3.11.

**For Backend Developers**:

- Backends must declare minimum Python version in `pyproject.toml`
- Test matrix should cover all supported Python versions
- Use feature detection for Python version-specific features

**Version Support Declaration**:

```python
# pyproject.toml
[project]
requires-python = ">=3.11"
```

### Core Libraries

#### Package Dependencies

- **Core Package**: Only depends on Pydantic for data validation and model definition
- **No ORM Dependencies**: Built from scratch without SQLAlchemy, Django ORM, or other ORMs
- **Backend Agnostic**: Core ActiveRecord functionality remains independent of specific database backends
- **Namespace Package Structure**: Uses namespace packages to allow distributed backend implementations

#### Version Numbering Rules

All packages MUST follow **PEP 440** compliance with **strict semantic versioning interpretation**:

**Full Format**: `[EPOCH!]RELEASE[-PRE][.postPOST][.devDEV][+LOCAL]`

**Semantic Versioning Rules**:

1. **MAJOR version (X.0.0)**: Incompatible API changes breaking backward compatibility
   - Breaking changes to public interfaces
   - Removal of deprecated features
   - Major architectural redesigns
   - Pydantic major version upgrades
   - **Python minimum version increases** (e.g., dropping Python 3.10 support)
   - **MUST** be incremented when backward compatibility is broken

2. **MINOR version (1.X.0)**: New features in backward-compatible manner
   - New functionality additions
   - New field types or query methods
   - Enhanced capabilities
   - **MUST NOT** break backward compatibility
   - **MUST NOT** change minimum Python version

3. **PATCH version (1.0.X)**: Backward-compatible bug fixes only
   - Bug fixes and corrections
   - Security patches
   - Performance improvements
   - Documentation updates
   - **MUST NOT** introduce new features or break compatibility

**Examples**:

```python
__version__ = "1.0.0"                # Final release
__version__ = "2!1.0.0a1"            # Epoch + Alpha
__version__ = "1.0.0-beta.2.post3"   # Beta with post-release
__version__ = "1.0.0.dev4+local.1"   # Dev version + local build
```

#### Version Components

1. **Epoch (Optional)**: Format `[N!]` (e.g., `2!1.0.0`)
   - Purpose: Resets version numbering for major compatibility breaks
   - Defaults to `0!` if omitted
   - Example: Migrating from Pydantic v1 to v2 could warrant epoch increment

2. **Release Segments**: Format `N(.N)*` (e.g., `1`, `1.2`, `1.0.0`)
   - Rules: At least one numeric segment
   - Major version increments indicate incompatible API changes

3. **Pre-release (Optional)**: Format `[-._]{a|alpha|b|beta|rc|pre|preview}[N]`
   - Short aliases: `a` = alpha, `b` = beta, `rc` = release candidate
   - Examples: `1.0a1`, `1.0-beta.2`, `1.0.0-rc.3`

4. **Post-release (Optional)**: Format `.postN` (e.g., `1.0.0.post1`)
   - Purpose: Bug fixes without altering the main release

5. **Dev-release (Optional)**: Format `.devN` (e.g., `1.0.0.dev2`)
   - Purpose: Marks in-development versions

6. **Local Version (Optional)**: Format `+[alphanum][._-alphanum]*`
   - Purpose: Identifies unofficial builds (ignored in version comparisons)

### Pre-release Development Cycle

Every new MAJOR.MINOR version MUST follow this standardized pre-release cycle:

**Development Phases**:

```
dev → alpha → beta → rc → release
```

#### Phase 1: Development (dev)

**Version Format**: `X.Y.0.devN` (e.g., `1.2.0.dev1`, `1.2.0.dev2`)

**Purpose**: Active feature development and early integration

**Characteristics**:

- **No fixed release count**: Release as frequently as needed for integration
- **No fixed time interval**: Can release multiple times per day if necessary
- **Focus**: Feature implementation, API design, initial testing
- **Stability**: Unstable, breaking changes allowed between dev releases
- **Branch**: Work happens on `release/vX.Y.0.devN` branch

**Guidelines**:

- Create dev releases for sharing work in progress
- Use for continuous integration testing
- No guarantee of stability or API consistency
- Can skip directly to alpha when feature set is complete

**Example Timeline**:

```
Day 1:  1.2.0.dev1 - Initial feature A implementation
Day 3:  1.2.0.dev2 - Feature B added, API refined
Day 5:  1.2.0.dev3 - Integration fixes
Day 8:  1.2.0.dev4 - Ready for alpha phase
```

#### Phase 2: Alpha (alpha/a)

**Version Format**: `X.Y.0aN` (e.g., `1.2.0a1`, `1.2.0a2`, `1.2.0a3`)

**Purpose**: Feature complete, internal testing and stabilization

**Characteristics**:

- **Target release count**: ~3 releases
- **Release interval**: ~1 week between releases
- **Maximum phase duration**: 1 month
- **Focus**: Feature freeze, bug fixes, internal testing
- **Stability**: Moderately stable, API changes still possible
- **Branch**: Releases from `release/vX.Y.0` branch

**Guidelines**:

- Feature set is frozen (no new features)
- API can still be adjusted based on testing feedback
- Focus on bug fixes and stabilization
- Skip if no critical issues found within 1 week
- If no new release needed after 1 month, advance to beta

**Example Timeline**:

```
Week 1: 1.2.0a1 - Feature complete, initial testing
Week 2: 1.2.0a2 - Bug fixes from testing
Week 3: 1.2.0a3 - API refinements
Week 4: Ready for beta phase
```

#### Phase 3: Beta (beta/b)

**Version Format**: `X.Y.0bN` (e.g., `1.2.0b1`, `1.2.0b2`, `1.2.0b3`)

**Purpose**: External testing, API freeze, comprehensive testing

**Characteristics**:

- **Target release count**: ~3 releases
- **Release interval**: ~1 week between releases
- **Maximum phase duration**: 1 month
- **Focus**: API frozen, bug fixes only, external testing
- **Stability**: Stable for testing, only critical bug fixes
- **Branch**: Releases from `release/vX.Y.0` branch

**Guidelines**:

- API is frozen (no API changes unless critical)
- Only bug fixes and documentation improvements
- External testers and early adopters can use
- Skip if no issues found within 1 week
- If no new release needed after 1 month, advance to RC

**Example Timeline**:

```
Week 5: 1.2.0b1 - API frozen, external testing begins
Week 6: 1.2.0b2 - Critical bug fixes
Week 7: 1.2.0b3 - Edge case fixes
Week 8: Ready for RC phase
```

#### Phase 4: Release Candidate (rc)

**Version Format**: `X.Y.0rcN` (e.g., `1.2.0rc1`, `1.2.0rc2`, `1.2.0rc3`)

**Purpose**: Final validation, production readiness verification

**Characteristics**:

- **Target release count**: ~3 releases (ideally 1-2)
- **Release interval**: ~1 week between releases
- **Maximum phase duration**: 1 month
- **Focus**: Final validation, critical bug fixes only
- **Stability**: Production-ready quality
- **Branch**: Releases from `release/vX.Y.0` branch

**Guidelines**:

- Only critical bug fixes (security, data loss, crashes)
- No feature changes, no API changes
- Should be identical to final release if no issues found
- Skip if RC1 passes all validation
- If no critical issues after 1 month, release as final

**Example Timeline**:

```
Week 9:  1.2.0rc1 - Release candidate for final validation
Week 10: 1.2.0rc2 - Critical security fix (if needed)
Week 11: 1.2.0rc3 - Final validation (if needed)
Week 12: Ready for final release
```

#### Phase 5: Final Release

**Version Format**: `X.Y.0` (e.g., `1.2.0`)

**Purpose**: Production release

**Characteristics**:

- **No suffix**: Clean version number
- **Focus**: Production deployment
- **Stability**: Production-ready
- **Support**: Full support begins

**Guidelines**:

- Tag with version number
- Publish to PyPI
- Update documentation
- Announce release
- Begin support lifecycle

### Phase Transition Rules

**Skip Rules**:

1. **Skip intermediate releases**: If no bugs found during 1-week interval, do not release
2. **Skip entire phase**: If no bugs found after 1 month in a phase, advance to next phase
3. **Direct advancement**: Can advance earlier if highly confident (e.g., alpha1 → beta1)

**Mandatory Delays**:

- Minimum 1 week between phase transitions (to allow for testing)
- Exception: Critical security issues may fast-track

**Example Fast-Track**:

```
1.2.0.dev4 → 1.2.0a1 (1 week) → 1.2.0b1 (1 week, a2/a3 skipped) 
→ 1.2.0rc1 (1 week, b2/b3 skipped) → 1.2.0 (1 week, rc2/rc3 skipped)
Total: 4 weeks minimum fast-track
```

**Example Full Cycle**:

```
1.2.0.dev1-4 (2 weeks) → 1.2.0a1-3 (3 weeks) → 1.2.0b1-3 (3 weeks) 
→ 1.2.0rc1-3 (3 weeks) → 1.2.0
Total: 11 weeks full cycle
```

## 2. Branching and Release Strategy

### Branch Structure

**Main Branch** (`main`):

- **Purpose**: Current production-ready state
- **Protection**: Required reviews, all CI checks must pass
- **Merge Strategy**: Squash and merge for features, rebase for hotfixes
- **Source of Truth**: Always represents the latest acceptable release state
- **Continuous Integration**: Must pass all tests at all times

**Pre-release Version Branches** (`release/vX.Y.Z[.devN|aN|bN|rcN]`):

- **Purpose**: Staging ground for specific version development
- **Creation**: Branched from `main` when starting new version development
- **Naming**: Uses full version number including pre-release suffix with `v` prefix
- **Lifecycle**: From dev phase through to final release
- **Examples**:
  - `release/v1.2.0.dev1` - Development branch
  - `release/v1.2.0` - Unified branch for alpha/beta/rc/final (reused across phases)

**Development Branches** (from pre-release branch):

- **Feature Branches**: `feature/{ticket-number}-{description}` or `feature/{description}`
- **Bug Fix Branches**: `fix/{ticket-number}-{description}` or `bugfix/{description}`
- **Documentation Branches**: `docs/{description}`
- **Test Branches**: `test/{description}`

**Hotfix Branches** (`hotfix/{ticket-number}-{description}` or `hotfix/{version}`):

- **Purpose**: Critical fixes to production releases
- **Source**: Branched from `main` or production tag
- **Target**: Merge back to `main` and active `release/` branches
- **Fast-tracked**: Emergency review and merge process

### Feature Branch Management

#### Creating Feature Branches

**Best Practices**:

- **Branch early, merge often**: Create feature branch as soon as work begins
- **Keep branches focused**: One feature/fix per branch
- **Small, incremental changes**: Easier to review and less conflict-prone
- **Regular synchronization**: Sync with pre-release branch frequently
- **Push early for CI feedback**: Get automated test results quickly

**Creation Process**:

```bash
# 1. Ensure pre-release branch is up to date
git checkout release/v1.2.0.dev1
git pull origin release/v1.2.0.dev1

# 2. Create focused feature branch
git checkout -b feature/ar-123-recursive-cte

# 3. Work in small, logical commits
# ... make changes ...
git add -p  # Stage changes selectively
git commit -m "feat(query): add recursive CTE parser"

# 4. Push early for visibility and CI feedback
git push origin feature/ar-123-recursive-cte

# 5. Create draft PR immediately for CI validation
# - Navigate to GitHub
# - Create draft PR to release/v1.2.0.dev1
# - CI runs automatically
# - Monitor CI results while developing
```

**CI-Driven Development**:

```bash
# Check CI status after push
# GitHub UI shows: ✓ or ✗ for each check

# If CI fails:
# 1. Review failure logs in GitHub Actions
# 2. Fix locally
git add .
git commit -m "fix: address test failure in CI"
git push  # Triggers new CI run

# 3. Wait for green checkmark before requesting review
```

#### Keeping Feature Branches Current

**Scenario 1: Another feature merged, your branch is behind**

```bash
# Your feature branch: feature/ar-123-recursive-cte
# Another feature was merged: feature/ar-124-window-functions

# Option A: Rebase (preferred for clean history)
git checkout feature/ar-123-recursive-cte
git fetch origin
git rebase origin/release/v1.2.0.dev1

# Resolve conflicts if any
# ... fix conflicts ...
git add .
git rebase --continue

# Force push (since history was rewritten)
git push origin feature/ar-123-recursive-cte --force-with-lease

# Option B: Merge (preserves all history)
git checkout feature/ar-123-recursive-cte
git fetch origin
git merge origin/release/v1.2.0.dev1

# Resolve conflicts if any
# ... fix conflicts ...
git add .
git commit -m "merge: sync with release/v1.2.0.dev1"

# Push normally
git push origin feature/ar-123-recursive-cte
```

**When to use Rebase vs Merge**:

- **Rebase**: For local branches not shared, or when you want linear history
- **Merge**: For shared branches, or when preserving exact history is important
- **Team Convention**: Agree on one approach per project

**Recommended Practice**: Rebase for feature branches, especially before final PR

#### Synchronization Schedule

**Frequency Guidelines**:

- **Daily**: If pre-release branch is very active (>5 commits/day)
- **Before PR**: Always sync immediately before creating pull request
- **After Major Merges**: When another large feature is merged
- **At Phase Transitions**: When moving from dev → alpha → beta → rc

**Synchronization Checklist**:

```bash
# 1. Commit your current work
git add .
git commit -m "wip: checkpoint before sync"

# 2. Fetch latest changes
git fetch origin

# 3. Check what changed in pre-release branch
git log HEAD..origin/release/v1.2.0.dev1 --oneline

# 4. Sync (rebase or merge)
git rebase origin/release/v1.2.0.dev1

# 5. Run tests locally
pytest tests/

# 6. Force push if rebased
git push origin feature/ar-123-recursive-cte --force-with-lease
```

#### Handling Abandoned Feature Branches

**Scenario: Feature branch will not be merged**

This can happen when:

- Feature is cancelled or postponed
- Alternative approach chosen
- Feature duplicates merged work

**Cleanup Process**:

```bash
# 1. Document why feature is abandoned
# Add comment to issue tracker explaining decision

# 2. Delete remote branch
git push origin --delete feature/ar-123-recursive-cte

# 3. Delete local branch
git checkout release/v1.2.0.dev1
git branch -D feature/ar-123-recursive-cte

# 4. Remove changelog fragment (if created)
rm changelog.d/123.added.md
git add changelog.d/
git commit -m "chore: remove changelog fragment for cancelled feature AR-123"
git push origin release/v1.2.0.dev1

# 5. Mark issue as "Won't Fix" or "Postponed" in issue tracker
```

**Preventing Fragment Conflicts**:

- Fragments are deleted along with abandoned branches
- No fragment enters CHANGELOG.md until release
- Only merged features contribute to release notes

**Communication**:

- Notify team via issue tracker
- Update project board/sprint planning
- Document decision for future reference

#### Long-Running Feature Branches

**Definition**: Feature branches that span multiple weeks or cross version boundaries

**Problems**:

- Accumulate merge conflicts
- Diverge significantly from pre-release branch
- Difficult to review when PR is finally created
- May block other work

**Strategies to Avoid**:

**1. Break Down Large Features**:

```bash
# Instead of one large branch:
feature/ar-123-full-graphql-support  # BAD: too large

# Break into smaller, mergeable pieces:
feature/ar-123-1-graphql-parser      # Part 1: Parser
feature/ar-123-2-graphql-resolver    # Part 2: Resolver
feature/ar-123-3-graphql-mutations   # Part 3: Mutations
```

**2. Feature Flags**:

```python
# Merge incomplete features behind flags
class QueryBuilder:
    def graphql_query(self, query: str):
        if not FEATURE_FLAGS.get('graphql_support'):
            raise NotImplementedError("GraphQL support not yet enabled")
        # Implementation...
```

**3. Regular Synchronization**:

```bash
# Set calendar reminder to sync every 3 days
git fetch origin
git rebase origin/release/v1.2.0.dev1
```

**4. Progressive PRs**:

```bash
# Create draft PR early for visibility and feedback
# Update PR with each commit
# Request incremental reviews
```

**If Feature Crosses Version Boundary**:

```bash
# Scenario: Working on feature for 1.2.0, but 1.2.0 is released
# and work continues on 1.3.0

# Option A: Rebase onto new version's pre-release branch
git checkout feature/ar-123-recursive-cte
git rebase --onto release/v1.3.0.dev1 release/v1.2.0.dev1

# Option B: Complete for 1.2.1 as bug fix if critical
# Convert to hotfix branch

# Option C: Postpone to next minor version
# Continue on 1.3.0 pre-release branch
```

#### Multiple Developers on Same Feature

**Scenario**: Large feature requires multiple developers

**Recommended Approach**:

```bash
# 1. Create shared feature branch
git checkout release/v1.2.0.dev1
git checkout -b feature/ar-123-graphql-support
git push origin feature/ar-123-graphql-support

# 2. Each developer creates sub-branch
# Developer A:
git checkout feature/ar-123-graphql-support
git checkout -b feature/ar-123-parser-alice

# Developer B:
git checkout feature/ar-123-graphql-support
git checkout -b feature/ar-123-resolver-bob

# 3. Merge sub-branches to shared feature branch
git checkout feature/ar-123-graphql-support
git merge feature/ar-123-parser-alice
git push origin feature/ar-123-graphql-support

# 4. Sync shared feature branch regularly
git fetch origin
git merge origin/release/v1.2.0.dev1

# 5. Finally merge shared feature branch to pre-release
git checkout release/v1.2.0.dev1
git merge --squash feature/ar-123-graphql-support
git commit -m "feat: add GraphQL support (#123)"
```

**Branch Hierarchy**:

```
release/v1.2.0.dev1
    └── feature/ar-123-graphql-support (shared)
        ├── feature/ar-123-parser-alice (individual)
        ├── feature/ar-123-resolver-bob (individual)
        └── feature/ar-123-mutations-charlie (individual)
```

#### Branch Lifecycle Best Practices

**General Guidelines**:

1. **Short-lived branches**: Aim for <1 week from creation to merge
2. **Focused scope**: Single responsibility per branch
3. **Regular updates**: Sync with pre-release branch at least 2x/week
4. **Early PRs**: Create draft PR within 24 hours of branch creation
5. **Clean history**: Squash trivial commits before final PR
6. **Delete after merge**: Remove branches immediately after merging
7. **Changelog fragments**: Create early, delete if branch abandoned

**Commit Frequency**:

- **Local commits**: As often as needed (can be messy)
- **Push commits**: When logical unit is complete
- **PR commits**: Squashed into logical story before merge

**Communication**:

- **Branch name**: Should clearly indicate purpose
- **WIP commits**: Use "wip:" prefix for work-in-progress
- **Blockers**: Label issues when blocked by other work
- **Status updates**: Comment on issue tracker regularly

### Pre-release Branch Workflow

#### Creating Pre-release Version Branch

```bash
# 1. Ensure main is up to date
git checkout main
git pull origin main

# 2. Create pre-release branch for new version (dev phase)
git checkout -b release/v1.2.0.dev1

# 3. First commit: Bump version number
# Edit pyproject.toml to update the `version` property
# version = "1.2.0.dev1"

git add pyproject.toml
git commit -m "chore: bump version to 1.2.0.dev1"
git push origin release/v1.2.0.dev1
```

#### Development Branch Workflow

```bash
# Developer working on feature
# 1. Create feature branch from pre-release branch
git checkout release/v1.2.0.dev1
git pull origin release/v1.2.0.dev1
git checkout -b feature/ar-123-recursive-cte

# 2. Develop feature
# ... make changes ...
git add .
git commit -m "feat: implement recursive CTE support"

# 3. Create changelog fragment
cat > changelog.d/123.added.md << 'EOF'
Added support for recursive CTEs in query builder, enabling hierarchical data queries.
EOF
git add changelog.d/123.added.md
git commit -m "docs: add changelog fragment for AR-123"

# 4. Push and create pull request to pre-release branch
git push origin feature/ar-123-recursive-cte
# Create PR: feature/ar-123-recursive-cte → release/v1.2.0.dev1
```

#### Merging Development Branches

```bash
# After PR approval
# Merge feature into pre-release branch
git checkout release/v1.2.0.dev1
git pull origin release/v1.2.0.dev1
git merge --squash feature/ar-123-recursive-cte
git commit -m "feat: implement recursive CTE support (#123)

Changelog fragment included."
git push origin release/v1.2.0.dev1

# After merge, verify CI passes on target branch
# Navigate to GitHub Actions for release/v1.2.0.dev1
# Ensure all checks are green before proceeding

# Delete merged branch
git push origin --delete feature/ar-123-recursive-cte
git branch -D feature/ar-123-recursive-cte
```

#### Phase Transitions

**Dev to Alpha Transition**:

```bash
# Rename branch or create new alpha branch
git checkout release/v1.2.0.dev4
git pull origin release/v1.2.0.dev4

# Create unified release branch (will be reused for all phases)
git checkout -b release/v1.2.0
git push origin release/v1.2.0

# Bump version to alpha
__version__ = "1.2.0a1"
git add src/rhosocial/activerecord/__init__.py
git commit -m "chore: bump version to 1.2.0a1 (alpha phase)"
git push origin release/v1.2.0

# Delete dev branch (optional)
git push origin --delete release/v1.2.0.dev4
```

**Alpha/Beta/RC Transitions** (same branch reused):

```bash
# Continue using release/v1.2.0 branch
git checkout release/v1.2.0
git pull origin release/v1.2.0

# Bump version within same branch
# Alpha to Beta:
__version__ = "1.2.0b1"

# Beta to RC:
__version__ = "1.2.0rc1"

# RC to Final:
__version__ = "1.2.0"

git add src/rhosocial/activerecord/__init__.py
git commit -m "chore: bump version to 1.2.0b1 (beta phase)"
git push origin release/v1.2.0
```

#### Merging to Main

```bash
# When ready for final release
git checkout main
git pull origin main

# Build changelog (Towncrier)
git checkout release/v1.2.0
towncrier build --version 1.2.0 --yes

# Commit changelog
git add CHANGELOG.md changelog.d/
git commit -m "docs: update CHANGELOG for 1.2.0"
git push origin release/v1.2.0

# **Wait for CI to pass before merging**
# Check GitHub Actions status: all checks must be green

# Create merge commit to preserve release branch history
git checkout main
git merge --no-ff release/v1.2.0

# **CI runs again after merge to main**
git push origin main

# **Only tag and publish if CI passes on main**
# Check GitHub Actions for main branch

# Tag the release
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin v1.2.0

# CI runs on tag (for release verification)

# Keep release branch for potential patches
# Or delete if no longer needed
git push origin --delete release/v1.2.0  # Optional
```

### Branch Protection Rules

**Linear History Requirement (All Branches)**:

- **CRITICAL**: All branches MUST maintain linear history - no merge commits, no forks
- Applies to `main`, `release/*`, and all development branches
- Applies equally to core team and external contributors
- Developers MUST manually sync with upstream before pushing
- DO NOT rely on CI auto-merge features

**Commit Strategy**:

- **Squash related commits**: Multiple commits for same purpose MUST be squashed into one
- Keep history clean and reviewable
- Each commit should represent one logical change
- Clear commit messages that explain the "why"
- Avoid confusing reviewers with messy commit history

**CI Requirements (All Protected Branches)**:

- **MANDATORY**: All status checks must pass before merge
- **No exceptions**: Even administrators must wait for CI (except documented emergencies)
- **Automatic enforcement**: GitHub prevents merge if CI fails

**main branch**:

- Require pull request reviews (minimum 1 approval)
- **Require status checks to pass**:
  - `test` (Python 3.11-3.14 x Firebird 5/6-snapshot matrix)
- **Require branches to be up to date before merge**
- **Require linear history** (no merge commits)
- Include administrators in restrictions
- No force pushes allowed
- No deletions allowed
- Enforce squash and merge for feature branches
- Enforce rebase for hotfixes to maintain linearity

**release/v* branches**:

- Require pull request reviews for merges from feature branches
- **Require status checks to pass**:
  - All tests from main branch requirements
- **Require linear history** (no merge commits)
- Require branches to be up to date before merge
- **Allow maintainers to bypass ONLY for**:
  - Version bump commits
  - Changelog builds (towncrier)
  - Documentation-only updates
- No force pushes allowed
- Enforce squash and merge for development branches

**Development Best Practices**:

```bash
# Before starting work - sync with upstream
git checkout main
git pull origin main
git checkout your-branch
git rebase main

# Before creating PR - ensure up to date
git fetch origin
git rebase origin/main

# Squash multiple WIP commits
git rebase -i HEAD~3  # Interactive rebase last 3 commits
# Mark commits as 'squash' or 'fixup' in editor

# Keep your branch updated during development
git fetch origin
git rebase origin/main  # NOT merge!
```

**Why Linear History Matters**:

- **Clean audit trail**: Easy to understand what changed and why
- **Simplified debugging**: `git bisect` works reliably
- **Clear code review**: Reviewers see logical changes, not noise
- **Easy rollback**: Simple to revert entire features
- **Professional quality**: Industry standard for serious projects

### Development Workflow Example

Complete workflow for developing version 1.2.0:

```bash
# Week 1: Start development phase
git checkout main
git pull origin main
git checkout -b release/v1.2.0.dev1
# Bump version to 1.2.0.dev1
git push origin release/v1.2.0.dev1

# Developer creates feature branch
git checkout release/v1.2.0.dev1
git checkout -b feature/ar-123-recursive-cte
# ... develop feature ...
# ... create changelog fragment ...
git push origin feature/ar-123-recursive-cte
# Create PR → release/v1.2.0.dev1

# Week 2: More dev releases as needed
# Bump to 1.2.0.dev2, dev3, dev4...

# Week 3: Transition to alpha
git checkout release/v1.2.0.dev4
git checkout -b release/v1.2.0
# Bump version to 1.2.0a1
git push origin release/v1.2.0

# Weeks 4-6: Alpha testing and bug fixes
# Fix branches → release/v1.2.0
# Bump to 1.2.0a2, a3 as needed

# Weeks 7-9: Beta testing
# Bump to 1.2.0b1, b2, b3 as needed

# Weeks 10-12: Release candidates
# Bump to 1.2.0rc1, rc2, rc3 as needed

# Week 13: Final release
git checkout main
# Build changelog
git checkout release/v1.2.0
towncrier build --version 1.2.0 --yes
git add CHANGELOG.md changelog.d/
git commit -m "docs: update CHANGELOG for 1.2.0"
git push origin release/v1.2.0

# Merge to main
git checkout main
git merge --no-ff release/v1.2.0
# Bump version to 1.2.0 (final)
git tag -a v1.2.0 -m "Release 1.2.0"
git push origin main --tags
```

### Hotfix Workflow

For critical production issues:

```bash
# Create hotfix from main
git checkout main
git pull origin main
git checkout -b hotfix/ar-999-critical-fix

# Implement fix
# ... make changes ...
git commit -m "fix: critical security issue (AR-999)"

# Create changelog fragment
cat > changelog.d/999.security.md << 'EOF'
**SECURITY**: Fixed SQL injection vulnerability in parameterized queries. CVE-2024-XXXXX.
EOF
git add changelog.d/999.security.md
git commit -m "docs: add security changelog fragment"

# Create PR to main
git push origin hotfix/ar-999-critical-fix
# Fast-track review and merge

# After merge to main, also merge to active release branches
git checkout release/v1.3.0  # If in development
git merge main  # Or cherry-pick specific commits
```

## 3. Continuous Integration Strategy

### 3.1 Overview

All critical branches MUST have continuous integration enabled to ensure code quality and prevent regressions. CI checks run automatically on:

- Direct commits to protected branches
- Pull requests to protected branches
- Release candidate builds

**Purpose**:
- Catch bugs before merge
- Verify cross-version compatibility
- Ensure code coverage standards
- Validate documentation builds
- Enforce code quality standards

### 3.2 Monitored Branches

**Primary Branches**:
- `main` - Production-ready code
- `release/v**` - All pre-release versions (dev, alpha, beta, rc)
- `maint/**` - Maintenance branches for LTS versions

**Development Branches** (indirect monitoring):
- Feature, bugfix, and hotfix branches tested via PRs to target branches

### 3.3 CI Pipeline Configuration

#### Test Matrix

All commits and PRs must pass tests across:

**Python Versions**:
- 3.11, 3.12, 3.13, 3.14 (latest stable)

**Test Categories**:
- Unit tests (local backend tests)
- Integration tests (with testsuite)
- Coverage analysis (minimum 90% for new code)

**Test Execution**:
- Retry flaky tests up to 3 times
- 1-second delay between retries
- Parallel execution where possible

#### Example Workflow Configuration

See `.github/workflows/test.yml` for the complete configuration. Key features:

```yaml
on:
  push:
    branches:
      - main
      - 'release/v**'
      - 'maint/**'
  pull_request:
    branches:
      - main
      - 'release/v**'
      - 'maint/**'
```

**Job Structure**:

1. **test**: Python 3.11-3.14 against Firebird 5 and 6-snapshot (4-job matrix)
2. **test-with-coverage**: Python 3.14 with full coverage reporting (Firebird 6-snapshot)

### 3.4 CI Check Requirements

#### For All Branches

**Mandatory Checks**:
- [ ] All tests pass across Python 3.11-3.14
- [ ] Code coverage ≥90% for modified files
- [ ] No regressions in existing tests
- [ ] Documentation builds successfully (if applicable)

**Pre-release Specific**:
- [ ] Testsuite compatibility tests pass
- [ ] Backend capability tests pass
- [ ] Performance benchmarks show no >5% regression (if applicable)

#### For Pull Requests

**Before Merge**:
1. CI status must be green (all checks passed)
2. Minimum 1 approving review
3. Branch must be up-to-date with target
4. No merge conflicts

**Handling CI Failures**:

```bash
# If CI fails on your branch
git checkout feature/ar-123-your-feature

# 1. Investigate failure in CI logs
# 2. Fix the issue locally
git add .
git commit -m "fix: address CI test failure"

# 3. Push and wait for re-run
git push origin feature/ar-123-your-feature

# CI automatically re-runs on push
```

### 3.5 Branch Protection with CI

Update branch protection rules to enforce CI:

**main branch**:
```
Protection Rules:
✓ Require pull request reviews (1 approval)
✓ Require status checks to pass before merging:
  - test (Python 3.11-3.14 x Firebird matrix)
  - test-with-coverage (Python 3.14)
✓ Require branches to be up to date
✓ Require linear history
✓ Include administrators
```

**release/v* branches**:
```
Protection Rules:
✓ Require pull request reviews (1 approval for features)
✓ Require status checks to pass:
  - test (Python 3.11-3.14 x Firebird matrix)
  - test-with-coverage (Python 3.14)
✓ Require linear history
⚠ Allow maintainers to bypass for version bumps only
```

**maint/* branches**:
```
Protection Rules:
✓ Require pull request reviews (1 approval)
✓ Require status checks to pass:
  - test (Python 3.11-3.14 x Firebird matrix)
  - test-with-coverage (Python 3.14)
✓ Require linear history
✓ Include administrators
```

### 3.6 CI in Development Workflow

#### Feature Development Flow

```bash
# 1. Create feature branch
git checkout release/v1.2.0.dev1
git checkout -b feature/ar-123-new-feature

# 2. Develop and commit
# ... make changes ...
git commit -m "feat: implement new feature"

# 3. Push early for CI feedback
git push origin feature/ar-123-new-feature

# 4. Create draft PR immediately
# - CI runs automatically on PR creation
# - Get early feedback on test failures

# 5. Iterate based on CI results
# - Fix any failing tests
# - Maintain >90% coverage
# - Address linting issues

# 6. Mark PR ready when CI is green
# - All checks passed
# - Ready for human review
```

#### Pre-release Version Flow

```bash
# CI runs on every commit to release branch
git checkout release/v1.2.0
git pull origin release/v1.2.0

# Version bump triggers CI
__version__ = "1.2.0a1"
git commit -m "chore: bump version to 1.2.0a1"
git push origin release/v1.2.0

# CI verifies:
# - All tests still pass with new version
# - Documentation builds correctly
# - Package can be built

# Only proceed to next phase if CI is green
```

### 3.7 Fast-tracking Hotfixes

Security and critical hotfixes MAY bypass some CI checks with approval:

```bash
# Create security hotfix
git checkout v1.2.0
git checkout -b hotfix/ar-999-security

# Implement fix with tests
git commit -m "security: fix critical vulnerability"

# Create URGENT PR
git push origin hotfix/ar-999-security

# Fast-track options:
# 1. Full CI (recommended): Wait for all checks
# 2. Partial CI (urgent): Require only critical tests
# 3. Post-merge CI (emergency): Merge with admin override, verify after
```

**Emergency Override Process**:
- Requires 2 maintainer approvals
- Document reason in PR
- Schedule immediate follow-up CI run after merge
- Revert if post-merge CI fails

### 3.8 Monitoring CI Health

**Regular Maintenance**:
- Review CI logs weekly for flaky tests
- Update test timeouts if needed
- Monitor CI execution time (target <10 minutes)
- Keep Python versions current

**Handling Flaky Tests**:
```yaml
# Tests configured with retry logic
- name: Run tests with retries
  run: |
    export PYTHONPATH=src
    pytest tests/ --reruns 3 --reruns-delay 1
```

**CI Performance Optimization**:
- Use caching for dependencies
- Parallelize test execution where possible
- Run expensive tests only on main/release branches

### 3.9 Changelog Fragment Validation

Ensure all PRs include appropriate changelog fragments unless explicitly exempted.

#### Workflow Configuration

See `.github/workflows/changelog-check.yml`:

```yaml
name: Changelog Fragment Check

on:
  pull_request:
    branches: 
      - main
      - 'release/v**'
      - 'maint/**'

jobs:
  check-fragment:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
      
      - name: Check for changelog fragment
        run: |
          # Get changed files
          CHANGED_FILES=$(git diff --name-only origin/${{ github.base_ref }}...${{ github.head_ref }})
          
          # Check if any changelog fragment was added
          if echo "$CHANGED_FILES" | grep -q "^changelog.d/[0-9].*\.md$"; then
            echo "✓ Changelog fragment found"
            exit 0
          fi
          
          # Check if this is an internal change (exempt from fragment requirement)
          if echo "$CHANGED_FILES" | grep -qE "^(tests/|docs/|\.github/)"; then
            echo "✓ Internal change, fragment not required"
            exit 0
          fi
          
          # Check if PR is marked as trivial
          if [[ "${{ github.event.pull_request.title }}" =~ \[trivial\] ]]; then
            echo "✓ PR marked as trivial, fragment not required"
            exit 0
          fi
          
          echo "✗ Missing changelog fragment"
          echo "Please add a changelog fragment in changelog.d/"
          echo "Example: changelog.d/${{ github.event.number }}.fixed.md"
          exit 1
```

**Fragment Exemptions**:

PRs are exempt from changelog fragments if:
- Only changes to `tests/`, `docs/`, or `.github/` directories
- PR title contains `[trivial]` marker
- PR explicitly marked with `no-changelog-needed` label (manual override)

### 3.10 Complete CI Workflow Example

**Scenario**: Developer adding a new feature to version 1.2.0

```bash
# Day 1: Start feature development
git checkout release/v1.2.0.dev1
git checkout -b feature/ar-456-window-functions

# Make initial changes
git commit -m "feat: add window function parser"

# Push immediately
git push origin feature/ar-456-window-functions

# Create draft PR on GitHub
# → CI runs automatically (5-10 minutes)
# → Check GitHub Actions tab

# Day 2: CI found an issue on Python 3.14 / Firebird 6-snapshot
# Review logs in GitHub Actions
# Fix the issue locally
git commit -m "fix: resolve Firebird 6 compatibility issue"
git push

# → CI re-runs automatically
# → All checks pass ✓

# Day 3: Request review
# Mark PR as "Ready for review" (no longer draft)
# Reviewer approves
# → Merge button enabled only because CI is green

# Merge via GitHub UI (squash and merge)
# → CI runs on release/v1.2.0.dev1 after merge
# → Confirms merge didn't break anything

# Day 10: Ready for alpha release
git checkout release/v1.2.0.dev1
git checkout -b release/v1.2.0

__version__ = "1.2.0a1"
git commit -m "chore: bump version to 1.2.0a1"
git push origin release/v1.2.0

# → CI runs on release branch
# → Wait for green before announcing alpha

# Final release day
git checkout release/v1.2.0
towncrier build --version 1.2.0 --yes
git commit -m "docs: update CHANGELOG for 1.2.0"
git push origin release/v1.2.0

# → CI runs, verifies final state
# → Only merge to main if CI passes

git checkout main
git merge --no-ff release/v1.2.0
git push origin main

# → CI runs on main (final verification)
# → Tag only if CI passes

git tag -a v1.2.0 -m "Release 1.2.0"
git push origin v1.2.0
```

**Key Points**:
- CI runs at EVERY significant step
- Never proceed if CI fails
- Green checkmarks required before:
  - Marking PR ready for review
  - Merging PRs
  - Announcing pre-releases
  - Tagging final releases
- Emergency override requires documented justification

## 4. Git Commit Message Standards

### Commit Message Format

All commit messages MUST follow the Conventional Commits specification with the following structure:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Examples**:

```
feat: add recursive CTE support
feat(query): implement window functions for Firebird backend
fix: resolve SQL injection vulnerability in parameterized queries
docs: update installation guide for Python 3.14
chore: bump version to 1.2.0
```

### Complex Commit Messages via File

When dealing with complex commit messages or messages containing special characters that may conflict with shell escaping (such as backticks, quotes, or regular expression patterns), you SHOULD write the commit message to a temporary file in `.claude/tmp/` and use the file option with git commit.

**When to use this approach:**

-   Commit message contains complex formatting or code examples
-   Message includes special shell characters (`$`, `` ` ``, `"`, `'`, `\`, `|`, `>`, `<`)
-   Multi-line descriptions that are difficult to format inline
-   Regular expressions or JSON examples in the commit message
-   Any situation where command-line escaping becomes error-prone

**Workflow:**

```bash
# 1. Create a commit message file
cat > .claude/tmp/my-commit-message.txt << 'EOF'
feat(query): add support for regex operators in WHERE clauses

Implement regular expression matching operators:
- ~ (case-sensitive match)
- ~* (case-insensitive match)
- !~ (case-sensitive non-match)
- !~* (case-insensitive non-match)

Example usage:
  User.where(name__regex__match=r'^[A-Z][a-z]+$')
  Post.where(content__regex__imatch=r'python|javascript')

Note: Backend support varies. PostgreSQL has full support,
while SQLite requires the REGEXP extension.

Closes AR-789
EOF

# 2. Commit using the file
git commit -F .claude/tmp/my-commit-message.txt

# 3. Clean up (optional)
rm .claude/tmp/my-commit-message.txt
```

**Best Practices:**

-   Use descriptive filenames (e.g., `ar-123-fix-commit.txt`)
-   Delete temporary files after use (they are gitignored)
-   Template files are available in `.claude/tmp/`:
    -   `commit-message-template.txt` - Basic template
    -   `commit-message-example-complex.txt` - Complex example with special characters

**Benefits:**

-   No shell escaping issues with special characters
-   Easier to edit and review multi-line messages
-   Better handling of code examples and regex patterns
-   Can use your preferred editor to compose messages

### Commit Message Language

-   **Default Language**: Commit messages MUST primarily be written in English.
-   **Non-English Messages**: If a commit message is written in a language other than English (e.g., for specific local context or internal project branches), it MUST be accompanied by an English translation in the commit body. The reason for using a non-English message should also be briefly explained in the commit body (e.g., "Reason: Internal project, localized message for team's convenience.").

### Commit Types

| Type | Purpose | Example |
|------|---------|---------|
| `feat` | New feature | `feat: add JSON field type support` |
| `fix` | Bug fix | `fix: resolve connection leak in Firebird backend` |
| `docs` | Documentation only | `docs: add CTE usage examples` |
| `style` | Code style/formatting | `style: apply black formatting` |
| `refactor` | Code restructuring | `refactor: simplify query builder logic` |
| `perf` | Performance improvement | `perf: optimize bulk insert for Postgres` |
| `test` | Add or modify tests | `test: add coverage for recursive CTE` |
| `chore` | Maintenance tasks | `chore: update dependencies` |
| `ci` | CI/CD changes | `ci: add Python 3.14 to test matrix` |
| `build` | Build system changes | `build: configure pyproject.toml for namespace packages` |
| `revert` | Revert previous commit | `revert: undo "feat: add feature X"` |

### Scope Guidelines

**Optional but recommended** for multi-component projects:
See the [.gemini/feature_points.md](.gemini/feature_points.md) document for a complete list and description of valid scopes.

**Core Package Scopes**:

- `query`: Query building and execution
- `backend`: Backend abstraction layer
- `field`: Field types and validation
- `relation`: Relationship management
- `event`: Event hooks system
- `mixin`: Mixin functionality

**Backend Package Scopes**:

- `mysql`: MySQL-specific
- `postgres`: Postgres-specific
- `sqlite`: SQLite-specific
- `firebird`: Firebird-specific
- `dialect`: SQL dialect handling
- Separate multiple scopes with commas: `feat(query,backend): add new query optimization feature`
- Scopes can be further subdivided for more detail, e.g., `backend-cli` for backend command-line tools or `backend-adapters` for type adapters.

**Testsuite Scopes**:

- `feature`: Feature tests
- `realworld`: Real-world scenarios
- `benchmark`: Performance tests
- `provider`: Provider interface

### Description Guidelines

**DO**:

- Use imperative mood: "add" not "added" or "adds"
- Start with lowercase letter
- Keep under 72 characters
- Be specific and descriptive
- Reference issue numbers when applicable

**DON'T**:

- End with period
- Use vague descriptions like "fix bug" or "update code"
- Include implementation details (save for body)

**Examples**:

```
✅ Good:
feat: implement optimistic locking for concurrent updates
fix: prevent duplicate records in bulk insert (AR-456)
docs: clarify transaction isolation level usage

❌ Bad:
feat: Added new feature.
fix: fixed bug
docs: Updates
```

### Commit Body

**When to include**:

- Complex changes requiring explanation
- Breaking changes
- Migration steps needed
- Design decisions context

**Format**:

- Separate from description with blank line
- Wrap at 72 characters
- Use bullet points for multiple items
- Explain "why" not "what" (code shows "what")

**Example**:

```
feat: add connection pooling to backend interface

Connection pooling significantly improves performance for
high-traffic applications by reusing database connections.

- Default pool size: 5 connections
- Configurable via ConnectionConfig
- Thread-safe implementation
- Automatic cleanup on disconnect

Closes AR-123
```

### Commit Footer

**Breaking Changes**:

```
feat!: remove deprecated find_by_id method

BREAKING CHANGE: find_by_id() removed, use find(id=...) instead.

Migration:
- Old: User.find_by_id(123)
- New: User.find_one(123)
```

**Issue References**:

```
Fixes AR-456
Closes #789
Resolves AR-123, AR-124
See also AR-100
```

**Co-authorship**:

```
Co-authored-by: Name <email@example.com>
```

### Special Commit Messages

**Version Bumps**:

```
chore: bump version to 1.2.0
chore: bump version to 1.2.0a1 (alpha phase)
chore: bump version to 1.2.0 - SECURITY RELEASE
```

**Merge Commits** (when absolutely necessary):

```
Merge branch 'release/v1.2.0' into main

Release version 1.2.0 with following changes:
- Feature A
- Feature B
- Critical fix C
```

**Reverts**:

Although revert commits are allowed, they should rarely occur in practice. By maintaining good development habits on feature and bugfix branches:

- Keep linear commits throughout development
- Squash and fix issues before pushing
- Resolve problems locally using rebase or amend

Reversions typically only appear on protected branches (main, release/*, hotfix/*) when:
- A critical issue is discovered after merge
- Quick rollback with explicit history is needed

In most cases, if development branches follow good practices, reversions will not be necessary on main or release branches.

```
revert: undo "feat: add recursive CTE support"

This reverts commit a1b2c3d4.

Reason: Feature causes performance regression in Firebird 5.0.
Reopens AR-456.
```

### Security-Related Commits

**Format**:

```
security: fix SQL injection in query parameter handling

SECURITY: Critical vulnerability allowing SQL injection through
parameterized queries when using untrusted input.

CVE: CVE-2024-XXXXX (if applicable)
Severity: Critical
Impact: SQL injection in all query methods
Affected versions: 1.0.0 - 1.2.0

Fixed by properly escaping parameters before query execution.

Fixes AR-999
```

### Pre-commit Checklist

Before committing, verify:

- [ ] Commit type is correct
- [ ] Description is clear and under 72 characters
- [ ] Breaking changes are marked with `!` and explained
- [ ] Issue numbers referenced (if applicable)
- [ ] Multiple unrelated changes are split into separate commits
- [ ] Related changes are squashed into single commit
- [ ] Commit message follows imperative mood
- [ ] No sensitive information in message

### Commit History Examples

**Good History** (linear, clean):

```
* a1b2c3d feat: add window function support for Postgres
* b2c3d4e fix: resolve connection timeout in Firebird backend
* c3d4e5f docs: add examples for CTE usage
* d4e5f6g test: increase coverage for query builder
* e5f6g7h chore: bump version to 1.2.0
```

**Bad History** (messy, unclear):

```
* a1b2c3d Update code
* b2c3d4e Fix bug
* c3d4e5f WIP
* d4e5f6g Fix typo
* e5f6g7h Merge branch 'develop'
* f6g7h8i More fixes
```

### Tools and Automation

**Commit Message Template**:

```bash
# .gitmessage template
# <type>[optional scope]: <description>
#
# [optional body]
#
# [optional footer(s)]
#
# Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert
# Scope: query, backend, field, relation, event, mixin, etc.
# Description: imperative mood, lowercase, no period, <72 chars
#
# Body: explain "why" not "what", wrap at 72 chars
#
# Footer: Fixes AR-XXX, BREAKING CHANGE, Co-authored-by

# Configure git to use template:
# git config commit.template .gitmessage
```

**Commit Linting**:

```bash
# Install commitlint (optional but recommended)
npm install -g @commitlint/cli @commitlint/config-conventional

# .commitlintrc.json
{
  "extends": ["@commitlint/config-conventional"],
  "rules": {
    "type-enum": [
      2,
      "always",
      ["feat", "fix", "docs", "style", "refactor", "perf", "test", "chore", "ci", "build", "revert"]
    ],
    "subject-case": [2, "always", "lower-case"],
    "subject-full-stop": [2, "never", "."]
  }
}
```

**Pre-commit Hook Example**:

```bash
#!/bin/sh
# .git/hooks/commit-msg

# Check commit message format
if ! head -1 "$1" | grep -qE "^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)(\(.+?\))?: .{1,72}$"; then
    echo "ERROR: Commit message does not follow Conventional Commits format"
    echo "Format: <type>[optional scope]: <description>"
    echo "Example: feat: add recursive CTE support"
    exit 1
fi
```

## 5. Changelog Management with Towncrier

### Overview

We use [Towncrier](https://towncrier.readthedocs.io/) to manage our CHANGELOG.md. This ensures:

- **Fragment-based workflow**: Changes documented in separate files
- **Consistent format**: Automated generation with standard structure
- **Easy collaboration**: Multiple developers can work without conflicts
- **Abandoned features handled**: Fragments deleted with abandoned branches
- **Clean releases**: Changelog assembled only during release

### Installation and Setup

**Install Towncrier**:

```bash
pip install towncrier
```

**Configuration** (`pyproject.toml`):

```toml
[tool.towncrier]
package = "rhosocial.activerecord"
package_dir = "src"
filename = "CHANGELOG.md"
directory = "changelog.d"
title_format = "## [{version}] - {project_date}"
template = "changelog.d/template.md"
start_string = "<!-- towncrier release notes start -->\n"
underlines = ["", "", ""]
issue_format = "[#{issue}](https://github.com/rhosocial/python-activerecord/issues/{issue})"

[[tool.towncrier.type]]
directory = "security"
name = "Security"
showcontent = true

[[tool.towncrier.type]]
directory = "removed"
name = "Removed"
showcontent = true

[[tool.towncrier.type]]
directory = "deprecated"
name = "Deprecated"
showcontent = true

[[tool.towncrier.type]]
directory = "added"
name = "Added"
showcontent = true

[[tool.towncrier.type]]
directory = "changed"
name = "Changed"
showcontent = true

[[tool.towncrier.type]]
directory = "fixed"
name = "Fixed"
showcontent = true

[[tool.towncrier.type]]
directory = "performance"
name = "Performance"
showcontent = true

[[tool.towncrier.type]]
directory = "docs"
name = "Documentation"
showcontent = true

[[tool.towncrier.type]]
directory = "internal"
name = "Internal"
showcontent = true
```

### Fragment Directory Structure

```
changelog.d/
├── template.md           # Towncrier template
├── .gitkeep             # Keep directory in git
├── 123.added.md         # New feature fragment
├── 124.fixed.md         # Bug fix fragment
├── 125.security.md      # Security fix fragment
└── README.md            # Instructions for contributors
```

### Fragment Naming Convention

**Format**: `{issue_number}.{type}.md`

**Examples**:

- `123.added.md` - New feature from issue #123
- `456.fixed.md` - Bug fix from issue #456
- `789.security.md` - Security fix from issue #789
- `999+1000.changed.md` - Change affecting multiple issues

**Fragment Types**:

| Type | Usage |
|------|-------|
| `security` | Security vulnerability fixes (CVEs) |
| `removed` | Removed features or APIs (breaking changes) |
| `deprecated` | Deprecated features (will be removed) |
| `added` | New features and functionality |
| `changed` | Changes to existing functionality (non-breaking) |
| `fixed` | Bug fixes |
| `performance` | Performance improvements |
| `docs` | Documentation changes (significant only) |
| `internal` | Internal changes (refactoring, testing) |

### Creating Changelog Fragments

**During Development**:

Every PR SHOULD include a changelog fragment unless:

- The change is purely internal (refactoring without behavior change)
- The change is a trivial fix (typo in code comment)
- The PR is part of a larger feature (fragment added in final PR)

**Creating a Fragment**:

```bash
# After creating PR #123 for a new feature
cd changelog.d/

# Create fragment file
cat > 123.added.md << 'EOF'
Added support for recursive CTEs in query builder, enabling hierarchical data queries.
EOF

# Or use towncrier create (if available)
towncrier create 123.added.md --content "Added support for recursive CTEs."

# Commit fragment with your PR
git add changelog.d/123.added.md
git commit -m "feat: add recursive CTE support

Changelog fragment added."
```

**Fragment Content Guidelines**:

1. **Write in past tense**: "Added support for..." not "Add support for..."
2. **Be specific but concise**: Include what changed and why it matters
3. **Focus on user impact**: What can users do now that they couldn't before?
4. **Link related issues**: Use issue number in filename
5. **One change per fragment**: If multiple changes, create multiple fragments

**Good Examples**:

```markdown
<!-- 123.added.md -->
Added support for recursive CTEs in SQLite 3.8.3+, enabling hierarchical data queries like organizational charts and category trees.
```

```markdown
<!-- 456.fixed.md -->
Fixed memory leak in connection pool that occurred when connections were not properly released after query timeout.
```

```markdown
<!-- 789.security.md -->
**SECURITY**: Fixed SQL injection vulnerability in parameterized queries when using list parameters. CVE-2024-XXXXX.
```

**Bad Examples**:

```markdown
<!-- Bad: Too vague -->
Fixed bug in queries.
```

```markdown
<!-- Bad: Too technical, no user impact -->
Refactored QueryBuilder._build_where() method to use visitor pattern.
```

```markdown
<!-- Bad: Multiple unrelated changes -->
Added CTE support, fixed connection leak, updated documentation.
```

### Handling Abandoned Features

**Scenario**: Feature branch is abandoned and will not be merged

**Process**:

```bash
# 1. Branch with fragment exists
changelog.d/123.added.md  # Fragment for abandoned feature

# 2. Delete the branch
git push origin --delete feature/ar-123-recursive-cte

# 3. Remove the fragment from pre-release branch
git checkout release/v1.2.0.dev1
rm changelog.d/123.added.md
git add changelog.d/123.added.md
git commit -m "chore: remove changelog fragment for abandoned feature AR-123"
git push origin release/v1.2.0.dev1
```

**Key Point**: Since fragments are NOT in CHANGELOG.md yet, abandoned features simply have their fragments deleted and never appear in release notes.

### Building Changelog

**During Release**:

```bash
# 1. Check current fragments (preview)
towncrier build --draft --version 1.2.0

# 2. Review the output, ensure all fragments are present
# Verify no fragments for abandoned features remain

# 3. Build actual changelog (removes fragments)
towncrier build --version 1.2.0 --yes

# This command:
# - Reads all fragments from changelog.d/
# - Generates formatted changelog entries
# - Inserts them at top of CHANGELOG.md
# - Deletes the processed fragment files

# 4. Review CHANGELOG.md changes
git diff CHANGELOG.md

# 5. Commit changelog (this is the last commit before release tag)
git add CHANGELOG.md changelog.d/
git commit -m "docs: update CHANGELOG for 1.2.0"
git push origin release/v1.2.0
```

**Changelog Location**:

Towncrier inserts new release notes at the top of CHANGELOG.md, below the "towncrier release notes start" marker:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

<!-- towncrier release notes start -->

## [1.2.0] - 2024-10-29

### Security

- **SECURITY**: Fixed SQL injection vulnerability... ([#789](https://github.com/rhosocial/python-activerecord/issues/789))

### Added

- Added support for recursive CTEs... ([#123](https://github.com/rhosocial/python-activerecord/issues/123))

### Fixed

- Fixed memory leak in connection pool... ([#456](https://github.com/rhosocial/python-activerecord/issues/456))

## [1.1.0] - 2024-09-15

...
```

### Pre-release Changelog Builds

**Important**: Fragments remain separate until final release

```bash
# During alpha/beta/rc phases:
# - Fragments accumulate in changelog.d/
# - CHANGELOG.md is NOT modified
# - Only at final release are fragments compiled

# Preview what release notes will look like
towncrier build --draft --version 1.2.0a1

# Do NOT build changelog during pre-release phases
# Fragments stay in changelog.d/ until final release
```

### Integration with Release Process

**Pre-release Checklist Update**:

```markdown
**For All Packages**:
- [ ] All tests pass on CI
- [ ] **Changelog fragments reviewed** (towncrier build --draft)
- [ ] **CHANGELOG.md built** (towncrier build --version X.Y.Z --yes)
- [ ] Fragments removed after build
- [ ] Documentation updated and builds successfully
- [ ] Version number updated in `__init__.py`
- [ ] Git tag created with version number
- [ ] Release notes drafted
```

**Release Commit Sequence**:

```bash
# 1. Last pre-release commit is version bump
__version__ = "1.2.0rc3"
git commit -m "chore: bump version to 1.2.0rc3"

# 2. When ready for final release, build changelog
__version__ = "1.2.0"
git add src/rhosocial/activerecord/__init__.py
git commit -m "chore: bump version to 1.2.0 (final release)"

towncrier build --version 1.2.0 --yes
git add CHANGELOG.md changelog.d/
git commit -m "docs: update CHANGELOG for 1.2.0"

# 3. Merge to main and tag
git checkout main
git merge --no-ff release/v1.2.0
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin main v1.2.0
```

### Automated Checks

Add CI check to ensure PRs include changelog fragments (see section 3.9).

### Maintenance Branch Changelog

For maintenance branches (e.g., `maint/1.2.x`), changelog fragments are managed independently:

```bash
# When backporting to maint/1.2.x
git checkout maint/1.2.x
git checkout -b backport/1.2.x/ar-456-fix

# Add fragment to maintenance branch
cat > changelog.d/456.fixed.md << 'EOF'
Fixed query null handling issue in WHERE clauses (backported from 1.3.1).
EOF

git add changelog.d/456.fixed.md
git commit -m "fix: backport query null handling fix

(cherry picked from commit <hash>)"
```

**Building Changelog for Patch Release**:

```bash
# On maintenance branch (maint/1.2.x)
# After all backports are merged

# Build changelog for patch version
towncrier build --version 1.2.6 --yes

# Commit
git add CHANGELOG.md changelog.d/
git commit -m "docs: update CHANGELOG for 1.2.6"

# Tag
git tag -a v1.2.6 -m "Release v1.2.6"
git push origin maint/1.2.x v1.2.6
```

### Fragment Examples by Type

**Security**:

```markdown
<!-- 999.security.md -->
**SECURITY**: Fixed SQL injection vulnerability in query parameter handling. All users should upgrade immediately. CVE-2024-XXXXX.
```

**Breaking Change (Removed)**:

```markdown
<!-- 1001.removed.md -->
**BREAKING**: Removed deprecated `Model.find_by()` method. Use `Model.where()` instead. This method was deprecated in v1.1.0.
```

**Deprecation**:

```markdown
<!-- 1002.deprecated.md -->
Deprecated `QueryBuilder.filter()` method in favor of `QueryBuilder.where()`. The old method will be removed in v2.0.0.
```

**New Feature**:

```markdown
<!-- 1003.added.md -->
Added support for window functions (ROW_NUMBER, RANK, LAG, LEAD) in Postgres and SQLite 3.25+. See documentation for usage examples.
```

**Behavior Change**:

```markdown
<!-- 1004.changed.md -->
Changed default connection pool size from 5 to 10 for better concurrency. Override with `pool_size` configuration parameter.
```

**Bug Fix**:

```markdown
<!-- 1005.fixed.md -->
Fixed race condition in connection pool that could cause deadlocks under high concurrent load.
```

**Performance**:

```markdown
<!-- 1006.performance.md -->
Improved bulk insert performance by 3x through batched operations. Inserts of 1000+ records now use database-specific bulk insert syntax.
```

**Documentation** (significant only):

```markdown
<!-- 1007.docs.md -->
Added comprehensive guide for implementing custom type converters with examples for JSON, UUID, and encrypted fields.
```

### Contributor Guide

**For Contributors** (`changelog.d/README.md`):

```markdown
# Changelog Fragments

We use Towncrier to manage our changelog. Each significant change should have a corresponding fragment file.

## Creating a Fragment

1. **Filename**: `{issue_number}.{type}.md`
   - Example: `123.added.md`

2. **Types**:
   - `security` - Security fixes (always significant)
   - `removed` - Removed features (breaking changes)
   - `deprecated` - Deprecation notices
   - `added` - New features
   - `changed` - Behavior changes
   - `fixed` - Bug fixes
   - `performance` - Performance improvements
   - `docs` - Documentation (significant changes only)
   - `internal` - Internal changes (optional)

3. **Content**:
   - Write in past tense
   - Be specific but concise
   - Focus on user impact
   - One change per fragment

## Fragment Lifecycle

- **Created**: When feature/fix branch is created
- **Merged**: Fragment merges with the code
- **Compiled**: During final release (not pre-releases)
- **Deleted**: Automatically removed after compilation
- **Abandoned**: Manually deleted if feature is abandoned

## Good Examples

```markdown
<!-- 123.added.md -->
Added support for recursive CTEs in query builder, enabling hierarchical queries.
```

## Bad Examples

```markdown
<!-- 123.added.md -->
Added CTE.
```

## When to Skip

- Internal refactoring (no behavior change)
- Trivial fixes (typos in comments)
- Work-in-progress (fragment in final PR)

## If Feature is Abandoned

Simply delete the fragment file:

```bash
rm changelog.d/123.added.md
```

The fragment never enters CHANGELOG.md, so no cleanup needed there.

## Commands

```bash
# Preview changelog
towncrier build --draft --version X.Y.Z

# Build changelog (removes fragments)
towncrier build --version X.Y.Z --yes
```
```

## 6. Version Increment Guidelines

### Core Package (rhosocial-activerecord)

**MAJOR version** (X.0.0):
- Incompatible API changes
- Breaking changes to public interfaces
- Major architectural redesigns
- Pydantic major version upgrades
- Examples:
  - Changing `ActiveRecord.save()` signature
  - Removing deprecated methods
  - Restructuring module organization

**MINOR version** (1.X.0):
- New features in backward-compatible manner
- New field types or query methods
- Enhanced functionality
- Examples:
  - Adding new query builder methods
  - Introducing new mixin classes
  - Supporting new Python versions

**PATCH version** (1.0.X):
- Backward-compatible bug fixes
- Security patches
- Performance improvements
- Documentation updates
- Examples:
  - Fixing query generation bugs
  - Correcting type annotations
  - Updating docstrings

### Test Suite Package (rhosocial-activerecord-testsuite)

**Version Synchronization Strategy**:
- **MAJOR.MINOR** must match core package for API compatibility
- **PATCH** can be independent for test-specific fixes
- Version format: `{core_major}.{core_minor}.{testsuite_patch}`

**Examples**:
```python
Core: 1.2.0 → Testsuite: 1.2.0  # Initial release
Core: 1.2.0 → Testsuite: 1.2.1  # Test bug fix
Core: 1.2.1 → Testsuite: 1.2.1  # Core patch, no test changes
Core: 1.3.0 → Testsuite: 1.3.0  # New core features require new tests
```

### Backend Extension Packages (rhosocial-activerecord-{backend})

**Version Synchronization Rules**:

- **MAJOR** must be synchronized with core package
- **MINOR** can be independent for backend-specific features
- **PATCH** is independent for each backend's bug fixes

**Dependency Specification**:

```python
# In backend package's pyproject.toml
dependencies = [
    "rhosocial-activerecord>=1.2.0,<2.0.0",  # Compatible with 1.x
    "firebird-driver>=2.0.0",                 # Native driver only
]
```

## 7. Post-Release Operations

### Publishing Release

After merging release branch to main, complete the following operations:

```bash
# After merge to main and changelog build
git checkout main
git pull origin main

# Verify version is final (e.g., 1.2.0)
# Verify CHANGELOG.md is updated
# Verify changelog.d/ fragments are removed

# Tag should already be created during merge
# If not, create now:
git tag -a v1.2.0 -m "Release version 1.2.0

See CHANGELOG.md for full details."

# Push tag
git push origin v1.2.0

# Build and publish to PyPI
python -m build
python -m twine upload dist/rhosocial-activerecord-1.2.0*
```

### Update Documentation

```bash
# Update version in documentation
# Update compatibility matrix
# Publish documentation for new version
# Update "latest" documentation link
```

### Release Announcement

- CHANGELOG.md already updated (by Towncrier)
- Create GitHub Release with tag
- Announce on project channels
- Update project website/homepage

### Post-Release Branch Management

**Keep release branch temporarily**:

```bash
# Keep release/v1.2.0 branch for potential hotfixes
# Do NOT delete immediately
```

**When to delete**:

- After next MINOR/MAJOR release is stable
- After all supported PATCH versions are released
- Typically keep for 2-4 weeks post-release

## 8. Handling Post-Release Defects

### PATCH Version Releases (1.2.X)

**For bugs discovered after release**:

#### Scenario 1: Minor Bug (Non-Critical)

```bash
# Create bugfix branch from main (or from tag if main has moved on)
git checkout v1.2.0  # Or main if v1.2.0 is still HEAD
git checkout -b fix/ar-456-query-bug

# Fix the bug
# ... make changes ...
git commit -m "fix: resolve query null handling issue (AR-456)"

# Create changelog fragment
cat > changelog.d/456.fixed.md << 'EOF'
Fixed query null handling issue in WHERE clauses.
EOF
git add changelog.d/456.fixed.md
git commit -m "docs: add changelog fragment for AR-456"

# Push and create PR to main
git push origin fix/ar-456-query-bug
# Create PR → main

# After merge, prepare PATCH release
git checkout main
git pull origin main

# Bump version to 1.2.1
__version__ = "1.2.1"
git add src/rhosocial/activerecord/__init__.py
git commit -m "chore: bump version to 1.2.1"

# Build changelog
towncrier build --version 1.2.1 --yes
git add CHANGELOG.md changelog.d/
git commit -m "docs: update CHANGELOG for 1.2.1"
git push origin main

# Tag and release
git tag -a v1.2.1 -m "Release version 1.2.1 - Bug fixes"
git push origin v1.2.1
python -m build && python -m twine upload dist/*
```

#### Scenario 2: Multiple Bugs Accumulation

```bash
# Collect multiple bug fixes in main
# Each with its own changelog fragment

# When ready for PATCH release:
git checkout main
git pull origin main

# Bump to next PATCH version
__version__ = "1.2.2"
git commit -m "chore: bump version to 1.2.2"

# Build changelog (will include all accumulated fragments)
towncrier build --version 1.2.2 --yes
git add CHANGELOG.md changelog.d/
git commit -m "docs: update CHANGELOG for 1.2.2"

# Tag and publish
git tag -a v1.2.2 -m "Release version 1.2.2"
git push origin main --tags
python -m build && python -m twine upload dist/*
```

### Security Patch Releases

**For critical security issues**:

```bash
# Create hotfix branch from affected version tag
git checkout v1.2.0
git checkout -b hotfix/ar-999-security-fix

# Implement security fix
# ... make changes ...
git commit -m "security: fix SQL injection vulnerability (AR-999)

SECURITY: This fixes a critical SQL injection vulnerability
in query parameter handling.

CVE: CVE-2024-XXXXX (if applicable)
Severity: Critical
Impact: SQL injection in parameterized queries"

# Create security fragment
cat > changelog.d/999.security.md << 'EOF'
**SECURITY**: Fixed SQL injection vulnerability in query parameter handling. All users should upgrade immediately. CVE-2024-XXXXX.
EOF
git add changelog.d/999.security.md
git commit -m "docs: add security changelog fragment"

# Push and create URGENT PR
git push origin hotfix/ar-999-security-fix
# Fast-track review (within 24-72 hours)

# After merge to main
git checkout main
git pull origin main

# Immediate PATCH release
__version__ = "1.2.1"
git add src/rhosocial/activerecord/__init__.py
git commit -m "chore: bump version to 1.2.1 - SECURITY RELEASE"

# Build changelog
towncrier build --version 1.2.1 --yes
git add CHANGELOG.md changelog.d/
git commit -m "docs: SECURITY RELEASE - update CHANGELOG for 1.2.1"

# Tag with security note
git tag -a v1.2.1 -m "SECURITY RELEASE v1.2.1

Critical security fix for SQL injection vulnerability.
All users should upgrade immediately.

CVE: CVE-2024-XXXXX
See SECURITY.md and CHANGELOG.md for details."

git push origin main --tags

# Expedited release
python -m build && python -m twine upload dist/*

# Security advisory
# - Create GitHub Security Advisory
# - Email notification to users
# - Update security documentation
```

### PATCH Release Cadence

**Regular PATCH releases**:

- Collect bug fixes over 2-4 weeks
- Release when significant bugs accumulated
- Or release immediately for critical issues

**Emergency PATCH releases**:

- Security vulnerabilities: Within 24-72 hours
- Data loss bugs: Within 1 week
- Critical crashes: Within 1 week

**PATCH release checklist**:

- [ ] All bug fixes merged to main
- [ ] Changelog fragments present for all fixes
- [ ] Version number bumped
- [ ] CHANGELOG.md built with Towncrier
- [ ] Fragments removed after build
- [ ] Tests pass on CI
- [ ] Tag created and pushed
- [ ] Published to PyPI
- [ ] Documentation updated (if needed)
- [ ] Users notified (for security issues)

## 9. Multi-Version Support and Backporting

### Version Support Policy

**Support Tiers**:

1. **Latest Stable** (main branch):
   - Full feature development
   - All bug fixes
   - Security patches
   - Performance improvements

2. **LTS (Long-Term Support)** versions:
   - Selected MAJOR.MINOR versions marked as LTS
   - Bug fixes and security patches only
   - No new features
   - Extended support period

3. **Legacy Versions**:
   - Security patches only (critical vulnerabilities)
   - No bug fixes unless security-related
   - Limited support period

**Support Windows**:

```
Version Type    | Full Support | Security Only | Total Lifecycle
----------------|--------------|---------------|----------------
Regular Release | 12 months    | +6 months     | 18 months
LTS Release     | 24 months    | +12 months    | 36 months
Legacy Version  | 0 months     | 6 months      | 6 months
```

### Maintenance Branch Strategy

**Creating Maintenance Branches**:

When a new MINOR version is released, create a maintenance branch for the previous version if it requires continued support:

```bash
# After releasing 1.3.0, create maintenance branch for 1.2.x
git checkout v1.2.5  # Last 1.2.x release
git checkout -b maint/1.2.x
git push origin maint/1.2.x
```

### Backporting Workflow

#### Single-Version Backport

```bash
# Bug affects 1.2.x (LTS version)
# Fix merged to main (current: 1.3.0)

# Checkout maintenance branch
git checkout maint/1.2.x
git pull origin maint/1.2.x

# Create backport branch
git checkout -b backport/1.2.x/ar-456-query-bug

# Cherry-pick from main
git cherry-pick <commit-hash-from-main>

# Add changelog fragment
cat > changelog.d/456.fixed.md << 'EOF'
Fixed query null handling issue in WHERE clauses (backported from 1.3.1).
EOF
git add changelog.d/456.fixed.md
git commit -m "docs: add changelog fragment for backport AR-456"

# Push and create PR to maintenance branch
git push origin backport/1.2.x/ar-456-query-bug
# Create PR: backport/1.2.x/ar-456-query-bug → maint/1.2.x
```

#### Multi-Version Backport

```bash
# Bug in: 1.3.x (current), 1.2.x (LTS), 1.1.x (security-only)
# Fix merged to main as v1.3.1

# Backport to 1.2.x
git checkout maint/1.2.x
git checkout -b backport/1.2.x/ar-999-security-fix
git cherry-pick <security-fix-commit>
# Create fragment
cat > changelog.d/999.security.md << 'EOF'
**SECURITY**: Fixed SQL injection vulnerability. CVE-2024-XXXXX.
EOF
git add changelog.d/999.security.md
git commit -m "docs: add security fragment"
git push origin backport/1.2.x/ar-999-security-fix

# Backport to 1.1.x
git checkout maint/1.1.x
git checkout -b backport/1.1.x/ar-999-security-fix
git cherry-pick <security-fix-commit>
# Create fragment
cat > changelog.d/999.security.md << 'EOF'
**SECURITY**: Fixed SQL injection vulnerability. CVE-2024-XXXXX.
EOF
git add changelog.d/999.security.md
git commit -m "docs: add security fragment"
git push origin backport/1.1.x/ar-999-security-fix

# After all PRs merged, release patches:
# - 1.3.1 (already released)
# - 1.2.6 (from maint/1.2.x)
# - 1.1.12 (from maint/1.1.x)

# For each maintenance branch:
git checkout maint/1.2.x
__version__ = "1.2.6"
git commit -m "chore: bump version to 1.2.6"
towncrier build --version 1.2.6 --yes
git add CHANGELOG.md changelog.d/
git commit -m "docs: SECURITY RELEASE - update CHANGELOG for 1.2.6"
git tag -a v1.2.6 -m "Security release v1.2.6"
git push origin maint/1.2.x v1.2.6
```

## 10. Capability-Based Version Management

### Capability Declaration System

Backends MUST declare their supported capabilities using the `DatabaseCapabilities` system:

```python
# Backend capability declaration example
from rhosocial.activerecord.backend.capabilities import (
    DatabaseCapabilities,
    CapabilityCategory,
    CTECapability,
    WindowFunctionCapability,
)

class FirebirdBackend(StorageBackend):
    def _initialize_capabilities(self):
        """Declare backend capabilities based on server version."""
        capabilities = DatabaseCapabilities()
        version = self.get_server_version()
        
        # CTEs supported from Firebird 2.1+
        if version >= (2, 1, 0):
            capabilities.add_cte([
                CTECapability.BASIC_CTE,
                CTECapability.RECURSIVE_CTE,
            ])
        
        # Window functions from Firebird 3.0+
        if version >= (3, 0, 0):
            capabilities.add_window_function(ALL_WINDOW_FUNCTIONS)
        
        return capabilities
```

### Capability-Driven Test Execution

Tests automatically skip when required capabilities are unavailable:

```python
from rhosocial.activerecord.backend.capabilities import (
    CapabilityCategory,
    CTECapability,
)
from rhosocial.activerecord.testsuite.utils import requires_capability

@requires_capability(CapabilityCategory.CTE, CTECapability.RECURSIVE_CTE)
def test_recursive_cte(tree_fixtures):
    """Test requires recursive CTE support."""
    Node = tree_fixtures[0]
    # Test implementation
```

**Capability Version Tracking**:

- New capabilities added in MINOR versions
- Capability deprecation in MAJOR versions
- Backend capability updates tracked in changelog
- Compatibility report generated during release

## 11. Test Coverage and Quality Standards

**Core Package**:

- Minimum 90% code coverage for new features
- 100% coverage for critical paths (save, delete, query)
- Unit tests for all public APIs
- Integration tests with built-in SQLite backend

**Test Suite**:

- Backend-agnostic test logic
- Provider interface compliance tests
- Capability negotiation tests
- Performance regression tests

**Backend Packages**:

- Backend-specific schema implementation tests
- Capability declaration verification tests
- Integration tests with testsuite
- Driver-specific edge case tests

## 12. Development Cycle

### Sprint Planning (Bi-weekly)

- Feature prioritization
- Backend compatibility review
- Testsuite updates planning
- Documentation requirements

### Daily Development

- Small, focused commits
- Continuous integration checks
- Early draft pull requests for feedback
- Cross-package impact assessment

### Code Review Requirements

- Core team approval required (minimum 1)
- Backend maintainers approval for backend changes
- Testsuite changes require core + testsuite maintainer approval
- Review checklist:
  - Code style compliance
  - Test coverage adequate
  - Documentation updated
  - Backward compatibility maintained
  - Breaking changes documented

### Testing Requirements

- Unit tests: ≥90% coverage for new code
- Integration tests: Pass across all supported backends
- Performance benchmarks: No significant regression (>5%)
- Compatibility tests: Pass with supported core versions

## 13. Release Process

### Pre-release Checklist

**For All Packages**:

- [ ] All tests pass on CI
- [ ] Documentation updated and builds successfully
- [ ] **Changelog fragments reviewed** (towncrier build --draft)
- [ ] **CHANGELOG.md built** (towncrier build --version X.Y.Z --yes)
- [ ] Fragments removed after build
- [ ] Version number updated in `__init__.py`
- [ ] Git tag created with version number
- [ ] Release notes drafted

**For Core Package**:

- [ ] Backward compatibility verified
- [ ] API changes documented
- [ ] Migration guide provided (if breaking changes)
- [ ] Performance benchmarks run
- [ ] Security audit completed (if applicable)

**For Test Suite**:

- [ ] Tests pass against target core version
- [ ] New tests for new core features
- [ ] Provider interface changes documented
- [ ] Capability requirements updated

**For Backend Packages**:

- [ ] Compatibility with declared core versions verified
- [ ] Capability declarations updated
- [ ] Backend-specific tests pass
- [ ] Schema files updated
- [ ] Driver version requirements documented

### Coordinated Release Process

**Phase 1: Core Package Release**

1. Finalize core package changes
2. Create release branch
3. Run full test suite
4. Build changelog with Towncrier
5. Update version
6. Tag and publish to PyPI
7. Generate release notes

**Phase 2: Test Suite Update**

1. Update testsuite to test new core features
2. Add capability requirements for new features
3. Verify testsuite passes with new core
4. Build changelog with Towncrier
5. Tag and publish matching version
6. Update documentation

**Phase 3: Backend Package Updates**

1. Backend maintainers test against new core
2. Implement new capabilities if applicable
3. Update capability declarations
4. Run compatibility tests
5. Build changelog with Towncrier
6. Publish updated backend packages
7. Generate compatibility reports

**Phase 4: Documentation Sync**

1. Update main documentation site
2. Publish compatibility matrix
3. Update installation guides
4. Announce release on channels

### Release Cadence

**Production Releases**:

- Core package: Monthly (if features ready)
- Test suite: Aligned with core releases
- Backend packages: Independent, as needed

**Beta Releases**:

- First Friday of each month (if features ready)
- Allow 2 weeks for community testing
- Production release third Friday

**Security Patch Releases**:

- As needed, within 72 hours of disclosure
- Coordinated across all affected packages
- Emergency hotfix process

**Release Schedule Example**:

```
Week 1: Core beta release (1.3.0-beta.1)
Week 2: Backend testing and feedback
Week 3: Core production release (1.3.0)
Week 3: Testsuite release (1.3.0)
Week 4: Backend updates (1.3.x)
```

### Support Windows

**Stable Releases**:

- Full support: 12 months
- Security fixes: Additional 6 months
- Total lifecycle: 18 months

**LTS Releases** (Selected major versions):

- Full support: 24 months
- Security fixes: Additional 12 months
- Total lifecycle: 36 months

**Deprecation Policy**:

- Deprecation warnings in MINOR versions
- Removal in next MAJOR version
- Minimum 12 months between deprecation and removal

## 14. Backend Extension Development

### Extension Package Guidelines

#### Package Structure

```
rhosocial-activerecord-{backend}/
├── src/rhosocial/activerecord/backend/impl/{backend}/
│   ├── __init__.py
│   ├── backend.py          # Backend implementation
│   ├── dialect.py          # SQL dialect specifics
│   ├── type_converter.py   # Type conversions
│   └── errors.py           # Backend-specific errors
├── tests/
│   ├── providers/          # Test providers
│   ├── schemas/            # SQL schemas
│   └── conftest.py         # Test configuration
├── docs/
│   ├── installation.md
│   ├── configuration.md
│   └── compatibility.md
├── pyproject.toml
└── README.md
```

#### Naming Conventions

**Package Name**: `rhosocial-activerecord-{backend}`

- Examples: `rhosocial-activerecord-firebird`, `rhosocial-activerecord-mysql`

**Module Path**: `rhosocial.activerecord.backend.impl.{backend}`

- Examples: `rhosocial.activerecord.backend.impl.firebird`

**Backend Class**: `{Backend}Backend`

- Examples: `FirebirdBackend`, `MySQLBackend`

#### Interface Compliance

All backends MUST implement:

1. **StorageBackend Interface**:

   ```python
   from rhosocial.activerecord.backend import StorageBackend
   
   class MyBackend(StorageBackend):
       def connect(self) -> None: ...
       def disconnect(self) -> None: ...
       def execute(self, sql: str, params: Dict) -> QueryResult: ...
       def insert(self, table: str, data: Dict) -> QueryResult: ...
       def update(self, table: str, data: Dict, where: str) -> QueryResult: ...
       def delete(self, table: str, where: str) -> QueryResult: ...
       def get_server_version(self) -> tuple: ...
       # ... other required methods
   ```

2. **Capability Declaration**:

   ```python
   def _initialize_capabilities(self) -> DatabaseCapabilities:
       """Declare backend capabilities."""
       capabilities = DatabaseCapabilities()
       # Add supported capabilities based on version/config
       return capabilities
   ```

3. **Test Provider Implementation**:

   ```python
   from rhosocial.activerecord.testsuite.core import IProvider
   
   class MyBackendProvider(IProvider):
       def setup_fixtures(self, scenario: str) -> Tuple[Type[ActiveRecord], ...]:
           # Setup models and schemas
           pass
       
       def cleanup(self, scenario: str) -> None:
           # Cleanup test data
           pass
   ```

#### Capability Declaration Requirements

Backends MUST accurately declare capabilities:

```python
def _initialize_capabilities(self):
    capabilities = DatabaseCapabilities()
    version = self.get_server_version()
    
    # Example: Firebird 5.0+ features
    if version >= (5, 0, 0):
        capabilities.add_cte([
            CTECapability.BASIC_CTE,
            CTECapability.RECURSIVE_CTE,
        ])
        capabilities.add_window_function(ALL_WINDOW_FUNCTIONS)
    
    # JSON operations
    if version >= (5, 7, 0):
        capabilities.add_json([
            JSONCapability.JSON_EXTRACT,
            JSONCapability.JSON_SET,
        ])
    
    return capabilities
```

**Capability Testing**:

- Backend must pass all tests for declared capabilities
- Tests automatically skip for unsupported capabilities
- False capability declarations fail during CI

#### Version Management for Extensions

**Dependency Declaration**:

```toml
# pyproject.toml
[project]
name = "rhosocial-activerecord-firebird"
version = "1.2.0"
dependencies = [
    "rhosocial-activerecord>=1.2.0,<2.0.0",
    "firebird-driver>=2.0.0",
]

[project.optional-dependencies]
test = [
    "rhosocial-activerecord-testsuite>=1.2.0,<1.3.0",
    "pytest>=7.0.0",
]
```

**Version Increment Strategy**:

- MAJOR: When core API breaks (follow core)
- MINOR: Backend-specific features or driver updates
- PATCH: Bug fixes and performance improvements

**Compatibility Matrix**:
Maintain a compatibility table in README.md:

```markdown
| Backend Version | Core Version | Driver Version | DB Version |
|-----------------|--------------|----------------|------------|
| 1.2.0           | 1.2.x        | 2.0.0+         | Firebird 6.0+ |
| 1.1.5           | 1.1.x        | 2.0.0+         | Firebird 5.0+ |
```

#### Testing Requirements

**Unit Tests**:

- Backend-specific functionality
- Capability declaration accuracy
- Connection handling
- Error handling
- Type conversions

**Integration Tests**:

- Full testsuite execution
- Provider interface compliance
- Schema setup and teardown
- Cross-scenario testing

**Performance Tests**:

- Query execution benchmarks
- Connection pool efficiency
- Bulk operation performance

**Compatibility Tests**:

- Multiple database versions
- Multiple Python versions
- Multiple core package versions (within declared range)

### Fork Development

**For Independent Forks**:

Forks creating independent implementations have full autonomy but should:

1. **Maintain Namespace Compatibility** (if desired):

   ```python
   # Still use rhosocial.activerecord namespace
   from rhosocial.activerecord.backend import StorageBackend
   ```

2. **Document Compatibility**:
   - State which core version fork is based on
   - Document deviations from official API
   - Maintain changelog of fork-specific changes

3. **Testing**:
   - Forks are responsible for their own test suite
   - May use official testsuite if compatible
   - Should declare compatibility with testsuite version

4. **Versioning**:
   - Independent version numbering allowed
   - Should indicate original core version in docs
   - Example: "Based on rhosocial-activerecord 1.2.0"

**For Community Backends**:

Community-developed backends can be:

1. Submitted for inclusion in official ecosystem
2. Maintained independently with ecosystem compatibility
3. Listed in official documentation (upon review)

**Quality Requirements for Listing**:

- Pass official testsuite
- Accurate capability declarations
- Documentation and examples
- Maintained and responsive to issues
- License compatible with core (MIT recommended)

## 15. Compatibility and Upgrade Strategy

### Backward Compatibility Promise

**Core Package**:

- MINOR versions: Fully backward compatible
- MAJOR versions: Breaking changes allowed with migration guide
- Deprecation warnings: Minimum 12 months before removal

**Test Suite**:

- Test interface changes only in MAJOR versions
- New tests added in MINOR versions
- Test fixes in PATCH versions

**Backend Packages**:

- Must maintain compatibility with declared core version range
- Breaking changes require MAJOR version bump
- Driver updates handled in MINOR/PATCH as appropriate

### Migration Guides

For each MAJOR version release, provide:

1. **Breaking Changes Summary**: List of all breaking changes
2. **Migration Steps**: Step-by-step upgrade instructions
3. **Code Examples**: Before/after comparison
4. **Automated Tools**: Scripts for common migrations (if applicable)
5. **FAQ**: Common issues and solutions

### Deprecation Process

1. **Announcement**: Deprecation warning in code and documentation
2. **Alternative**: Provide recommended alternative approach
3. **Timeline**: Minimum 12 months before removal
4. **Removal**: Only in next MAJOR version

Example:

```python
import warnings

def old_method(self):
    warnings.warn(
        "old_method() is deprecated and will be removed in version 2.0. "
        "Use new_method() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return self.new_method()
```

## 16. Documentation Requirements

### Version-Specific Documentation

Each release must include:

**Release Notes** (`CHANGELOG.md`):

- Version number and date (automatically generated by Towncrier)
- Breaking changes (if any)
- New features
- Bug fixes
- Deprecations
- Known issues

**API Documentation**:

- Auto-generated from docstrings
- Version switcher for multiple versions
- Examples for new features

**Migration Guides** (for MAJOR versions):

- Detailed upgrade instructions
- Breaking changes explained
- Code migration examples

### Documentation Versioning

- Documentation versioned with package
- Separate docs for each MAJOR.MINOR version
- Latest stable docs as default
- Dev/unstable docs available

## 17. Current Status

### Core Package (rhosocial-activerecord)

**Current Version**: `1.0.0.dev11`

**Status**:

- ✅ Core ActiveRecord implementation stable
- ✅ Query builder functional
- ✅ Relationship management operational
- 🚧 Event hooks system in development
- 🚧 Advanced field types in progress

**Supported Python Versions**: 3.8+

**Supported Pydantic Versions**: 2.x series

**Key Features**:

- Basic CRUD operations
- Query building with conditions
- One-to-many, many-to-one relationships
- Type-safe field definitions
- Backend abstraction layer
- Transaction management
- Optimistic locking mixin
- Timestamp tracking mixin

### Test Suite Package (rhosocial-activerecord-testsuite)

**Current Version**: Tracks core package

**Status**:

- ✅ Provider interface system operational
- ✅ Capability negotiation implemented
- ✅ Basic feature tests complete
- ✅ Query feature tests comprehensive
- 🚧 Real-world scenario tests expanding
- 🚧 Benchmark suite in development

**Test Coverage**:

- Feature tests: Comprehensive
- Real-world scenarios: Growing
- Performance benchmarks: Initial set
- Compatibility tests: Cross-backend

**Supported Test Categories**:

- `feature.basic`: CRUD, validation, fields
- `feature.query`: CTE, window functions, aggregates
- `feature.events`: Event hooks, callbacks
- `feature.mixins`: Timestamp, soft delete, optimistic lock
- `realworld.*`: Business scenario tests (planned)
- `benchmark.*`: Performance tests (planned)

### Backend Implementations

#### SQLite (Built-in)

**Status**: ✅ Production-ready, actively maintained

**Capabilities**:

- Basic CRUD ✅
- CTEs (version 3.8.3+) ✅
- Window functions (version 3.25.0+) ✅
- RETURNING clause (version 3.35.0+) ⚠️ (Python 3.10+ recommended)
- JSON operations (version 3.38.0+) ✅
- Recursive CTEs ✅

**Version Support**: SQLite 3.8.3+

**Notes**:

- Built-in, no additional installation
- RETURNING clause limitations in Python <3.10
- Excellent for development and testing
- Production-ready for moderate workloads

#### MySQL (rhosocial-activerecord-mysql)

**Status**: ✅ Stable implementation, separate package

**Capabilities**:

- Basic CRUD ✅
- CTEs (MySQL 8.0+) ✅
- Window functions (MySQL 8.0+) ✅
- RETURNING clause ❌ (Not supported)
- JSON operations ✅
- Recursive CTEs ✅
- Upsert (ON DUPLICATE KEY UPDATE) ✅

**Driver**: mysql-connector-python

**Version Support**: MySQL 5.7+, MySQL 8.0+ recommended

**Installation**: `pip install rhosocial-activerecord-mysql`

#### Postgres (rhosocial-activerecord-postgres)

**Status**: ✅ Stable implementation, separate package

**Capabilities**:

- Basic CRUD ✅
- CTEs ✅
- Window functions ✅
- RETURNING clause ✅
- JSON operations (JSONB) ✅
- Recursive CTEs ✅
- Upsert (ON CONFLICT) ✅
- Array types ✅

**Driver**: psycopg
**Notes**: Supports psycopg (version 3) only. Psycopg2 is not supported.

**Version Support**: Postgres 9.6+, Postgres 12+ recommended

**Installation**: `pip install rhosocial-activerecord-postgres`

#### Firebird (rhosocial-activerecord-firebird)

**Status**: ✅ Stable implementation, separate package

**Capabilities**:

- Basic CRUD ✅
- CTEs ✅
- Recursive CTEs ✅
- Window functions ✅
- RETURNING clause ✅
- JSON operations ✅
- Upsert (MERGE / UPDATE OR INSERT) ✅
- Sequences / Generators ✅
- BLOB (binary / text) ✅
- Executable blocks (EXECUTE BLOCK) ✅
- Stored procedures, packages, external functions ✅
- Triggers (table / database) ✅
- Domains, exceptions, roles, users ✅
- Autonomous transactions ✅
- Monitoring tables ✅
- Table partitioning ✅

**Driver**: firebird-driver

**Notes**: INTERSECT/EXCEPT set operators are not supported as standalone
keywords (use UNION). TIMESTAMP precision is 100µs.

**Version Support**: Firebird 5.0+, Firebird 6.0+ recommended

**Installation**: `pip install rhosocial-activerecord-firebird`

#### Community Backends

Community-maintained backends can be developed following the extension guidelines. Popular targets include:

- MongoDB (planned)
- Redis (planned)

## Summary

### Version Management Hierarchy

```
Core Package (Independent)
    ↓
Test Suite (Tracks MAJOR.MINOR)
    ↓
Backend Packages (Synced MAJOR, Independent MINOR/PATCH)
```

### Key Principles

1. **Semantic Versioning**: Strict interpretation - MAJOR for breaking changes, MINOR for features, PATCH for fixes
2. **Pre-release Cycle**: Every MAJOR.MINOR follows dev→alpha→beta→rc→release
3. **Branch Strategy**: Pre-release branches from main, development branches from pre-release
4. **Version Bumps**: First commit in new branch updates version number
5. **Phase Transitions**: Reuse `release/vX.Y.Z` branch across alpha/beta/rc phases
6. **Merge Strategy**: Squash for features, no-ff merge for releases to preserve history
7. **Changelog Management**: Towncrier-based fragment workflow for all packages
8. **Post-Release**: Structured process for PATCH releases and security fixes
9. **Backporting**: Maintenance branches for LTS versions with independent changelog
10. **Capability System**: Enables fine-grained feature detection and test selection
11. **Coordinated Releases**: Phased release process ensures ecosystem compatibility
12. **Quality Standards**: Minimum 90% test coverage, comprehensive documentation
13. **Python Version Support**: Clear policy with migration timelines for version drops
14. **Continuous Integration**: Mandatory CI checks on all protected branches

### Quick Reference

**Creating New Version**:

1. Branch from `main` → `release/vX.Y.Z.dev1`
2. First commit bumps version number
3. Create feature branches from release branch
4. Create changelog fragments for each feature
5. Merge features back to release branch (fragments stay)

**Phase Transitions**:

1. Create `release/vX.Y.Z` from final dev branch
2. Bump version to alpha/beta/rc in same branch
3. Continue using same branch through all phases
4. Fragments accumulate but CHANGELOG.md not updated until final

**Final Release**:

1. Build changelog with Towncrier (removes fragments)
2. Commit changelog to release branch
3. Merge release branch to main (no-ff)
4. Tag with version number
5. Publish to PyPI
6. Update documentation

**Post-Release Defects**:

1. Fix bugs in main branch with changelog fragments
2. Bump to next PATCH version
3. Build changelog with Towncrier
4. Tag and publish immediately (critical) or batch (non-critical)
5. Backport to LTS versions if needed (with fragments)

**Abandoned Features**:

1. Delete feature branch
2. Delete changelog fragment from pre-release branch
3. Fragment never enters CHANGELOG.md

### Release Coordination

1. Core package releases first (with changelog build)
2. Test suite updates for new core features (with changelog build)
3. Backend packages test and update capability declarations (with changelog build)
4. Documentation synced across all packages
5. Compatibility matrix published with each release
