// Shared permission label catalog used across user/group/profile/authorization views.
export const PERMISSION_OPTIONS = [
  { key: 'view', label: '查看资产' },
  { key: 'manage', label: '管理资产' },
  { key: 'authorize', label: '资产授权' },
  { key: 'view_users', label: '查看用户' },
  { key: 'user_mgmt', label: '用户管理' },
  { key: 'sys_config', label: '系统设置' },
  { key: 'audit_log', label: '日志审计' },
  { key: 'view_pwd', label: '查看密码' },
  { key: 'export', label: '导出资产' },
  { key: 'export_pwd', label: '导出密码' },
]

export const PERMISSION_LABELS: Record<string, string> = Object.fromEntries(
  PERMISSION_OPTIONS.map(opt => [opt.key, opt.label])
)
