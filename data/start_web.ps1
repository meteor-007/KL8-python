# Thin root wrapper -> scripts/ops/start_web.ps1
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$here\scripts\ops\start_web.ps1" @args
