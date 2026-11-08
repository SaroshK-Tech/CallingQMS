# Prints the machine's primary LAN IPv4 address (used by start_server_on_host.bat).
$addr = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notlike '127.*' -and
    $_.IPAddress -notlike '169.254.*' -and
    $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback|VirtualBox|VMware|Hyper-V'
} | Select-Object -First 1 -ExpandProperty IPAddress

if (-not $addr) {
    $addr = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*'
    } | Select-Object -First 1 -ExpandProperty IPAddress
}

[Console]::Out.Write($addr)