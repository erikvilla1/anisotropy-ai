#!/bin/sh
# Points the folders that Claude Code scans, .claude/skills and .claude/agents, at docs/agents/skills
# and docs/agents/subagents (ADR-0023, ADR-0047). The macOS and Linux companion to link-agent-dirs.ps1,
# which creates the same two links as Windows junctions.
# Tooling that is not part of the product does not read this repository's skills (ADR-0028).
# The symlinks are local and ignored by git. Run once after cloning and in every new worktree:
#   sh scripts/link-agent-dirs.sh
# A session started before .claude/agents existed lists no subagent until it is restarted.

set -eu

root=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
mkdir -p "$root/.claude"

# Every link sits one level below the root, so its target is the source prefixed with one '..'.
link_one() {
    relative=$1
    source=$2
    target=../$source
    link=$root/$relative

    if [ -L "$link" ]; then
        if [ "$(readlink "$link")" = "$target" ]; then
            echo "ok       $relative -> $source"
            return
        fi
        echo "$relative is a symlink to $(readlink "$link"), not $source. Move it aside and run again." >&2
        exit 1
    fi

    if [ -e "$link" ]; then
        echo "$relative exists and is not a symlink to $source. Move it aside and run again." >&2
        exit 1
    fi

    ln -s "$target" "$link"
    echo "created  $relative -> $source"
}

link_one '.claude/skills' 'docs/agents/skills'
link_one '.claude/agents' 'docs/agents/subagents'
