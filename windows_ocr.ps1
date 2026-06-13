param(
  [Parameter(Mandatory = $true)]
  [string]$ImagePath
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]

function Wait-WinRt {
  param(
    [Parameter(Mandatory = $true)] $Operation,
    [Parameter(Mandatory = $true)] [Type] $ResultType
  )
  $methods = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
      $_.Name -eq "AsTask" -and
      $_.IsGenericMethodDefinition -and
      $_.GetParameters().Count -eq 1
    }
  $method = $methods[0].MakeGenericMethod($ResultType)
  $task = $method.Invoke($null, @($Operation))
  $task.Wait()
  return $task.Result
}

$fullPath = [System.IO.Path]::GetFullPath($ImagePath)
$file = Wait-WinRt ([Windows.Storage.StorageFile]::GetFileFromPathAsync($fullPath)) ([Windows.Storage.StorageFile])
$stream = Wait-WinRt ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Wait-WinRt ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Wait-WinRt ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$language = [Windows.Globalization.Language]::new("zh-Hans-CN")
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if ($null -eq $engine) {
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if ($null -eq $engine) {
  throw "Windows OCR engine is unavailable."
}

$result = Wait-WinRt ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$lines = @()
foreach ($line in $result.Lines) {
  $lineText = ($line.Words | ForEach-Object { $_.Text }) -join ""
  if (-not [string]::IsNullOrWhiteSpace($lineText)) {
    $lines += $lineText
  }
}

function ConvertTo-CodePoints {
  param([string]$Text)
  $codes = @()
  foreach ($ch in $Text.ToCharArray()) {
    $codes += [int][char]$ch
  }
  return ,$codes
}

$lineCodes = @()
foreach ($line in $lines) {
  $lineCodes += ,(ConvertTo-CodePoints $line)
}

@{
  line_count = $lines.Count
  line_codes = $lineCodes
} | ConvertTo-Json -Depth 4 -Compress | ForEach-Object {
  [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($_))
}
