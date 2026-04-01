<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, SearchOutlined, FolderOpenOutlined, FolderOutlined, FileTextOutlined, DownOutlined, KeyOutlined, EditOutlined, DeleteOutlined, CloseOutlined, PlusCircleOutlined, UserOutlined, EyeOutlined, CopyOutlined, AppstoreOutlined, ClusterOutlined, DatabaseOutlined, CloudServerOutlined, GlobalOutlined, RobotOutlined, MenuOutlined } from '@ant-design/icons-vue'
import { getAssets, getOrganizations, createAsset, updateAsset, deleteAsset, getCredentials, createCredential, decryptCredential, deleteCredential } from '@/api/assets'
import type { Asset, AssetCategory, Organization, Credential } from '@/types'

// Data
const assets = ref<Asset[]>([])
const organizations = ref<Organization[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const limit = ref(20)

// Filters
const activeCategory = ref<AssetCategory | 'all'>('all')
const searchQuery = ref('')
const selectedOrgId = ref<number | null>(null)

// Asset tree expansion
const expandedOrgIds = ref<Set<number>>(new Set())

// Modal
const showModal = ref(false)
const showCredentialModal = ref(false)
const modalLoading = ref(false)
const editingAsset = ref<Asset | null>(null)
const selectedAsset = ref<Asset | null>(null)
const credentials = ref<Credential[]>([])
const credentialLoading = ref(false)

// Credential form
const credentialForm = ref({
  username: '',
  password: '',
  credential_type: 'password'
})

// Decrypted passwords cache
const decryptedPasswords = ref<Map<number, string>>(new Map())

// Form
const form = ref({
  name: '',
  asset_code: '',
  category: 'host' as AssetCategory,
  address: '',
  platform: '',
  organization_id: null as number | null,
  device_type: '',
  vendor: '',
  model: '',
  serial_number: '',
  url: '',
  notes: ''
})

// Categories
const categories = [
  { key: 'all', label: '全部', icon: MenuOutlined },
  { key: 'host', label: '主机', icon: AppstoreOutlined },
  { key: 'network', label: '网络设备', icon: ClusterOutlined },
  { key: 'database', label: '数据库', icon: DatabaseOutlined },
  { key: 'cloud', label: '云服务', icon: CloudServerOutlined },
  { key: 'web', label: '网站服务', icon: GlobalOutlined },
  { key: 'gpt', label: 'AI服务', icon: RobotOutlined }
]

// Category options for form
const categoryOptions = categories.filter(c => c.key !== 'all')

// Platform options by category
const platformOptions: Record<string, string[]> = {
  host: ['Linux', 'Windows', 'Unix', 'macOS'],
  network: ['Cisco IOS', 'Huawei VRP', 'Juniper JunOS', 'Aruba OS'],
  database: ['MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Oracle'],
  cloud: ['AWS', '阿里云', '腾讯云', 'Azure', 'GCP'],
  web: ['Nginx', 'Apache', 'IIS', 'Tomcat'],
  gpt: ['OpenAI', 'Claude', 'ChatGLM', '通义千问']
}

// Device type options for network
const deviceTypeOptions = ['交换机', '路由器', '防火墙', '无线控制器', '负载均衡']

// Modal title
const modalTitle = computed(() => editingAsset.value ? '编辑资产' : '创建资产')

// Fetch assets
async function fetchAssets() {
  loading.value = true
  try {
    const result = await getAssets({
      page: page.value,
      limit: limit.value,
      category: activeCategory.value !== 'all' ? activeCategory.value : undefined,
      search: searchQuery.value || undefined,
      organization_id: selectedOrgId.value || undefined
    })
    assets.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    message.error('获取资产列表失败')
    assets.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// Fetch organizations
async function fetchOrganizations() {
  try {
    organizations.value = await getOrganizations() || []
  } catch (error) {
    console.error('Failed to fetch organizations')
    organizations.value = []
  }
}

// Change category
function changeCategory(category: AssetCategory | 'all') {
  activeCategory.value = category
  page.value = 1
  fetchAssets()
}

// Handle search
function handleSearch() {
  page.value = 1
  fetchAssets()
}

// Handle page change
function handlePageChange(newPage: number) {
  page.value = newPage
  fetchAssets()
}

// Get category icon
function getCategoryIcon(category: string) {
  const cat = categories.find(c => c.key === category)
  return cat?.icon || MenuOutlined
}

// Toggle org expansion
function toggleOrg(orgId: number) {
  if (expandedOrgIds.value.has(orgId)) {
    expandedOrgIds.value.delete(orgId)
  } else {
    expandedOrgIds.value.add(orgId)
  }
}

// Check if org is expanded
function isOrgExpanded(orgId: number): boolean {
  return expandedOrgIds.value.has(orgId)
}

// Select organization
function selectOrganization(orgId: number | null) {
  selectedOrgId.value = orgId
  handleSearch()
}

// Get flattened org tree for display
const flattenedOrgs = computed(() => {
  const result: { id: number; name: string; count: number; level: number; hasChildren: boolean }[] = []

  function flatten(orgs: Organization[], level: number = 0) {
    for (const org of orgs) {
      result.push({
        id: org.id,
        name: org.name,
        count: org.count || 0,
        level,
        hasChildren: (org.children?.length || 0) > 0
      })
      if (isOrgExpanded(org.id) && org.children) {
        flatten(org.children, level + 1)
      }
    }
  }

  flatten(organizations.value)
  return result
})

// Open create modal
function openCreateModal() {
  editingAsset.value = null
  form.value = {
    name: '',
    asset_code: '',
    category: 'host',
    address: '',
    platform: '',
    organization_id: selectedOrgId.value,
    device_type: '',
    vendor: '',
    model: '',
    serial_number: '',
    url: '',
    notes: ''
  }
  showModal.value = true
}

// Open edit modal
function openEditModal(asset: Asset) {
  editingAsset.value = asset
  form.value = {
    name: asset.name,
    asset_code: asset.asset_code || '',
    category: asset.category,
    address: asset.address || '',
    platform: asset.platform || '',
    organization_id: asset.organization_id,
    device_type: asset.device_type || '',
    vendor: asset.vendor || '',
    model: asset.model || '',
    serial_number: asset.serial_number || '',
    url: asset.url || '',
    notes: asset.notes || ''
  }
  showModal.value = true
}

// Submit form
async function handleSubmit() {
  if (!form.value.name) {
    message.error('请输入资产名称')
    return
  }

  modalLoading.value = true
  try {
    const data = {
      name: form.value.name,
      asset_code: form.value.asset_code || undefined,
      category: form.value.category,
      address: form.value.address || undefined,
      platform: form.value.platform || undefined,
      organization_id: form.value.organization_id || undefined,
      device_type: form.value.device_type || undefined,
      vendor: form.value.vendor || undefined,
      model: form.value.model || undefined,
      serial_number: form.value.serial_number || undefined,
      url: form.value.url || undefined,
      notes: form.value.notes || undefined
    }

    if (editingAsset.value) {
      await updateAsset(editingAsset.value.id, data)
      message.success('资产更新成功')
    } else {
      await createAsset(data)
      message.success('资产创建成功')
    }
    showModal.value = false
    fetchAssets()
  } catch (error: any) {
    message.error(error.response?.data?.detail || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

// Delete asset
async function handleDelete(asset: Asset) {
  if (!confirm(`确定要删除资产 "${asset.name}" 吗?`)) return

  try {
    await deleteAsset(asset.id)
    message.success('资产已删除')
    fetchAssets()
  } catch (error) {
    message.error('删除失败')
  }
}

// Open credential modal
async function openCredentialModal(asset: Asset) {
  selectedAsset.value = asset
  credentials.value = []
  credentialLoading.value = true
  showCredentialModal.value = true
  decryptedPasswords.value.clear()

  try {
    credentials.value = await getCredentials(asset.id)
  } catch (error) {
    message.error('获取凭证失败')
  } finally {
    credentialLoading.value = false
  }
}

// View/decrypt password
async function viewPassword(credential: Credential) {
  if (decryptedPasswords.value.has(credential.id)) {
    // Already decrypted, copy to clipboard
    const password = decryptedPasswords.value.get(credential.id)!
    await copyToClipboard(password)
    return
  }

  try {
    const result = await decryptCredential(credential.id)
    if (result.password) {
      decryptedPasswords.value.set(credential.id, result.password)
      message.success('密码已解密')
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || '解密失败')
  }
}

// Copy to clipboard
async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制到剪贴板')
  } catch {
    message.error('复制失败')
  }
}

// Copy username
function copyUsername(username: string) {
  copyToClipboard(username)
}

// Copy password
function copyPassword(credential: Credential) {
  const password = decryptedPasswords.value.get(credential.id)
  if (password) {
    copyToClipboard(password)
  } else {
    message.warning('请先点击查看密码')
  }
}

// Add credential
async function addCredential() {
  if (!credentialForm.value.username || !credentialForm.value.password) {
    message.error('请填写用户名和密码')
    return
  }

  if (!selectedAsset.value) return

  try {
    await createCredential(selectedAsset.value.id, {
      username: credentialForm.value.username,
      password: credentialForm.value.password,
      credential_type: credentialForm.value.credential_type
    })
    message.success('凭证添加成功')
    credentialForm.value = { username: '', password: '', credential_type: 'password' }
    credentials.value = await getCredentials(selectedAsset.value.id)
  } catch (error: any) {
    message.error(error.response?.data?.detail || '添加失败')
  }
}

// Delete credential
async function handleDeleteCredential(credential: Credential) {
  if (!confirm(`确定要删除凭证 "${credential.username}" 吗?`)) return

  try {
    await deleteCredential(credential.id)
    message.success('凭证已删除')
    credentials.value = credentials.value.filter(c => c.id !== credential.id)
    decryptedPasswords.value.delete(credential.id)
  } catch (error) {
    message.error('删除失败')
  }
}

// Initial load
onMounted(() => {
  fetchAssets()
  fetchOrganizations()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">资产列表</h1>
        <p class="text-slate-500 mt-1">管理和查看所有IT基础设施资产</p>
      </div>
      <button @click="openCreateModal" class="btn-primary flex items-center gap-2">
        <PlusOutlined />
        创建资产
      </button>
    </div>

    <!-- Category Tabs -->
    <div class="bg-white rounded-xl shadow-sm overflow-x-auto">
      <div class="flex border-b border-slate-100">
        <button
          v-for="cat in categories"
          :key="cat.key"
          @click="changeCategory(cat.key as AssetCategory | 'all')"
          class="flex items-center gap-2 px-6 py-4 text-sm font-medium transition-colors whitespace-nowrap"
          :class="
            activeCategory === cat.key
              ? 'text-teal-600 border-b-2 border-teal-600'
              : 'text-slate-500 hover:text-slate-700'
          "
        >
          <component :is="cat.icon" class="text-lg" />
          {{ cat.label }}
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex gap-6">
      <!-- Asset Tree (Left Panel) -->
      <div class="hidden lg:block w-60 flex-shrink-0">
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold text-slate-900">资产树</h3>
            <button
              v-if="selectedOrgId"
              @click="selectOrganization(null)"
              class="text-xs text-primary hover:underline"
            >
              清除筛选
            </button>
          </div>
          <!-- Tree -->
          <div class="text-sm">
            <div
              class="py-2 px-2 rounded cursor-pointer hover:bg-slate-50 mb-1"
              :class="selectedOrgId === null ? 'bg-primary/10 text-primary' : 'text-slate-600'"
              @click="selectOrganization(null)"
            >
              <FolderOpenOutlined class="text-sm mr-1" />
              全部资产
            </div>
            <template v-for="org in flattenedOrgs" :key="org.id">
              <div
                class="py-1.5 px-2 rounded cursor-pointer hover:bg-slate-50 flex items-center gap-1"
                :class="selectedOrgId === org.id ? 'bg-primary/10 text-primary' : 'text-slate-600'"
                :style="{ paddingLeft: `${org.level * 16 + 8}px` }"
                @click="selectOrganization(org.id)"
              >
                <DownOutlined v-if="org.hasChildren" class="text-xs cursor-pointer hover:bg-slate-200 rounded" @click.stop="toggleOrg(org.id)" />
                <span v-else class="w-4"></span>
                <FolderOutlined v-if="org.hasChildren" class="text-sm mr-1" />
                <FileTextOutlined v-else class="text-sm mr-1" />
                <span class="flex-1 truncate">{{ org.name }}</span>
                <span class="text-xs text-slate-400">({{ org.count }})</span>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- Asset Table (Right Panel) -->
      <div class="flex-1">
        <!-- Toolbar -->
        <div class="bg-white rounded-xl shadow-sm p-4 mb-4">
          <div class="flex items-center gap-4">
            <div class="relative flex-1 max-w-md">
              <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                v-model="searchQuery"
                type="text"
                placeholder="搜索资产..."
                class="input-field pl-10"
                @keyup.enter="handleSearch"
              />
            </div>
            <button @click="handleSearch" class="btn-secondary">
              搜索
            </button>
          </div>
        </div>

        <!-- Table -->
        <div class="bg-white rounded-xl shadow-sm overflow-hidden">
          <table class="data-table">
            <thead>
              <tr>
                <th>名称</th>
                <th>地址</th>
                <th>平台</th>
                <th>凭证</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="5" class="text-center py-8 text-slate-500">
                  加载中...
                </td>
              </tr>
              <tr v-else-if="assets.length === 0">
                <td colspan="5" class="text-center py-8 text-slate-500">
                  暂无数据
                </td>
              </tr>
              <tr v-for="asset in assets" :key="asset.id">
                <td>
                  <div class="flex items-center gap-3">
                    <component :is="getCategoryIcon(asset.category)" class="text-primary" />
                    <div>
                      <p class="font-medium text-slate-900">{{ asset.name }}</p>
                      <p v-if="asset.asset_code" class="text-xs text-slate-400">{{ asset.asset_code }}</p>
                    </div>
                  </div>
                </td>
                <td>
                  <span class="text-sm text-slate-600 font-mono">{{ asset.address || asset.url || '-' }}</span>
                </td>
                <td>
                  <span class="text-sm text-slate-600">{{ asset.platform || '-' }}</span>
                </td>
                <td>
                  <button
                    @click="openCredentialModal(asset)"
                    class="flex items-center gap-1 text-primary hover:underline"
                  >
                    <KeyOutlined class="text-sm" />
                    <span class="text-xs">{{ asset.credentials?.length || 0 }} 个凭证</span>
                  </button>
                </td>
                <td>
                  <div class="flex items-center gap-2">
                    <button @click="openEditModal(asset)" class="p-1.5 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-600" title="编辑">
                      <EditOutlined class="text-lg" />
                    </button>
                    <button
                      @click="handleDelete(asset)"
                      class="p-1.5 hover:bg-red-50 rounded text-slate-400 hover:text-red-600"
                      title="删除"
                    >
                      <DeleteOutlined class="text-lg" />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- Pagination -->
          <div class="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
            <span class="text-sm text-slate-500">
              共 {{ total }} 条记录
            </span>
            <div class="flex items-center gap-2">
              <button
                @click="handlePageChange(page - 1)"
                :disabled="page === 1"
                class="px-3 py-1.5 text-sm border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50"
              >
                上一页
              </button>
              <span class="text-sm text-slate-600">{{ page }} / {{ Math.ceil(total / limit) || 1 }}</span>
              <button
                @click="handlePageChange(page + 1)"
                :disabled="page >= Math.ceil(total / limit)"
                class="px-3 py-1.5 text-sm border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-50"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create/Edit Asset Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showModal = false"></div>
      <div class="relative bg-white w-full max-w-2xl rounded-xl shadow-2xl max-h-[90vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-bold text-slate-900">{{ modalTitle }}</h2>
          <button @click="showModal = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleSubmit" class="space-y-4">
            <!-- Basic Info -->
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">资产名称 <span class="text-red-500">*</span></label>
                <input v-model="form.name" type="text" class="input-field" placeholder="请输入资产名称" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">资产编号</label>
                <input v-model="form.asset_code" type="text" class="input-field" placeholder="CI编号" />
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">资产类型 <span class="text-red-500">*</span></label>
                <select v-model="form.category" class="input-field">
                  <option v-for="cat in categoryOptions" :key="cat.key" :value="cat.key">{{ cat.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">所属组织</label>
                <select v-model="form.organization_id" class="input-field">
                  <option :value="null">无</option>
                  <option v-for="org in organizations" :key="org.id" :value="org.id">{{ org.name }}</option>
                </select>
              </div>
            </div>

            <!-- Address/URL based on category -->
            <div class="grid grid-cols-2 gap-4">
              <div v-if="form.category !== 'cloud' && form.category !== 'gpt' && form.category !== 'web'">
                <label class="block text-sm font-medium text-slate-700 mb-1">地址</label>
                <input v-model="form.address" type="text" class="input-field" placeholder="IP 或 主机名:端口" />
              </div>
              <div v-if="form.category === 'web' || form.category === 'gpt'">
                <label class="block text-sm font-medium text-slate-700 mb-1">URL</label>
                <input v-model="form.url" type="text" class="input-field" placeholder="https://" />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">平台</label>
                <select v-model="form.platform" class="input-field">
                  <option value="">请选择</option>
                  <option v-for="p in platformOptions[form.category]" :key="p" :value="p">{{ p }}</option>
                </select>
              </div>
            </div>

            <!-- Network specific -->
            <template v-if="form.category === 'network'">
              <div class="grid grid-cols-3 gap-4">
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">设备类型</label>
                  <select v-model="form.device_type" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="t in deviceTypeOptions" :key="t" :value="t">{{ t }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">厂商</label>
                  <input v-model="form.vendor" type="text" class="input-field" placeholder="如: Cisco" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">型号</label>
                  <input v-model="form.model" type="text" class="input-field" placeholder="如: C9300-48P" />
                </div>
              </div>
            </template>

            <!-- Notes -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">备注</label>
              <textarea v-model="form.notes" class="input-field h-24 resize-none" placeholder="资产描述或备注"></textarea>
            </div>

            <!-- Actions -->
            <div class="flex justify-end gap-2 pt-4">
              <button type="button" @click="showModal = false" class="btn-secondary">取消</button>
              <button type="submit" :disabled="modalLoading" class="btn-primary">
                {{ modalLoading ? '处理中...' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Credential Modal -->
    <div v-if="showCredentialModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showCredentialModal = false"></div>
      <div class="relative bg-white w-full max-w-2xl rounded-xl shadow-2xl max-h-[80vh] overflow-y-auto">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-xl font-bold text-slate-900">凭证管理 - {{ selectedAsset?.name }}</h2>
          <button @click="showCredentialModal = false" class="p-2 hover:bg-slate-50 rounded-full">
            <CloseOutlined />
          </button>
        </div>
        <div class="p-6">
          <!-- Add Credential Form -->
          <div class="bg-slate-50 rounded-lg p-4 mb-4">
            <h4 class="font-medium text-slate-700 mb-3">添加凭证</h4>
            <div class="grid grid-cols-3 gap-3">
              <input
                v-model="credentialForm.username"
                type="text"
                class="input-field"
                placeholder="用户名"
              />
              <input
                v-model="credentialForm.password"
                type="password"
                class="input-field"
                placeholder="密码"
              />
              <button @click="addCredential" class="btn-primary">
                <PlusCircleOutlined class="text-sm mr-1" />
                添加
              </button>
            </div>
          </div>

          <!-- Credentials List -->
          <div v-if="credentialLoading" class="text-center py-8 text-slate-500">加载中...</div>
          <div v-else-if="credentials.length === 0" class="text-center py-8 text-slate-500">暂无凭证</div>
          <div v-else class="space-y-3">
            <div
              v-for="cred in credentials"
              :key="cred.id"
              class="flex items-center justify-between bg-slate-50 rounded-lg p-3"
            >
              <div class="flex items-center gap-4">
                <UserOutlined class="text-slate-400" />
                <div>
                  <p class="font-medium text-slate-900">{{ cred.username }}</p>
                  <p v-if="decryptedPasswords.has(cred.id)" class="text-sm text-slate-600 font-mono">
                    {{ decryptedPasswords.get(cred.id) }}
                  </p>
                  <p v-else class="text-sm text-slate-400">••••••••</p>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <button
                  @click="copyUsername(cred.username)"
                  class="p-1.5 hover:bg-white rounded text-slate-400 hover:text-slate-600"
                  title="复制用户名"
                >
                  <CopyOutlined class="text-lg" />
                </button>
                <button
                  @click="viewPassword(cred)"
                  class="p-1.5 hover:bg-white rounded text-slate-400 hover:text-slate-600"
                  title="查看密码"
                >
                  <EyeOutlined class="text-lg" />
                </button>
                <button
                  @click="copyPassword(cred)"
                  class="p-1.5 hover:bg-white rounded text-slate-400 hover:text-slate-600"
                  title="复制密码"
                >
                  <KeyOutlined class="text-lg" />
                </button>
                <button
                  @click="handleDeleteCredential(cred)"
                  class="p-1.5 hover:bg-red-50 rounded text-slate-400 hover:text-red-600"
                  title="删除"
                >
                  <DeleteOutlined class="text-lg" />
                </button>
              </div>
            </div>
          </div>

          <div class="flex justify-end mt-4">
            <button @click="showCredentialModal = false" class="btn-secondary">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>