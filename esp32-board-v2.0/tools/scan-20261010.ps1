$ErrorActionPreference = "Continue"
$proj = "c4799361d2dd4e09bdd31ddc8a57a1ba"
$out = "C:\Code\epdf-hardware\esp32-board-v2.0\work\scan-20261010"
New-Item -ItemType Directory -Force -Path $out | Out-Null
function Run($name, $a) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  & easyeda @a 2>&1 | Out-File -FilePath (Join-Path $out "$name.log") -Encoding utf8
  Write-Output ("{0,-16} {1,7} ms" -f $name, $sw.ElapsedMilliseconds)
}
Run "board-list"   @("board","list","--project",$proj)
Run "board-current" @("board","current","--project",$proj)
Run "sch-pages"    @("sch","pages","--project",$proj)
Run "pcb-layers"   @("pcb","layers","--project",$proj)
Run "pcb-stackup"  @("pcb","stackup","show","--project",$proj)
Run "pcb-outline"  @("pcb","outline-get","--project",$proj)
Run "drc-rules"    @("pcb","drc-rules","--project",$proj)
Run "pcb-nets"     @("pcb","nets","--project",$proj)
Run "pcb-report"   @("pcb","report","--project",$proj)
Run "pcb-pours"    @("pcb","pour-list","--project",$proj)
Run "pcb-vias"     @("pcb","via-list","--project",$proj)
Run "pcb-list"     @("pcb","list","--project",$proj,"--include-bbox")

