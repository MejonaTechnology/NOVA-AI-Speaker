$port = new-Object System.IO.Ports.SerialPort COM10,115200,None,8,one
$port.Open()
$port.WriteLine("o")
Start-Sleep -Seconds 3
$buffer = ""
while($port.BytesToRead -gt 0) {
    $buffer += $port.ReadExisting()
}
$port.Close()
Write-Output $buffer
