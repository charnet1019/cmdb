# CMDB 原型页面分析总结

## 一、页面清单与字段映射

### 1. 登录页面 (prototype/cmdb/code.html)
**字段**:
- 用户名 (username)
- 密码 (password)
- 记住设备 (checkbox)
- 语言选择器 (简体中文)

**布局**: 左右分屏，左侧品牌展示 + 右侧表单

---

### 2. 仪表盘 (prototype/simplified/code.html)
**资产统计卡片**:
- 总资产: 1,284
- 运行中: 1,242
- 离线: 42
- 使用率: 96.7%

**用户统计卡片**:
- 总用户: 56
- 活跃: 52
- 禁用: 4
- 当前在线: 12

**资产类型分布**: 饼图 (虚拟机50%, 裸金属30%, 网络设备20%)
**在线状态**: 用户列表 (头像 + 姓名 + 状态)

---

### 3. 资产管理 - 主机 (prototype/_2/code.html)
**分类标签**: 所有、主机、网络设备、数据库、云服务、Web、GPT

**表格字段**:
- 名称 (name + 资产编号)
- IP/主机 (address)
- 系统平台 (platform + OS图标)
- 用户名密码 (多个凭证，每个包含: username + password + 操作按钮)

**凭证操作**: 复制用户名、复制密码、查看密码、编辑、删除

---

### 4. 资产管理 - 网络设备 (prototype/_3/code.html)
**表格字段**:
- 名称 (name + SN序列号)
- IP地址 (ip_address)
- 设备类型 (device_type: 交换机/路由器/无线控制器)
- 厂商/型号 (vendor/model: Cisco/Huawei/Aruba)
- 管理凭据 (admin账号 + snmp_v3)

**特殊凭证**: SNMP v3 (AuthPriv)

---

### 5. 资产管理 - 数据库 (prototype/_11/code.html)
**表格字段**:
- 名称 (name + 数据库编号)
- IP/主机 (ip_address)
- 数据库类型 (db_type: MySQL 8.0/PostgreSQL 15)
- 用户名密码 (多账号: admin/readonly)

---

### 6. 资产管理 - 云服务 (prototype/url/code.html)
**表格字段**:
- 名称 (name + 资源ID)
- URL (带彩色图标)
- 系统平台 (platform: AWS/阿里云/腾讯云)
- 访问凭证 (AKID/Secret/RAM-User/SecretId)

**特点**: URL列带彩色link图标，凭证字段大写显示

---

### 7. 资产管理 - 资产树 (prototype/expanded_sidebar_navigation/code.html)
**左侧树导航**:
- 资产树/类型树 标签切换
- 树结构: Default → 余姚 → git, gpu, pve, ucloud, virtsmart

**右侧表格**: 紧凑型布局，与主机页面相同字段

---

### 8. 资产管理 - 类型树 (prototype/_7/code.html)
**类型层级**:
- 所有类型
  - 主机 (Linux, Unix, Windows)
  - 网络设备 (交换机, 路由器, 防火墙)
  - 数据库 (MySQL, MongoDB, Redis)
  - 云服务 (Kubernetes, 公有云, 私有云)
  - Web (网站)

---

### 9. 用户管理 - 用户列表 (prototype/cleaned_layout/code.html)
**表格字段**:
- 用户名 (username + 头像)
- 姓名 (full_name)
- 邮箱 (email)
- 用户组 (group_name)
- 最后登录时间 (last_login_at)
- 状态 (status: Active/Disabled)

**操作**: 已授权资产、编辑、重置密码、删除

---

### 10. 创建用户 (prototype/add_user_final_layout/code.html)
**Modal表单字段**:
- 用户名 (username) *必填
- 姓名 (full_name) *必填
- 邮箱 (email) *必填
- 手机号 (phone) 可选
- 用户组 (group_id) 下拉选择
- 状态 (is_active) 单选: 活跃/禁用
- MFA开启 (mfa_enabled) 单选: 开启/关闭
- 密码 (password) *必填
- 确认密码 (password_confirm) *必填

---

### 11. 用户管理 - 用户组 (prototype/added_authorized_assets/code.html)
**表格字段**:
- 用户组名称 (name + 图标)
- 描述 (description)
- 成员数量 (member_count)
- 创建时间 (created_at)

**操作**: 已授权资产、编辑、删除

---

### 12. 创建用户组 (prototype/_4/code.html)
**Modal表单字段**:
- 用户组名称 (name) *必填
- 用户组描述 (description) textarea
- 初始成员 (member_ids) chip选择器 + 搜索

---

### 13. 权限管理 - 资产授权列表 (prototype/full_navigation_hierarchy/code.html)
**表格字段**:
- 用户/用户组 (entity_type + entity_id, 显示头像+名称)
- 资产/资产组 (target_type + target_id)
- 权限类型 (permissions: 多个徽章显示)
- 授权时间 (created_at)
- 状态 (status: Active/Expired)

**权限类型**:
- 管理资产用户名密码
- 查看资产
- 查看复制资产密码
- 管理资产

**操作**: 编辑、禁用、删除

---

### 14. 新增授权 (prototype/_1/code.html)
**Modal表单字段**:
- 授权对象 (entity_type) 切换: 用户/用户组
- 选择对象 (entity_id) 搜索 + 已选标签
- 资产范围 (target_type) 切换: 单个资产/资产组
- 选择资产 (target_id) 搜索
- 权限类型 (permissions) 多选复选框:
  - 查看资产
  - 管理资产
  - 用户管理
  - 系统设置
  - 日志审计
  - 查看复制资产密码
  - 管理资产用户名密码
- 有效期 (validity) 单选: 永久/临时
- 起止时间 (valid_from, valid_until) 日期选择器

---

### 15. 日志审计 - 登录日志 (prototype/_6/code.html)
**统计卡片**:
- 今日总登录: 1,284
- 成功率: 98.2%
- 异常尝试: 24
- 主要地域: Beijing

**筛选栏**:
- 用户查询 (search)
- 时间范围 (date_range)
- 状态 (status) 下拉

**表格字段**:
- 时间 (created_at)
- 用户名 (username + 头像)
- 登录名 (login_name)
- 来源IP (ip_address)
- 登录方式 (login_method: Password/SSH Key/OAuth 2.0/LDAP)
- 状态 (status: 成功/失败)

---

### 16. 日志审计 - 操作日志 (prototype/_5/code.html)
**统计卡片**:
- Today's Total Operations: 1,482
- Success Rate: 99.2%
- High-Risk Activities: 07

**筛选栏**:
- 操作者搜索 (operator_search)
- 时间范围 (date_range)
- 操作类型 (action_type: CREATE/EDIT/DELETE/AUTHORIZE)

**表格字段**:
- 时间 (created_at)
- 操作者 (operator + 头像)
- 操作类型 (action: 彩色徽章)
- 目标资产 (target_asset)
- 状态 (status: 成功/失败)

---

### 17. 日志审计 - 改密日志 (prototype/_9/code.html)
**统计卡片**:
- 今日改密总数: 128
- 执行成功率: 98.4%
- 高危操作数: 3

**筛选栏**:
- 搜索 (search: 操作者/资产/账号)
- 状态 (status)
- 时间范围 (date_range)

**表格字段**:
- 时间 (created_at)
- 操作者 (operator)
- 目标资产 (target_asset: 名称 + IP)
- 目标账号 (target_account)
- 类型 (change_type: 自动改密/手动修改/计划任务/手动强制)
- 状态 (status)

**特点**: 高危操作橙色背景高亮

---

### 18. 系统设置 (prototype/_10/code.html)
**基础配置**:
- 站点标题 (site_title)
- 组织名称 (organization_name)

**登录首页**:
- 登录欢迎标题 (login_welcome_title)
- 自定义背景图片 (login_background_image) 上传
- 显示组织Logo (show_organization_logo) 开关

**访问限制**:
- 最大登录失败次数 (max_login_failures) 下拉
- 锁定时间 (lockout_duration) 下拉
- 备案号 (icp_number)
- 备案链接 (icp_link)

**密码复杂度规则**:
- 大写字母 (require_uppercase) checkbox
- 小写字母 (require_lowercase) checkbox
- 数字 (require_digit) checkbox
- 特殊字符 (require_special) checkbox
- 最小长度 (min_length) 滑块: 8-32

---

### 19. 修改密码 (prototype/_8/code.html)
**Modal表单字段**:
- 原密码 (old_password)
- 新密码 (new_password)
- 确认新密码 (new_password_confirm)

**密码策略提示**:
- 必须包含大小写字母和数字
- 长度不少于8个字符
- 不可与最近3次使用的密码重复

---

### 20. GPT资产页面
**设计参考**: prototype/url/code.html (云服务页面)

**表格字段**:
- 名称 (name)
- URL (url)
- 系统平台 (platform: OpenAI/Claude/ChatGLM)
- 访问凭证 (API Key)

---

## 二、通用设计模式

### 布局结构
```
固定顶部导航栏 (h-16) + 固定左侧边栏 (w-64) + 主内容区
```

### 分类标签页
- 图标 + 文字
- 激活状态: 底部2px蓝色下划线 + 图标FILL:1

### 数据表格
- 表头: bg-slate-50
- 行悬停: hover:bg-slate-50/50
- 复选框: 左侧第一列
- 排序图标: unfold_more

### 凭证显示
- 灰色背景卡片: bg-slate-100/80
- 用户名 + 分隔线 + 密码(隐藏)
- 操作图标: 复制、查看、编辑、删除
- 图标大小: text-[14px]

### 状态徽章
- Active: 绿色
- Disabled/Expired: 灰色
- 成功: 绿色
- 失败: 红色

### Modal对话框
- 最大宽度: max-w-2xl
- 圆角: rounded-xl
- 阴影: shadow-2xl
- 背景遮罩: bg-slate-900/60 backdrop-blur-sm

---

## 三、核心技术要求

### 后端
- Python 3.11+ / FastAPI
- PostgreSQL 15+ (数据存储)
- Redis 7+ (缓存/会话)
- SQLAlchemy 2.0 (ORM)
- Alembic (数据库迁移)
- JWT (认证)
- bcrypt (密码哈希)
- Fernet (凭证加密)

### 前端
- TypeScript / Vue 3 (Composition API)
- Ant Design Vue 4.x
- Vite (构建工具)
- Pinia (状态管理)
- Vue Router 4
- Tailwind CSS
- Material Symbols Outlined (图标)
- Manrope (标题字体) + Inter (正文字体)

### 设计系统
- 无边界设计 (禁用1px边框)
- 表面层级系统 (surface → surface_container_low → surface_container_lowest)
- 玻璃效果 (backdrop-blur + 半透明)
- 主色调: #005daa (primary) / #0075d5 (primary-container)
- 圆角: 4px/8px/12px/9999px

---

## 四、数据库核心表

1. **users** - 用户表
2. **groups** - 用户组表
3. **user_groups** - 用户组关系表
4. **organizations** - 组织架构表
5. **assets** - 资产表
6. **credentials** - 凭证表 (加密存储)
7. **authorizations** - 授权表
8. **login_logs** - 登录日志表
9. **operation_logs** - 操作日志表
10. **password_change_logs** - 改密日志表
11. **settings** - 系统设置表

---

## 五、关键功能实现

### 凭证加密
- 使用 Fernet 对称加密
- 密钥存储在环境变量
- 解密需要权限验证

### 权限验证
- 基于 JWT Token
- 细粒度权限控制
- 支持有效期检查

### 资产树
- 递归查询组织结构
- 统计每个节点资产数量
- 支持展开/折叠

### 审计日志
- 自动记录所有操作
- 异步写入提高性能
- 支持高级筛选和导出

---

**文档版本**: v1.0
**创建日期**: 2026-03-26
**对应原型**: 20个HTML页面完整分析
