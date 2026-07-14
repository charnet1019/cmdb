# CMDB 部署说明

本文档说明如何使用 Docker Compose 或 Kubernetes 部署 CMDB。

## 服务与镜像

| 组件 | 镜像名 | 服务名 | 说明 |
| --- | --- | --- | --- |
| 前端 | `cmdb-frontend:latest` | `cmdb-frontend` | Nginx 托管静态文件，并反向代理 `/api` 与 `/uploads` |
| 后端 | `cmdb-backend:latest` | `cmdb-backend` | FastAPI 服务，启动时自动执行数据库迁移和初始化 |
| 数据库 | `postgres:16-alpine` | `postgres` | PostgreSQL |
| 缓存 | `redis:7-alpine` | `redis` | Redis 会话、在线状态和事件推送 |

## Docker Compose 部署

在项目根目录执行：

```bash
docker compose up -d
```

默认访问地址：

```text
前端: http://localhost
后端: http://localhost:8000
健康检查: http://localhost:8000/health
```

如需调整端口或初始密码，可在启动前设置环境变量：

```bash
FRONTEND_PORT=8080 \
BACKEND_PORT=18000 \
CMDB_INITIAL_ADMIN_PASSWORD='YourStrongPassword123' \
JWT_SECRET_KEY='replace-with-a-long-random-secret' \
ENCRYPTION_KEY='replace-with-a-long-random-encryption-key' \
docker compose up -d
```

查看服务状态：

```bash
docker compose ps
docker compose logs -f cmdb-backend
```

停止服务：

```bash
docker compose down
```

如需同时删除数据库、Redis 和上传文件卷：

```bash
docker compose down -v
```

## Kubernetes 部署

部署前请确保集群可以拉取或已加载以下镜像：

```text
cmdb-frontend:latest
cmdb-backend:latest
postgres:16-alpine
redis:7-alpine
```

在项目根目录执行：

```bash
kubectl apply -f k8s/
```

默认资源部署在 `cmdb` Namespace：

```bash
kubectl get pods -n cmdb
kubectl get svc -n cmdb
```

默认前端 Service 使用 NodePort：

```text
cmdb-frontend: NodePort 30080
```

访问方式取决于集群环境，常见地址为：

```text
http://<node-ip>:30080
```

查看后端日志：

```bash
kubectl logs -n cmdb deploy/cmdb-backend -f
```

删除部署：

```bash
kubectl delete -f k8s/
```

## 默认账号

首次初始化会创建默认管理员：

```text
用户名: admin
密码: ChangeMe123
```

首次登录后系统会要求修改密码。

可通过以下变量修改初始管理员密码：

```text
CMDB_INITIAL_ADMIN_PASSWORD
```

注意：该变量只在第一次创建 `admin` 用户时生效。如果数据库中已存在 `admin` 用户，后续修改该变量不会重置密码。

## 自动初始化说明

后端应用启动生命周期中会自动执行：

1. Alembic 数据库迁移到最新版本。
2. 默认系统设置初始化。
3. 默认管理员用户和管理员组初始化。

因此，正常情况下不需要手动执行迁移或种子脚本。只要 Postgres 和 Redis 可用，`cmdb-backend` 启动后会自动完成初始化。

## 数据持久化

Docker Compose 使用以下命名卷：

| 卷 | 用途 |
| --- | --- |
| `postgres-data` | PostgreSQL 数据 |
| `redis-data` | Redis 数据 |
| `backend-uploads` | 后端上传文件 |

Kubernetes 使用以下 PVC：

| PVC | 用途 |
| --- | --- |
| `postgres-data` | PostgreSQL 数据 |
| `redis-data` | Redis 数据 |
| `backend-uploads` | 后端上传文件 |

删除卷或 PVC 会导致对应数据丢失。

## 生产环境注意事项

上线前必须修改以下默认值：

```text
POSTGRES_PASSWORD
JWT_SECRET_KEY
ENCRYPTION_KEY
CMDB_INITIAL_ADMIN_PASSWORD
```

`ENCRYPTION_KEY` 用于加密资产凭据等敏感数据。系统投入使用后不要随意更换，否则历史加密数据可能无法解密。

建议使用 Fernet 格式密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

同时建议：

- 使用外部托管数据库或配置数据库备份。
- 为前端配置正式域名和 HTTPS。
- 将 Kubernetes Secret 替换为集群内的密钥管理方案。
- 根据实际访问域名调整 `CORS_ORIGINS`。
- 不要在生产环境继续使用默认 NodePort、默认密码或示例 Secret。

## 常见问题

### 后端没有完成初始化

先查看后端日志：

```bash
docker compose logs -f cmdb-backend
```

或：

```bash
kubectl logs -n cmdb deploy/cmdb-backend -f
```

重点检查：

- `DATABASE_URL` 是否正确。
- Postgres 是否健康。
- Redis 是否可连接。
- `JWT_SECRET_KEY` 和 `ENCRYPTION_KEY` 是否已设置。

### Kubernetes Pod 拉取镜像失败

`k8s/cmdb.yaml` 默认使用：

```text
cmdb-frontend:latest
cmdb-backend:latest
```

请先将镜像推送到集群可访问的镜像仓库，或将镜像加载到本地集群节点，然后按实际镜像地址修改清单中的 `image` 字段。
