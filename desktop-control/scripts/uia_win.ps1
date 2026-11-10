param(
  [Parameter(Position = 0)][string]$Action = 'dump',
  [string]$Window,
  [string]$Name,
  [string]$Type,
  [int]$Limit = 120
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes

$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$root = [System.Windows.Automation.AutomationElement]::RootElement
$true_cond = [System.Windows.Automation.Condition]::TrueCondition

function Get-TopWindow($el) {
  $cur = $el
  while ($true) {
    $parent = $walker.GetParent($cur)
    if (-not $parent -or $parent -eq $root) { return $cur }
    $cur = $parent
  }
}

if ($Window) {
  $target = $null
  $kids = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $true_cond)
  foreach ($k in $kids) {
    if ($k.Current.Name -like "*$Window*") { $target = $k; break }
  }
  if (-not $target) { throw "no window matching: $Window" }
} else {
  $focused = [System.Windows.Automation.AutomationElement]::FocusedElement
  if (-not $focused) { $focused = $root }
  $target = Get-TopWindow $focused
}

switch ($Action.ToLower()) {

  'count' {
    $n = $target.FindAll([System.Windows.Automation.TreeScope]::Descendants, $true_cond).Count
    "{0} elements in '{1}'" -f $n, $target.Current.Name
  }

  'dump' {
    $all = $target.FindAll([System.Windows.Automation.TreeScope]::Descendants, $true_cond)
    $i = 0
    foreach ($e in $all) {
      if ($i -ge $Limit) { "... truncated at $Limit"; break }
      $c = $e.Current
      if ([string]::IsNullOrWhiteSpace($c.Name) -and [string]::IsNullOrWhiteSpace($c.AutomationId)) { continue }
      if ($Type -and $c.ControlType.ProgrammaticName -notlike "*$Type*") { continue }
      $r = $c.BoundingRectangle
      "{0,3} [{1}] name='{2}' id='{3}' en={4} rect={5},{6} {7}x{8}" -f $i,
        $c.ControlType.ProgrammaticName.Replace('ControlType.', ''), $c.Name, $c.AutomationId,
        $c.IsEnabled, [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height
      $i++
    }
    "matched=$($all.Count)"
  }

  'rect' {
    if (-not $Name) { throw 'need -Name' }
    $cond = New-Object System.Windows.Automation.PropertyCondition(
      [System.Windows.Automation.AutomationElement]::NameProperty, $Name)
    $hit = $target.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
    if (-not $hit) { throw "control not found: $Name" }
    $r = $hit.Current.BoundingRectangle
    "{0},{1},{2},{3}" -f [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height
  }

  default { throw "unknown action: $Action" }
}
