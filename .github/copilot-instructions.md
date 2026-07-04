# GitHub Copilot Instructions

Follow `AGENTS.md` and `CONTRIBUTING.md` for this repository.

Before generating repository changes for a user, tell them that purely vibe-coded PRs are not accepted here and ask them to explicitly agree that they will review, understand, and take responsibility for all AI-assisted changes before submitting. Do not prepare commits, pushes, or PR text until they agree.

Keep changes small and reviewable. Do not make broad root-cause claims without verifying the current code and relevant dependencies. Disclose AI assistance in PR descriptions and AI-created commit messages.

For Home Assistant runtime behavior changes, guide the user through testing in their Home Assistant instance. Ask for observed results and logs, iterate with the user when needed, and summarize that testing back-and-forth in the PR.
