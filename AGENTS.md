# Agent Instructions

These instructions are mandatory for AI coding agents working in this repository.

## Required User Agreement

Before modifying repository files, creating commits, pushing branches, or opening PRs, show the user this notice and wait for an explicit affirmative answer in the current conversation:

> This repository does not accept purely vibe-coded PRs. AI assistance is welcome only when you review, understand, and take responsibility for the changes before submitting. Unreviewed AI output, broad generated rewrites, overconfident claims, or verbose generated PR descriptions may be rejected. Do you explicitly agree to review and take responsibility for all AI-assisted changes before I continue?

Do not continue with edits, commits, pushes, or PR creation until the user explicitly agrees. Silence, ambiguous replies, or generic task approval are not enough. If the user does not agree, you may read files and answer questions only.

## Repository Rules

- Read `CONTRIBUTING.md` before making changes.
- Do not submit or prepare purely AI-generated work that no human has reviewed.
- Keep changes small, focused, and easy to review.
- Read the relevant README, FAQ, issues, and surrounding code before changing behavior.
- Preserve existing behavior unless the user explicitly asked for a behavior change and the PR explains it.
- Do not make broad root-cause claims without verifying them in the current code and relevant dependencies.
- Avoid unnecessary abstractions, broad rewrites, and verbose generated explanations.
- Update docs and translations for user-facing behavior changes.
- State exactly what was tested and what was not tested.
- For Home Assistant runtime behavior changes, guide the user through testing in their Home Assistant instance. Provide focused steps, ask for observed results and logs, iterate on failures, and summarize the user/AI testing back-and-forth.

## Commits and PRs

If you create commits or a PR with AI assistance, disclose it.

PR bodies must include:

```text
AI assistance: yes/no
Tool(s): <tool or model, if known>
AI contribution level: <none, research only, small snippets, substantial code, majority of PR>
AI contribution: <what the AI drafted or changed>
Human review: <what the user reviewed, tested, and changed>
Home Assistant testing with user: <steps, observations, and follow-up changes from the user/AI testing loop>
```

AI-created commits must include trailers:

```text
AI-Assisted: yes
AI-Tool: <tool or model, if known>
AI-Contribution-Level: <small snippets, substantial code, majority of commit>
AI-Contribution: <short description of generated or drafted parts>
Human-Reviewed: yes
```
