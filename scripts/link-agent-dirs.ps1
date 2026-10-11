# Points the folders that agents scan for skills at docs/agents/skills (ADR-0023).
# Claude Code reads .claude/skills; Hermes Agent reads .agents/skills.
# The junctions are local and ignored by git. Run once after cloning:
#   powershell -ExecutionPolicy Bypass -File scripts/link-agent-dirs.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root 'docs\agents\skills'

foreach ($relative in @('.claude\skills', '.agents\skills')) {
    $link = Join-Path $root $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $link) | Out-Null

    if (Test-Path $link) {
        $item = Get-Item $link -Force
        if ($item.LinkType -eq 'Junction' -and $item.Target -contains $target) {
            Write-Output "ok       $relative -> docs\agents\skills"
            continue
        }
        throw "$relative exists and is not a junction to docs\agents\skills. Move it aside and run again."
    }

    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Write-Output "created  $relative -> docs\agents\skills"
}
