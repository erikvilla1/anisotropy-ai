# Points the folders that Claude Code scans, .claude/skills and .claude/agents, at docs/agents/skills
# and docs/agents/subagents (ADR-0023, ADR-0047).
# Tooling that is not part of the product does not read this repository's skills (ADR-0028).
# The junctions are local and ignored by git. Run once after cloning and in every new worktree:
#   powershell -ExecutionPolicy Bypass -File scripts/link-agent-dirs.ps1
# A session started before .claude/agents existed lists no subagent until it is restarted.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$links = [ordered]@{
    '.claude\skills' = 'docs\agents\skills'
    '.claude\agents' = 'docs\agents\subagents'
}

foreach ($relative in $links.Keys) {
    $source = $links[$relative]
    $target = Join-Path $root $source
    $link = Join-Path $root $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $link) | Out-Null

    if (Test-Path $link) {
        $item = Get-Item $link -Force
        if ($item.LinkType -eq 'Junction' -and $item.Target -contains $target) {
            Write-Output "ok       $relative -> $source"
            continue
        }
        throw "$relative exists and is not a junction to $source. Move it aside and run again."
    }

    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Write-Output "created  $relative -> $source"
}
