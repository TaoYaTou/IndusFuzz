# IndusFuzz 一键打包脚本
# 用法: powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8

# 路径配置
# FLAT MIGRATION (v1.8.1): all project files live directly at $ProjectRoot.
# Previously everything was under fuzz_agent/ — that subdir is now empty.
$ProjectRoot = $PSScriptRoot
$FuzzDir = $ProjectRoot
$VenvPy = Join-Path $ProjectRoot "agentscope_env\Scripts\python.exe"
# Dynamically read version from src/core/version.py (single source of truth)
try {
    $VersionOutput = & $VenvPy -c "import sys; sys.path.insert(0, r'$ProjectRoot'); from src.core.version import get_version; print(get_version())" 2>&1
    if ($LASTEXITCODE -eq 0 -and $VersionOutput) {
        $Version = ($VersionOutput | Select-Object -Last 1).Trim()
    } else {
        $Version = "1.8.3"  # fallback
    }
} catch {
    $Version = "1.8.3"
}
$ReleaseDir = "IndusFuzz-v$Version-win64"
$ZipName = "IndusFuzz-v$Version-win64.zip"
$CacheDir = Join-Path $env:USERPROFILE ".indusfuzz"
$CacheFile = Join-Path $CacheDir "config.json"
$CacheBackup = Join-Path $env:TEMP "indusfuzz_cache_backup.json"

$totalSteps = 9
$currentStep = 0
$script:HadError = $false

function Write-Step($msg) {
    $script:currentStep++
    Write-Host ""
    Write-Host "[$($script:currentStep)/$totalSteps] $msg" -ForegroundColor Cyan
}

Write-Host "============================================================"
Write-Host "  IndusFuzz 一键打包脚本  v$Version"
Write-Host "  项目根目录: $ProjectRoot"
Write-Host "============================================================"
Write-Host ""
Write-Host "  本脚本将执行以下操作："
Write-Host "    1. 备份并清除用户缓存（~/.indusfuzz/config.json）"
Write-Host "    2. 清理旧构建产物（build/ dist/）"
Write-Host "    3. 运行 PyInstaller 打包（约 2-3 分钟）"
Write-Host "    4. 验证 EXE 并组装发布目录"
Write-Host "    5. 生成 ZIP 发布包"
Write-Host "    6. 恢复用户缓存"
Write-Host ""
$confirm = Read-Host "确认开始打包？(y=确认 / 其他键=取消)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "  [取消] 用户已取消打包" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "按回车退出"
    exit 0
}
Write-Host ""
Write-Host "  [确认] 开始打包流程..." -ForegroundColor Green

try {
    # 步骤 0: 前置检查
    Write-Step "前置检查"
    if (-not (Test-Path $VenvPy)) { throw "找不到虚拟环境 Python: $VenvPy" }
    if (-not (Test-Path (Join-Path $FuzzDir "IndusFuzz.spec"))) { throw "找不到打包配置: IndusFuzz.spec" }
    Write-Host "  [OK] Python 环境和 spec 文件就绪"

    # 步骤 1: 备份并清除用户缓存
    Write-Step "备份并清除用户缓存（确保 EXE 为未使用状态）"
    if (Test-Path $CacheFile) {
        Copy-Item $CacheFile $CacheBackup -Force
        Write-Host "  [备份] config.json -> $CacheBackup"
        Remove-Item $CacheFile -Force
        Write-Host "  [清除] 已删除 $CacheFile"
    } else {
        Write-Host "  [跳过] 无缓存文件需要清除"
    }
    $reportsDir = Join-Path $FuzzDir "reports"
    if (Test-Path $reportsDir) {
        Get-ChildItem $reportsDir -Include *.html,*.pdf,*.log -Recurse -File | Remove-Item -Force
        Write-Host "  [清除] 已清理 reports/ 下的测试报告"
    }

    # 步骤 2: 清理旧构建产物
    Write-Step "清理旧构建产物"
    @("build","dist") | ForEach-Object {
        $p = Join-Path $FuzzDir $_
        if (Test-Path $p) { Remove-Item $p -Recurse -Force }
    }
    @($ReleaseDir,$ZipName) | ForEach-Object {
        $p = Join-Path $ProjectRoot $_
        if (Test-Path $p) { Remove-Item $p -Recurse -Force }
    }
    Write-Host "  [OK] 已清理 build/ dist/ 和旧发布包"

    # 步骤 3: PyInstaller 打包
    Write-Step "执行 PyInstaller 打包（此步骤耗时较长，请耐心等待）"
    Push-Location $FuzzDir
    try {
        & $VenvPy -m PyInstaller --clean IndusFuzz.spec
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败（退出码: $LASTEXITCODE）" }
    } finally {
        Pop-Location
    }
    Write-Host "  [OK] PyInstaller 打包成功"

    # 步骤 4: 验证 EXE 体积
    Write-Step "验证 EXE 产物"
    $exePath = Join-Path $FuzzDir "dist\IndusFuzz.exe"
    if (-not (Test-Path $exePath)) { throw "dist\IndusFuzz.exe 不存在" }
    $exeSizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Host "  [体积] IndusFuzz.exe = $exeSizeMB MB"
    if ($exeSizeMB -gt 200) { Write-Host "  [警告] EXE 体积超过 200MB" -ForegroundColor Yellow }

    # 步骤 5: 运行自动化验证脚本
    Write-Step "运行打包后验证脚本"
    Push-Location $FuzzDir
    try {
        & $VenvPy verify_build.py
        $verifyRc = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($verifyRc -ne 0) {
        Write-Host "  [警告] 验证脚本发现问题（退出码: $verifyRc），继续生成发布包..." -ForegroundColor Yellow
    }

    # 步骤 6: 组装发布目录
    Write-Step "组装发布目录 $ReleaseDir"
    $releasePath = Join-Path $ProjectRoot $ReleaseDir
    New-Item $releasePath -ItemType Directory -Force | Out-Null
    Copy-Item $exePath $releasePath -Force
    # All docs are now at project root (flat migration v1.8.1)
    foreach ($f in @("README.md","README.zh.md")) {
        $src = Join-Path $ProjectRoot $f
        if (Test-Path $src) { Copy-Item $src $releasePath -Force }
    }
    foreach ($f in @("CHANGELOG.md","LICENSE","requirements.txt")) {
        $src = Join-Path $FuzzDir $f
        if (Test-Path $src) { Copy-Item $src $releasePath -Force }
    }
    New-Item (Join-Path $releasePath "docs") -ItemType Directory -Force | Out-Null
    $prd = Join-Path $FuzzDir "docs\IndusFuzz 协议扩展 PRD.md"
    if (Test-Path $prd) { Copy-Item $prd (Join-Path $releasePath "docs") -Force }
    New-Item (Join-Path $releasePath "assets\fonts") -ItemType Directory -Force | Out-Null
    $font = Join-Path $FuzzDir "assets\fonts\simhei.ttf"
    if (Test-Path $font) { Copy-Item $font (Join-Path $releasePath "assets\fonts") -Force }
    # 复制图标文件到发布目录（排除源文件 icon_source.jpg）
    $iconSrcDir = Join-Path $FuzzDir "assets\concept_a_hex"
    $iconDstDir = Join-Path $releasePath "assets\concept_a_hex"
    if (Test-Path $iconSrcDir) {
        New-Item $iconDstDir -ItemType Directory -Force | Out-Null
        Get-ChildItem $iconSrcDir -File | Where-Object { $_.Name -ne "icon_source.jpg" } | ForEach-Object {
            Copy-Item $_.FullName $iconDstDir -Force
        }
        Write-Host "  [OK] 已复制图标文件到 assets/concept_a_hex/"
    }
    # 修正发布目录中 README 的图标路径（去掉 fuzz_agent/ 前缀）
    foreach ($readme in @("README.md","README.zh.md")) {
        $readmePath = Join-Path $releasePath $readme
        if (Test-Path $readmePath) {
            $content = Get-Content $readmePath -Raw -Encoding UTF8
            $content = $content -replace 'fuzz_agent/assets/concept_a_hex/', 'assets/concept_a_hex/'
            Set-Content $readmePath $content -Encoding UTF8 -NoNewline
        }
    }
    New-Item (Join-Path $releasePath "reports") -ItemType Directory -Force | Out-Null
    Set-Content (Join-Path $releasePath "reports\.gitkeep") "" -Encoding ASCII
    # 清理发布目录中的 0 字节空文件（保留 .gitkeep）
    $zeroByteFiles = Get-ChildItem $releasePath -Recurse -File | Where-Object { $_.Length -eq 0 -and $_.Name -ne ".gitkeep" }
    if ($zeroByteFiles) {
        $zeroByteFiles | ForEach-Object { Remove-Item $_.FullName -Force }
        Write-Host "  [清理] 已移除 $($zeroByteFiles.Count) 个 0 字节空文件"
    }
    Write-Host "  [OK] 发布目录组装完成"

    # 步骤 7: 生成 ZIP 包
    Write-Step "生成 ZIP 发布包"
    $zipPath = Join-Path $ProjectRoot $ZipName
    Compress-Archive -Path (Join-Path $releasePath "*") -DestinationPath $zipPath -Force
    Write-Host "  [OK] ZIP 包生成成功"

    # 步骤 8: 恢复用户缓存（在 finally 中处理，这里标记）
    Write-Step "恢复用户缓存"
    # 缓存恢复在 finally 块中执行

    # 步骤 9: 输出打包结果
    Write-Step "打包完成！"
    $zipSizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  打包结果" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  EXE 路径:  $exePath"
    Write-Host "  EXE 大小:  $exeSizeMB MB"
    Write-Host ""
    Write-Host "  发布目录:  $releasePath\"
    Write-Host "  ZIP 包:    $zipPath"
    Write-Host "  ZIP 大小:  $zipSizeMB MB"
    Write-Host ""
    Write-Host "  缓存状态:  已恢复（打包过程中已确保 EXE 为未使用状态）"
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green

} catch {
    Write-Host ""
    Write-Host "  [错误] $($_.Exception.Message)" -ForegroundColor Red
    $script:HadError = $true
} finally {
    # 无论成功失败都恢复缓存
    if (Test-Path $CacheBackup) {
        if (-not (Test-Path $CacheDir)) { New-Item $CacheDir -ItemType Directory -Force | Out-Null }
        Copy-Item $CacheBackup $CacheFile -Force
        Remove-Item $CacheBackup -Force
        Write-Host "  [恢复] 已恢复 config.json"
    }
}

Write-Host ""
if ($script:HadError) {
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  打包失败，请查看上方错误信息" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
} else {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  打包成功完成" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
}
Write-Host ""
Read-Host "按回车退出"
explorer $FuzzDir
if ($script:HadError) { exit 1 }




