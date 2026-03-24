# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

claudeStockTrader — a stock trading system. The project is in early stages with scaffolded directories (`cache/`, `jobs/`, `snapshots/`, `webhooks/`) but no application code yet.

## MCP Servers

- **CrawlForge** is configured in `.mcp.json` for web scraping, search, and content extraction. Use `mcp__crawlforge__*` tools for fetching market data from the web.

## Custom Commands

- `/enhanced-plan` — read-only codebase exploration and implementation planning (no file modifications)
- `/agent-creation` — design and create AI agent configurations from requirements

These live in `.claude/commands/`.

## Environment

- `.env` contains API keys and secrets — never commit this file
