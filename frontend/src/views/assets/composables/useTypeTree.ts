/**
 * Type tree management composable
 * Handles type tree structure, expansion, and selection
 */
import { ref, computed } from 'vue'
import type { AssetCategory } from '@/types'
import {
  AppstoreOutlined,
  ClusterOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  GlobalOutlined,
  RobotOutlined
} from '@ant-design/icons-vue'

// Category definitions
export const categories = [
  { key: 'all', label: '全部', icon: AppstoreOutlined },
  { key: 'host', label: '主机', icon: AppstoreOutlined },
  { key: 'network', label: '网络设备', icon: ClusterOutlined },
  { key: 'database', label: '数据库', icon: DatabaseOutlined },
  { key: 'cloud', label: '云服务', icon: CloudServerOutlined },
  { key: 'web', label: '网站服务', icon: GlobalOutlined },
  { key: 'gpt', label: 'AI服务', icon: RobotOutlined }
]

export const categoryOptions = categories.filter(c => c.key !== 'all')

// Platform options by category
export const platformOptions: Record<string, string[]> = {
  host: ['Linux', 'Windows', 'Unix', 'MacOS', 'NAS', 'SAN'],
  network: ['Cisco', 'Huawei', 'H3C', 'Ruijie', 'ZTE', 'TP-Link', 'Tenda', 'ASUS', 'MERCURY', 'Netgear', 'Juniper'],
  database: ['物理机', '虚拟机', 'RDS', 'Kubernetes', 'Docker'],
  cloud: ['Proxmox', 'Kubernetes', 'KubeSphere', 'Rancher', 'Harvester', 'OpenStack', 'ZStack', 'CloudStack', 'VMware', 'oVirt', 'KVM', 'AWS', 'Azure', 'GCP', '阿里云', '腾讯云', '青云', 'UCloud', '火山云', '天翼云', '移动云', '华为云'],
  web: ['Nginx', 'Apache', 'IIS', 'Tomcat', 'Nginx Ingress', 'Higress', 'Traefik', 'APISIX', 'Loadbalancer', 'F5'],
  gpt: ['OpenAI', 'Claude', 'GLM', 'Qwen', 'DeepSeek', 'Gemini', 'MiMo', 'MiniMax', 'Kimi', 'Gemma', 'ERNIE']
}

// Device type options for network
export const deviceTypeOptions = ['交换机', '路由器', '防火墙', '无线控制器', '负载均衡']

// Database type options
export const dbTypeOptions = ['MySQL', 'MongoDB', 'Redis', 'PostgreSQL', 'Oracle', 'SQL Server', 'InfluxDB', 'Elasticsearch', 'RabbitMQ', 'RocketMQ', 'Kafka', 'ClickHouse', 'EMQ', '达梦', 'TiDB', 'IoTDB', 'TDengine', 'Prometheus', 'Neo4j', 'Milvus', 'Weaviate', 'Qdrant']

export interface AssetStats {
  total: number
  by_category: Record<string, number>
  by_platform: Record<string, number>
  by_device_type: Record<string, number>
  by_db_type: Record<string, number>
}

export function useTypeTree(assetStats: { value: AssetStats }) {
  // State
  const expandedTypeIds = ref<string[]>(['all'])
  const selectedTypeNodeId = ref<string>('all')
  const activeCategory = ref<AssetCategory | 'all'>('all')

  // Type tree structure
  const typeTreeStructure = computed(() => {
    const treeData: any[] = [
      {
        id: 'all',
        name: '所有类型',
        count: assetStats.value.total,
        level: 0,
        hasChildren: true,
        isRoot: true
      }
    ]

    categories.forEach(cat => {
      if (cat.key === 'all') return
      const categoryCount = assetStats.value.by_category[cat.key] || 0

      // Determine sub-categories for this type
      let subCategories: string[] = []
      if (cat.key === 'host') subCategories = platformOptions.host
      else if (cat.key === 'network') subCategories = deviceTypeOptions
      else if (cat.key === 'database') subCategories = dbTypeOptions
      else if (cat.key === 'cloud') subCategories = platformOptions.cloud
      else if (cat.key === 'web') subCategories = platformOptions.web
      else if (cat.key === 'gpt') subCategories = platformOptions.gpt

      const hasChildren = subCategories.length > 0

      treeData.push({
        id: cat.key,
        name: `${cat.label} (${categoryCount})`,
        count: categoryCount,
        level: 1,
        hasChildren,
        parentId: 'all',
        category: cat.key
      })

      subCategories.forEach(subCat => {
        // Determine count from stats
        let subCatCount = 0
        if (cat.key === 'network') {
          subCatCount = assetStats.value.by_device_type[subCat] || 0
        } else if (cat.key === 'database') {
          subCatCount = assetStats.value.by_db_type[subCat] || 0
        } else {
          const platformKey = `${cat.key}:${subCat}`
          subCatCount = assetStats.value.by_platform[platformKey] || 0
        }

        const idSuffix = subCat.toLowerCase().replace(/\s+/g, '')
        treeData.push({
          id: `${cat.key}-${idSuffix}`,
          name: `${subCat} (${subCatCount})`,
          count: subCatCount,
          level: 2,
          hasChildren: false,
          parentId: cat.key,
          subCategory: subCat,
          category: cat.key
        })
      })
    })

    return treeData
  })

  // Flattened type tree for display
  const flattenedTypeTree = computed(() => {
    const result: any[] = []

    const root = typeTreeStructure.value.find((node: any) => node.isRoot)
    if (root) {
      result.push(root)

      if (expandedTypeIds.value.includes(root.id)) {
        const level1Nodes = typeTreeStructure.value.filter((node: any) => node.parentId === root.id)
        for (const level1Node of level1Nodes) {
          result.push({ ...level1Node, level: 1 })

          if (expandedTypeIds.value.includes(level1Node.id)) {
            const level2Nodes = typeTreeStructure.value.filter((node: any) => node.parentId === level1Node.id)
            for (const level2Node of level2Nodes) {
              result.push({ ...level2Node, level: 2 })
            }
          }
        }
      }
    }

    return result
  })

  // Selected type node
  const selectedTypeNode = computed(() => {
    if (selectedTypeNodeId.value === 'all') {
      return null
    }
    return flattenedTypeTree.value.find((node: any) => node.id === selectedTypeNodeId.value) || null
  })

  // Toggle type expansion
  function toggleType(typeId: string) {
    if (typeId === 'all') {
      const index = expandedTypeIds.value.indexOf('all')
      if (index > -1) {
        expandedTypeIds.value.splice(index, 1)
        expandedTypeIds.value = expandedTypeIds.value.filter(id => !categories.some(c => c.key === id))
      } else {
        expandedTypeIds.value.push('all')
      }
    } else {
      const index = expandedTypeIds.value.indexOf(typeId)
      if (index > -1) {
        expandedTypeIds.value.splice(index, 1)
      } else {
        expandedTypeIds.value = expandedTypeIds.value.filter(id => id === 'all' || !categories.some(c => c.key === id))
        expandedTypeIds.value.push(typeId)
      }
    }
  }

  // Check if type node is selected
  function isSelectedTypeNode(node: any): boolean {
    return selectedTypeNodeId.value === node.id
  }

  // Select type node
  function selectType(node: any, callback?: (category: AssetCategory | 'all', orgId: number | null) => void) {
    if (node.isRoot) {
      toggleType('all')
      selectedTypeNodeId.value = 'all'
      callback?.('all', null)
    } else if (node.hasChildren) {
      toggleType(node.id)
      selectedTypeNodeId.value = node.id
      if (node.category) {
        activeCategory.value = node.category as AssetCategory
      }
      callback?.(activeCategory.value, null)
    } else if (node.subCategory && node.category) {
      selectedTypeNodeId.value = node.id
      activeCategory.value = node.category as AssetCategory
      callback?.(activeCategory.value, null)
    } else if (node.category) {
      selectedTypeNodeId.value = node.id
      activeCategory.value = node.category as AssetCategory
      callback?.(activeCategory.value, null)
    }
  }

  // Get category icon
  function getCategoryIcon(category: string) {
    const cat = categories.find(c => c.key === category)
    return cat?.icon || AppstoreOutlined
  }

  return {
    // State
    expandedTypeIds,
    selectedTypeNodeId,
    activeCategory,
    flattenedTypeTree,
    selectedTypeNode,

    // Actions
    toggleType,
    isSelectedTypeNode,
    selectType,
    getCategoryIcon
  }
}