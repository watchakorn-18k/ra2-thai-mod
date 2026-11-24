param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("Install", "Uninstall")]
    [string]$Mode
)

$ErrorActionPreference = "Stop"
$ModDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FilesDir = Join-Path $ModDir "files"
$ManifestPath = Join-Path $ModDir "manifest.json"
$Manifest = Get-Content -Path $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

# Resolve game directory (supports placing mod folder inside game dir or subfolder)
$GameDir = $null
$candidate = $ModDir
for ($i = 0; $i -lt 4; $i++) {
    if ((Test-Path (Join-Path $candidate "gamemd.exe")) -or (Test-Path (Join-Path $candidate "game.exe"))) {
        $GameDir = $candidate
        break
    }
    $parent = Split-Path -Parent $candidate
    if (-not $parent -or $parent -eq $candidate) { break }
    $candidate = $parent
}

if (-not $GameDir) {
    Write-Host "[ERROR] ไม่พบไฟล์เกม (gamemd.exe / game.exe) กรุณาแตกไฟล์ม็อดไว้ในโฟลเดอร์เกม Red Alert 2" -ForegroundColor Red
    exit 1
}

$running = Get-Process -Name "gamemd","game","RA2MD","Ra2","YURI" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "[ERROR] กรุณาปิดเกม Red Alert 2 / Yuri's Revenge ก่อนดำเนินการ" -ForegroundColor Red
    exit 1
}

$BackupDir = Join-Path $GameDir "Ra2ThaiMod_Backup"
$TargetFiles = @("GAME.FNT", "ra2md.csf", "ra2.csf", "ddraw.dll", "ddraw.ini")

if ($Mode -eq "Install") {
    Write-Host "=== ติดตั้งม็อดภาษาไทย Red Alert 2 & Yuri's Revenge (v$($Manifest.version)) ===" -ForegroundColor Cyan
    Write-Host "เครดิตผู้พัฒนา: $($Manifest.credit)" -ForegroundColor Gray
    Write-Host "โฟลเดอร์เกม: $GameDir"

    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir | Out-Null
    }

    $state = @{}
    foreach ($f in $TargetFiles) {
        $dst = Join-Path $GameDir $f
        $bak = Join-Path $BackupDir $f
        $src = Join-Path $FilesDir $f

        # Verify source mod file hash
        $srcHash = (Get-FileHash -Path $src -Algorithm SHA256).Hash.ToLower()
        $expectedHash = $Manifest.files.$f.sha256.ToLower()
        if ($srcHash -ne $expectedHash) {
            Write-Host "[ERROR] ไฟล์ม็อด $f เสียหายหรือแฮชไม่ตรง ($srcHash != $expectedHash)" -ForegroundColor Red
            exit 1
        }

        if (Test-Path $dst) {
            $dstHash = (Get-FileHash -Path $dst -Algorithm SHA256).Hash.ToLower()
            if ($dstHash -ne $expectedHash -and -not (Test-Path $bak)) {
                Copy-Item -Path $dst -Destination $bak -Force
                $state[$f] = "restored_from_backup"
            } elseif (Test-Path $bak) {
                $state[$f] = "restored_from_backup"
            } else {
                $state[$f] = "already_modded"
            }
        } else {
            if (-not (Test-Path $bak)) {
                $state[$f] = "remove_on_uninstall"
            } else {
                $state[$f] = "restored_from_backup"
            }
        }

        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "  [OK] ติดตั้ง $f" -ForegroundColor Green
    }

    $statePath = Join-Path $BackupDir "backup_state.json"
    if (-not (Test-Path $statePath)) {
        $state | ConvertTo-Json | Set-Content -Path $statePath -Encoding UTF8
    }

    Write-Host "`nติดตั้งม็อดภาษาไทยสำเร็จ! สามารถเปิดเกมเล่นได้ทันที" -ForegroundColor Green
}
elseif ($Mode -eq "Uninstall") {
    Write-Host "=== ถอนการติดตั้งม็อดภาษาไทย Red Alert 2 & Yuri's Revenge ===" -ForegroundColor Yellow
    $statePath = Join-Path $BackupDir "backup_state.json"
    $state = $null
    if (Test-Path $statePath) {
        $state = Get-Content -Path $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    }

    foreach ($f in $TargetFiles) {
        $dst = Join-Path $GameDir $f
        $bak = Join-Path $BackupDir $f
        if (Test-Path $bak) {
            Copy-Item -Path $bak -Destination $dst -Force
            Write-Host "  [OK] คืนค่าไฟล์เดิม $f" -ForegroundColor Green
        } elseif ($state -and $state.$f -eq "remove_on_uninstall" -and (Test-Path $dst)) {
            Remove-Item -Path $dst -Force
            Write-Host "  [OK] ลบไฟล์ม็อด $f" -ForegroundColor Green
        }
    }
    Write-Host "`nถอนการติดตั้งเรียบร้อยแล้ว" -ForegroundColor Green
}
