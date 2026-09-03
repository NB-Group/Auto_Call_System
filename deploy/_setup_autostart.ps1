param([string]$Role = "server", [string]$ServerUrl = "")
$name = @{ server = "叫号系统-服务器"; teacher = "叫号系统-老师端"; display = "叫号系统-教室端" }[$Role]
if (-not $name) { $name = "叫号系统" }
$startup = [Environment]::GetFolderPath("Startup")
$lnk = Join-Path $startup "$name.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = "C:\CallCenter\call-center.exe"
$s.Arguments = "--role $Role"
# 可选:钉死服务器地址(显示端与服务器同机时建议 http://127.0.0.1:8800,
# 免 UDP 广播发现受防火墙 profile/多网卡影响)
if ($ServerUrl) { $s.Arguments += " --server-url $ServerUrl" }
$s.WorkingDirectory = "C:\CallCenter"
$s.Save()
Write-Output "autostart created: $lnk args=$($s.Arguments)"
