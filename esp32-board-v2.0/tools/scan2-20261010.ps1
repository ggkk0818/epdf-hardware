$ErrorActionPreference = "Continue"
$proj = "c4799361d2dd4e09bdd31ddc8a57a1ba"
$out = "C:\Code\epdf-hardware\esp32-board-v2.0\work\scan-20261010"
New-Item -ItemType Directory -Force -Path $out | Out-Null
function Run($name, $a) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  & easyeda @a 2>&1 | Out-File -FilePath (Join-Path $out "$name.log") -Encoding utf8
  Write-Output ("{0,-18} {1,7} ms" -f $name, $sw.ElapsedMilliseconds)
}
Run "sch-p1"      @("sch","read","--page","7b1ca0ce011868e2","--project",$proj,"--no-check")
Run "sch-p2"      @("sch","read","--page","f568f62f67600e3d","--project",$proj,"--no-check")
Run "sch-connect" @("sch","connectivity","--page","7b1ca0ce011868e2","--project",$proj)
Run "pcb-drc"     @("pcb","drc","--json","--timeout","150","--project",$proj)
Run "pcb-check"   @("pcb","check","--project",$proj)
Run "pcb-tracks"  @("pcb","track-list","--project",$proj)
Run "pcb-vias-json" @("pcb","via-list","--project",$proj)

