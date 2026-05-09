# CMDB Backend - 数据库运维指南

## 环境准备

### 激活虚拟环境
```bash
# 进入后端目录
cd /home/tim/workspace/cmdb/backend

# 激活虚拟环境
source venv/bin/activate
```

## 数据库迁移

### 查看当前迁移状态
```bash
alembic current
```

### 升级到最新迁移
```bash
# 激活虚拟环境并执行迁移
source venv/bin/activate && alembic upgrade head
```

### 创建新迁移
```bash
# 创建新迁移文件
alembic revision -m "描述迁移内容"

# 生成迁移文件后，编辑 alembic/versions/ 下的最新文件
```

### 回滚迁移
```bash
# 回滚到指定版本
alembic downgrade <revision_id>

# 回滚一个版本
alembic downgrade -1
```

## 常用命令

```bash
# 查看迁移历史
alembic history

# 查看迁移差异（需要安装 alembic-autoapi）
alembic autogenerate -m "自动生成的迁移"
```

## 注意事项

1. **必须先激活虚拟环境**：`alembic` 命令在虚拟环境中，执行迁移前必须激活
2. **迁移顺序**：确保按顺序执行迁移，不要跳过版本
3. **备份**：执行迁移前建议备份数据库
4. **生产环境**：生产环境执行迁移前请先在测试环境验证

## 快速参考

| 操作 | 命令 |
|------|------|
| 激活环境 | `source venv/bin/activate` |
| 升级到最新 | `alembic upgrade head` |
| 查看当前版本 | `alembic current` |
| 创建迁移 | `alembic revision -m "描述"` |
| 回滚一步 | `alembic downgrade -1` |
