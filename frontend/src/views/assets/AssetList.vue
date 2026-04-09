<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message, Modal, Dropdown } from 'ant-design-vue'
import { SearchOutlined, FolderOpenOutlined, FolderOutlined, FileTextOutlined, DownOutlined, UpOutlined, RightOutlined, KeyOutlined, DeleteOutlined, CloseOutlined, PlusCircleOutlined, UserOutlined, EyeOutlined, EyeInvisibleOutlined, CopyOutlined, AppstoreOutlined, ClusterOutlined, DatabaseOutlined, CloudServerOutlined, GlobalOutlined, RobotOutlined, StopOutlined, CheckCircleOutlined, EditOutlined, FolderAddOutlined } from '@ant-design/icons-vue'
import { getAssets, getOrganizationsWithStats, createAsset, updateAsset, deleteAsset, getCredentials, createCredential, updateCredential, decryptCredential, deleteCredential, getAssetStats, bulkUpdateAssets, bulkDeleteAssets, createOrganization, updateOrganization, deleteOrganization, reorderOrganizations } from '@/api/assets'
import type { Asset, AssetCategory, Organization, Credential } from '@/types'

// Extended asset type with runtime properties for UI state
interface AssetWithUI extends Asset {
  expandedNotes?: boolean
  selected?: boolean
}

// Asset statistics
interface AssetStats {
  total: number
  by_category: Record<string, number>
  by_platform: Record<string, number>
  by_device_type: Record<string, number>
}

const router = useRouter()
const route = useRoute()

// Data
const assets = ref<AssetWithUI[]>([])
const organizations = ref<Organization[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const limit = ref(20)

// Organization tree statistics
const rootAssetCount = ref(0)  // Assets directly under root (no organization)
const totalAssetCount = ref(0)  // Total assets in the system

// Asset statistics
const assetStats = ref<AssetStats>({
  total: 0,
  by_category: {},
  by_platform: {},
  by_device_type: {}
})

// Bulk selection
const allSelected = ref(false)

// Filters
const activeCategory = ref<AssetCategory | 'all'>('all')
const searchQuery = ref('')
const selectedOrgId = ref<number | null>(null)

// Asset tree expansion
const expandedOrgIds = ref<Set<number>>(new Set())

// Root node expansion state (for "Default" root)
const isRootExpanded = ref(true)

// Tree view mode: 'asset' for organization tree, 'type' for category tree
const treeViewMode = ref<'asset' | 'type'>('asset')

// Type tree expansion - use array for better Vue reactivity
const expandedTypeIds = ref<string[]>(['all'])

// Type tree selected node ID - for accurate active state tracking
const selectedTypeNodeId = ref<string>('all')

// Modal
const showModal = ref(false)
const showCredentialModal = ref(false)
const showPassword = ref(false)
const modalLoading = ref(false)
const editingAsset = ref<Asset | null>(null)
const selectedAsset = ref<Asset | null>(null)
const credentials = ref<Credential[]>([])
const credentialLoading = ref(false)

// Credential form for new credentials in modal
const newCredentialForm = ref({
  username: '',
  password: '',
  credential_type: 'password'
})

// Decrypted passwords cache (for asset list)
const decryptedPasswords = ref<Map<number, string>>(new Map())

// Decrypted form credentials passwords (for edit modal - existing credentials with id)
const decryptedFormPasswords = ref<Map<number, string>>(new Map())

// Track visible passwords for new credentials (without id) - indexed by formCredentials index
const visibleNewPasswords = ref<Set<number>>(new Set())

// Form credentials - for create/edit modal (can have multiple)
const formCredentials = ref<Array<{ username: string; password: string; id?: number }>>([])

// Track which credential fields are in edit mode by double-click
const editingCredentialField = ref<{ index: number; field: 'username' | 'password' } | null>(null)

// Refs for input elements
const credentialInputRefs = ref<Map<string, HTMLInputElement>>(new Map())

// Organization context menu state
const showOrgContextMenu = ref(false)
const orgContextMenuPosition = ref({ x: 0, y: 0 })
const orgContextMenuTarget = ref<{ id: number | null; name: string; isRoot: boolean } | null>(null)

// Organization modal state
const showOrgModal = ref(false)
const orgModalMode = ref<'create' | 'rename'>('create')
const orgModalLoading = ref(false)
const orgForm = ref({
  name: '',
  parentId: null as number | null
})

// Drag and drop state for organization tree
const draggedOrgId = ref<number | null>(null)
const dragOverOrgId = ref<number | null>(null)

// Form
const form = ref({
  name: '',
  asset_code: '',
  category: 'host' as AssetCategory,
  address: '',
  platform: '',
  device_type: '',
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
  network: ['Cisco', 'Huawei', 'H3C', 'Ruijie', 'ZTE', 'TP-Link', 'Tenda', 'ASUS', 'MERCURY', 'Netgear', 'Juniper'],
  database: ['MySQL', 'MongoDB', 'Redis', 'PostgreSQL', 'Oracle', 'SQL Server', 'InfluxDB', 'Elasticsearch', 'RabbitMQ', 'RocketMQ', 'Kafka', 'ClickHouse', 'EMQ', '达梦', 'TiDB', 'IoTDB', 'TDengine', 'Prometheus', 'Neo4j', 'Milvus', 'Weaviate', 'Qdrant'],
  cloud: ['Kubernetes', 'KubeSphere', 'Rancher', 'Harvester', 'OpenStack', 'ZStack', 'CloudStack', 'VMware', 'oVirt', 'KVM', 'AWS', 'Azure', 'GCP', '阿里云', '腾讯云', '青云', 'UCloud', '火山云', '天翼云', '移动云', '华为云'],
  web: ['Nginx', 'Apache', 'IIS', 'Tomcat', 'Nginx Ingress', 'Higress', 'Traefik', 'APISIX', 'Loadbalancer', 'F5'],
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
    count: assetStats.value.total,
    level: 0,
    hasChildren: true,
    isRoot: true
  });

  // Define static subcategories for each category according to prototype
  const hostSubCategories = ['Linux', 'Unix', 'Windows', 'MacOS', 'NAS'];
  const networkSubCategories = ['交换机', '路由器', '防火墙', '负载均衡', '无线控制器'];
  const databaseSubCategories = ['MySQL', 'MongoDB', 'Redis', 'PostgreSQL', 'Oracle', 'SQL Server', 'InfluxDB', 'Elasticsearch', 'RabbitMQ', 'RocketMQ', 'Kafka', 'ClickHouse', 'EMQ', '达梦', 'TiDB', 'IoTDB', 'TDengine', 'Prometheus', 'Neo4j', 'Milvus', 'Weaviate', 'Qdrant'];
  const cloudSubCategories = ['Kubernetes', 'KubeSphere', 'Rancher', 'Harvester', 'OpenStack', 'ZStack', 'CloudStack', 'VMware', 'oVirt', 'KVM', 'AWS', 'Azure', 'GCP', '阿里云', '腾讯云', '青云', 'UCloud', '火山云', '天翼云', '移动云', '华为云'];
  const webSubCategories = ['Nginx', 'Apache', 'IIS', 'Tomcat', 'Nginx Ingress', 'Higress', 'Traefik', 'APISIX', 'Loadbalancer', 'F5'];
  const gptSubCategories = ['OpenAI', 'Claude', 'ChatGLM', '通义千问'];

  // Add category nodes
  categories.forEach(cat => {
    if (cat.key !== 'all') {
      // Use stats for category count
      const categoryCount = assetStats.value.by_category[cat.key] || 0;

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
        name: `${cat.label} (${categoryCount})`,
        count: categoryCount,
        level: 1,
        hasChildren: hasChildren,
        parentId: 'all',
        category: cat.key
      });

      // Add all possible sub-types for each category
      if (cat.key === 'host') {
        hostSubCategories.forEach(subCat => {
          const platformKey = `host:${subCat}`;
          const subCatCount = assetStats.value.by_platform[platformKey] || 0;
          treeData.push({
            id: `host-${subCat.toLowerCase().replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatCount})`,
            count: subCatCount,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      } else if (cat.key === 'network') {
        networkSubCategories.forEach(subCat => {
          const subCatCount = assetStats.value.by_device_type[subCat] || 0;
          treeData.push({
            id: `network-${subCat.replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatCount})`,
            count: subCatCount,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      } else if (cat.key === 'database') {
        databaseSubCategories.forEach(subCat => {
          const platformKey = `database:${subCat}`;
          const subCatCount = assetStats.value.by_platform[platformKey] || 0;
          treeData.push({
            id: `database-${subCat.toLowerCase().replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatCount})`,
            count: subCatCount,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      } else if (cat.key === 'cloud') {
        cloudSubCategories.forEach(subCat => {
          const platformKey = `cloud:${subCat}`;
          const subCatCount = assetStats.value.by_platform[platformKey] || 0;
          treeData.push({
            id: `cloud-${subCat.replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatCount})`,
            count: subCatCount,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      } else if (cat.key === 'web') {
        webSubCategories.forEach(subCat => {
          const platformKey = `web:${subCat}`;
          const subCatCount = assetStats.value.by_platform[platformKey] || 0;
          treeData.push({
            id: `web-${subCat.toLowerCase().replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatCount})`,
            count: subCatCount,
            level: 2,
            hasChildren: false,
            parentId: cat.key,
            subCategory: subCat,
            category: cat.key
          });
        });
      } else if (cat.key === 'gpt') {
        gptSubCategories.forEach(subCat => {
          const platformKey = `gpt:${subCat}`;
          const subCatCount = assetStats.value.by_platform[platformKey] || 0;
          treeData.push({
            id: `gpt-${subCat.toLowerCase().replace(/\s+/g, '')}`,
            name: `${subCat} (${subCatCount})`,
            count: subCatCount,
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
})

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
    // Clicked on a node with children - toggle expansion AND select this category
    toggleType(node.id);
    // Set selection to this node
    selectedTypeNodeId.value = node.id;
    // Set active category to filter assets
    if (node.category) {
      activeCategory.value = node.category as AssetCategory;
    }
    selectedOrgId.value = null;
    fetchAssets();
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

// Fetch asset statistics
async function fetchAssetStats() {
  try {
    assetStats.value = await getAssetStats()
  } catch (error) {
    console.error('Failed to fetch asset stats')
  }
}

// Fetch organizations
async function fetchOrganizations() {
  try {
    const result = await getOrganizationsWithStats()
    organizations.value = result.organizations || []
    rootAssetCount.value = result.root_asset_count || 0
    totalAssetCount.value = result.total_assets || 0
  } catch (error) {
    console.error('Failed to fetch organizations')
    organizations.value = []
    rootAssetCount.value = 0
    totalAssetCount.value = 0
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

// Select organization - optimized for instant UI feedback
function selectOrganization(orgId: number | null) {
  // Always update selection immediately for instant visual feedback
  selectedOrgId.value = orgId

  // Defer search to next tick to ensure UI updates first
  nextTick(() => {
    page.value = 1
    fetchAssets()
  })
}

// Toggle root node expansion
function toggleRootExpansion() {
  isRootExpanded.value = !isRootExpanded.value
}

// Handle root node click - toggle expansion
function handleRootClick() {
  toggleRootExpansion()
}

// Handle organization node click - toggle expansion if has children, otherwise select
function handleOrgClick(org: { id: number; name: string; hasChildren: boolean }) {
  if (org.hasChildren) {
    // Toggle expansion for nodes with children
    toggleOrg(org.id)
  } else {
    // Select and load data for leaf nodes
    selectOrganization(org.id)
  }
}

// Global click handler to close context menu
function handleGlobalClick() {
  if (showOrgContextMenu.value) {
    closeOrgContextMenu()
  }
}

// Get flattened org tree for display
const flattenedOrgs = computed(() => {
  const result: { id: number; name: string; count: number; level: number; hasChildren: boolean }[] = []

  function flatten(orgs: Organization[], level: number = 0) {
    for (const org of orgs) {
      result.push({
        id: org.id,
        name: org.name,
        count: org.total_count || org.count || 0,  // Use total_count if available
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

// Get organization path by id (e.g., "Default / 节点1 / 节点2")
function getOrgPath(orgId: number | null): string {
  if (orgId === null) {
    return 'Default'
  }

  // Build a map of id -> organization with parent info
  const orgMap = new Map<number, { name: string; parentId: number | null }>()

  function buildMap(orgs: Organization[], parentId: number | null = null) {
    for (const org of orgs) {
      orgMap.set(org.id, { name: org.name, parentId })
      if (org.children && org.children.length > 0) {
        buildMap(org.children, org.id)
      }
    }
  }

  buildMap(organizations.value)

  // Build path from leaf to root
  const pathParts: string[] = []
  let currentId: number | null = orgId

  while (currentId !== null) {
    const orgInfo = orgMap.get(currentId)
    if (orgInfo) {
      pathParts.unshift(orgInfo.name)
      currentId = orgInfo.parentId
    } else {
      break
    }
  }

  // Add "Default" as root
  pathParts.unshift('Default')

  return pathParts.join(' / ')
}

// Get currently selected type tree node
const selectedTypeNode = computed(() => {
  if (treeViewMode.value !== 'type' || selectedTypeNodeId.value === 'all') {
    return null;
  }
  return flattenedTypeTree.value.find((node: any) => node.id === selectedTypeNodeId.value) || null;
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
    device_type: '',
    model: '',
    serial_number: '',
    url: '',
    notes: ''
  }

  // Auto-fill based on selected type tree node
  if (selectedTypeNode.value && selectedTypeNode.value.category) {
    const node = selectedTypeNode.value;
    form.value.category = node.category as AssetCategory;

    // Fill platform or device_type based on category and subCategory
    if (node.subCategory) {
      if (node.category === 'network') {
        // Network: subCategory is device_type
        form.value.device_type = node.subCategory;
      } else {
        // Other categories: subCategory is platform
        form.value.platform = node.subCategory;
      }
    }
  }

  formCredentials.value = []
  newCredentialForm.value = { username: '', password: '', credential_type: 'password' }
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
    device_type: asset.device_type || '',
    model: asset.model || '',
    serial_number: asset.serial_number || '',
    url: asset.url || '',
    notes: asset.notes || ''
  }
  // Load existing credentials
  formCredentials.value = (asset.credentials || []).map(c => ({
    id: c.id,
    username: c.username,
    password: '' // Password not loaded for existing credentials
  }))
  newCredentialForm.value = { username: '', password: '', credential_type: 'password' }
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
      device_type: form.value.device_type || undefined,
      model: form.value.model || undefined,
      serial_number: form.value.serial_number || undefined,
      url: form.value.url || undefined,
      notes: form.value.notes || undefined,
      organization_id: selectedOrgId.value || undefined
    }

    if (editingAsset.value) {
      await updateAsset(editingAsset.value.id, data)
      // Handle credentials: create new ones and update existing ones
      for (const cred of formCredentials.value) {
        if (cred.username) {
          if (cred.id && cred.password) {
            // Update existing credential if password is provided
            await updateCredential(cred.id, {
              username: cred.username,
              password: cred.password
            })
          } else if (!cred.id && cred.password) {
            // Create new credential
            await createCredential(editingAsset.value.id, {
              username: cred.username,
              password: cred.password,
              credential_type: 'password'
            })
          }
        }
      }
      message.success('资产更新成功')
    } else {
      const newAsset = await createAsset(data)
      // Create all credentials that have both username and password
      for (const cred of formCredentials.value) {
        if (cred.username && cred.password && newAsset.id) {
          await createCredential(newAsset.id, {
            username: cred.username,
            password: cred.password,
            credential_type: 'password'
          })
        }
      }
      message.success('资产创建成功')
    }
    showModal.value = false
    fetchAssets()
    fetchAssetStats() // Update stats after asset changes
  } catch (error: any) {
    message.error(error.response?.data?.detail || '操作失败')
  } finally {
    modalLoading.value = false
  }
}

// Add credential to form
function addCredentialToForm() {
  if (!newCredentialForm.value.username || !newCredentialForm.value.password) {
    message.warning('请输入用户名和密码')
    return
  }
  formCredentials.value.push({
    username: newCredentialForm.value.username,
    password: newCredentialForm.value.password
  })
  newCredentialForm.value = { username: '', password: '', credential_type: 'password' }
}

// Remove credential from form
function removeCredentialFromForm(index: number) {
  formCredentials.value.splice(index, 1)
  // Clear any field editing
  editingCredentialField.value = null
}

// Start double-click edit for a credential field
function startFieldEdit(index: number, field: 'username' | 'password') {
  editingCredentialField.value = { index, field }
  // Use nextTick to ensure input is rendered before focusing
  nextTick(() => {
    const key = `${index}-${field}`
    const input = credentialInputRefs.value.get(key)
    if (input) {
      input.focus()
    }
  })
}

// Stop field edit (blur or enter)
function stopFieldEdit() {
  // Use setTimeout to ensure blur event completes before removing the input
  setTimeout(() => {
    editingCredentialField.value = null
  }, 100)
}

// Check if a field is being edited
function isFieldEditing(index: number, field: 'username' | 'password'): boolean {
  return editingCredentialField.value?.index === index && editingCredentialField.value?.field === field
}

// Toggle password visibility for new credentials (without id)
function toggleNewPasswordVisibility(index: number) {
  if (visibleNewPasswords.value.has(index)) {
    visibleNewPasswords.value.delete(index)
  } else {
    visibleNewPasswords.value.add(index)
  }
}

// View password for credential in form (for existing credentials with id)
async function viewFormCredentialPassword(cred: { id?: number; password: string }, index?: number) {
  if (cred.id) {
    // Existing credential - check if already decrypted
    if (decryptedFormPasswords.value.has(cred.id)) {
      // Toggle: remove from decrypted to hide
      decryptedFormPasswords.value.delete(cred.id)
      return
    }
    // Decrypt from server
    try {
      const result = await decryptCredential(cred.id)
      if (result.password) {
        decryptedFormPasswords.value.set(cred.id, result.password)
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '解密失败')
    }
  } else if (index !== undefined) {
    // New credential - toggle visibility
    toggleNewPasswordVisibility(index)
  }
}

// View password for credential in asset list - decrypt and display inline
async function viewPassword(credential: { id: number }) {
  // If already decrypted, toggle visibility (remove from cache to hide)
  if (decryptedPasswords.value.has(credential.id)) {
    decryptedPasswords.value.delete(credential.id)
    return
  }

  // Decrypt and store for inline display
  try {
    const result = await decryptCredential(credential.id)
    if (result.password) {
      decryptedPasswords.value.set(credential.id, result.password)
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || '解密失败')
  }
}

// Edit credential in asset list (opens credential modal)
// Delete credential
async function handleDeleteCredential(credential: { id: number; username?: string }) {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除凭证 "${credential.username || '此凭证'}" 吗？删除后无法恢复。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    centered: true,
    async onOk() {
      try {
        await deleteCredential(credential.id)
        message.success('凭证已删除')
        // Refresh assets to update credential counts
        fetchAssets()
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}

// Delete asset
async function handleDelete(asset: Asset) {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除资产 "${asset.name}" 吗？删除后无法恢复。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    centered: true,
    async onOk() {
      try {
        await deleteAsset(asset.id)
        message.success('资产已删除')
        fetchAssets()
        fetchAssetStats() // Update stats after deletion
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}

// Copy to clipboard with fallback
async function copyToClipboard(text: string) {
  try {
    // Try modern clipboard API first
    await navigator.clipboard.writeText(text)
    message.success('已复制到剪贴板')
  } catch {
    // Fallback: use textarea method
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    textarea.style.top = '0'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    try {
      const success = document.execCommand('copy')
      if (success) {
        message.success('已复制到剪贴板')
      } else {
        message.error('复制失败')
      }
    } catch {
      message.error('复制失败')
    }
    document.body.removeChild(textarea)
  }
}

// Copy username
function copyUsername(username: string) {
  copyToClipboard(username)
}

// Copy password - decrypt and copy, but don't change display (keep asterisks)
async function copyPassword(credential: { id: number }) {
  // If already visible (decrypted), use cached password
  const cachedPassword = decryptedPasswords.value.get(credential.id)
  if (cachedPassword) {
    copyToClipboard(cachedPassword)
    return
  }

  // Decrypt password for copying only (don't store in decryptedPasswords to keep asterisks display)
  try {
    const result = await decryptCredential(credential.id)
    if (result.password) {
      copyToClipboard(result.password)
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || '解密失败')
  }
}

// Add credential to existing asset (in credential modal)
async function addCredential() {
  if (!newCredentialForm.value.username || !newCredentialForm.value.password) {
    message.error('请填写用户名和密码')
    return
  }

  if (!selectedAsset.value) return

  try {
    await createCredential(selectedAsset.value.id, {
      username: newCredentialForm.value.username,
      password: newCredentialForm.value.password,
      credential_type: newCredentialForm.value.credential_type
    })
    message.success('凭证添加成功')
    newCredentialForm.value = { username: '', password: '', credential_type: 'password' }
    credentials.value = await getCredentials(selectedAsset.value.id)
  } catch (error: any) {
    message.error(error.response?.data?.detail || '添加失败')
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

// Get selected asset IDs
function getSelectedAssetIds(): number[] {
  return assets.value.filter(asset => asset.selected).map(asset => asset.id);
}

// Get selected assets count
const selectedCount = computed(() => assets.value.filter(asset => asset.selected).length);

// Get count of selected active assets
const selectedActiveCount = computed(() => assets.value.filter(asset => asset.selected && asset.is_active).length);

// Get count of selected inactive assets
const selectedInactiveCount = computed(() => assets.value.filter(asset => asset.selected && !asset.is_active).length);

// Check if can disable (has active assets selected)
const canDisable = computed(() => selectedActiveCount.value > 0);

// Check if can activate (has inactive assets selected)
const canActivate = computed(() => selectedInactiveCount.value > 0);

// Bulk disable assets
async function bulkDisable() {
  // Only disable active assets
  const activeIds = assets.value.filter(asset => asset.selected && asset.is_active).map(asset => asset.id);
  if (activeIds.length === 0) {
    message.warning('选中的资产中没有可禁用的资产');
    return;
  }

  Modal.confirm({
    title: '确认禁用',
    content: `确定要禁用选中的 ${activeIds.length} 个资产吗？`,
    okText: '确定',
    okType: 'danger',
    cancelText: '取消',
    centered: true,
    async onOk() {
      try {
        await bulkUpdateAssets(activeIds, { is_active: false });
        message.success(`已禁用 ${activeIds.length} 个资产`);
        fetchAssets();
        fetchAssetStats();
      } catch (error: any) {
        message.error(error.response?.data?.detail || '批量禁用失败');
      }
    }
  });
}

// Bulk activate assets
async function bulkActivate() {
  // Only activate inactive assets
  const inactiveIds = assets.value.filter(asset => asset.selected && !asset.is_active).map(asset => asset.id);
  if (inactiveIds.length === 0) {
    message.warning('选中的资产中没有可激活的资产');
    return;
  }

  Modal.confirm({
    title: '确认激活',
    content: `确定要激活选中的 ${inactiveIds.length} 个资产吗？`,
    okText: '确定',
    cancelText: '取消',
    centered: true,
    async onOk() {
      try {
        await bulkUpdateAssets(inactiveIds, { is_active: true });
        message.success(`已激活 ${inactiveIds.length} 个资产`);
        fetchAssets();
        fetchAssetStats();
      } catch (error: any) {
        message.error(error.response?.data?.detail || '批量激活失败');
      }
    }
  });
}

// Bulk delete assets
async function bulkDelete() {
  const ids = getSelectedAssetIds();
  if (ids.length === 0) {
    message.warning('请先选择要删除的资产');
    return;
  }

  Modal.confirm({
    title: '确认删除',
    content: `确定要删除选中的 ${ids.length} 个资产吗？删除后无法恢复。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    centered: true,
    async onOk() {
      try {
        await bulkDeleteAssets(ids);
        message.success(`已删除 ${ids.length} 个资产`);
        allSelected.value = false;
        fetchAssets();
        fetchAssetStats();
      } catch (error: any) {
        message.error(error.response?.data?.detail || '批量删除失败');
      }
    }
  });
}

// Organization context menu handler
function handleOrgContextMenu(event: MouseEvent, org: { id: number | null; name: string; isRoot: boolean }) {
  event.preventDefault();
  event.stopPropagation();
  orgContextMenuTarget.value = org;
  orgContextMenuPosition.value = { x: event.clientX, y: event.clientY };
  showOrgContextMenu.value = true;
}

// Close context menu
function closeOrgContextMenu() {
  showOrgContextMenu.value = false;
  orgContextMenuTarget.value = null;
}

// Open create organization modal
function openCreateOrgModal(parentId: number | null) {
  orgModalMode.value = 'create';
  orgForm.value = {
    name: '',
    parentId: parentId
  };
  showOrgModal.value = true;
  closeOrgContextMenu();
}

// Open rename organization modal
function openRenameOrgModal(org: { id: number | null; name: string; isRoot: boolean } | null) {
  if (!org || org.isRoot || org.id === null) return;
  orgModalMode.value = 'rename';
  orgForm.value = {
    name: org.name,
    parentId: null
  };
  // Store the org id in the target for rename operation
  orgContextMenuTarget.value = { id: org.id, name: org.name, isRoot: false };
  showOrgModal.value = true;
  // Close context menu but keep the target for rename operation
  showOrgContextMenu.value = false;
}

// Handle organization modal submit
async function handleOrgModalSubmit() {
  if (!orgForm.value.name.trim()) {
    message.warning('请输入节点名称');
    return;
  }

  orgModalLoading.value = true;
  try {
    if (orgModalMode.value === 'create') {
      await createOrganization(orgForm.value.name, orgForm.value.parentId ?? undefined);
      message.success('节点创建成功');
    } else if (orgModalMode.value === 'rename' && orgContextMenuTarget.value?.id) {
      await updateOrganization(orgContextMenuTarget.value.id, orgForm.value.name);
      message.success('节点重命名成功');
    }
    showOrgModal.value = false;
    fetchOrganizations();
  } catch (error: any) {
    message.error(error.response?.data?.detail || '操作失败');
  } finally {
    orgModalLoading.value = false;
  }
}

// Handle delete organization
function handleDeleteOrg(org: { id: number | null; name: string; isRoot: boolean } | null) {
  closeOrgContextMenu();
  if (!org || org.isRoot || org.id === null) return;

  Modal.confirm({
    title: '确认删除',
    content: `确定要删除节点 "${org.name}" 吗？删除后该节点下的所有子节点也会被删除。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    centered: true,
    async onOk() {
      try {
        await deleteOrganization(org.id!);
        message.success('节点已删除');
        // Clear selection if deleted org was selected
        if (selectedOrgId.value === org.id) {
          selectedOrgId.value = null;
        }
        fetchOrganizations();
        fetchAssets();
      } catch (error: any) {
        message.error(error.response?.data?.detail || '删除失败');
      }
    }
  });
}

// Drag and drop handlers for organization sorting
function handleOrgDragStart(event: DragEvent, orgId: number) {
  draggedOrgId.value = orgId;
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', String(orgId));
  }
}

function handleOrgDragOver(event: DragEvent, orgId: number | null) {
  event.preventDefault();
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move';
  }
  dragOverOrgId.value = orgId;
}

function handleOrgDragLeave() {
  dragOverOrgId.value = null;
}

async function handleOrgDrop(event: DragEvent, targetOrgId: number | null) {
  event.preventDefault();
  dragOverOrgId.value = null;

  if (draggedOrgId.value === null || draggedOrgId.value === targetOrgId) {
    draggedOrgId.value = null;
    return;
  }

  // Find the parent and get all children IDs in order
  const parentId = targetOrgId || null;

  // Find siblings at the same level
  let siblings: Organization[];
  if (parentId === null) {
    siblings = organizations.value;
  } else {
    const parent = organizations.value.find(o => o.id === parentId);
    siblings = parent?.children || [];
  }

  // Reorder: move dragged item to the position after target
  const draggedIndex = siblings.findIndex(o => o.id === draggedOrgId.value);
  if (draggedIndex === -1) {
    // Dragged org might not be in the same level, try to move it
    // For simplicity, we'll just add it to the end of the target level
    siblings = [...siblings, organizations.value.find(o => o.id === draggedOrgId.value)!];
  }

  // Create new ordered IDs
  const orderedIds = siblings
    .filter(o => o.id !== draggedOrgId.value)
    .map(o => o.id);

  // Insert dragged org at appropriate position
  if (targetOrgId !== null) {
    const targetIndex = orderedIds.indexOf(targetOrgId);
    orderedIds.splice(targetIndex + 1, 0, draggedOrgId.value);
  } else {
    orderedIds.push(draggedOrgId.value);
  }

  try {
    await reorderOrganizations(parentId, orderedIds);
    message.success('排序已更新');
    fetchOrganizations();
  } catch (error: any) {
    message.error(error.response?.data?.detail || '排序失败');
  }

  draggedOrgId.value = null;
}

function handleOrgDragEnd() {
  draggedOrgId.value = null;
  dragOverOrgId.value = null;
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
})

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
  fetchAssetStats()

  // Add global click handler to close context menu
  document.addEventListener('click', handleGlobalClick)
})

// Cleanup
onUnmounted(() => {
  document.removeEventListener('click', handleGlobalClick)
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
              <!-- Asset Tree - Root Node -->
              <div
                class="py-2 px-2 rounded cursor-pointer hover:bg-slate-50 mb-1 font-medium"
                :class="[
                  selectedOrgId === null && isRootExpanded ? 'bg-primary/10 text-primary' : 'text-slate-700',
                  dragOverOrgId === null && draggedOrgId !== null ? 'bg-blue-50' : ''
                ]"
                @click="handleRootClick"
                @contextmenu.prevent.stop="handleOrgContextMenu($event, { id: null, name: 'Default', isRoot: true })"
                @dragover.prevent="handleOrgDragOver($event, null)"
                @dragleave="handleOrgDragLeave"
                @drop.prevent="handleOrgDrop($event, null)"
              >
                <div class="flex items-center gap-1">
                  <DownOutlined
                    v-if="isRootExpanded"
                    class="text-xs cursor-pointer hover:bg-slate-200 rounded p-0.5"
                  />
                  <RightOutlined
                    v-else
                    class="text-xs cursor-pointer hover:bg-slate-200 rounded p-0.5"
                  />
                  <FolderOpenOutlined v-if="isRootExpanded" class="text-sm" />
                  <FolderOutlined v-else class="text-sm" />
                  <span class="flex-1">Default</span>
                  <span class="text-xs text-slate-400">({{ totalAssetCount }})</span>
                </div>
              </div>

              <!-- Child Nodes (only show when root is expanded) -->
              <template v-if="isRootExpanded">
                <div
                  v-for="org in flattenedOrgs"
                  :key="org.id"
                  class="py-1.5 px-2 rounded cursor-pointer hover:bg-slate-50 flex items-center gap-1"
                  :class="{
                    'bg-primary/10 text-primary': selectedOrgId === org.id,
                    'text-slate-600': selectedOrgId !== org.id,
                    'opacity-50': draggedOrgId === org.id,
                    'bg-blue-50 border-t-2 border-primary': dragOverOrgId === org.id
                  }"
                  :style="{ paddingLeft: `${(org.level + 1) * 20 + 8}px` }"
                  @click.stop="handleOrgClick(org)"
                  @contextmenu.prevent.stop="handleOrgContextMenu($event, { id: org.id, name: org.name, isRoot: false })"
                  draggable="true"
                  @dragstart="handleOrgDragStart($event, org.id)"
                  @dragover.prevent="handleOrgDragOver($event, org.id)"
                  @dragleave="handleOrgDragLeave"
                  @drop.prevent="handleOrgDrop($event, org.id)"
                  @dragend="handleOrgDragEnd"
                >
                  <DownOutlined v-if="org.hasChildren && isOrgExpanded(org.id)" class="text-xs cursor-pointer hover:bg-slate-200 rounded" />
                  <RightOutlined v-else-if="org.hasChildren && !isOrgExpanded(org.id)" class="text-xs cursor-pointer hover:bg-slate-200 rounded" />
                  <span v-else class="w-3"></span>
                  <FolderOutlined v-if="org.hasChildren && !isOrgExpanded(org.id)" class="text-sm" />
                  <FolderOpenOutlined v-else-if="org.hasChildren && isOrgExpanded(org.id)" class="text-sm" />
                  <FileTextOutlined v-else class="text-sm text-slate-400" />
                  <span class="flex-1 truncate">{{ org.name }}</span>
                  <span class="text-xs text-slate-400">({{ org.count }})</span>
                </div>
              </template>

              <!-- Organization Context Menu -->
              <div
                v-if="showOrgContextMenu"
                class="fixed z-50 bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[140px]"
                :style="{ left: `${orgContextMenuPosition.x}px`, top: `${orgContextMenuPosition.y}px` }"
                @click.stop
              >
                <div
                  @click.stop="openCreateOrgModal(orgContextMenuTarget?.id || null)"
                  class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
                >
                  <FolderAddOutlined class="text-sm" />
                  创建节点
                </div>
                <template v-if="orgContextMenuTarget && !orgContextMenuTarget.isRoot">
                  <div
                    @click.stop="openRenameOrgModal(orgContextMenuTarget)"
                    class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
                  >
                    <EditOutlined class="text-sm" />
                    重命名节点
                  </div>
                  <div class="border-t border-slate-100 my-1"></div>
                  <div
                    @click.stop="handleDeleteOrg(orgContextMenuTarget)"
                    class="px-4 py-2 text-sm text-red-500 hover:bg-red-50 cursor-pointer flex items-center gap-2"
                  >
                    <DeleteOutlined class="text-sm" />
                    删除节点
                  </div>
                </template>
              </div>
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
              <Dropdown :trigger="['click']">
                <button class="border border-slate-300 text-slate-600 text-xs px-3 py-1.5 rounded hover:bg-slate-50 transition-colors flex items-center gap-1">
                  更多操作
                  <DownOutlined class="text-[10px]" />
                </button>
                <template #overlay>
                  <div class="bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[140px]">
                    <div
                      @click="canDisable && bulkDisable()"
                      class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
                      :class="!canDisable ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''"
                    >
                      <StopOutlined class="text-sm" />
                      批量禁用
                      <span v-if="selectedActiveCount > 0" class="text-xs text-slate-400 ml-auto">({{ selectedActiveCount }})</span>
                    </div>
                    <div
                      @click="canActivate && bulkActivate()"
                      class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 cursor-pointer flex items-center gap-2"
                      :class="!canActivate ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''"
                    >
                      <CheckCircleOutlined class="text-sm" />
                      批量激活
                      <span v-if="selectedInactiveCount > 0" class="text-xs text-slate-400 ml-auto">({{ selectedInactiveCount }})</span>
                    </div>
                    <div class="border-t border-slate-100 my-1"></div>
                    <div
                      @click="selectedCount > 0 && bulkDelete()"
                      class="px-4 py-2 text-sm text-red-500 hover:bg-red-50 cursor-pointer flex items-center gap-2"
                      :class="selectedCount === 0 ? 'opacity-50 cursor-not-allowed hover:bg-transparent' : ''"
                    >
                      <DeleteOutlined class="text-sm" />
                      批量删除
                      <span v-if="selectedCount > 0" class="text-xs text-slate-400 ml-auto">({{ selectedCount }})</span>
                    </div>
                  </div>
                </template>
              </Dropdown>
            </div>
            <div class="flex items-center gap-2">
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
                  <th>地址 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>设备类型 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>厂商/型号 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>用户名密码 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                </template>
                <template v-else-if="activeCategory === 'database'">
                  <th>名称 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>地址 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>数据库类型 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>用户名密码 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                </template>
                <template v-else-if="activeCategory === 'cloud'">
                  <th>名称 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>地址 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>系统平台 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>用户名密码 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                </template>
                <template v-else-if="activeCategory === 'web'">
                  <th>名称 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>地址 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>Web服务器 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>用户名密码 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                </template>
                <template v-else-if="activeCategory === 'gpt'">
                  <th>名称 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>地址 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>AI平台 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
                  <th>用户名密码 <DownOutlined class="text-[12px] align-middle ml-1" /></th>
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
              <tr v-for="asset in assets" :key="asset.id" :class="{ 'opacity-50 bg-slate-50': !asset.is_active }">
                <td>
                  <input
                    type="checkbox"
                    class="rounded border-gray-300 text-primary focus:ring-primary w-3.5 h-3.5"
                    v-model="asset.selected"
                    @change="selectionChanged"
                  />
                </td>
                <td>
                  <div>
                    <p class="font-medium text-slate-900">{{ asset.name }}</p>
                    <p v-if="asset.asset_code" class="text-xs text-slate-400">{{ asset.asset_code }}</p>
                  </div>
                </td>

                <!-- Host category or All category (show host-style columns for all asset types) -->
                <template v-if="activeCategory === 'host' || activeCategory === 'all'">
                  <td>
                    <span class="text-sm text-slate-600 font-mono">{{ asset.url || asset.address || '-' }}</span>
                  </td>
                  <td>
                    <span class="text-sm text-slate-600">{{ asset.platform || '-' }}</span>
                  </td>
                  <td>
                    <div class="flex flex-col gap-2 py-1">
                      <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                        <span class="font-medium">{{ cred.username }}</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyUsername(cred.username)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <span v-if="decryptedPasswords.has(cred.id)" class="text-slate-700 font-mono ml-1">{{ decryptedPasswords.get(cred.id) }}</span>
                        <span v-else class="text-slate-400 font-mono ml-1">********</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyPassword(cred)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <template v-if="asset.is_active">
                          <EyeOutlined v-if="!decryptedPasswords.has(cred.id)" class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="查看密码" />
                          <EyeInvisibleOutlined v-else class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="隐藏密码" />
                        </template>
                        <EyeOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed ml-1" />
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
                    <span class="text-sm text-slate-600">{{ asset.platform && asset.model ? `${asset.platform}/${asset.model}` : (asset.platform || asset.model || '-') }}</span>
                  </td>
                  <td>
                    <div class="flex flex-col gap-2 py-1">
                      <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                        <span class="font-medium">{{ cred.username }}</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyUsername(cred.username)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <span v-if="decryptedPasswords.has(cred.id)" class="text-slate-700 font-mono ml-1">{{ decryptedPasswords.get(cred.id) }}</span>
                        <span v-else class="text-slate-400 font-mono ml-1">********</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyPassword(cred)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <template v-if="asset.is_active">
                          <EyeOutlined v-if="!decryptedPasswords.has(cred.id)" class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="查看密码" />
                          <EyeInvisibleOutlined v-else class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="隐藏密码" />
                        </template>
                        <EyeOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed ml-1" />
                      </div>
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
                    <div class="flex flex-col gap-2 py-1">
                      <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                        <span class="font-medium">{{ cred.username }}</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyUsername(cred.username)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <span v-if="decryptedPasswords.has(cred.id)" class="text-slate-700 font-mono ml-1">{{ decryptedPasswords.get(cred.id) }}</span>
                        <span v-else class="text-slate-400 font-mono ml-1">********</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyPassword(cred)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <template v-if="asset.is_active">
                          <EyeOutlined v-if="!decryptedPasswords.has(cred.id)" class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="查看密码" />
                          <EyeInvisibleOutlined v-else class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="隐藏密码" />
                        </template>
                        <EyeOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed ml-1" />
                      </div>
                    </div>
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
                    <div class="flex flex-col gap-2 py-1">
                      <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                        <span class="font-medium">{{ cred.username }}</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyUsername(cred.username)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <span v-if="decryptedPasswords.has(cred.id)" class="text-slate-700 font-mono ml-1">{{ decryptedPasswords.get(cred.id) }}</span>
                        <span v-else class="text-slate-400 font-mono ml-1">********</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyPassword(cred)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <template v-if="asset.is_active">
                          <EyeOutlined v-if="!decryptedPasswords.has(cred.id)" class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="查看密码" />
                          <EyeInvisibleOutlined v-else class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="隐藏密码" />
                        </template>
                        <EyeOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed ml-1" />
                      </div>
                    </div>
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
                    <div class="flex flex-col gap-2 py-1">
                      <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                        <span class="font-medium">{{ cred.username }}</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyUsername(cred.username)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <span v-if="decryptedPasswords.has(cred.id)" class="text-slate-700 font-mono ml-1">{{ decryptedPasswords.get(cred.id) }}</span>
                        <span v-else class="text-slate-400 font-mono ml-1">********</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyPassword(cred)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <template v-if="asset.is_active">
                          <EyeOutlined v-if="!decryptedPasswords.has(cred.id)" class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="查看密码" />
                          <EyeInvisibleOutlined v-else class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="隐藏密码" />
                        </template>
                        <EyeOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed ml-1" />
                      </div>
                    </div>
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
                    <div class="flex flex-col gap-2 py-1">
                      <div v-for="cred in asset.credentials || []" :key="cred.id" class="flex items-center gap-1.5 text-slate-600 py-1">
                        <span class="font-medium">{{ cred.username }}</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyUsername(cred.username)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <span v-if="decryptedPasswords.has(cred.id)" class="text-slate-700 font-mono ml-1">{{ decryptedPasswords.get(cred.id) }}</span>
                        <span v-else class="text-slate-400 font-mono ml-1">********</span>
                        <CopyOutlined v-if="asset.is_active" class="text-[14px] cursor-pointer hover:text-primary" @click="copyPassword(cred)" />
                        <CopyOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed" />
                        <template v-if="asset.is_active">
                          <EyeOutlined v-if="!decryptedPasswords.has(cred.id)" class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="查看密码" />
                          <EyeInvisibleOutlined v-else class="text-[14px] cursor-pointer hover:text-primary ml-1" @click="viewPassword(cred)" title="隐藏密码" />
                        </template>
                        <EyeOutlined v-else class="text-[14px] text-slate-300 cursor-not-allowed ml-1" />
                      </div>
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
                    <button
                      v-if="asset.is_active"
                      @click="openEditModal(asset)"
                      class="bg-primary text-white px-2 py-0.5 rounded hover:bg-blue-600 transition-colors text-xs"
                    >
                      更新
                    </button>
                    <button
                      v-else
                      disabled
                      class="bg-slate-200 text-slate-400 px-2 py-0.5 rounded cursor-not-allowed text-xs"
                    >
                      更新
                    </button>
                    <button
                      v-if="asset.is_active"
                      @click="handleDelete(asset)"
                      class="border border-red-400 text-red-500 px-2 py-0.5 rounded hover:bg-red-50 transition-colors text-xs"
                    >
                      删除
                    </button>
                    <button
                      v-else
                      disabled
                      class="border border-slate-200 text-slate-300 px-2 py-0.5 rounded cursor-not-allowed text-xs"
                    >
                      删除
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
          <h2 class="text-lg font-bold text-slate-900">{{ modalTitle }}</h2>
          <button @click="showModal = false" class="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
            <CloseOutlined class="text-slate-400" />
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleSubmit" class="space-y-5">
            <!-- Row 1: 资产名称、资产编号 -->
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1.5">资产名称 <span class="text-red-500">*</span></label>
                <input v-model="form.name" type="text" class="input-field" placeholder="请输入资产名称" />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1.5">资产编号</label>
                <input v-model="form.asset_code" type="text" class="input-field" placeholder="CI编号" />
              </div>
            </div>

            <!-- Row 2: 节点路径 -->
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1.5">节点</label>
              <div class="input-field bg-slate-50 text-slate-600 cursor-not-allowed flex items-center gap-2">
                <FolderOutlined class="text-sm text-slate-400" />
                <span class="truncate">{{ getOrgPath(selectedOrgId) }}</span>
              </div>
            </div>

            <!-- Network设备专用布局 -->
            <template v-if="form.category === 'network'">
              <!-- Row 2: 资产类型、设备类型 -->
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">资产类型 <span class="text-red-500">*</span></label>
                  <select v-model="form.category" class="input-field">
                    <option v-for="cat in categoryOptions" :key="cat.key" :value="cat.key">{{ cat.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">设备类型</label>
                  <select v-model="form.device_type" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="t in deviceTypeOptions" :key="t" :value="t">{{ t }}</option>
                  </select>
                </div>
              </div>

              <!-- Row 3: 平台（厂商）、型号 -->
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">厂商</label>
                  <select v-model="form.platform" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="p in platformOptions[form.category]" :key="p" :value="p">{{ p }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">型号</label>
                  <input v-model="form.model" type="text" class="input-field" placeholder="如: C9300-48P" />
                </div>
              </div>

              <!-- Row 4: 地址 -->
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1.5">地址</label>
                <input
                  v-model="form.address"
                  type="text"
                  class="input-field"
                  placeholder="支持格式: IP、IP:端口"
                />
              </div>
            </template>

            <!-- 其他类别布局 -->
            <template v-else>
              <!-- Row 2: 资产类型、平台 -->
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">资产类型 <span class="text-red-500">*</span></label>
                  <select v-model="form.category" class="input-field">
                    <option v-for="cat in categoryOptions" :key="cat.key" :value="cat.key">{{ cat.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-600 mb-1.5">平台</label>
                  <select v-model="form.platform" class="input-field">
                    <option value="">请选择</option>
                    <option v-for="p in platformOptions[form.category]" :key="p" :value="p">{{ p }}</option>
                  </select>
                </div>
              </div>

              <!-- Row 3: 地址 -->
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1.5">
                  {{ form.category === 'cloud' || form.category === 'web' || form.category === 'gpt' ? 'URL' : '地址' }}
                </label>
                <input
                  v-if="form.category !== 'cloud' && form.category !== 'gpt' && form.category !== 'web'"
                  v-model="form.address"
                  type="text"
                  class="input-field"
                  placeholder="支持格式: IP、IP:端口、主机名、主机名:端口"
                />
                <input
                  v-else
                  v-model="form.url"
                  type="text"
                  class="input-field"
                  placeholder="https://"
                />
              </div>
            </template>

            <!-- Row 4: 用户名密码 -->
            <div class="border border-slate-200 rounded-lg overflow-hidden">
              <div class="bg-slate-50 px-4 py-2.5 border-b border-slate-200">
                <label class="text-xs font-medium text-slate-600">用户名密码</label>
              </div>
              <div class="p-4">
                <!-- Existing credentials list -->
                <div v-if="formCredentials.length > 0" class="space-y-2 mb-4">
                  <div v-for="(cred, index) in formCredentials" :key="index" class="bg-slate-50 px-3 py-2 rounded-lg border border-slate-200">
                    <div class="flex items-center gap-3">
                      <!-- Username field -->
                      <div class="flex items-center gap-2 flex-1">
                        <span class="text-xs text-slate-500">用户名:</span>
                        <input
                          v-if="isFieldEditing(index, 'username')"
                          :ref="(el: any) => { if (el) credentialInputRefs.set(`${index}-username`, el) }"
                          v-model="cred.username"
                          type="text"
                          class="input-field text-sm flex-1"
                          @blur="stopFieldEdit"
                          @keyup.enter="stopFieldEdit"
                        />
                        <span
                          v-else
                          class="font-medium text-slate-700 cursor-pointer hover:bg-slate-200 px-1 rounded"
                          @dblclick="startFieldEdit(index, 'username')"
                          title="双击编辑"
                        >{{ cred.username }}</span>
                      </div>
                      <!-- Password field -->
                      <div class="flex items-center gap-2 flex-1">
                        <span class="text-xs text-slate-500">密码:</span>
                        <input
                          v-if="isFieldEditing(index, 'password')"
                          :ref="(el: any) => { if (el) credentialInputRefs.set(`${index}-password`, el) }"
                          v-model="cred.password"
                          type="text"
                          class="input-field text-sm flex-1"
                          @blur="stopFieldEdit"
                          @keyup.enter="stopFieldEdit"
                          placeholder="输入新密码"
                        />
                        <span
                          v-else-if="cred.id && decryptedFormPasswords.has(cred.id)"
                          class="text-slate-700 font-mono cursor-pointer hover:bg-slate-200 px-1 rounded"
                          @dblclick="startFieldEdit(index, 'password')"
                          title="双击编辑"
                        >{{ decryptedFormPasswords.get(cred.id) }}</span>
                        <span
                          v-else-if="!cred.id && visibleNewPasswords.has(index)"
                          class="text-slate-700 font-mono cursor-pointer hover:bg-slate-200 px-1 rounded"
                          @dblclick="startFieldEdit(index, 'password')"
                          title="双击编辑"
                        >{{ cred.password }}</span>
                        <span
                          v-else
                          class="text-slate-400 font-mono cursor-pointer hover:bg-slate-200 px-1 rounded"
                          @dblclick="startFieldEdit(index, 'password')"
                          title="双击编辑"
                        >********</span>
                      </div>
                      <!-- Actions -->
                      <div class="flex items-center gap-0.5">
                        <!-- Eye icon for existing credentials -->
                        <button v-if="cred.id" type="button" @click="viewFormCredentialPassword(cred)" class="p-1.5 text-slate-400 hover:text-primary hover:bg-slate-100 rounded" :title="decryptedFormPasswords.has(cred.id) ? '隐藏密码' : '查看密码'">
                          <EyeOutlined v-if="!decryptedFormPasswords.has(cred.id)" class="text-sm" />
                          <EyeInvisibleOutlined v-else class="text-sm" />
                        </button>
                        <!-- Eye icon for new credentials -->
                        <button v-else type="button" @click="viewFormCredentialPassword(cred, index)" class="p-1.5 text-slate-400 hover:text-primary hover:bg-slate-100 rounded" :title="visibleNewPasswords.has(index) ? '隐藏密码' : '查看密码'">
                          <EyeOutlined v-if="!visibleNewPasswords.has(index)" class="text-sm" />
                          <EyeInvisibleOutlined v-else class="text-sm" />
                        </button>
                        <button type="button" @click="removeCredentialFromForm(index)" class="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded" title="删除">
                          <DeleteOutlined class="text-sm" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Add new credential form -->
                <div class="flex items-end gap-3">
                  <div class="flex-1">
                    <label class="block text-xs text-slate-500 mb-1">用户名</label>
                    <input
                      v-model="newCredentialForm.username"
                      type="text"
                      class="input-field text-sm"
                      placeholder="输入用户名"
                    />
                  </div>
                  <div class="flex-1 relative">
                    <label class="block text-xs text-slate-500 mb-1">密码</label>
                    <input
                      v-model="newCredentialForm.password"
                      :type="showPassword ? 'text' : 'password'"
                      class="input-field text-sm w-full pr-8"
                      placeholder="输入密码"
                    />
                    <button
                      type="button"
                      @click="showPassword = !showPassword"
                      class="absolute right-2 top-[calc(50%+10px)] -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      <EyeOutlined v-if="!showPassword" class="text-sm" />
                      <EyeInvisibleOutlined v-else class="text-sm" />
                    </button>
                  </div>
                  <button
                    type="button"
                    @click="addCredentialToForm"
                    class="bg-primary text-white px-4 py-2 rounded text-sm hover:bg-blue-600 transition-colors h-[38px]"
                  >
                    <PlusCircleOutlined class="mr-1" /> 添加
                  </button>
                </div>
              </div>
            </div>

            <!-- Notes -->
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1.5">描述</label>
              <textarea v-model="form.notes" class="input-field h-20 resize-none" placeholder="资产描述或备注"></textarea>
            </div>

            <!-- Actions -->
            <div class="flex justify-end gap-3 pt-2 border-t border-slate-100">
              <button type="button" @click="showModal = false" class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors">
                取消
              </button>
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
                v-model="newCredentialForm.username"
                type="text"
                class="input-field"
                placeholder="用户名"
              />
              <input
                v-model="newCredentialForm.password"
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
                  :title="decryptedPasswords.has(cred.id) ? '隐藏密码' : '查看密码'"
                >
                  <EyeOutlined v-if="!decryptedPasswords.has(cred.id)" class="text-lg" />
                  <EyeInvisibleOutlined v-else class="text-lg" />
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

    <!-- Organization Node Modal (Create/Rename) -->
    <div v-if="showOrgModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showOrgModal = false"></div>
      <div class="relative bg-white w-full max-w-md rounded-xl shadow-2xl">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-lg font-bold text-slate-900">
            {{ orgModalMode === 'create' ? '创建节点' : '重命名节点' }}
          </h2>
          <button @click="showOrgModal = false" class="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
            <CloseOutlined class="text-slate-400" />
          </button>
        </div>
        <div class="p-6">
          <form @submit.prevent="handleOrgModalSubmit" class="space-y-4">
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1.5">节点名称 <span class="text-red-500">*</span></label>
              <input
                v-model="orgForm.name"
                type="text"
                class="input-field"
                placeholder="请输入节点名称"
                autofocus
              />
            </div>
            <div class="flex justify-end gap-3 pt-2 border-t border-slate-100">
              <button
                type="button"
                @click="showOrgModal = false"
                class="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                type="submit"
                :disabled="orgModalLoading"
                class="btn-primary"
              >
                {{ orgModalLoading ? '处理中...' : '确定' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>