param(
    [string]$LauncherPath = "D:\FILE_GAME\Ra2\RA2MD.exe",
    [string]$TargetProcess = "gamemd",
    [string]$OutputPath = "D:\FILE_GAME\Ra2\ThaiPatch\evidence\test-menu.png",
    [int]$WaitSeconds = 8
)

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinCap3 {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern IntPtr GetWindowDC(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr hWnd, IntPtr hDC);
    [DllImport("gdi32.dll")] public static extern bool BitBlt(IntPtr hdcDest, int xDest, int yDest, int w, int h, IntPtr hdcSrc, int xSrc, int ySrc, int rop);
}
"@

Start-Process -FilePath $LauncherPath -WorkingDirectory (Split-Path $LauncherPath) | Out-Null
Start-Sleep -Seconds $WaitSeconds

$gp = Get-Process -Name $TargetProcess -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1
if (-not $gp) {
    Write-Host "No window found for $TargetProcess"
} else {
    $hwnd = $gp.MainWindowHandle
    $rect = New-Object WinCap3+RECT
    [WinCap3]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
    $w = [Math]::Max(1, $rect.Right - $rect.Left)
    $h = [Math]::Max(1, $rect.Bottom - $rect.Top)
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdcDest = $g.GetHdc()
    $hdcSrc = [WinCap3]::GetWindowDC($hwnd)
    [WinCap3]::BitBlt($hdcDest, 0, 0, $w, $h, $hdcSrc, 0, 0, 0x00CC0020) | Out-Null
    [WinCap3]::ReleaseDC($hwnd, $hdcSrc) | Out-Null
    $g.ReleaseHdc($hdcDest)
    $bmp.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    Write-Host "Captured ${w}x${h} ($($gp.MainWindowTitle)) to $OutputPath"
}

Get-Process gamemd,RA2MD,game,Ra2 -ErrorAction SilentlyContinue | Stop-Process -Force
