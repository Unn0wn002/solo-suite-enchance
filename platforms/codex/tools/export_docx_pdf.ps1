param(
    [Parameter(Mandatory = $true)][string]$InputDocx,
    [Parameter(Mandatory = $true)][string]$OutputPdf
)

$ErrorActionPreference = "Stop"

$word = New-Object -ComObject Word.Application
try {
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $missing = [Type]::Missing
    $doc = $word.Documents.Open(
        $InputDocx,
        $false,
        $true,
        $false,
        "",
        "",
        $false,
        "",
        "",
        0,
        $missing,
        $false,
        $true,
        $missing,
        $true,
        $missing
    )
    try {
        $doc.ExportAsFixedFormat($OutputPdf, 17)
    }
    finally {
        $doc.Close($false)
    }
}
finally {
    $word.Quit()
}
