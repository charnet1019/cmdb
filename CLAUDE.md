# CMDB Configuration Management Database

## 技术栈

### 后端
- **框架**: Python 3.11+ / FastAPI
- **数据库**: PostgreSQL 15+
- **缓存**: Redis 7+
- **数据库版本管理**: Alembic
- **ORM**: SQLAlchemy 2.0

### 前端
- **框架**: TypeScript / Vue 3
- **UI组件库**: Ant Design Vue 4.x
- **构建工具**: Vite
- **状态管理**: Pinia
- **路由**: Vue Router 4

## 开发环境

### 数据库配置
- **PostgreSQL**: `127.0.0.1:5432`
- **数据库名**: `cmdb`
- **用户名**: `navi`
- **密码**: `uy7YGp4bqwljX5N`

### Redis配置
- **地址**: `127.0.0.1:6379`
- **密码**: `EgYGGE6GqDgAJU8dSWkY`

### 环境说明
- 开发环境运行在 Windows WSL2 中
- PostgreSQL 和 Redis 通过 docker-compose 运行在本机

## 项目结构

```
cmdb/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── models/         # 数据库模型
│   │   ├── schemas/        # Pydantic模型
│   │   ├── services/       # 业务逻辑
│   │   ├── core/           # 核心配置
│   │   └── utils/          # 工具函数
│   ├── alembic/            # 数据库迁移
│   ├── tests/              # 测试代码
│   └── requirements.txt
├── frontend/                # 前端代码
│   ├── src/
│   │   ├── api/            # API调用
│   │   ├── components/     # 组件
│   │   ├── layouts/        # 布局组件
│   │   ├── router/         # 路由配置
│   │   ├── stores/         # Pinia状态
│   │   ├── types/          # TypeScript类型
│   │   └── views/          # 页面视图
│   └── package.json
└── prototype/              # 原型设计文件
```

## 核心功能模块

### 1. 认证模块
- 用户登录/登出
- JWT Token认证
- 权限验证

### 2. 仪表盘
- 资产统计概览
- 用户统计概览
- 资产类型分布
- 在线用户列表

### 3. 资产管理
- 资产树导航
- 资产CRUD
- 资产分组
- 资产凭证管理

### 4. 用户管理
- 用户CRUD
- 用户组管理
- MFA支持

### 5. 权限管理
- 资产授权
- 权限类型控制
- 有效期管理

### 6. 日志审计
- 登录日志
- 操作日志
- 改密日志

## API 配置

### 后端服务
- **端口**: `8000`
- **API前缀**: `/api/v1`
- **认证方式**: JWT Bearer Token
- **文档地址**: `http://localhost:8000/docs` (Swagger UI)

## 安全机制

### 凭证加密
- **加密算法**: Fernet (对称加密)
- **密钥存储**: 环境变量 `ENCRYPTION_KEY`
- **加密范围**: 所有资产凭证 (用户名、密码、API Key、Secret)

### 密码策略
- **哈希算法**: bcrypt (cost factor: 12)
- **复杂度要求**: 可配置 (大小写字母、数字、特殊字符)
- **最小长度**: 8-32 字符 (可配置)
- **历史检查**: 不可与最近 3 次密码重复

### 权限控制
- **认证**: JWT Token (有效期 24 小时)
- **授权**: 基于资源的权限控制 (RBAC)
- **权限类型**: 查看资产、管理资产、用户管理、系统设置、日志审计、查看/复制密码、管理凭证

## 资产类型说明

### 主机 (Host)
- **地址格式**: IP、IP:端口、主机名、主机名:端口
- **平台**: Linux、Unix、Windows
- **凭证**: 多个用户名/密码对
- **备注**: 支持全文搜索

### 网络设备 (Network)
- **地址格式**: IP 地址
- **设备类型**: 交换机、路由器、防火墙、无线控制器
- **厂商**: Cisco、Huawei、Aruba 等
- **凭证**: 管理账号 + SNMP v3

### 数据库 (Database)
- **地址格式**: IP:端口
- **数据库类型**: MySQL、PostgreSQL、MongoDB、Redis
- **凭证**: 多个账号 (admin、readonly 等)

### 云服务 (Cloud)
- **平台**: AWS、阿里云、腾讯云、Azure
- **凭证**: AKID/Secret、RAM-User、SecretId/SecretKey
- **资源 ID**: 云资源唯一标识

### Web 应用 (Web)
- **URL**: 完整访问地址
- **凭证**: 登录用户名/密码

### GPT 服务 (GPT)
- **平台**: OpenAI、Claude、ChatGLM、通义千问
- **凭证**: API Key
- **URL**: API 端点地址

## 设计规范

参考 `prototype/nexus_infrastructure/DESIGN.md`:
- **无边界设计**: 使用背景色层级而非1px边框
- **色调层级**: surface → surface_container_low → surface_container_lowest
- **玻璃效果**: 浮动元素使用 backdrop-blur + 半透明
- **字体**: Manrope (标题) + Inter (正文)
- **主色调**: Primary #005daa, Primary Container #0075d5
- **图标**: Material Symbols Outlined
- **圆角**: 4px/8px/12px/9999px

## 开发规范

### 详细开发计划
参考 `docs/DETAILED_DEVELOPMENT_PLAN.md` (v2.2):
- 完整数据库设计 (11 张核心表)
- API 接口定义 (RESTful 规范)
- 前端组件设计 (Vue 3 Composition API)
- 权限控制矩阵
- 测试用例设计

### 代码规范
- **后端**: PEP 8 (Python)、类型注解、异步优先
- **前端**: ESLint + Prettier、TypeScript strict mode
- **提交**: Conventional Commits 格式
- **测试覆盖率**: 最低 80%

### 测试策略
- **单元测试**: pytest (后端)、Vitest (前端)
- **集成测试**: API 端点测试、数据库操作测试
- **E2E 测试**: Playwright (关键用户流程)

## 开发工作流

1. **需求分析** - 参考原型页面和开发计划
2. **数据库设计** - 使用 Alembic 创建迁移
3. **后端开发** - FastAPI 路由 + 服务层 + 测试
4. **前端开发** - Vue 组件 + API 集成 + 测试
5. **集成测试** - 端到端测试关键流程
6. **代码审查** - 安全检查 + 性能优化

## 参考文档

- **原型分析**: `docs/PROTOTYPE_ANALYSIS_SUMMARY.md`
- **开发计划**: `docs/DETAILED_DEVELOPMENT_PLAN.md`
- **设计系统**: `prototype/nexus_infrastructure/DESIGN.md`