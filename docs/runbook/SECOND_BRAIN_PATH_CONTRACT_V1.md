# SECOND_BRAIN_PATH_CONTRACT_V1

## Purpose

This fixes the second-brain path boundary for home desktop Hermes automations.

## Path Roles

| Role | Path | Owner | Rule |
|---|---|---|---|
| Home desktop automation canonical | `/home/yk/brain-linux` | Hermes / cron / WSL automation | Write, commit, push here |
| Windows Obsidian mirror | `/mnt/c/Users/82106/Documents/brain` | Obsidian UI | Pull-only mirror unless manually editing |
| Legacy alias | `/home/yk/brain` | compatibility only | Do not use as a new automation default |
| MacBook checkout | `/Users/youngkwon/projects/second-brain` | MacBook Codex / LaunchAgents | Mac-local capture and review |

## Runtime Contract

Home desktop scripts must read:

```bash
SECOND_BRAIN_DIR=/home/yk/brain-linux
```

If no env var is present, home desktop scripts should fallback to `/home/yk/brain-linux`, not `/home/yk/brain`.

## Sync Flow

```text
Hermes / cron writes
  -> /home/yk/brain-linux
  -> push second-brain origin/main
  -> windows_obsidian_mirror_pull.py
  -> /mnt/c/Users/82106/Documents/brain
```

`windows_obsidian_mirror_pull.py` only fast-forwards when the mirror is clean. It does not stash, merge, commit, or overwrite Obsidian-local edits.

## Why This Exists

`/home/yk/brain` points to a Windows-mounted folder. On WSL drvfs/9p, POSIX permissions can appear as `777` even after `chmod 644`, which creates noisy and unsafe automation behavior.

`/home/yk/brain-linux` is a real Linux filesystem checkout, so file modes and Git automation behave predictably.

