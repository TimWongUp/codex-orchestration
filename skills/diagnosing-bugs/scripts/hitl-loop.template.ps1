# Human-in-the-loop reproduction loop for PowerShell.
# Copy this file, edit the steps below, and run it.
# Usage: pwsh -File hitl-loop.template.ps1

$ErrorActionPreference = "Stop"

function Step([string]$Instruction) {
    Write-Host "`n>>> $Instruction"
    Read-Host "    [Enter when done]" | Out-Null
}

function Capture([string]$Question) {
    Write-Host "`n>>> $Question"
    return Read-Host "    >"
}

# --- edit below ---------------------------------------------------------

Step "Open the app at http://localhost:3000 and sign in."

$Errored = Capture "Click the 'Export' button. Did it throw an error? (y/n)"

$ErrorMessage = Capture "Paste the error message (or 'none'):"

# --- edit above ---------------------------------------------------------

Write-Host "`n--- Captured ---"
Write-Host "ERRORED=$Errored"
Write-Host "ERROR_MSG=$ErrorMessage"
