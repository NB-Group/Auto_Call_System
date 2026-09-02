param([string]$Role = "server")
$name = @{ server = "叫号系统-服务器"; teacher = "叫号系统-老师端"; display = "叫号系统-教室端" }[$Role]
if (-not $name) { $name = "叫号系统" }
$startup = [Environment]::GetFolderPath("Startup")
$lnk = Join-Path $startup "$name.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = "C:\CallCenter\call-center.exe"
$s.Arguments = "--role $Role"
$s.WorkingDirectory = "C:\CallCenter"
$s.Save()
Write-Output "autostart created: $lnk"
