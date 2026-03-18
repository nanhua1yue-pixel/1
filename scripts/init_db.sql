-- 采购补货决策系统 - 数据库初始化脚本
-- 在宝塔面板MySQL中执行

CREATE DATABASE IF NOT EXISTS purchase_decision
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'purchase_system'@'localhost' IDENTIFIED BY 'PurchaseSystem@2026';
GRANT ALL PRIVILEGES ON purchase_decision.* TO 'purchase_system'@'localhost';
FLUSH PRIVILEGES;

USE purchase_decision;

-- 表结构由 Flask-SQLAlchemy 自动创建 (db.create_all())
-- 首次启动应用时会自动建表
