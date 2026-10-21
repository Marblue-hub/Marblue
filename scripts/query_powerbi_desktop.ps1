param(
    [Parameter(Mandatory=$true)][string]$InputFile,
    [Parameter(Mandatory=$true)][string]$OutputFile,
    [Parameter(Mandatory=$true)][int]$Port,
    [string]$DesktopBin='D:\Apps\Power BI Desktop\bin'
)
$ErrorActionPreference='Stop'
[void][Reflection.Assembly]::LoadFrom((Join-Path $DesktopBin 'Microsoft.PowerBI.AdomdClient.dll'))
$connection=New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection
$connection.ConnectionString='Data Source=localhost:'+$Port
$connection.Open()
try {
    $command=$connection.CreateCommand()
    $command.CommandText='SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS'
    $reader=$command.ExecuteReader()
    $catalogs=@()
    while ($reader.Read()) { $catalogs += $reader.GetString(0) }
    $reader.Close()
    if ($catalogs.Count -ne 1) { throw 'Expected exactly one Desktop model.' }
    $connection.ChangeDatabase($catalogs[0])
    $queries=Get-Content -LiteralPath $InputFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $results=@()
    foreach ($query in $queries) {
        $command=$connection.CreateCommand()
        $command.CommandTimeout=120
        $command.CommandText=$query.dax
        $reader=$command.ExecuteReader()
        $rows=@()
        while ($reader.Read()) {
            $row=[ordered]@{}
            for ($index=0;$index -lt $reader.FieldCount;$index++) {
                $name=$reader.GetName($index)
                if ($name.StartsWith('[')) { $name=$name.Substring(1,$name.Length-2) }
                $value=if ($reader.IsDBNull($index)) {$null} else {$reader.GetValue($index)}
                # Preserve native DateTime.Kind; PowerShell 5 otherwise interprets
                # unspecified engine dates as local time when emitting JSON epochs.
                $row[$name]=if ($value -is [DateTime]) {$value.ToString('o')} else {$value}
            }
            $rows += [PSCustomObject]$row
        }
        $reader.Close()
        $results += [PSCustomObject]@{id=$query.id;rows=$rows}
    }
    [PSCustomObject]@{catalog=$catalogs[0];port=$Port;queried_at_utc=[DateTime]::UtcNow.ToString('o');queries=$results} |
        ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $OutputFile -Encoding UTF8
} finally {
    $connection.Close()
}
