$ErrorActionPreference = "Continue"
$proj = "c4799361d2dd4e09bdd31ddc8a57a1ba"
$out = "C:\Code\epdf-hardware\esp32-board-v2.0\work\scan-20261010"
New-Item -ItemType Directory -Force -Path $out | Out-Null
function Run($name, $a) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  & easyeda @a 2>&1 | Out-File -FilePath (Join-Path $out "$name.log") -Encoding utf8
  Write-Output ("{0,-18} {1,7} ms" -f $name, $sw.ElapsedMilliseconds)
}
Run "board-dump"    @("pcb","dump","--include-copper","--label","esp32s3-board-v2.0","--project",$proj,"--out",(Join-Path $out "board-dump.json"))
Run "net-class-list" @("pcb","net-class","list","--project",$proj)
Run "layout-lint"   @("pcb","layout-lint","--project",$proj)
Run "pcb-regions"   @("pcb","region","list","--project",$proj)
Run "pcb-zones"     @("pcb","zones","status","--project",$proj)
Run "sch-status"    @("sch","status","--project",$proj)
Run "sch-check-p1"  @("sch","check","--page","7b1ca0ce011868e2","--project",$proj)
Run "sch-check-p2"  @("sch","check","--page","f568f62f67600e3d","--project",$proj)

