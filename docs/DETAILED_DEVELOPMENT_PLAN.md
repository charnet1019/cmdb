# CMDB 详细开发规划文档

## 文档信息
- **项目名称**: CMDB (Configuration Management Database)
- **设计理念**: The Digital Architect - 无边界设计系统
- **创建日期**: 2026-03-26
- **版本**: v2.0 (详细版)

---

## 一、菜单结构与页面映射

### 1.1 完整菜单层级

```
CMDB
├── 仪表盘 (Dashboard)
├── 资产管理 (Asset Management)
│   └── 资产列表 (Asset List)
├── 用户管理 (User Management)
│   ├── 用户 (Users)
│   └── 用户组 (User Groups)
├── 权限管理 (Permission Management)
│   └── 资产授权 (Asset Authorization)
├── 日志审计 (Audit Logs)
│   ├── 登录日志 (Login Logs)
│   ├── 操作日志 (Operation Logs)
│   └── 改密日志 (Password Change Logs)
└── 系统设置 (System Settings)
```

---

## 二、页面详细分析

### 2.1 登录页面 (Login Page)

**原型文件**: `prototype/cmdb/code.html`

#### 布局结构
```
┌─────────────────────────────────────────────────────────┐
│  左侧视觉区 (50%)        │  右侧表单区 (50%)          │
│  ─────────────────────   │  ────────────────────────   │
│  • 背景: primary-container│  • 欢迎回来                │
│  • 径向网格装饰          │  • 语言切换 (右上角)        │
│  • 玻璃效果 Logo 容器    │  • 用户名输入框            │
│  • CMDB 标题             │    - 左侧 person 图标      │
│  • 标语文案              │  • 密码输入框              │
│  • 抽象技术图形          │    - 左侧 lock 图标        │
│  • 底部品牌标识          │    - 右侧可见性切换        │
│                          │  • 记住该设备 (checkbox)    │
│                          │  • 立即登录按钮 (渐变)      │
│                          │  • 忘记密码链接            │
│                          │  • 底部链接 (安全策略/服务条款)│
└─────────────────────────────────────────────────────────┘
```

#### 字段清单
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| username | string | 是 | 用户名或邮箱 |
| password | string | 是 | 密码 |
| remember | boolean | 否 | 记住设备 |

#### 设计规范
- **左侧背景**: `bg-primary-container` + 径向渐变网格 (20% opacity)
- **Logo 容器**: `bg-white/10 backdrop-blur-xl border border-white/20 rounded-full p-8`
- **输入框**: `bg-surface-container-lowest rounded-xl px-4 py-3.5`
- **登录按钮**: `bg-gradient-to-r from-primary to-primary-container rounded-xl shadow-lg shadow-primary/20`
- **响应式**: 移动端隐藏左侧，表单全屏

#### API 接口
```
POST /api/v1/auth/login
Request: {
  "username": "admin",
  "password": "password123",
  "remember": true
}
Response: {
  "code": 0,
  "message": "success",
  "data": {
    "token": "eyJhbGc...",
    "user": {
      "id": 1,
      "username": "admin",
      "full_name": "管理员",
      "email": "admin@example.com"
    },
    "expires_at": "2024-03-27T07:52:15Z"
  }
}
```

---

### 2.2 仪表盘页面 (Dashboard)

**原型文件**: `prototype/simplified/code.html`

#### 布局结构
```
┌──────────────────────────────────────────────────────────┐
│  TopNavBar (h-16, 固定顶部)                              │
├────────┬─────────────────────────────────────────────────┤
│        │  页面标题: 仪表盘                                │
│        ├─────────────────────────────────────────────────┤
│ Side   │  统计卡片区 (4列网格)                            │
│ Nav    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────┐│
│ Bar    │  │资产总数  │ │用户总数  │ │在线用户  │ │告警 ││
│ (w-60) │  │  1,247   │ │   156    │ │   23     │ │  5  ││
│        │  └──────────┘ └──────────┘ └──────────┘ └─────┘│
│        │                                                  │
│        │  图表区域 (2列网格)                              │
│        │  ┌─────────────────────┐ ┌──────────────────┐  │
│        │  │ 资产类型分布 (饼图) │ │ 最近登录用户列表 │  │
│        │  │ - 主机: 450         │ │ - 张伟 15:30     │  │
│        │  │ - 网络设备: 120     │ │ - 李娜 14:22     │  │
│        │  │ - 数据库: 89        │ │ - 王强 13:45     │  │
│        │  │ - 云服务: 234       │ │                  │  │
│        │  │ - Web: 298          │ │                  │  │
│        │  │ - GPT: 56           │ │                  │  │
│        │  └─────────────────────┘ └──────────────────┘  │
└────────┴─────────────────────────────────────────────────┘
```

#### 统计卡片字段
| 卡片名称 | 数据字段 | 说明 |
|---------|---------|------|
| 资产总数 | total_assets | 所有资产数量 |
| 用户总数 | total_users | 所有用户数量 |
| 在线用户 | online_users | 当前在线用户数 |
| 告警数量 | alerts | 待处理告警数 |

#### 设计规范
- **统计卡片**: `bg-surface-container-lowest rounded-xl shadow-sm p-6`
- **大数字**: `text-3xl font-bold font-headline text-on-surface`
- **标签**: `text-xs font-semibold text-on-surface-variant uppercase`
- **图标容器**: `w-12 h-12 rounded-full bg-gradient-to-br from-primary to-primary-container`

#### API 接口
```
GET /api/v1/dashboard/stats
Response: {
  "code": 0,
  "data": {
    "total_assets": 1247,
    "total_users": 156,
    "online_users": 23,
    "alerts": 5,
    "asset_type_distribution": [
      {"type": "主机", "count": 450},
      {"type": "网络设备", "count": 120},
      {"type": "数据库", "count": 89},
      {"type": "云服务", "count": 234},
      {"type": "Web", "count": 298},
      {"type": "GPT", "count": 56}
    ],
    "recent_logins": [
      {"user": "张伟", "time": "2024-03-26 15:30:22", "ip": "192.168.1.100"},
      {"user": "李娜", "time": "2024-03-26 14:22:15", "ip": "192.168.1.101"}
    ]
  }
}
```

---


### 2.3 资产列表页面 (Asset List)

**原型文件**: `prototype/expanded_sidebar_navigation/code.html`, `prototype/_2/code.html` (主机), `prototype/_3/code.html` (网络设备), `prototype/url/code.html` (云服务)

#### 布局结构
```
┌──────────────────────────────────────────────────────────┐
│  TopNavBar (h-16, 固定)                                  │
├────────┬─────────────────────────────────────────────────┤
│        │  标题栏: 资产列表 + 返回按钮                     │
│        ├─────────────────────────────────────────────────┤
│        │  分类标签页 (水平滚动)                           │
│ Side   │  [所有] [主机] [网络设备] [数据库] [云服务] [Web] [GPT]│
│ Nav    ├────────┬────────────────────────────────────────┤
│        │ 资产树 │  操作栏                                │
│        │ (w-60) │  [创建] [更多操作▼] [标签] [搜索] [工具图标]│
│        │        ├────────────────────────────────────────┤
│        │ 资产树/│  数据表格                              │
│        │ 类型树 │  ┌──┬────┬────┬────┬────────┬────┐   │
│        │ 切换   │  │☑│名称│地址│平台│用户名密码│操作│   │
│        │        │  ├──┼────┼────┼────┼────────┼────┤   │
│        │        │  │☐│A800│IP  │OS  │凭证列表│更新│   │
└────────┴────────┴──┴──┴────┴────┴────────┴────┘   │
```

#### 分类标签页
| 标签 | 图标 | 说明 |
|------|------|------|
| 所有 | menu | 显示所有类型资产 |
| 主机 | dns | Linux/Windows 服务器 |
| 网络设备 | router | 交换机/路由器/防火墙 |
| 数据库 | database | MySQL/PostgreSQL/Oracle |
| 云服务 | cloud | AWS/阿里云/腾讯云 |
| Web | public | Web 应用/网站 |
| GPT | psychology | AI 服务 |

#### 资产树组件字段
```json
{
  "id": 1,
  "name": "Default",
  "count": 57,
  "expanded": true,
  "children": [
    {
      "id": 2,
      "name": "余姚",
      "count": 57,
      "children": [
        {"id": 3, "name": "git", "count": 1},
        {"id": 4, "name": "gpu", "count": 1},
        {"id": 5, "name": "pve", "count": 27},
        {"id": 6, "name": "ucloud", "count": 17},
        {"id": 7, "name": "virtsmart", "count": 11}
      ]
    }
  ]
}
```

#### 主机资产表格字段 (prototype/_2/code.html)
| 列名 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 复选框 | - | checkbox | 批量选择 |
| 名称 | name | string | 资产名称 + CI编号 |
| IP/主机 | address | string | **支持格式**: IP、IP:端口、主机名、主机名:端口 |
| 系统平台 | platform | string | Linux/Windows + 图标 |
| 用户名密码 | credentials | array | 凭证列表 |
| 备注 | notes | text | 资产备注信息（可选列） |
| 操作 | - | actions | 更新/更多按钮 |

**address 字段示例**:
- `192.168.1.100` (纯IP)
- `192.168.1.100:22` (IP:端口)
- `server01.example.com` (主机名)
- `server01.example.com:8080` (主机名:端口)

**凭证行结构**:
```
┌─────────────────────────────────────────────────────┐
│ [用户名] [复制] │ [********] [复制][👁][编辑][删除] │
└─────────────────────────────────────────────────────┘
```

#### 网络设备表格字段 (prototype/_3/code.html)
| 列名 | 字段 | 说明 |
|------|------|------|
| 名称 | name | 设备名称 + 序列号 |
| IP地址 | address | **支持格式**: IP、IP:端口、主机名、主机名:端口 |
| 设备类型 | device_type | 交换机/路由器/无线控制器 |
| 厂商/型号 | vendor_model | Cisco/Huawei + 型号 |
| 管理凭据 | credentials | 包含 SNMP 凭据 |
| 备注 | notes | 设备备注信息（可选列） |

**address 字段示例**:
- `10.0.0.1` (纯IP)
- `10.0.0.1:443` (IP:HTTPS端口)
- `switch01.local` (主机名)
- `switch01.local:8443` (主机名:端口)

#### 云服务表格字段 (prototype/url/code.html)
| 列名 | 字段 | 说明 |
|------|------|------|
| 名称 | name | 服务名称 + 资源ID |
| URL | url | 服务地址 + 彩色图标 |
| 系统平台 | platform | AWS/阿里云/腾讯云 |
| 访问凭证 | credentials | AKID/Secret/RAM-User |
| 备注 | notes | 云服务备注信息（可选列） |

**云服务凭证特殊字段**:
- AKID (AWS Access Key ID): 截断显示 `ASIA...4V7A`
- Secret: 隐藏显示 `********`
- RAM-User (阿里云): 用户标识
- SecretId (腾讯云): 密钥ID

#### 设计规范
- **分类标签激活**: `border-b-2 border-teal-600 text-teal-600 font-bold`
- **树节点选中**: `bg-blue-50 text-primary`
- **表格行悬停**: `hover:bg-blue-50/30`
- **凭证卡片**: `bg-slate-100/80 rounded px-2 py-1`
- **操作按钮**: `bg-teal-600 text-white` (主要) / `border border-outline-variant/30` (次要)

#### API 接口
```
GET /api/v1/assets?category={category}&organization_id={id}&page={page}&limit={limit}&search={keyword}
POST /api/v1/assets
PUT /api/v1/assets/:id
DELETE /api/v1/assets/:id

GET /api/v1/credentials?asset_id={id}
POST /api/v1/credentials
PUT /api/v1/credentials/:id
DELETE /api/v1/credentials/:id
POST /api/v1/credentials/:id/decrypt
```

**创建/编辑资产 API 请求示例**:
```json
POST /api/v1/assets
{
  "name": "Web-Prod-Server-01",
  "category": "host",
  "address": "192.168.1.100:22",
  "platform": "Linux",
  "organization_id": 2,
  "notes": "生产环境Web服务器，每周三凌晨2点自动备份",
  "metadata": {
    "os_version": "Ubuntu 22.04 LTS",
    "cpu": "8 cores",
    "memory": "32GB"
  }
}
```

**资产列表 API 响应示例**:
```json
GET /api/v1/assets?category=host&page=1&limit=20
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": 1,
        "name": "Web-Prod-Server-01",
        "asset_code": "CI-20240501-A",
        "category": "host",
        "address": "192.168.1.100:22",
        "platform": "Linux",
        "notes": "生产环境Web服务器，每周三凌晨2点自动备份",
        "credentials": [
          {
            "id": 1,
            "username": "root",
            "credential_type": "password"
          },
          {
            "id": 2,
            "username": "deploy",
            "credential_type": "password"
          }
        ],
        "created_at": "2024-03-26T10:30:00Z"
      }
    ],
    "total": 57,
    "page": 1,
    "limit": 20
  }
}
```

---


### 2.4 用户管理页面 (Users)

**原型文件**: `prototype/add_user_final_layout/code.html`

#### 布局结构
```
┌──────────────────────────────────────────────────────────┐
│  TopNavBar                                               │
├────────┬─────────────────────────────────────────────────┤
│        │  页面标题: 用户列表                              │
│        │  副标题: 管理企业架构中的所有系统访问用户及其权限角色│
│ Side   │  [批量操作▼] [添加用户] (右上角)                 │
│ Nav    ├─────────────────────────────────────────────────┤
│        │  数据表格                                        │
│        │  ┌────┬────┬──────┬────┬────────┬────┬────┐   │
│        │  │用户名│姓名│邮箱  │用户组│最后登录│状态│操作│   │
│        │  ├────┼────┼──────┼────┼────────┼────┼────┤   │
│        │  │JD  │John│email │Admin│14:32  │●Active│⚙│   │
│        │  │    │Doe │      │     │       │      │  │   │
└────────┴────┴────┴──────┴────┴────────┴────┴────┘   │
```

#### 表格字段详细
| 列名 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 用户名 | username | string | 头像(首字母) + 用户名 |
| 姓名 | full_name | string | 真实姓名 |
| 邮箱 | email | string | 邮箱地址 |
| 用户组 | groups | array | 徽章显示 |
| 最后登录时间 | last_login_at | datetime | 格式: YYYY-MM-DD HH:mm |
| 状态 | is_active | boolean | Active/Inactive + 绿点 |
| 操作 | - | actions | 编辑/重置密码/删除 |

#### 添加用户模态框字段
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| username | string | 是 | 用户名 (唯一) |
| full_name | string | 是 | 姓名 |
| email | string | 是 | 邮箱 (唯一) |
| phone | string | 否 | 手机号 |
| group_id | integer | 是 | 用户组 (下拉选择) |
| is_active | boolean | 是 | 状态 (单选: 活跃/禁用) |
| mfa_enabled | boolean | 是 | MFA开关 (单选: 开启/关闭) |
| password | string | 是 | 密码 |
| password_confirm | string | 是 | 确认密码 |

**模态框布局**: 2列网格 `grid-cols-2 gap-6`

#### 设计规范
- **头像**: `w-8 h-8 rounded-lg bg-blue-100 text-blue-700` (首字母缩写)
- **用户组徽章**: `px-2 py-1 rounded-md bg-blue-50 text-blue-700 text-[10px] font-bold border border-blue-100`
- **状态徽章**: `px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700` + 绿点
- **操作图标**: `p-1.5 hover:bg-white rounded-lg shadow-sm`

#### API 接口
```
GET /api/v1/users?page={page}&limit={limit}&search={keyword}
POST /api/v1/users
PUT /api/v1/users/:id
DELETE /api/v1/users/:id
POST /api/v1/users/:id/reset-password
```

---

### 2.5 用户组管理页面 (User Groups)

**原型文件**: `prototype/added_authorized_assets/code.html`, `prototype/_4/code.html`

#### 布局结构
```
┌──────────────────────────────────────────────────────────┐
│  TopNavBar                                               │
├────────┬─────────────────────────────────────────────────┤
│        │  页面标题: 用户组                                │
│        │  副标题: 管理用户组及其所属权限                  │
│ Side   │  [创建用户组] (右上角)                           │
│ Nav    ├─────────────────────────────────────────────────┤
│        │  数据表格                                        │
│        │  ┌────────┬────────┬────────┬────────┬────┐   │
│        │  │用户组名称│描述    │成员数量│创建时间│操作│   │
│        │  ├────────┼────────┼────────┼────────┼────┤   │
│        │  │🛡Admin │系统最高│  (3)   │2023-01 │编辑│   │
│        │  │        │权限    │ 👤👤+5 │        │删除│   │
└────────┴────────┴────────┴────────┴────────┴────┘   │
```

#### 表格字段详细
| 列名 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 用户组名称 | name | string | 图标 + 名称 |
| 描述 | description | text | 用户组说明 |
| 成员数量 | member_count | integer | 徽章 + 头像堆叠 |
| 创建时间 | created_at | date | YYYY-MM-DD |
| 操作 | - | actions | 已授权资产/编辑/删除 |

#### 创建用户组模态框字段
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| name | string | 是 | 用户组名称 (唯一) |
| description | text | 否 | 用户组描述 |
| initial_members | array | 否 | 初始成员 (多选) |

**初始成员选择器**: 
- 搜索输入框
- 已选成员显示为标签 (头像 + 名称 + 删除按钮)
- 标签样式: `bg-white px-2 py-1 rounded-lg border border-outline-variant/30 shadow-sm`

#### 设计规范
- **图标容器**: `w-10 h-10 rounded bg-primary/10 text-primary`
- **成员数徽章**: `px-3 py-1 rounded-full bg-secondary-container/20 text-on-secondary-container font-semibold`
- **头像堆叠**: `-space-x-2` + `border-2 border-white`
- **操作按钮**: 文字 + 图标组合

#### API 接口
```
GET /api/v1/groups
POST /api/v1/groups
PUT /api/v1/groups/:id
DELETE /api/v1/groups/:id
GET /api/v1/groups/:id/members
POST /api/v1/groups/:id/members
DELETE /api/v1/groups/:id/members/:user_id
```

---


### 2.6 资产授权页面 (Asset Authorization)

**原型文件**: `prototype/full_navigation_hierarchy/code.html`, `prototype/added_authorized_assets/code.html`

#### 布局结构
```
┌──────────────────────────────────────────────────────────┐
│  TopNavBar                                               │
├────────┬─────────────────────────────────────────────────┤
│        │  页面标题: 资产授权                              │
│        │  副标题: 管理和维护系统资产与用户/用户组之间的权限关系│
│ Side   │  [新增授权] (右上角)                             │
│ Nav    ├─────────────────────────────────────────────────┤
│        │  筛选栏                                          │
│        │  [搜索] [权限类型▼] [状态▼] [重置]              │
│        ├─────────────────────────────────────────────────┤
│        │  数据表格                                        │
│        │  ┌────────┬────────┬────────┬────┬────┬────┐  │
│        │  │用户/组 │资产/组 │权限类型│授权│状态│操作│  │
│        │  │        │        │        │时间│    │    │  │
└────────┴────────┴────────┴────────┴────┴────┴────┘  │
```

#### 表格字段详细
| 列名 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 用户/用户组 | entity | object | 头像+名称+邮箱/成员数 |
| 资产/资产组 | target | object | 资产名称 + 类型标识 |
| 权限类型 | permissions | array | 多个徽章显示 |
| 授权时间 | created_at | datetime | YYYY-MM-DD HH:mm |
| 状态 | status | string | Active/Expired + 圆点 |
| 操作 | - | actions | 编辑/禁用/删除 |

#### 权限类型枚举
| 权限代码 | 显示名称 | 说明 |
|---------|---------|------|
| view | 查看资产 | 查看资产基本信息 |
| manage | 管理资产 | 创建/编辑/删除资产 |
| user_mgmt | 用户管理 | 管理用户和用户组 |
| sys_config | 系统设置 | 修改系统配置 |
| audit_log | 日志审计 | 查看审计日志 |
| view_pwd | 查看复制资产密码 | 查看和复制凭证密码 |
| manage_pwd | 管理资产用户名密码 | 创建/编辑/删除凭证 |

#### 新增授权模态框字段
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| entity_type | enum | 是 | 用户/用户组 (切换按钮) |
| entity_ids | array | 是 | 选中的用户/组ID (多选) |
| target_type | enum | 是 | 单个资产/资产组 (切换按钮) |
| target_ids | array | 是 | 选中的资产/组ID (多选) |
| permissions | array | 是 | 权限类型 (多选复选框) |
| validity_type | enum | 是 | 永久/临时 (单选) |
| valid_from | date | 条件 | 开始日期 (临时时必填) |
| valid_until | date | 条件 | 结束日期 (临时时必填) |

**模态框布局**:
- 授权对象选择: 切换按钮 + 搜索框 + 已选标签
- 资产范围选择: 切换按钮 + 搜索框
- 权限类型: 3列网格复选框
- 有效期: 单选 + 日期选择器

#### 设计规范
- **实体头像**: `w-8 h-8 rounded-full bg-blue-100` (用户) / `bg-purple-100` (组)
- **权限徽章**: `px-2 py-0.5 rounded-md bg-primary/10 text-primary text-[10px] font-bold uppercase`
- **状态Active**: `bg-green-100 text-green-700` + 绿点
- **状态Expired**: `bg-surface-container-high text-on-surface-variant` + 灰点
- **切换按钮**: `bg-white shadow-sm text-primary` (激活) / `text-on-surface-variant` (未激活)

#### API 接口
```
GET /api/v1/authorizations?search={keyword}&permission_type={type}&status={status}&page={page}&limit={limit}
POST /api/v1/authorizations
PUT /api/v1/authorizations/:id
DELETE /api/v1/authorizations/:id
GET /api/v1/authorizations/:id/check
```

---


### 2.7 日志审计 - 操作日志 (Operation Logs)

**原型文件**: `prototype/_5/code.html`

#### 布局结构
```
┌──────────────────────────────────────────────────────────┐
│  TopNavBar                                               │
├────────┬─────────────────────────────────────────────────┤
│        │  页面标题: 操作日志 (Operation Logs)             │
│        │  副标题: 审计系统内所有用户的操作行为            │
│ Side   ├─────────────────────────────────────────────────┤
│ Nav    │  统计卡片区 (3列)                                │
│        │  [今日操作总数] [成功率] [高风险活动]            │
│        ├─────────────────────────────────────────────────┤
│        │  筛选栏                                          │
│        │  [搜索操作者] [日期范围] [类型▼] [筛选] [刷新]  │
│        ├─────────────────────────────────────────────────┤
│        │  数据表格                                        │
│        │  ┌────┬────┬────┬────────┬────┬────┐          │
│        │  │时间│操作者│类型│目标资产│状态│详情│          │
└────────┴────┴────┴────┴────────┴────┴────┘          │
```

#### 统计卡片字段
| 卡片名称 | 字段 | 说明 |
|---------|------|------|
| Today's Total Operations | today_total | 今日操作总数 + 增长率 |
| Success Rate | success_rate | 成功率百分比 |
| High-Risk Activities | high_risk_count | 高风险操作数 |

#### 表格字段详细
| 列名 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 时间 | created_at | datetime | YYYY-MM-DD HH:mm:ss |
| 操作者 | operator | object | 头像(首字母) + 用户名 |
| 操作类型 | action_type | enum | CREATE/EDIT/DELETE/AUTHORIZE |
| 目标资产 | target_asset | string | 资产名称 (等宽字体) |
| 状态 | status | enum | 成功/失败 + 圆点 |
| 详情 | - | action | 查看详情/错误日志 |

#### 操作类型枚举
| 类型 | 徽章颜色 | 说明 |
|------|---------|------|
| CREATE | green-100/green-700 | 创建资源 |
| EDIT | blue-100/blue-700 | 编辑资源 |
| DELETE | red-100/red-700 | 删除资源 |
| AUTHORIZE | yellow-100/yellow-700 | 授权操作 |

#### 筛选器字段
| 字段名 | 类型 | 说明 |
|--------|------|------|
| operator_search | string | 搜索操作者 |
| date_range | daterange | 日期范围选择器 |
| action_type | enum | 操作类型过滤 |

#### 设计规范
- **统计卡片**: `bg-white p-6 rounded-lg border border-outline-variant shadow-sm`
- **大数字**: `text-3xl font-bold font-headline`
- **增长率**: `text-xs text-success font-bold` (正) / `text-error` (负)
- **操作类型徽章**: `text-[10px] font-bold px-1.5 py-0.5 rounded uppercase`
- **失败行背景**: `bg-error/5`

#### API 接口
```
GET /api/v1/logs/operation?operator={user}&date_from={date}&date_to={date}&action_type={type}&page={page}&limit={limit}
GET /api/v1/logs/operation/:id
GET /api/v1/logs/operation/stats?date={date}
```

---

### 2.8 日志审计 - 登录日志 (Login Logs)

**原型文件**: 需推断 (与操作日志类似结构)

#### 表格字段详细
| 列名 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 时间 | created_at | datetime | 登录时间 |
| 用户名 | username | string | 登录用户名 |
| IP地址 | ip_address | string | 来源IP |
| User Agent | user_agent | string | 浏览器信息 |
| 状态 | status | enum | success/failed |
| 失败原因 | failure_reason | string | 失败时显示 |

#### API 接口
```
GET /api/v1/logs/login?username={user}&date_from={date}&date_to={date}&status={status}&page={page}&limit={limit}
```

---

### 2.9 日志审计 - 改密日志 (Password Change Logs)

**原型文件**: 需推断

#### 表格字段详细
| 列名 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 时间 | created_at | datetime | 改密时间 |
| 用户 | user | object | 执行改密的用户 |
| 变更类型 | change_type | enum | user_password/asset_credential |
| 目标 | target | string | 用户名或资产名 |
| IP地址 | ip_address | string | 来源IP |

#### API 接口
```
GET /api/v1/logs/password-change?user_id={id}&change_type={type}&date_from={date}&date_to={date}&page={page}&limit={limit}
```

---

### 2.10 系统设置页面 (System Settings)

**原型文件**: 未提供 (需设计)

#### 功能模块
1. **基本设置**
   - 系统名称
   - Logo 上传
   - 时区设置
   - 语言设置

2. **安全设置**
   - 密码策略
   - 会话超时时间
   - MFA 强制启用
   - IP 白名单

3. **邮件设置**
   - SMTP 服务器
   - 发件人信息
   - 邮件模板

4. **备份设置**
   - 自动备份开关
   - 备份频率
   - 备份保留天数

#### API 接口
```
GET /api/v1/settings
PUT /api/v1/settings
GET /api/v1/settings/:key
PUT /api/v1/settings/:key
```

---


## 三、数据库设计详细

### 3.1 核心表结构

#### users 表
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100),
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(100),
    last_login_at TIMESTAMP,
    last_login_ip VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_is_active (is_active)
);
```

#### groups 表
```sql
CREATE TABLE groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_name (name)
);
```

#### user_groups 表
```sql
CREATE TABLE user_groups (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, group_id),
    INDEX idx_user_id (user_id),
    INDEX idx_group_id (group_id)
);
```

#### organizations 表
```sql
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_id INTEGER REFERENCES organizations(id),
    path VARCHAR(500),
    level INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_parent_id (parent_id),
    INDEX idx_path (path)
);
```

#### assets 表
```sql
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,  -- host, network, database, cloud, web, gpt
    address VARCHAR(255),  -- IP/主机地址，支持格式: IP, IP:端口, 主机名, 主机名:端口
    platform VARCHAR(50),
    organization_id INTEGER REFERENCES organizations(id),
    device_type VARCHAR(50),  -- 网络设备: 交换机/路由器/无线控制器
    vendor VARCHAR(100),      -- 厂商
    model VARCHAR(100),       -- 型号
    serial_number VARCHAR(100), -- 序列号
    url VARCHAR(500),         -- 云服务/Web URL
    notes TEXT,               -- 备注字段 (新增)
    metadata JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_organization_id (organization_id),
    INDEX idx_name (name),
    INDEX idx_is_active (is_active),
    INDEX idx_notes_fulltext (to_tsvector('simple', notes))  -- 备注全文搜索
);
```

**address 字段格式说明**:
- **主机资产** (category='host'):
  - 纯IP: `192.168.1.100`
  - IP:端口: `192.168.1.100:22` (SSH默认端口)
  - 主机名: `server01.example.com`
  - 主机名:端口: `server01.example.com:8080`

- **网络设备** (category='network'):
  - 纯IP: `10.0.0.1`
  - IP:端口: `10.0.0.1:443` (HTTPS管理)
  - 主机名: `switch01.local`
  - 主机名:端口: `switch01.local:8443`

- **数据库** (category='database'):
  - IP:端口: `10.0.8.42:3306` (MySQL)
  - IP:端口: `10.0.12.115:5432` (PostgreSQL)
  - 主机名:端口: `db01.example.com:3306`

- **云服务/Web/GPT**: URL存储在address字段或url字段

**notes 字段说明**:
- 用于记录资产的额外信息、维护记录、配置说明等
- 支持全文搜索
- 前端显示为可展开/折叠的文本区域

#### credentials 表
```sql
CREATE TABLE credentials (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    username VARCHAR(100) NOT NULL,
    password_encrypted TEXT NOT NULL,
    credential_type VARCHAR(50) DEFAULT 'password',  -- password, ssh_key, api_key, snmp
    metadata JSONB,  -- 云服务特殊字段: akid, secret, ram_user
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_asset_id (asset_id)
);
```

#### authorizations 表
```sql
CREATE TABLE authorizations (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL,  -- user, group
    entity_id INTEGER NOT NULL,
    target_type VARCHAR(20) NOT NULL,  -- asset, asset_group
    target_id INTEGER NOT NULL,
    permissions JSONB NOT NULL,  -- ["view", "manage", "view_pwd", ...]
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_entity (entity_type, entity_id),
    INDEX idx_target (target_type, target_id),
    INDEX idx_is_active (is_active)
);
```

#### login_logs 表
```sql
CREATE TABLE login_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    username VARCHAR(50),
    ip_address VARCHAR(45),
    user_agent TEXT,
    status VARCHAR(20),  -- success, failed
    failure_reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_status (status)
);
```

#### operation_logs 表
```sql
CREATE TABLE operation_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(50) NOT NULL,  -- create, update, delete, authorize
    resource_type VARCHAR(50),
    resource_id INTEGER,
    details JSONB,
    ip_address VARCHAR(45),
    status VARCHAR(20) DEFAULT 'success',  -- success, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at),
    INDEX idx_resource (resource_type, resource_id)
);
```

#### password_change_logs 表
```sql
CREATE TABLE password_change_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    credential_id INTEGER REFERENCES credentials(id),
    change_type VARCHAR(20),  -- user_password, asset_credential
    changed_by INTEGER REFERENCES users(id),
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_changed_by (changed_by),
    INDEX idx_created_at (created_at)
);
```

#### settings 表
```sql
CREATE TABLE settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSONB,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_key (key)
);
```

---


## 四、前端组件设计

### 4.1 布局组件

#### TopNavBar.vue
```vue
<template>
  <header class="fixed top-0 w-full h-14 bg-white border-b border-gray-100 z-50 px-6 flex items-center justify-between">
    <div class="flex items-center gap-8">
      <span class="text-lg font-bold tracking-tight text-slate-900">CMDB</span>
    </div>
    <div class="flex items-center gap-4">
      <SearchInput />
      <NotificationButton />
      <UserMenu />
    </div>
  </header>
</template>
```

#### SideNavBar.vue
```vue
<template>
  <aside class="fixed left-0 top-14 h-[calc(100vh-56px)] w-60 bg-white border-r border-gray-100 overflow-y-auto">
    <nav class="p-3 space-y-0.5">
      <MenuItem v-for="item in menuItems" :key="item.path" :item="item" />
    </nav>
  </aside>
</template>
```

**菜单数据结构**:
```typescript
interface MenuItem {
  path: string
  label: string
  icon: string
  children?: MenuItem[]
}

const menuItems: MenuItem[] = [
  { path: '/dashboard', label: '仪表盘', icon: 'dashboard' },
  {
    path: '/assets',
    label: '资产管理',
    icon: 'inventory_2',
    children: [
      { path: '/assets/list', label: '资产列表', icon: '' }
    ]
  },
  {
    path: '/users',
    label: '用户管理',
    icon: 'group',
    children: [
      { path: '/users/list', label: '用户', icon: '' },
      { path: '/users/groups', label: '用户组', icon: '' }
    ]
  },
  {
    path: '/permissions',
    label: '权限管理',
    icon: 'verified_user',
    children: [
      { path: '/permissions/authorizations', label: '资产授权', icon: '' }
    ]
  },
  {
    path: '/logs',
    label: '日志审计',
    icon: 'history_edu',
    children: [
      { path: '/logs/login', label: '登录日志', icon: '' },
      { path: '/logs/operation', label: '操作日志', icon: '' },
      { path: '/logs/password', label: '改密日志', icon: '' }
    ]
  },
  { path: '/settings', label: '系统设置', icon: 'settings' }
]
```

### 4.2 通用组件

#### DataTable.vue
```vue
<template>
  <div class="bg-white rounded-xl shadow-sm overflow-hidden">
    <table class="w-full text-left border-collapse">
      <thead class="bg-gray-50 border-b border-gray-100">
        <tr>
          <th v-for="column in columns" :key="column.key" class="px-6 py-4 text-xs font-bold text-slate-500 uppercase">
            {{ column.title }}
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-50">
        <tr v-for="row in data" :key="row.id" class="hover:bg-blue-50/30 transition-colors">
          <td v-for="column in columns" :key="column.key" class="px-6 py-4 text-sm">
            <slot :name="`cell-${column.key}`" :row="row">
              {{ row[column.key] }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
```

#### Modal.vue
```vue
<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="handleClose"></div>
      <div class="relative bg-white w-full max-w-2xl rounded-xl shadow-2xl">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-extrabold text-slate-900">{{ title }}</h2>
          <button @click="handleClose" class="p-2 hover:bg-slate-50 rounded-full">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <div class="p-6">
          <slot></slot>
        </div>
      </div>
    </div>
  </Teleport>
</template>
```

---

## 五、开发阶段规划

### 阶段一：基础架构（已完成）
- [x] 后端项目初始化
- [x] 数据库模型设计
- [x] 认证系统实现
- [x] 基础配置

### 阶段二：核心功能开发（当前）

#### 后端开发任务
1. **资产管理模块** (5天)
   - [ ] 资产 CRUD API
   - [ ] 资产树结构生成
   - [ ] 分类过滤实现
   - [ ] 凭证加密存储

2. **用户管理模块** (3天)
   - [ ] 用户 CRUD API
   - [ ] 用户组管理
   - [ ] 密码重置
   - [ ] MFA 支持

3. **权限管理模块** (4天)
   - [ ] 授权 CRUD API
   - [ ] 权限验证中间件
   - [ ] 有效期检查

4. **日志审计模块** (2天)
   - [ ] 日志记录装饰器
   - [ ] 日志查询 API

#### 前端开发任务
1. **布局与路由** (2天)
   - [ ] TopNavBar 组件
   - [ ] SideNavBar 组件
   - [ ] 路由配置

2. **页面开发** (10天)
   - [ ] 登录页面 (1天)
   - [ ] 仪表盘 (2天)
   - [ ] 资产列表 (3天)
   - [ ] 用户管理 (2天)
   - [ ] 资产授权 (2天)

3. **通用组件** (3天)
   - [ ] DataTable
   - [ ] Modal
   - [ ] Pagination
   - [ ] StatusBadge

### 阶段三：功能完善（2周）
- [ ] 搜索优化
- [ ] 批量操作
- [ ] 导入导出
- [ ] 单元测试

### 阶段四：部署上线（1周）
- [ ] Docker 配置
- [ ] CI/CD 配置
- [ ] 生产部署

---

## 六、关键技术实现

### 6.1 凭证加密
```python
from cryptography.fernet import Fernet

cipher = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_credential(password: str) -> str:
    return cipher.encrypt(password.encode()).decode()

def decrypt_credential(encrypted: str) -> str:
    return cipher.decrypt(encrypted.encode()).decode()
```

### 6.2 权限验证
```python
async def check_permission(permission: str, current_user = Depends(get_current_user)):
    # 查询用户授权
    # 验证权限类型
    # 检查有效期
    pass
```

### 6.3 操作日志记录
```python
def log_operation(action: str, resource_type: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            # 记录日志
            return result
        return wrapper
    return decorator
```

---

## 七、总结

本详细开发规划文档基于对所有原型页面的深入分析，严格按照菜单结构组织，涵盖：

1. **完整的页面分析** - 每个页面的布局、字段、设计规范
2. **详细的数据库设计** - 所有表结构和索引
3. **清晰的 API 接口** - 每个功能的接口定义
4. **前端组件规划** - 布局和通用组件设计
5. **分阶段开发计划** - 可执行的任务清单

**下一步行动**:
1. 继续完成阶段二的后端 API 开发
2. 严格按照原型设计实现前端页面
3. 确保所有字段和功能完整实现

---

**文档版本**: v2.0 (详细版)  
**最后更新**: 2026-03-26  
**维护者**: 开发团队


## 八、前端表单设计与验证

### 8.1 创建/编辑资产表单字段

#### 表单字段清单
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| name | string | 是 | 资产名称 |
| category | enum | 是 | 资产类型 (host/network/database/cloud/web/gpt) |
| address | string | 是 | IP/主机地址，支持多种格式 |
| platform | string | 否 | 系统平台 |
| notes | text | 否 | **备注信息 (新增)** |
| organization_id | integer | 否 | 所属组织 |

#### 地址字段输入提示
```
占位符文本: "支持格式: IP、IP:端口、主机名、主机名:端口"
示例提示: "如: 192.168.1.100 或 192.168.1.100:22 或 server01.example.com:8080"
```

### 8.2 地址格式验证规则

#### 前端验证 (TypeScript)
```typescript
// utils/validators.ts
export function validateAddress(address: string): { valid: boolean; message?: string } {
  if (!address?.trim()) {
    return { valid: false, message: '地址不能为空' }
  }

  const parts = address.split(':')
  if (parts.length > 2) {
    return { valid: false, message: '格式错误，端口只能有一个' }
  }

  const host = parts[0]
  const port = parts[1]

  // 验证IP或主机名
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/
  const hostnameRegex = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/
  
  if (!ipRegex.test(host) && !hostnameRegex.test(host)) {
    return { valid: false, message: '无效的IP地址或主机名' }
  }

  // 验证端口
  if (port) {
    const portNum = parseInt(port, 10)
    if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
      return { valid: false, message: '端口号必须在 1-65535 之间' }
    }
  }

  return { valid: true }
}
```

#### 后端验证 (Python)
```python
# app/utils/validators.py
import re

def validate_address(address: str) -> tuple[bool, str]:
    """验证地址格式: IP, IP:端口, 主机名, 主机名:端口"""
    if not address or not address.strip():
        return False, "地址不能为空"

    parts = address.split(':')
    if len(parts) > 2:
        return False, "格式错误"

    host = parts[0]
    port = parts[1] if len(parts) == 2 else None

    # 验证IP或主机名
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    
    if not (re.match(ip_pattern, host) or re.match(hostname_pattern, host)):
        return False, "无效的IP地址或主机名"

    # 验证端口
    if port:
        try:
            port_num = int(port)
            if not (1 <= port_num <= 65535):
                return False, "端口号必须在 1-65535 之间"
        except ValueError:
            return False, "无效的端口号"

    return True, ""
```

### 8.3 备注字段显示

#### 表格中备注列显示
- **默认**: 截断显示前50个字符
- **展开**: 点击"展开"按钮显示完整内容
- **可选列**: 用户可选择显示/隐藏备注列

#### 备注搜索支持
- 后端使用 PostgreSQL 全文搜索
- 前端搜索框支持备注内容搜索

---

## 九、数据库迁移脚本

### 9.1 添加备注字段迁移

```python
# alembic/versions/xxxx_add_notes_to_assets.py
"""add notes field to assets table

Revision ID: xxxx
Revises: yyyy
Create Date: 2026-03-27

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # 添加 notes 字段
    op.add_column('assets', sa.Column('notes', sa.Text(), nullable=True))
    
    # 添加全文搜索索引
    op.execute("""
        CREATE INDEX idx_assets_notes_fulltext 
        ON assets 
        USING gin(to_tsvector('simple', notes))
    """)

def downgrade():
    op.drop_index('idx_assets_notes_fulltext', table_name='assets')
    op.drop_column('assets', 'notes')
```

---

## 十、API 接口完整示例

### 10.1 创建资产 API

**请求示例 - 主机资产**:
```json
POST /api/v1/assets
{
  "name": "Web-Prod-Server-01",
  "category": "host",
  "address": "192.168.1.100:22",
  "platform": "Linux",
  "notes": "生产环境Web服务器\n每周三凌晨2点自动备份\n负责人: 张三",
  "organization_id": 2
}
```

**请求示例 - 网络设备**:
```json
POST /api/v1/assets
{
  "name": "Core-Switch-01",
  "category": "network",
  "address": "10.0.0.1:443",
  "platform": "Cisco IOS",
  "notes": "核心交换机，24口千兆\n机柜位置: A-01-U12",
  "metadata": {
    "device_type": "交换机",
    "vendor": "Cisco",
    "model": "Catalyst 9300",
    "serial_number": "CZJ0921L04X"
  }
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "创建成功",
  "data": {
    "id": 1,
    "name": "Web-Prod-Server-01",
    "category": "host",
    "address": "192.168.1.100:22",
    "platform": "Linux",
    "notes": "生产环境Web服务器\n每周三凌晨2点自动备份\n负责人: 张三",
    "created_at": "2026-03-27T01:00:00Z"
  }
}
```

### 10.2 搜索资产 API (支持备注搜索)

```
GET /api/v1/assets?search=备份&category=host&page=1&limit=20

搜索范围: name, address, platform, notes
```

---

## 十一、开发任务清单

### 11.1 后端任务
- [ ] 数据库迁移: 添加 notes 字段
- [ ] 更新 Asset 模型: 添加 notes 属性
- [ ] 更新 AssetSchema: 添加 notes 验证
- [ ] 实现地址格式验证函数
- [ ] 更新搜索逻辑: 包含 notes 字段
- [ ] API 测试: 验证 notes 字段和地址格式

### 11.2 前端任务
- [ ] 更新资产表单: 添加备注输入框 (textarea)
- [ ] 实现地址格式验证
- [ ] 添加地址输入提示
- [ ] 更新表格列: 添加备注列 (可选)
- [ ] 实现备注展开/收起功能
- [ ] 更新搜索: 支持备注搜索
- [ ] UI 测试: 验证所有资产类型

### 11.3 测试用例
- [ ] 测试地址格式: IP, IP:端口, 主机名, 主机名:端口
- [ ] 测试备注字段: 创建、编辑、搜索
- [ ] 测试边界情况: 空备注、超长备注、特殊字符
- [ ] 测试所有资产类型: host, network, database, cloud, web, gpt

---

**文档版本**: v2.1 (增强版)  
**最后更新**: 2026-03-27  
**更新内容**: 
- 添加备注字段到所有资产类型
- 明确 IP:端口 格式支持
- 完善地址验证规则
- 添加前端表单设计
- 添加数据库迁移脚本
- 添加开发任务清单


## 十二、用户操作功能详细设计

### 12.1 功能概述

用户列表页面提供4个核心操作：
1. **已授权资产** - 查看用户的所有资产授权
2. **编辑** - 修改用户信息
3. **重置密码** - 管理员重置密码
4. **删除** - 删除用户账号

### 12.2 已授权资产功能

#### 功能描述
点击"已授权资产"按钮，打开Modal显示该用户的所有授权记录，包括直接授权和通过用户组继承的授权。

#### Modal设计
```
┌─────────────────────────────────────────────────────┐
│  用户授权资产列表 - 张三 (zhangsan)          [X]    │
├─────────────────────────────────────────────────────┤
│  筛选栏:                                            │
│  [搜索资产] [权限类型▼] [状态▼] [授权来源▼]        │
├─────────────────────────────────────────────────────┤
│  数据表格:                                          │
│  ┌────┬────────┬────┬────────┬────────┬────┬────┐ │
│  │资产│资产类型│权限│授权来源│有效期  │状态│操作│ │
│  ├────┼────────┼────┼────────┼────────┼────┼────┤ │
│  │Web │主机    │查看│直接授权│永久    │●  │取消│ │
│  │DB01│数据库  │管理│用户组  │30天后  │●  │-  │ │
│  └────┴────────┴────┴────────┴────────┴────┴────┘ │
│                                                     │
│  共 15 条授权记录                    [关闭]        │
└─────────────────────────────────────────────────────┘
```

#### 表格字段
| 列名 | 字段 | 说明 |
|------|------|------|
| 资产名称 | asset_name | 资产名称 + 类型图标 |
| 资产类型 | asset_category | 主机/网络设备/数据库等 |
| 权限类型 | permissions | 徽章显示，多个权限 |
| 授权来源 | source | 直接授权/用户组名称 |
| 有效期 | validity | 永久/剩余天数 |
| 状态 | status | Active/Expired |
| 操作 | actions | 取消授权（仅直接授权可操作） |

#### API接口
```
GET /api/v1/users/:id/authorizations
Response: {
  "code": 0,
  "data": {
    "direct": [
      {
        "id": 1,
        "asset_id": 10,
        "asset_name": "Web-Prod-Server-01",
        "asset_category": "host",
        "permissions": ["view", "manage"],
        "valid_until": null,
        "status": "active"
      }
    ],
    "inherited": [
      {
        "group_id": 2,
        "group_name": "运维组",
        "asset_id": 20,
        "asset_name": "DB-Master-01",
        "asset_category": "database",
        "permissions": ["view", "view_pwd"],
        "valid_until": "2026-04-27T00:00:00Z",
        "status": "active"
      }
    ]
  }
}

DELETE /api/v1/authorizations/:id
```

---

### 12.3 编辑用户功能

#### Modal设计
```
┌─────────────────────────────────────────────────────┐
│  编辑用户 - zhangsan                         [X]    │
├─────────────────────────────────────────────────────┤
│  基本信息:                                          │
│  ┌─────────────────┬─────────────────┐            │
│  │ 用户名 (不可编辑)│ 姓名 *          │            │
│  │ zhangsan        │ [张三_______]   │            │
│  └─────────────────┴─────────────────┘            │
│  ┌─────────────────┬─────────────────┐            │
│  │ 邮箱 *          │ 手机号          │            │
│  │ [zhang@ex.com_] │ [13800138000_]  │            │
│  └─────────────────┴─────────────────┘            │
│                                                     │
│  用户组:                                            │
│  [运维组 ▼] [开发组 ▼]                             │
│                                                     │
│  状态设置:                                          │
│  ○ 活跃  ● 禁用                                    │
│                                                     │
│  MFA设置:                                           │
│  ● 开启  ○ 关闭                                    │
│                                                     │
│                              [取消]  [保存]        │
└─────────────────────────────────────────────────────┘
```

#### 可编辑字段
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| full_name | string | 是 | 姓名 |
| email | string | 是 | 邮箱（唯一） |
| phone | string | 否 | 手机号 |
| group_ids | array | 否 | 用户组（多选） |
| is_active | boolean | 是 | 状态 |
| mfa_enabled | boolean | 是 | MFA开关 |

**注意**: 用户名不可修改，密码通过"重置密码"功能单独处理

#### API接口
```
GET /api/v1/users/:id
Response: {
  "code": 0,
  "data": {
    "id": 1,
    "username": "zhangsan",
    "full_name": "张三",
    "email": "zhang@example.com",
    "phone": "13800138000",
    "groups": [
      {"id": 1, "name": "运维组"},
      {"id": 2, "name": "开发组"}
    ],
    "is_active": true,
    "mfa_enabled": false
  }
}

PUT /api/v1/users/:id
Request: {
  "full_name": "张三",
  "email": "zhang@example.com",
  "phone": "13800138000",
  "group_ids": [1, 2],
  "is_active": true,
  "mfa_enabled": false
}
```

---

### 12.4 重置密码功能

#### Modal设计
```
┌─────────────────────────────────────────────────────┐
│  重置密码 - 张三 (zhangsan)                  [X]    │
├─────────────────────────────────────────────────────┤
│  选择重置方式:                                      │
│                                                     │
│  ● 自动生成密码并发送邮件                          │
│    系统将生成随机密码并发送到用户邮箱              │
│    zhang@example.com                               │
│                                                     │
│  ○ 手动设置新密码                                  │
│    ┌─────────────────────────────────────┐        │
│    │ 新密码: [________________] [👁]     │        │
│    │ 确认密码: [________________] [👁]   │        │
│    └─────────────────────────────────────┘        │
│                                                     │
│  密码策略提示:                                      │
│  • 长度不少于8个字符                               │
│  • 必须包含大小写字母和数字                        │
│  • 建议包含特殊字符                                │
│                                                     │
│                              [取消]  [重置密码]    │
└─────────────────────────────────────────────────────┘
```

#### 重置方式
1. **自动生成** (推荐)
   - 生成16位随机密码
   - 包含大小写字母、数字、特殊字符
   - 发送邮件到用户邮箱
   - 强制用户首次登录修改密码

2. **手动设置**
   - 管理员输入新密码
   - 前端验证密码强度
   - 可选择是否强制用户修改

#### API接口
```
POST /api/v1/users/:id/reset-password
Request: {
  "method": "auto",  // auto | manual
  "new_password": null,  // manual时必填
  "force_change": true,  // 是否强制首次登录修改
  "send_email": true     // 是否发送邮件通知
}

Response: {
  "code": 0,
  "message": "密码重置成功",
  "data": {
    "temp_password": "Xy9#mK2$pL4@qR8z",  // auto时返回
    "email_sent": true
  }
}
```

#### 改密日志记录
```python
# 自动记录到 password_change_logs 表
{
  "user_id": 1,
  "change_type": "admin_reset",
  "changed_by": current_admin_id,
  "ip_address": request.client.host,
  "method": "auto"  # auto | manual
}
```

---

### 12.5 删除用户功能

#### 确认对话框设计
```
┌─────────────────────────────────────────────────────┐
│  ⚠️  删除用户确认                            [X]    │
├─────────────────────────────────────────────────────┤
│  您确定要删除以下用户吗？                          │
│                                                     │
│  用户名: zhangsan                                  │
│  姓名: 张三                                        │
│  邮箱: zhang@example.com                           │
│                                                     │
│  ⚠️ 警告:                                          │
│  • 该用户有 5 条授权记录                           │
│  • 该用户有 128 条操作日志                         │
│                                                     │
│  删除方式:                                          │
│  ● 软删除 (标记为已删除，保留数据)                │
│  ○ 硬删除 (永久删除，不可恢复)                    │
│                                                     │
│  请输入用户名以确认: [___________]                 │
│                                                     │
│                              [取消]  [确认删除]    │
└─────────────────────────────────────────────────────┘
```

#### 删除前检查
```python
# 后端检查逻辑
def check_user_dependencies(user_id: int) -> dict:
    return {
        "authorizations_count": count_user_authorizations(user_id),
        "operation_logs_count": count_user_operations(user_id),
        "created_assets_count": count_created_assets(user_id),
        "can_delete": True,  # 是否允许删除
        "warnings": [
            "该用户有5条授权记录将被同时删除",
            "该用户创建的资产将保留"
        ]
    }
```

#### 软删除 vs 硬删除
| 类型 | 操作 | 数据保留 | 可恢复 | 使用场景 |
|------|------|---------|--------|---------|
| 软删除 | 设置 is_deleted=true | 是 | 是 | 默认方式，保留审计 |
| 硬删除 | DELETE FROM users | 否 | 否 | 测试账号、违规账号 |

#### API接口
```
DELETE /api/v1/users/:id?method=soft
Request: {
  "confirm_username": "zhangsan",
  "delete_method": "soft"  // soft | hard
}

Response: {
  "code": 0,
  "message": "用户已删除",
  "data": {
    "deleted_authorizations": 5,
    "deleted_sessions": 2
  }
}
```

#### 操作日志记录
```python
# 记录到 operation_logs 表
{
  "user_id": current_admin_id,
  "action": "delete_user",
  "resource_type": "user",
  "resource_id": deleted_user_id,
  "details": {
    "username": "zhangsan",
    "delete_method": "soft",
    "authorizations_deleted": 5
  }
}
```

---


## 十三、用户操作前端组件实现

### 13.1 用户列表操作按钮组

```vue
<!-- components/UserActions.vue -->
<template>
  <div class="flex items-center gap-2">
    <!-- 已授权资产 -->
    <button
      @click="showAuthorizations"
      class="text-xs text-primary hover:underline flex items-center gap-1"
    >
      <span class="material-symbols-outlined text-[16px]">shield</span>
      已授权资产
    </button>

    <!-- 编辑 -->
    <button
      @click="editUser"
      class="p-1.5 hover:bg-slate-100 rounded"
      title="编辑"
    >
      <span class="material-symbols-outlined text-[18px]">edit</span>
    </button>

    <!-- 重置密码 -->
    <button
      @click="resetPassword"
      class="p-1.5 hover:bg-slate-100 rounded"
      title="重置密码"
    >
      <span class="material-symbols-outlined text-[18px]">lock_reset</span>
    </button>

    <!-- 删除 -->
    <button
      @click="deleteUser"
      class="p-1.5 hover:bg-red-50 text-error rounded"
      title="删除"
    >
      <span class="material-symbols-outlined text-[18px]">delete</span>
    </button>
  </div>
</template>
```

### 13.2 已授权资产Modal组件

```vue
<!-- components/UserAuthorizationsModal.vue -->
<template>
  <Modal :visible="visible" :title="`用户授权资产 - ${user.full_name}`" @close="handleClose">
    <!-- 筛选栏 -->
    <div class="flex gap-2 mb-4">
      <Input v-model="filters.search" placeholder="搜索资产" />
      <Select v-model="filters.permission" placeholder="权限类型" />
      <Select v-model="filters.status" placeholder="状态" />
      <Select v-model="filters.source" placeholder="授权来源" />
    </div>

    <!-- 数据表格 -->
    <DataTable :columns="columns" :data="authorizations" :loading="loading">
      <template #cell-asset="{ row }">
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-[18px]">{{ getAssetIcon(row.asset_category) }}</span>
          <span>{{ row.asset_name }}</span>
        </div>
      </template>

      <template #cell-permissions="{ row }">
        <div class="flex flex-wrap gap-1">
          <span
            v-for="perm in row.permissions"
            :key="perm"
            class="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded"
          >
            {{ getPermissionLabel(perm) }}
          </span>
        </div>
      </template>

      <template #cell-source="{ row }">
        <span v-if="row.source_type === 'direct'" class="text-xs text-slate-600">
          直接授权
        </span>
        <span v-else class="text-xs text-slate-600">
          用户组: {{ row.group_name }}
        </span>
      </template>

      <template #cell-actions="{ row }">
        <button
          v-if="row.source_type === 'direct'"
          @click="revokeAuthorization(row.id)"
          class="text-xs text-error hover:underline"
        >
          取消授权
        </button>
        <span v-else class="text-xs text-slate-400">-</span>
      </template>
    </DataTable>
  </Modal>
</template>
```

### 13.3 编辑用户Modal组件

```vue
<!-- components/EditUserModal.vue -->
<template>
  <Modal :visible="visible" title="编辑用户" @close="handleClose">
    <form @submit.prevent="handleSubmit" class="space-y-4">
      <!-- 用户名（只读） -->
      <FormItem label="用户名">
        <Input :value="form.username" disabled />
      </FormItem>

      <!-- 基本信息 -->
      <div class="grid grid-cols-2 gap-4">
        <FormItem label="姓名" required>
          <Input v-model="form.full_name" />
        </FormItem>
        <FormItem label="邮箱" required>
          <Input v-model="form.email" type="email" />
        </FormItem>
      </div>

      <FormItem label="手机号">
        <Input v-model="form.phone" />
      </FormItem>

      <!-- 用户组 -->
      <FormItem label="用户组">
        <Select v-model="form.group_ids" mode="multiple" placeholder="选择用户组">
          <Option v-for="group in groups" :key="group.id" :value="group.id">
            {{ group.name }}
          </Option>
        </Select>
      </FormItem>

      <!-- 状态 -->
      <FormItem label="状态">
        <Radio.Group v-model="form.is_active">
          <Radio :value="true">活跃</Radio>
          <Radio :value="false">禁用</Radio>
        </Radio.Group>
      </FormItem>

      <!-- MFA -->
      <FormItem label="MFA">
        <Radio.Group v-model="form.mfa_enabled">
          <Radio :value="true">开启</Radio>
          <Radio :value="false">关闭</Radio>
        </Radio.Group>
      </FormItem>

      <!-- 按钮 -->
      <div class="flex justify-end gap-2">
        <Button @click="handleClose">取消</Button>
        <Button type="primary" html-type="submit" :loading="loading">保存</Button>
      </div>
    </form>
  </Modal>
</template>
```

### 13.4 重置密码Modal组件

```vue
<!-- components/ResetPasswordModal.vue -->
<template>
  <Modal :visible="visible" :title="`重置密码 - ${user.full_name}`" @close="handleClose">
    <form @submit.prevent="handleSubmit" class="space-y-4">
      <!-- 重置方式 -->
      <FormItem label="重置方式">
        <Radio.Group v-model="resetMethod">
          <Radio value="auto">
            <div class="flex flex-col">
              <span>自动生成密码并发送邮件</span>
              <span class="text-xs text-slate-500">
                系统将生成随机密码并发送到 {{ user.email }}
              </span>
            </div>
          </Radio>
          <Radio value="manual">手动设置新密码</Radio>
        </Radio.Group>
      </FormItem>

      <!-- 手动设置密码 -->
      <div v-if="resetMethod === 'manual'" class="space-y-3">
        <FormItem label="新密码" required>
          <Input.Password v-model="form.new_password" />
        </FormItem>
        <FormItem label="确认密码" required>
          <Input.Password v-model="form.confirm_password" />
        </FormItem>
      </div>

      <!-- 密码策略提示 -->
      <Alert type="info" show-icon>
        <template #message>
          <div class="text-xs">
            <div>密码策略:</div>
            <ul class="list-disc list-inside mt-1">
              <li>长度不少于8个字符</li>
              <li>必须包含大小写字母和数字</li>
              <li>建议包含特殊字符</li>
            </ul>
          </div>
        </template>
      </Alert>

      <!-- 选项 -->
      <FormItem>
        <Checkbox v-model="form.force_change">强制用户首次登录修改密码</Checkbox>
      </FormItem>

      <!-- 按钮 -->
      <div class="flex justify-end gap-2">
        <Button @click="handleClose">取消</Button>
        <Button type="primary" html-type="submit" :loading="loading">重置密码</Button>
      </div>
    </form>
  </Modal>
</template>
```

---

## 十四、权限控制设计

### 14.1 操作权限矩阵

| 操作 | 所需权限 | 说明 |
|------|---------|------|
| 查看用户列表 | user_mgmt.view | 基础查看权限 |
| 查看用户详情 | user_mgmt.view | 包括基本信息 |
| 查看已授权资产 | user_mgmt.view + authorization.view | 需要两个权限 |
| 编辑用户 | user_mgmt.edit | 修改用户信息 |
| 重置密码 | user_mgmt.reset_password | 管理员重置 |
| 删除用户 | user_mgmt.delete | 删除权限 |
| 取消授权 | authorization.delete | 授权管理权限 |

### 14.2 前端权限控制

```typescript
// composables/usePermission.ts
export function usePermission() {
  const authStore = useAuthStore()

  const hasPermission = (permission: string): boolean => {
    return authStore.permissions.includes(permission)
  }

  const hasAnyPermission = (permissions: string[]): boolean => {
    return permissions.some(p => hasPermission(p))
  }

  const hasAllPermissions = (permissions: string[]): boolean => {
    return permissions.every(p => hasPermission(p))
  }

  return {
    hasPermission,
    hasAnyPermission,
    hasAllPermissions
  }
}
```

```vue
<!-- 使用示例 -->
<template>
  <div>
    <!-- 编辑按钮 -->
    <button v-if="hasPermission('user_mgmt.edit')" @click="editUser">
      编辑
    </button>

    <!-- 删除按钮 -->
    <button v-if="hasPermission('user_mgmt.delete')" @click="deleteUser">
      删除
    </button>
  </div>
</template>
```

### 14.3 后端权限验证

```python
# app/core/permissions.py
from functools import wraps
from fastapi import HTTPException, Depends

def require_permission(permission: str):
    """权限验证装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=Depends(get_current_user), **kwargs):
            if not has_permission(current_user, permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"需要权限: {permission}"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# 使用示例
@router.put("/users/{user_id}")
@require_permission("user_mgmt.edit")
async def update_user(user_id: int, data: UserUpdate):
    pass

@router.delete("/users/{user_id}")
@require_permission("user_mgmt.delete")
async def delete_user(user_id: int):
    pass
```

---


## 十五、用户操作功能开发任务

### 15.1 后端开发任务

#### API接口开发
- [ ] GET /api/v1/users/:id/authorizations - 获取用户授权列表
- [ ] DELETE /api/v1/authorizations/:id - 取消授权
- [ ] GET /api/v1/users/:id - 获取用户详情
- [ ] PUT /api/v1/users/:id - 更新用户信息
- [ ] POST /api/v1/users/:id/reset-password - 重置密码
- [ ] DELETE /api/v1/users/:id - 删除用户
- [ ] GET /api/v1/users/:id/dependencies - 检查用户依赖

#### 业务逻辑实现
- [ ] 实现授权查询（直接+继承）
- [ ] 实现密码生成和邮件发送
- [ ] 实现软删除/硬删除逻辑
- [ ] 实现用户依赖检查
- [ ] 添加操作日志记录
- [ ] 添加改密日志记录

#### 权限控制
- [ ] 定义权限常量
- [ ] 实现权限验证装饰器
- [ ] 为每个接口添加权限验证

### 15.2 前端开发任务

#### 组件开发
- [ ] UserAuthorizationsModal.vue - 已授权资产
- [ ] EditUserModal.vue - 编辑用户
- [ ] ResetPasswordModal.vue - 重置密码
- [ ] DeleteUserConfirm.vue - 删除确认
- [ ] UserActions.vue - 操作按钮组

#### 功能实现
- [ ] 实现授权列表展示和筛选
- [ ] 实现用户信息编辑表单
- [ ] 实现密码重置（自动/手动）
- [ ] 实现删除确认和依赖检查
- [ ] 实现权限控制指令/组合式函数

#### API集成
- [ ] 封装用户操作相关API
- [ ] 实现错误处理和提示
- [ ] 实现加载状态管理

### 15.3 测试任务

#### 单元测试
- [ ] 测试授权查询逻辑
- [ ] 测试密码生成函数
- [ ] 测试用户依赖检查
- [ ] 测试权限验证逻辑

#### 集成测试
- [ ] 测试编辑用户流程
- [ ] 测试重置密码流程（自动/手动）
- [ ] 测试删除用户流程（软/硬删除）
- [ ] 测试取消授权流程

#### UI测试
- [ ] 测试所有Modal打开/关闭
- [ ] 测试表单验证
- [ ] 测试权限控制显示/隐藏
- [ ] 测试操作成功/失败提示

---

## 十六、测试用例设计

### 16.1 已授权资产功能测试

| 测试场景 | 输入 | 期望输出 |
|---------|------|---------|
| 查看直接授权 | 用户ID | 显示直接授权列表 |
| 查看继承授权 | 用户ID | 显示用户组授权列表 |
| 筛选授权记录 | 权限类型=查看 | 只显示查看权限 |
| 取消直接授权 | 授权ID | 授权被删除，列表更新 |
| 取消继承授权 | 授权ID | 提示无法操作 |

### 16.2 编辑用户功能测试

| 测试场景 | 输入 | 期望输出 |
|---------|------|---------|
| 正常编辑 | 修改姓名、邮箱 | 保存成功 |
| 邮箱重复 | 已存在的邮箱 | 提示邮箱已被使用 |
| 必填项为空 | 姓名为空 | 提示必填 |
| 修改用户组 | 添加/移除用户组 | 用户组更新 |
| 禁用用户 | is_active=false | 用户被禁用 |

### 16.3 重置密码功能测试

| 测试场景 | 输入 | 期望输出 |
|---------|------|---------|
| 自动生成密码 | method=auto | 生成随机密码，发送邮件 |
| 手动设置密码 | 新密码 | 密码更新成功 |
| 密码强度不足 | 弱密码 | 提示密码不符合策略 |
| 两次密码不一致 | 不同密码 | 提示密码不一致 |
| 邮件发送失败 | 无效邮箱 | 提示邮件发送失败 |

### 16.4 删除用户功能测试

| 测试场景 | 输入 | 期望输出 |
|---------|------|---------|
| 软删除用户 | method=soft | 用户标记为已删除 |
| 硬删除用户 | method=hard | 用户永久删除 |
| 确认用户名错误 | 错误的用户名 | 提示用户名不匹配 |
| 删除有授权的用户 | 有5条授权 | 显示警告，授权同时删除 |
| 删除管理员 | 最后一个管理员 | 提示不能删除 |

---

## 十七、更新总结

### 17.1 本次更新内容

1. **已授权资产功能**
   - Modal设计和字段定义
   - 支持直接授权和继承授权查看
   - 支持取消直接授权

2. **编辑用户功能**
   - 表单设计和可编辑字段
   - 用户名不可修改
   - 支持多用户组选择

3. **重置密码功能**
   - 自动生成和手动设置两种方式
   - 邮件通知功能
   - 改密日志记录

4. **删除用户功能**
   - 软删除和硬删除支持
   - 依赖检查和警告
   - 二次确认机制

5. **权限控制**
   - 前端权限指令
   - 后端权限验证
   - 权限矩阵定义

### 17.2 涉及的文件

#### 后端文件
- `app/api/users.py` - 用户API路由
- `app/services/user_service.py` - 用户业务逻辑
- `app/core/permissions.py` - 权限验证
- `app/utils/password.py` - 密码生成
- `app/utils/email.py` - 邮件发送

#### 前端文件
- `views/users/UserList.vue` - 用户列表页
- `components/UserAuthorizationsModal.vue` - 授权Modal
- `components/EditUserModal.vue` - 编辑Modal
- `components/ResetPasswordModal.vue` - 重置密码Modal
- `components/DeleteUserConfirm.vue` - 删除确认
- `composables/usePermission.ts` - 权限控制

---

**文档版本**: v2.2 (用户操作增强版)  
**最后更新**: 2026-03-27  
**更新内容**: 
- 添加用户操作功能详细设计（已授权资产、编辑、重置密码、删除）
- 添加前端组件实现代码
- 添加权限控制设计
- 添加开发任务清单
- 添加测试用例设计

