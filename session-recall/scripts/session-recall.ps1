param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Args
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Resolve-SessionRecallPython {
    $candidates = @()
    if ($env:SESSION_RECALL_PYTHON) {
        $candidates += @{ Command = $env:SESSION_RECALL_PYTHON; Args = @() }
    }
    $candidates += @{ Command = "python"; Args = @() }
    $candidates += @{ Command = "py"; Args = @("-3") }

    foreach ($candidate in $candidates) {
        $command = [string]$candidate.Command
        if ([System.IO.Path]::IsPathRooted($command)) {
            if (Test-Path -LiteralPath $command) {
                return $candidate
            }
            continue
        }

        if (Get-Command $command -ErrorAction SilentlyContinue) {
            return $candidate
        }
    }

    throw "Python 3 was not found. Install Python 3 or set SESSION_RECALL_PYTHON to python.exe."
}

$Tool = Join-Path $PSScriptRoot "memory_tool.py"
$Python = Resolve-SessionRecallPython
& $Python.Command @($Python.Args) $Tool @Args
