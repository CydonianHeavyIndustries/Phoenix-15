param(
  [int]$Port = 16326
)

$ErrorActionPreference = "SilentlyContinue"

function Test-PortOpen {
  param(
    [string]$Ip,
    [int]$Port,
    [int]$TimeoutMs = 150
  )
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $iar = $client.BeginConnect($Ip, $Port, $null, $null)
    if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
      $client.Close()
      return $false
    }
    $client.EndConnect($iar) | Out-Null
    $client.Close()
    return $true
  } catch {
    return $false
  }
}

$prefixes = @()
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object {
    $_.IPAddress -and
    $_.IPAddress -notlike '127.*' -and
    $_.IPAddress -notlike '169.254.*' -and
    $_.InterfaceAlias -notmatch 'Loopback|vEthernet|Hyper-V|Virtual'
  } |
  ForEach-Object {
    $parts = $_.IPAddress.Split('.')
    if ($parts.Length -eq 4) {
      $prefixes += ($parts[0..2] -join '.')
    }
  }

$prefixes = $prefixes | Select-Object -Unique
if (-not $prefixes) {
  exit 1
}

foreach ($prefix in $prefixes) {
  foreach ($host in 1..254) {
    $ip = "$prefix.$host"
    if (-not (Test-PortOpen -Ip $ip -Port $Port)) {
      continue
    }
    try {
      $url = "http://${ip}:$Port/ready.json"
      $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 1
      if ($resp -and $resp.project -eq "Phoenix-15" -and $resp.user) {
        Write-Output "$ip|$($resp.user)"
        exit 0
      }
    } catch {
    }
  }
}

exit 1
