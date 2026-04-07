<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, SearchOutlined, FolderOpenOutlined, FolderOutlined, FileTextOutlined, DownOutlined, UpOutlined, RightOutlined, KeyOutlined, EditOutlined, DeleteOutlined, CloseOutlined, PlusCircleOutlined, UserOutlined, EyeOutlined, CopyOutlined, AppstoreOutlined, ClusterOutlined, DatabaseOutlined, CloudServerOutlined, GlobalOutlined, RobotOutlined } from '@ant-design/icons-vue'
import { getAssets, getOrganizations, createAsset, updateAsset, deleteAsset, getCredentials, createCredential, decryptCredential, deleteCredential } from '@/api/assets'
import type { Asset, AssetCategory, Organization, Credential } from '@/types'

const router = useRouter()
const route = useRoute()

// Data
const assets = ref<Asset[]>([])
const organizations = ref<Organization[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const limit = ref(20)

// Bulk selection
const allSelected = ref(false)

// Filters
const activeCategory = ref<AssetCategory | 'all'>('all')
const searchQuery = ref('')
const selectedOrgId = ref<number | null>(null)

// Asset tree expansion
const expandedOrgIds = ref<Set<number>>(new Set())

// Tree view mode: 'asset' for organization tree, 'type' for category tree
const treeViewMode = ref<'asset' | 'type'>('asset')

// Type tree expansion - use array for better Vue reactivity
const expandedTypeIds = ref<string[]>(['all'])

// Type tree selected node ID - for accurate active state tracking
const selectedTypeNodeId = ref<string>('all')

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
  { key: 'all', label: '全部', icon: AppstoreOutlined },
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
  host: ['Linux', 'Windows', 'Unix', 'MacOS', 'NAS'],
  network: ['Cisco IOS', 'Huawei VRP', 'Juniper JunOS', 'Aruba OS'],
  database: ['MySQL', 'MongoDB', 'Redis', 'PostgreSQL', 'Oracle', 'SQL Server', 'InfluxDB', 'Elasticsearch', 'RabbitMQ', 'RocketMQ', 'Kafka', 'ClickHouse', 'EMQ', '达梦', 'TiDB', 'IoTDB', 'TDengine', 'Prometheus', 'Neo4j', 'Milvus', 'Weaviate', 'Qdrant'],
  cloud: ['Kubernetes', 'KubeSphere', 'Rancher', 'Harvester', 'OpenStack', 'ZStack', 'CloudStack', 'VMware', 'oVirt', 'KVM', 'AWS', 'Azure', 'GCP', '阿里云', '腾讯云', '青云', 'UCloud', '火山云', '天翼云', '移动云', '华为云'],
  web: ['Nginx', 'Apache', 'IIS', 'Tomcat'],
  gpt: ['OpenAI', 'Claude', 'ChatGLM', '通义千问']
}

// Device type options for network
const deviceTypeOptions = ['交换机', '路由器', '防火墙', '无线控制器', '负载均衡']

// Modal title
const modalTitle = computed(() => editingAsset.value ? '编辑资产' : '创建资产')

// Type tree structure
const typeTreeStructure = computed(() => {
  const treeData = [];

  // Add root node for all types
  treeData.push({
    id: 'all',
    name: '所有类型',
    count: total.value,
    level: 0,
    hasChildren: true,
    isRoot: true
  });

  // Define static subcategories for each category according to prototype
  const hostSubCategories = ['Linux', 'Unix', 'Windows', 'MacOS', 'NAS'];
  const networkSubCategories = ['交换机', '路由器', '防火墙', '负载均衡', '无线控制器'];
  const databaseSubCategories = ['MySQL', 'MongoDB', 'Redis', 'PostgreSQL', 'Oracle', 'SQL Server', 'InfluxDB', 'Elasticsearch', 'RabbitMQ', 'RocketMQ', 'Kafka', 'ClickHouse', 'EMQ', '达梦', 'TiDB', 'IoTDB', 'TDengine', 'Prometheus', 'Neo4j', 'Milvus', 'Weaviate', 'Qdrant'];
  const cloudSubCategories = ['Kubernetes', 'KubeSphere', 'Rancher', 'Harvester', 'OpenStack', 'ZStack', 'CloudStack', 'VMware', 'oVirt', 'KVM', 'AWS', 'Azure', 'GCP', '阿里云', '腾讯云', '青云', 'UCloud', '火山云', '天翼云', '移动云', '华为云'];
  const webSubCategories = ['网站'];
  const gptSubCategories = ['OpenAI', 'Claude', 'ChatGLM', '通义千问'];

  // Add category nodes
  categories.forEach(cat => {
    if (cat.key !== 'all') {
      const categoryAssets = assets.value.filter(a => a.category === cat.key);

      // Determine subcategories for this category
      let subCategories = [];
      if (cat.key === 'host') {
        subCategories = hostSubCategories;
      } else if (cat.key === 'network') {
        subCategories = networkSubCategories;
      } else if (cat.key === 'database') {
        subCategories = databaseSubCategories;
      } else if (cat.key === 'cloud') {
        subCategories = cloudSubCategories;
      } else if (cat.key === 'web') {
        subCategories = webSubCategories;
      } else if (cat.key === 'gpt') {
        subCategories = gptSubCategories;
      }

      // Category always has children if subcategories are defined
      const hasChildren = subCategories.length > 0;

      treeData.push({
        id: cat.key,
        name: `${cat.label} (${categoryAssets.length})`,
        count: categoryAssets.length,
        level: 1,
        hasChildren: hasChildren,
        parentId: 'all',
        category: cat.key
      });

      // Add all possible sub-types for each category (whether they have assets or not)
      if (cat.key === 'host') {
        hostSubCategories.forEach(subCat => {
          const subCatAssets = categoryAssets.filter(a => a.platform === subCat);
          treeData.push({
            id: `host-${subCat.toLowerCase().replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatAssets.length})`,
            count: subCatAssets.length,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      } else if (cat.key === 'network') {
        networkSubCategories.forEach(subCat => {
          const subCatAssets = categoryAssets.filter(a => a.device_type === subCat);
          treeData.push({
            id: `network-${subCat.replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatAssets.length})`,
            count: subCatAssets.length,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      } else if (cat.key === 'database') {
        databaseSubCategories.forEach(subCat => {
          const subCatAssets = categoryAssets.filter(a => a.platform === subCat);
          treeData.push({
            id: `database-${subCat.toLowerCase().replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatAssets.length})`,
            count: subCatAssets.length,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      } else if (cat.key === 'cloud') {
        cloudSubCategories.forEach(subCat => {
          const subCatAssets = categoryAssets.filter(a => a.platform === subCat);
          treeData.push({
            id: `cloud-${subCat.replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatAssets.length})`,
            count: subCatAssets.length,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      } else if (cat.key === 'web') {
        webSubCategories.forEach(subCat => {
          const subCatAssets = categoryAssets.filter(a => a.platform === subCat);
          treeData.push({
            id: `web-${subCat.toLowerCase().replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatAssets.length})`,
            count: subCatAssets.length,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      } else if (cat.key === 'gpt') {
        gptSubCategories.forEach(subCat => {
          const subCatAssets = categoryAssets.filter(a => a.platform === subCat);
          treeData.push({
            id: `gpt-${subCat.toLowerCase().replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatAssets.length})`,
            count: subCatAssets.length,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      }
    }
  });

  return treeData;
});

// Flatten type tree for display
const flattenedTypeTree = computed(() => {
  const result: any[] = [];

  // Add root node
  const root = typeTreeStructure.value.find((node: any) => node.isRoot);
  if (root) {
    result.push(root);

    // Add level 1 children of root if root is expanded
    if (expandedTypeIds.value.includes(root.id)) {
      const level1Nodes = typeTreeStructure.value.filter((node: any) => node.parentId === root.id);
      for (const level1Node of level1Nodes) {
        result.push({
          ...level1Node,
          level: 1
        });

        // Add level 2 children if the level 1 node is expanded
        if (expandedTypeIds.value.includes(level1Node.id)) {
          const level2Nodes = typeTreeStructure.value.filter((node: any) => node.parentId === level1Node.id);
          for (const level2Node of level2Nodes) {
            result.push({
              ...level2Node,
              level: 2
            });
          }
        }
      }
    }
  }

  return result;
});

// Reset filters and tree selection
function resetFilters() {
  selectedOrgId.value = null;
  treeViewMode.value = 'asset';
  activeCategory.value = 'all';
  selectedTypeNodeId.value = 'all';
  fetchAssets();
}

// Switch between asset tree and type tree
function switchTreeView(mode: 'asset' | 'type') {
  treeViewMode.value = mode;
  if (mode === 'asset') {
    selectedOrgId.value = null;
    activeCategory.value = 'all';
  } else {
    // Switch to type tree - reset to root selection
    selectedTypeNodeId.value = 'all';
    activeCategory.value = 'all';
    selectedOrgId.value = null;
    fetchAssets();
  }
}

// Toggle type expansion - accordion effect: only one sibling can be expanded
function toggleType(typeId: string) {
  if (typeId === 'all') {
    // Root node: toggle its expansion
    const index = expandedTypeIds.value.indexOf('all');
    if (index > -1) {
      expandedTypeIds.value.splice(index, 1);
      // When collapsing root, also collapse all level 1 nodes
      expandedTypeIds.value = expandedTypeIds.value.filter(id => !categories.some(c => c.key === id));
    } else {
      expandedTypeIds.value.push('all');
    }
  } else {
    // Level 1 node: accordion effect - collapse other siblings first
    const index = expandedTypeIds.value.indexOf(typeId);
    if (index > -1) {
      // Collapse this node
      expandedTypeIds.value.splice(index, 1);
    } else {
      // First collapse all other level 1 category nodes (accordion effect)
      expandedTypeIds.value = expandedTypeIds.value.filter(id => id === 'all' || !categories.some(c => c.key === id));
      // Then expand this node
      expandedTypeIds.value.push(typeId);
    }
  }
}

// Check if a type node is currently selected
function isSelectedTypeNode(node: any): boolean {
  if (treeViewMode.value !== 'type') return false;

  // Simply check if this node's ID matches the selected node ID
  return selectedTypeNodeId.value === node.id;
}

// Select a type node (toggle expansion when clicking on nodes with children)
function selectType(node: any) {
  if (node.isRoot) {
    // Clicked on "All Types" - toggle expansion only
    toggleType('all');
    // Set selection to root
    selectedTypeNodeId.value = 'all';
    activeCategory.value = 'all';
    selectedOrgId.value = null;
    fetchAssets();
  } else if (node.hasChildren) {
    // Clicked on a node with children - toggle expansion only
    toggleType(node.id);
    // Do not change selection when clicking parent nodes (accordion toggle)
  } else if (node.subCategory && node.category) {
    // Clicked on a leaf sub-category node (level 2) - apply filter
    selectedTypeNodeId.value = node.id;
    activeCategory.value = node.category as AssetCategory;
    selectedOrgId.value = null;
    fetchAssets();
  } else if (node.category) {
    // Clicked on a leaf category node (level 1 without children) - apply filter
    selectedTypeNodeId.value = node.id;
    activeCategory.value = node.category as AssetCategory;
    selectedOrgId.value = null;
    fetchAssets();
  }
}

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
    // Initialize expandedNotes and selected properties for each asset
    assets.value = (result.items || []).map(asset => ({
      ...asset,
      expandedNotes: false,
      selected: false
    }))
    total.value = result.total || 0
  } catch (error) {
    message.error('获取资产列表失败')
    assets.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// Update expandedTypeIds after assets are loaded
function updateExpandedTypeIds() {
  // Only expand root by default, not level 1 categories (accordion effect)
  expandedTypeIds.value = ['all'];
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
  selectedTypeNodeId.value = category
  // When clicking "全部" tab, switch to asset tree view
  // When clicking other category tabs, switch to type tree view
  treeViewMode.value = category === 'all' ? 'asset' : 'type'
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
  return cat?.icon || AppstoreOutlined
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

// Address validation function
function validateAddress(address: string): { valid: boolean; message?: string } {
  if (!address?.trim()) {
    return { valid: false, message: '地址不能为空' }
  }

  const parts = address.split(':')
  if (parts.length > 2) {
    return { valid: false, message: '格式错误，端口只能有一个' }
  }

  const host = parts[0]
  const port = parts[1]

  // Validate IP or hostname
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/
  const hostnameRegex = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/

  if (!ipRegex.test(host) && !hostnameRegex.test(host)) {
    return { valid: false, message: '无效的IP地址或主机名' }
  }

  // Validate port
  if (port) {
    const portNum = parseInt(port, 10)
    if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
      return { valid: false, message: '端口号必须在 1-65535 之间' }
    }
  }

  return { valid: true }
}

// Submit form
async function handleSubmit() {
  if (!form.value.name) {
    message.error('请输入资产名称')
    return
  }

  // Validate address format for certain categories
  if (form.value.category === 'host' || form.value.category === 'network' || form.value.category === 'database') {
    if (form.value.address) {
      const addressValidation = validateAddress(form.value.address)
      if (!addressValidation.valid) {
        message.error(addressValidation.message)
        return
      }
    }
  }

  // For cloud, web, gpt categories, validate URL if provided
  if ((form.value.category === 'cloud' || form.value.category === 'web' || form.value.category === 'gpt') && form.value.url) {
    try {
      new URL(form.value.url)
    } catch {
      message.error('请输入有效的URL地址')
      return
    }
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

// Bulk selection functions
function selectAllChanged(event: Event) {
  const target = event.target as HTMLInputElement;
  const checked = target.checked;
  allSelected.value = checked;
  assets.value.forEach(asset => {
    asset.selected = checked;
  });
}

function selectionChanged() {
  allSelected.value = assets.value.every(asset => asset.selected);
}

// Edit credential function
function editCredential(credential: Credential) {
  message.info('请在凭证弹窗中编辑此凭证');
  // In real implementation, this would open an edit modal for the credential
}

// Refresh assets
function refreshAssets() {
  fetchAssets();
}

// Sync state to URL query parameters
function syncStateToUrl() {
  const query: Record<string, string> = {}

  if (treeViewMode.value !== 'asset') {
    query.view = treeViewMode.value
  }
  if (activeCategory.value !== 'all') {
    query.category = activeCategory.value
  }
  if (selectedTypeNodeId.value !== 'all') {
    query.typeNode = selectedTypeNodeId.value
  }
  if (expandedTypeIds.value.length > 0 && expandedTypeIds.value.includes('all')) {
    query.expanded = expandedTypeIds.value.join(',')
  }
  if (selectedOrgId.value !== null) {
    query.org = String(selectedOrgId.value)
  }
  if (page.value !== 1) {
    query.page = String(page.value)
  }
  if (searchQuery.value) {
    query.search = searchQuery.value
  }

  router.replace({ query })
}

// Restore state from URL query parameters
function restoreStateFromUrl() {
  const query = route.query

  if (query.view) {
    treeViewMode.value = query.view as 'asset' | 'type'
  }
  if (query.category) {
    activeCategory.value = query.category as AssetCategory | 'all'
  }
  if (query.typeNode) {
    selectedTypeNodeId.value = query.typeNode as string
  }
  if (query.expanded) {
    expandedTypeIds.value = (query.expanded as string).split(',')
  }
  if (query.org) {
    selectedOrgId.value = Number(query.org)
  }
  if (query.page) {
    page.value = Number(query.page)
  }
  if (query.search) {
    searchQuery.value = query.search as string
  }
}

// Watch state changes and sync to URL
watch([treeViewMode, activeCategory, selectedTypeNodeId, expandedTypeIds, selectedOrgId, page, searchQuery], () => {
  syncStateToUrl()
}, { deep: true })

// Initial load
onMounted(() => {
  // Restore state from URL first
  restoreStateFromUrl()

  // Set defaults if not restored from URL
  if (!route.query.expanded) {
    expandedTypeIds.value = ['all']
  }
  if (!route.query.typeNode) {
    selectedTypeNodeId.value = 'all'
  }

  fetchAssets()
  fetchOrganizations()
})
</script>

<template>
  <div class="space-y-4">
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
      <!-- Asset/Type Tree (Left Panel) -->
      <div class="hidden lg:block w-60 flex-shrink-0">
        <div class="card">
          <!-- Tab Controls -->
          <div class="flex border-b border-slate-100 mb-4">
            <button
              @click="switchTreeView('asset')"
              class="flex-1 py-2 text-xs font-medium text-center"
              :class="treeViewMode === 'asset' ? 'font-bold text-primary border-b-2 border-primary' : 'text-slate-400 hover:text-primary'"
            >
              资产树
            </button>
            <button
              @click="switchTreeView('type')"
              class="flex-1 py-2 text-xs font-medium text-center"
              :class="treeViewMode === 'type' ? 'font-bold text-primary border-b-2 border-primary' : 'text-slate-400 hover:text-primary'"
            >
              类型树
            </button>
          </div>

          <!-- Tree Content -->
          <div class="text-sm">
            <template v-if="treeViewMode === 'asset'">
              <!-- Asset Tree -->
              <div
                class="py-2 px-2 rounded cursor-pointer hover:bg-slate-50 mb-1"
                :class="selectedOrgId === null ? 'bg-primary/10 text-primary' : 'text-slate-600'"
                @click="selectOrganization(null)"
              >
                <FolderOpenOutlined class="text-sm mr-1" />
                Default
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
            </template>

            <template v-else-if="treeViewMode === 'type'">
              <!-- Type Tree -->
              <template v-for="node in flattenedTypeTree" :key="node.id">
                <div
                  class="py-1.5 px-2 rounded cursor-pointer hover:bg-slate-50 flex items-center gap-1"
                  :class="isSelectedTypeNode(node) ? 'bg-primary/10 text-primary' : 'text-slate-600'"
                  :style="{ paddingLeft: `${node.level * 16 + 8}px` }"
                  @click="selectType(node)"
                >
                  <!-- Root node: up arrow when expanded, down arrow when collapsed -->
                  <UpOutlined v-if="node.isRoot && expandedTypeIds.includes('all')" class="text-xs cursor-pointer hover:bg-slate-200 rounded" @click.stop="toggleType('all')" />
                  <DownOutlined v-if="node.isRoot && !expandedTypeIds.includes('all')" class="text-xs cursor-pointer hover:bg-slate-200 rounded" @click.stop="toggleType('all')" />
                  <!-- Level 1 nodes with children: up/down arrow based on expansion state -->
                  <UpOutlined v-else-if="node.level === 1 && node.hasChildren && expandedTypeIds.includes(node.id)" class="text-xs cursor-pointer hover:bg-slate-200 rounded" @click.stop="toggleType(node.id)" />
                  <DownOutlined v-else-if="node.level === 1 && node.hasChildren && !expandedTypeIds.includes(node.id)" class="text-xs cursor-pointer hover:bg-slate-200 rounded" @click.stop="toggleType(node.id)" />
                  <!-- Level 2 nodes: small right arrow -->
                  <RightOutlined v-else-if="node.level === 2" class="text-xs" />
                  <!-- Leaf nodes at level 1: empty spacer -->
                  <span v-else-if="node.level === 1 && !node.hasChildren" class="w-4"></span>
                  <!-- Icon: root node uses account_tree style icon, others use category icon -->
                  <AppstoreOutlined v-if="node.isRoot" class="text-sm mr-1" />
                  <component v-else :is="getCategoryIcon(node.category)" class="text-sm mr-1" />
                  <span class="flex-1 truncate">{{ node.name }}</span>
                </div>
              </template>
            </template>
          </div>
        </div>
      </div>

      <!-- Asset Table (Right Panel) -->
      <div class="flex-1">
        <!-- Action Bar -->
        <div class="bg-white rounded-xl shadow-sm p-3 mb-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <button @click="openCreateModal" class="btn-primary text-xs px-3 py-1.5">
                创建
              </button>
              <button class="border border-gray-200 text-slate-600 px-3 py-1.5 rounded text-xs font-medium hover:bg-gray-50 flex items-center gap-1 transition-colors">
                更多操作 <DownOutlined class="text-[14px]" />
              </button>
            </div>
            <div class="flex items-center gap-2">
              <button class="border border-gray-200 text-slate-600 px-3 py-1.5 rounded text-xs font-medium hover:bg-gray-50 flex items-center gap-1 transition-colors">
                <span class="material-symbols-outlined text-[14px]">label</span> 标签
              </button>
              <div class="relative flex items-center border border-gray-200 rounded overflow-hidden bg-white w-72">
                <div class="px-2 border-r border-gray-100 bg-gray-50 text-slate-400 flex items-center cursor-pointer">
                  <DownOutlined class="text-[14px]" />
                </div>
                <input
                  v-model="searchQuery"
                  type="text"
                  placeholder="搜索"
                  class="w-full border-none py-1.5 px-3 text-xs focus:ring-0 placeholder:text-slate-400"
                  @keyup.enter="handleSearch"
                />
                <SearchOutlined class="absolute right-2 text-slate-400 text-sm" />
              </div>
              <div class="flex items-center gap-2 text-slate-400">
                <button @click="handleSearch" class="hover:text-primary transition-colors">
                  <span class="material-symbols-outlined text-lg">refresh</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Table -->
        <div class="bg-white rounded-xl shadow-sm overflow-hidden">
          <table class="data-table">
            <thead>
              <tr>
                <th class="w-10">
                  <input
                    type="checkbox"
                    class="rounded border-gray-300 text-primary focus:ring-primary w-3.5 h-3.5"
                    @change="selectAllChanged($event)"
                    :checked="allSelected"
                  />
                </th>
                <template v-if="activeCategory === 'host' || activeCategory === 'all'">
                  <th>名称 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>地址 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>系统平台 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>用户名密码 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                </template>
                <template v-else-if="activeCategory === 'network'">
                  <th>名称 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>IP地址 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>设备类型 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>厂商/型号 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>管理凭据</th>
                </template>
                <template v-else-if="activeCategory === 'database'">
                  <th>名称 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>连接地址 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>数据库类型 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>访问凭证 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                </template>
                <template v-else-if="activeCategory === 'cloud'">
                  <th>名称 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>URL <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>系统平台 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>访问凭证 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                </template>
                <template v-else-if="activeCategory === 'web'">
                  <th>名称 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>URL <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>Web服务器 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>访问凭证 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                </template>
                <template v-else-if="activeCategory === 'gpt'">
                  <th>名称 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>URL <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>AI平台 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>访问凭证 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                </template>
                <th>备注 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                <th class="text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td :colspan="activeCategory === 'all' ? 9 : 8" class="text-center py-8 text-slate-500">
                  加载中...
                </td>
              </tr>
              <tr v-else-if="assets.length === 0">
                <td :colspan="activeCategory === 'all' ? 9 : 8" class="text-center py-8 text-slate-500">
                  暂无数据
                </td>
              </tr>
              <tr v-for="asset in assets" :key="asset.id">
                <td>
                  <input
                    type="checkbox"
                    class="rounded border-gray-300 text-primary focus:ring-primary w-3.5 h-3.5"
                    v-model="asset.selected"
                    @change="selectionChanged"
                  />
                </td>
                <td>
                  <div class="flex items-center gap-3">
                    <component :is="getCategoryIcon(asset.category)" class="text-primary" />
                    <div>
                      <p class="font-medium text-slate-900">{{ asset.name }}</p>
                      <p v-if="asset.asset_code" class="text-xs text-slate-400">{{ asset.asset_code }}</p>
                    </div>
                  </div>
                </td>

                <!-- Host category specific columns -->
                <template v-if="activeCategory === 'host' || activeCategory === 'all'">
                  <td>
                    <span class="text-sm text-slate-600 font-mono">{{ asset.address || '-' }}</span>
                  </td>
                  <td>
                    <span class="text-sm text-slate-600">{{ asset.platform || '-' }}</span>
                  </td>
                  <td>
                    <div class="flex flex-col gap-2 py-1">
                      <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                        <span class="font-medium">{{ cred.username }}</span>
                        <CopyOutlined class="text-[14px] cursor-pointer hover:text-primary" @click="copyUsername(cred.username)" />
                        <span class="text-slate-400 font-mono ml-1">********</span>
                        <CopyOutlined class="text-[14px] cursor-pointer hover:text-primary" @click="copyPassword({ id: cred.id, username: cred.username })" />
                        <EyeOutlined class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword({ id: cred.id, username: cred.username })" />
                        <EditOutlined class="text-[14px] cursor-pointer hover:text-primary" @click="editCredential(cred)" />
                        <DeleteOutlined class="text-[14px] cursor-pointer hover:text-error" @click="handleDeleteCredential(cred)" />
                      </div>
                    </div>
                  </td>
                </template>

                <!-- Network category specific columns -->
                <template v-else-if="activeCategory === 'network'">
                  <td>
                    <span class="text-sm text-slate-600 font-mono">{{ asset.address || '-' }}</span>
                  </td>
                  <td>
                    <span class="text-sm text-slate-600">{{ asset.device_type || '-' }}</span>
                  </td>
                  <td>
                    <span class="text-sm text-slate-600">{{ asset.vendor && asset.model ? `${asset.vendor}/${asset.model}` : (asset.vendor || asset.model || '-') }}</span>
                  </td>
                  <td>
                    <div class="flex flex-col gap-2 py-1">
                      <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                        <span class="font-medium">{{ cred.username }}</span>
                        <CopyOutlined class="text-[14px] cursor-pointer hover:text-primary" @click="copyUsername(cred.username)" />
                        <span class="text-slate-400 font-mono ml-1">********</span>
                        <CopyOutlined class="text-[14px] cursor-pointer hover:text-primary" @click="copyPassword({ id: cred.id, username: cred.username })" />
                        <EyeOutlined class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword({ id: cred.id, username: cred.username })" />
                        <EditOutlined class="text-[14px] cursor-pointer hover:text-primary" @click="editCredential(cred)" />
                        <DeleteOutlined class="text-[14px] cursor-pointer hover:text-error" @click="handleDeleteCredential(cred)" />
                      </div>
                      <button
                        v-if="!(asset.credentials && asset.credentials.length > 0)"
                        @click="openCredentialModal(asset)"
                        class="text-primary hover:underline text-xs"
                      >
                        {{ asset.credentials?.length || 0 }} 个凭证
                      </button>
                    </div>
                  </td>
                </template>

                <!-- Database category specific columns -->
                <template v-else-if="activeCategory === 'database'">
                  <td>
                    <span class="text-sm text-slate-600 font-mono">{{ asset.address || '-' }}</span>
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
                </template>

                <!-- Cloud category specific columns -->
                <template v-else-if="activeCategory === 'cloud'">
                  <td>
                    <span class="text-sm text-slate-600 font-mono">{{ asset.url || asset.address || '-' }}</span>
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
                </template>

                <!-- Web category specific columns -->
                <template v-else-if="activeCategory === 'web'">
                  <td>
                    <span class="text-sm text-slate-600 font-mono">{{ asset.url || asset.address || '-' }}</span>
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
                </template>

                <!-- GPT category specific columns -->
                <template v-else-if="activeCategory === 'gpt'">
                  <td>
                    <span class="text-sm text-slate-600 font-mono">{{ asset.url || asset.address || '-' }}</span>
                  </td>
                  <td>
                    <span class="text-sm text-slate-600">{{ asset.platform || '-' }}</span>
                  </td>
                  <td>
                    <div class="flex flex-col gap-1.5">
                      <div
                        v-for="cred in asset.credentials || []"
                        :key="cred.id"
                        class="flex items-center gap-2 bg-slate-100/80 px-2 py-1 rounded text-xs"
                      >
                        <span class="font-semibold text-slate-700 uppercase">{{ cred.credential_type || 'API' }}</span>
                        <CopyOutlined class="text-[14px] cursor-pointer hover:text-primary" @click="copyUsername(cred.username)" />
                        <div class="h-3 w-px bg-slate-300"></div>
                        <span class="font-mono text-slate-500">{{
                          decryptedPasswords.has(cred.id) ?
                            decryptedPasswords.get(cred.id) :
                            '********'
                        }}</span>
                        <div class="flex items-center gap-1 ml-auto">
                          <EyeOutlined
                            class="text-[14px] cursor-pointer hover:text-primary"
                            @click="viewPassword(cred)"
                          />
                          <EditOutlined
                            class="text-[14px] cursor-pointer hover:text-primary"
                            @click="editCredential(cred)"
                          />
                        </div>
                      </div>
                      <button
                        v-if="!(asset.credentials && asset.credentials.length > 0)"
                        @click="openCredentialModal(asset)"
                        class="text-primary hover:underline text-xs"
                      >
                        {{ asset.credentials?.length || 0 }} 个凭证
                      </button>
                    </div>
                  </td>
                </template>

                <!-- Common notes column -->
                <td>
                  <div v-if="asset.notes" class="relative">
                    <div
                      class="text-sm text-slate-600 max-h-12 overflow-hidden cursor-pointer"
                      :class="{'line-clamp-2': !asset.expandedNotes}"
                      @click="asset.expandedNotes = !asset.expandedNotes"
                    >
                      {{ asset.notes }}
                    </div>
                    <div
                      v-if="asset.notes.length > 100"
                      class="mt-1 text-xs text-primary cursor-pointer"
                      @click="asset.expandedNotes = !asset.expandedNotes"
                    >
                      {{ asset.expandedNotes ? '收起' : '展开' }}
                    </div>
                  </div>
                  <div v-else class="-">
                    <span class="text-sm text-slate-400">-</span>
                  </div>
                </td>

                <!-- Action column -->
                <td class="text-right">
                  <div class="flex items-center justify-end gap-1">
                    <button @click="openEditModal(asset)" class="bg-primary text-white px-2 py-0.5 rounded hover:bg-blue-600 transition-colors text-xs">
                      更新
                    </button>
                    <button class="border border-primary/30 text-primary px-2 py-0.5 rounded hover:bg-blue-50 flex items-center gap-0.5 transition-colors text-xs">
                      更多 <DownOutlined class="text-[10px]" />
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
                <input v-model="form.address" type="text" class="input-field" placeholder="支持格式: IP、IP:端口、主机名、主机名:端口" />
              </div>
              <div v-if="form.category === 'cloud' || form.category === 'web' || form.category === 'gpt'">
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