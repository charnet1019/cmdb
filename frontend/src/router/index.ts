import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false, title: '登录' }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard'
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘', icon: 'dashboard' }
      },
      {
        path: 'assets',
        name: 'Assets',
        component: () => import('@/views/assets/AssetList.vue'),
        meta: { title: '资产列表', icon: 'inventory_2' }
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/users/UserList.vue'),
        meta: { title: '用户', icon: 'person' }
      },
      {
        path: 'users/groups',
        name: 'UserGroups',
        component: () => import('@/views/users/UserGroups.vue'),
        meta: { title: '用户组', icon: 'groups' }
      },
      {
        path: 'permissions/authorizations',
        name: 'Authorizations',
        component: () => import('@/views/permissions/Authorizations.vue'),
        meta: { title: '资产授权', icon: 'verified_user' }
      },
      {
        path: 'logs/login',
        name: 'LoginLogs',
        component: () => import('@/views/logs/LoginLogs.vue'),
        meta: { title: '登录日志', icon: 'login' }
      },
      {
        path: 'logs/operation',
        name: 'OperationLogs',
        component: () => import('@/views/logs/OperationLogs.vue'),
        meta: { title: '操作日志', icon: 'history' }
      },
      {
        path: 'logs/password',
        name: 'PasswordLogs',
        component: () => import('@/views/logs/PasswordLogs.vue'),
        meta: { title: '改密日志', icon: 'password' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '系统设置', icon: 'settings' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && !token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.name === 'Login' && token) {
    next({ name: 'Dashboard' })
  } else {
    // Set page title
    document.title = to.meta.title ? `${to.meta.title} - CMDB` : 'CMDB'
    next()
  }
})

export default router