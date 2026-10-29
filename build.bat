@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo  GoGauge Windows 打包 (PyInstaller 单文件 exe)
echo ============================================
echo.

echo [1/2] 安装锁定依赖...
rem 必须用全量 lock: 裸装 requirements.txt 会随上游漂移 (pythonnet/.NET 桥事故的教训)
python -m pip install -q -r requirements-windows.lock.txt || goto :err

echo [2/2] 构建 dist\GoGauge.exe ...
rem 所有 PyInstaller 参数与 _build_info.py 生成统一在 scripts/build.py
python scripts\build.py --platform windows %* || goto :err

echo.
echo 完成! 输出: dist\GoGauge.exe
exit /b 0

:err
echo.
echo 打包失败, 请检查上方错误信息
exit /b 1
