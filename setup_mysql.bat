@echo off
echo ========================================
echo   MySQL 初始化和数据库创建脚本
echo ========================================
echo.

echo [1/6] 正在初始化 MySQL 数据目录...
"%ProgramFiles%\MySQL\MySQL Server 8.0\bin\mysqld.exe" --initialize-insecure
if %errorlevel% neq 0 (
    echo ❌ 初始化失败！请确保以管理员身份运行此脚本。
    pause
    exit /b 1
)
echo ✅ 数据目录初始化成功
echo.

echo [2/6] 正在安装 MySQL 服务...
"%ProgramFiles%\MySQL\MySQL Server 8.0\bin\mysqld.exe" --install MySQL80
if %errorlevel% neq 0 (
    echo ⚠️ 服务可能已存在，继续...
)
echo ✅ 服务安装完成
echo.

echo [3/6] 正在启动 MySQL 服务...
net start MySQL80
if %errorlevel% neq 0 (
    echo ❌ 启动失败！
    pause
    exit /b 1
)
echo ✅ MySQL 服务启动成功
echo.

echo [4/6] 等待 MySQL 就绪...
timeout /t 3 /nobreak >nul
echo ✅ MySQL 已就绪
echo.

echo [5/6] 正在设置 root 密码为 912419...
"%ProgramFiles%\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '912419'; FLUSH PRIVILEGES;"
if %errorlevel% neq 0 (
    echo ❌ 设置密码失败！
    pause
    exit /b 1
)
echo ✅ root 密码设置成功
echo.

echo [6/6] 正在创建 cnagentos 数据库...
"%ProgramFiles%\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p912419 -e "CREATE DATABASE IF NOT EXISTS cnagentos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; SHOW DATABASES LIKE 'cnagentos';"
if %errorlevel% neq 0 (
    echo ❌ 创建数据库失败！
    pause
    exit /b 1
)
echo.
echo ========================================
echo   🎉 全部完成！
echo ========================================
echo.
echo   MySQL root 密码: 912419
echo   数据库名: cnagentos
echo   端口: 3306
echo.
echo   现在可以访问后台配置数据库了:
echo   http://localhost:10086/admin/database
echo.
pause
