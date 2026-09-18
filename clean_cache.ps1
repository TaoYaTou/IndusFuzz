# IndusFuzz 清除 EXE 缓存脚本
# 清除 ~/.indusfuzz/config.json（包含 last_selection 和 API Key）
# 使 EXE 恢复到未使用状态

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8

$CacheDir = Join-Path $env:USERPROFILE ".indusfuzz"
$CacheFile = Join-Path $CacheDir "config.json"
$ReportsDir = Join-Path $PSScriptRoot "fuzz_agent\reports"

Write-Host "============================================================"
Write-Host "  IndusFuzz 清除 EXE 缓存"
Write-Host "============================================================"
Write-Host ""
Write-Host "  本脚本将执行以下操作："
Write-Host "    1. 显示当前缓存内容摘要"
Write-Host "    2. 询问确认后删除 ~/.indusfuzz/config.json"
Write-Host "    3. 可选清除 reports/ 下的测试报告"
Write-Host ""
$confirm = Read-Host "确认继续？(y=确认 / 其他键=取消)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "  [取消] 用户已取消" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "按回车退出"
    exit 0
}
Write-Host ""

try {
    # 检查缓存是否存在
    if (-not (Test-Path $CacheFile)) {
        Write-Host "  [信息] 当前无缓存文件，EXE 已是未使用状态" -ForegroundColor Green
        Write-Host "  路径: $CacheFile"
        Write-Host ""
    } else {
        # 显示缓存摘要
        Write-Host "  缓存路径: $CacheFile"
        try {
            $cache = Get-Content $CacheFile -Raw | ConvertFrom-Json
        } catch {
            Write-Host "  [警告] 缓存文件解析失败，将直接删除" -ForegroundColor Yellow
            $cache = $null
        }
        Write-Host ""
        Write-Host "  --- 缓存内容摘要 ---"
        if ($cache -and $cache.model) {
            Write-Host "  模型提供商: $($cache.model.provider)"
            Write-Host "  模型名称:   $($cache.model.name)"
            Write-Host "  API 地址:   $($cache.model.base_url)"
            if ($cache.model.api_key_encrypted) {
                Write-Host "  API Key:    [已加密存储]"
            } else {
                Write-Host "  API Key:    [明文 - 建议清除]" -ForegroundColor Yellow
            }
        }
        if ($cache -and $cache.last_selection) {
            Write-Host "  上次选择:   存在 ($($cache.last_selection.protocols.Count) 个协议)"
        }
        Write-Host "  ---"
        Write-Host ""

        # 确认清除
        $confirm = Read-Host "确认清除以上缓存？(y=确认清除 / n=取消)"
        if ($confirm -ne "y" -and $confirm -ne "Y") {
            Write-Host "  [取消] 未清除缓存" -ForegroundColor Yellow
        } else {
            # 执行清除
            Remove-Item $CacheFile -Force
            Write-Host "  [完成] 已删除 config.json" -ForegroundColor Green

            # 可选：清除测试报告
            if (Test-Path $ReportsDir) {
                $reportCount = (Get-ChildItem $ReportsDir -Include *.html,*.pdf,*.log -Recurse -File -ErrorAction SilentlyContinue).Count
                if ($reportCount -gt 0) {
                    $clearReports = Read-Host "是否同时清除 reports/ 下的 $reportCount 个测试报告？(y/n)"
                    if ($clearReports -eq "y" -or $clearReports -eq "Y") {
                        Get-ChildItem $ReportsDir -Include *.html,*.pdf,*.log -Recurse -File | Remove-Item -Force
                        Write-Host "  [完成] 已清除 $reportCount 个测试报告" -ForegroundColor Green
                    }
                }
            }
        }
    }

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  缓存清除完成！EXE 现在为未使用状态" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "  [错误] $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Read-Host "按回车退出"
