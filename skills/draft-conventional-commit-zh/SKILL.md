---
name: draft-conventional-commit-zh
description: "Draft Conventional Commits messages in Chinese from short change summaries. Use when a user asks to write commit messages, polish commit text, or map brief code-change notes into `type(scope): subject` format that follows Conventional Commits."
---

# Draft Conventional Commit Zh

Draft concise, valid Conventional Commit messages in Chinese. Infer missing details from short summaries and prefer one high-confidence recommendation.

## Workflow

1. Parse the user summary into intent:
- change type
- affected module/scope
- core action/result
- breaking-change signal
- issue reference (if provided)
2. Choose the Conventional Commit `type`:
- `feat`: new feature or user-visible capability
- `fix`: bug fix or incorrect behavior correction
- `docs`: documentation-only changes
- `style`: formatting/style only (no logic change)
- `refactor`: internal restructuring without behavior change
- `perf`: performance optimization
- `test`: test creation or updates
- `build`: build system or dependency changes
- `ci`: CI/CD pipeline changes
- `chore`: maintenance tasks not covered above
- `revert`: reverting prior commit
3. Infer `scope` from mentioned component (example: `auth`, `api`, `ui`, `deps`). Omit scope if uncertain.
4. Write the subject in Simplified Chinese:
- keep it short and specific (prefer <= 50 chars)
- start with an action verb
- avoid ending punctuation
- describe observable change outcome, not implementation trivia
5. Build the header with exact format:
- with scope: `<type>(<scope>): <中文subject>`
- without scope: `<type>: <中文subject>`
6. Handle breaking changes:
- append `!` to type or type/scope in header
- add footer line: `BREAKING CHANGE: <中文影响说明>`
7. Add issue footers only when requested or clearly supplied:
- `Refs: #123`
- `Closes: #123`

## Output Rules

- Default output: return one best commit message line only.
- If the user asks for options: return 3 alternatives and label the recommended one first.
- Keep `type`, `scope`, and footer keys in English; keep subject/body explanation in Chinese.
- If the summary is too vague, make the safest assumption (`chore` without scope) and state one short clarification question after the draft.

## Examples

Input summary: `新增微信登录，并调整登录按钮文案`
Output: `feat(auth): 支持微信登录并优化登录按钮文案`

Input summary: `修复导出 CSV 时中文乱码问题`
Output: `fix(export): 修复导出 CSV 时中文乱码`

Input summary: `重构缓存层，接口不兼容旧配置`
Output:
`refactor(cache)!: 重构缓存层配置模型`
`BREAKING CHANGE: 旧版缓存配置字段不再兼容`
