"""
Asset Import Service
Handles XLSX template generation and file import processing
"""
from io import BytesIO
from typing import List, Dict, Any, Optional, Tuple
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.encryption import encrypt_value

from app.models import Asset, Organization
from sqlalchemy import select

# Host field definitions for templates
# Format: (field_name, display_label, is_required)
HOST_CREATE_FIELDS = [
    ("name", "*资产名称", True),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("platform", "*平台", True),
    ("external_address", "外网地址", False),
    ("internal_address", "*内网地址", True),
    ("model", "型号", False),
    ("serial_number", "序列号", False),
    ("cpu", "CPU", False),
    ("memory", "内存", False),
    ("system_disk", "系统盘", False),
    ("data_disk", "数据盘", False),
    ("oob", "OOB 地址", False),
    ("oob_username", "OOB 用户名", False),
    ("oob_password", "OOB 密码", False),
    ("applicant", "申请人", False),
    ("is_active", "状态", False),  # 启用/禁用 或 True/False 或 1/0
    ("credentials", "*用户名密码", True),  # 格式：username:password，每行一个
    ("notes", "描述", False),
]

HOST_UPDATE_FIELDS = [
    ("id", "*ID", True),
    ("name", "资产名称", False),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("platform", "平台", False),
    ("external_address", "外网地址", False),
    ("internal_address", "内网地址", False),
    ("model", "型号", False),
    ("serial_number", "序列号", False),
    ("cpu", "CPU", False),
    ("memory", "内存", False),
    ("system_disk", "系统盘", False),
    ("data_disk", "数据盘", False),
    ("oob", "OOB 地址", False),
    ("oob_username", "OOB 用户名", False),
    ("oob_password", "OOB 密码", False),
    ("applicant", "申请人", False),
    ("is_active", "状态", False),  # 启用/禁用 或 True/False 或 1/0
    ("credentials", "用户名密码", False),  # 格式：username:password，每行一个
    ("notes", "描述", False),
]

# Network field definitions
NETWORK_CREATE_FIELDS = [
    ("name", "*资产名称", True),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("device_type", "*设备类型", True),  # 交换机/路由器/防火墙/无线控制器
    ("vendor", "*厂商", True),  # Cisco/Huawei/Aruba 等
    ("model", "型号", False),
    ("serial_number", "序列号", False),
    ("external_address", "外网地址", False),  # 多行，每行一个
    ("internal_address", "内网地址", False),  # 多行，每行一个
    ("applicant", "申请人", False),
    ("credentials", "*用户名密码", True),  # 格式：username:password，多行每行一个
    ("is_active", "*状态", True),  # 启用/禁用 或 True/False 或 1/0
    ("notes", "描述", False),
]

NETWORK_UPDATE_FIELDS = [
    ("id", "*ID", True),
    ("name", "资产名称", False),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("device_type", "设备类型", False),
    ("vendor", "厂商", False),
    ("model", "型号", False),
    ("serial_number", "序列号", False),
    ("external_address", "外网地址", False),
    ("internal_address", "内网地址", False),
    ("applicant", "申请人", False),
    ("credentials", "用户名密码", False),
    ("is_active", "状态", False),  # 启用/禁用 或 True/False 或 1/0
    ("notes", "描述", False),
]

# Database field definitions
DATABASE_CREATE_FIELDS = [
    ("name", "*资产名称", True),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("platform", "*数据库类型", True),  # MySQL/PostgreSQL/MongoDB/Redis
    ("address", "*地址:端口", True),
    ("credentials", "*用户名密码", True),  # 格式：username:password，每行一个
    ("version", "版本", False),
    ("notes", "描述", False),
]

DATABASE_UPDATE_FIELDS = [
    ("id", "*ID", True),
    ("name", "资产名称", False),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("platform", "数据库类型", False),
    ("address", "地址:端口", False),
    ("credentials", "用户名密码", False),
    ("version", "版本", False),
    ("notes", "描述", False),
]

# Cloud field definitions
CLOUD_CREATE_FIELDS = [
    ("name", "*资产名称", True),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("platform", "*云平台", True),  # AWS/阿里云/腾讯云/Azure
    ("external_address", "外网地址", False),  # 多行，每行一个
    ("internal_address", "内网地址", False),  # 多行，每行一个
    ("resource_id", "资源 ID", False),  # 云资源唯一标识
    ("credentials", "*访问凭证", True),  # 格式：AKID:Secret 或 username:password
    ("region", "区域", False),  # 如：cn-hangzhou
    ("applicant", "申请人", False),
    ("is_active", "状态", False),  # 启用/禁用 或 True/False 或 1/0
    ("notes", "描述", False),
]

CLOUD_UPDATE_FIELDS = [
    ("id", "*ID", True),
    ("name", "资产名称", False),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("platform", "云平台", False),
    ("external_address", "外网地址", False),
    ("internal_address", "内网地址", False),
    ("resource_id", "资源 ID", False),
    ("credentials", "访问凭证", False),
    ("region", "区域", False),
    ("applicant", "申请人", False),
    ("is_active", "状态", False),
    ("notes", "描述", False),
]

# Web field definitions
WEB_CREATE_FIELDS = [
    ("name", "*资产名称", True),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("external_address", "*外网地址", True),
    ("internal_address", "内网地址", False),
    ("credentials", "*用户名密码", True),  # 格式：username:password，每行一个
    ("applicant", "申请人", False),
    ("is_active", "状态", False),  # 启用/禁用 或 True/False 或 1/0
    ("notes", "描述", False),
]

WEB_UPDATE_FIELDS = [
    ("id", "*ID", True),
    ("name", "资产名称", False),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("external_address", "外网地址", False),
    ("internal_address", "内网地址", False),
    ("credentials", "用户名密码", False),
    ("applicant", "申请人", False),
    ("is_active", "状态", False),
    ("notes", "描述", False),
]

# GPT field definitions
GPT_CREATE_FIELDS = [
    ("name", "*资产名称", True),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("platform", "*AI 平台", True),  # OpenAI/Claude/ChatGLM/通义千问
    ("external_address", "*外网地址", True),  # API 地址
    ("internal_address", "内网地址", False),
    ("credentials", "*API Key", True),  # 格式：key_name:api_key，每行一个
    ("applicant", "申请人", False),
    ("is_active", "状态", False),  # 启用/禁用 或 True/False 或 1/0
    ("notes", "描述", False),
]

GPT_UPDATE_FIELDS = [
    ("id", "*ID", True),
    ("name", "资产名称", False),
    ("asset_code", "资产编号", False),
    ("organization", "节点", False),
    ("platform", "AI 平台", False),
    ("external_address", "外网地址", False),
    ("internal_address", "内网地址", False),
    ("credentials", "API Key", False),
    ("applicant", "申请人", False),
    ("is_active", "状态", False),
    ("notes", "描述", False),
]

# Category field mapping
CATEGORY_FIELDS = {
    "host": {"create": HOST_CREATE_FIELDS, "update": HOST_UPDATE_FIELDS},
    "network": {"create": NETWORK_CREATE_FIELDS, "update": NETWORK_UPDATE_FIELDS},
    "database": {"create": DATABASE_CREATE_FIELDS, "update": DATABASE_UPDATE_FIELDS},
    "cloud": {"create": CLOUD_CREATE_FIELDS, "update": CLOUD_UPDATE_FIELDS},
    "web": {"create": WEB_CREATE_FIELDS, "update": WEB_UPDATE_FIELDS},
    "gpt": {"create": GPT_CREATE_FIELDS, "update": GPT_UPDATE_FIELDS},
}

# Category display names
CATEGORY_NAMES = {
    "host": "主机",
    "network": "网络设备",
    "database": "数据库",
    "cloud": "云服务",
    "web": "网站服务",
    "gpt": "AI 服务",
}


def generate_host_create_template() -> BytesIO:
    """Generate XLSX template for host creation"""
    example_data = [
        "test-server-01", "CI001", "研发部/服务器组", "Linux",
        "192.168.1.100", "10.0.0.100", "Dell R740",
        "SN123456", "8 核", "16GB", "500GB SSD", "2TB HDD",
        "192.168.1.100", "admin", "password", "张三",
        "admin:password123\nroot:rootpass",
        "测试服务器"
    ]
    return _generate_template("host", "create", "主机导入模板", HOST_CREATE_FIELDS, example_data)


# Generic template generation function
def _generate_template(
    category: str,
    mode: str,
    title: str,
    fields: List[Tuple[str, str, bool]],
    example_data: List[str]
) -> BytesIO:
    """
    Generic XLSX template generator

    Args:
        category: Asset category (host, network, etc.)
        mode: 'create' or 'update'
        title: Sheet title
        fields: List of (field_name, display_label, is_required)
        example_data: Example row data
    """
    wb = Workbook()
    ws = wb.active
    ws.title = title

    # Header styles
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_alignment = Alignment(horizontal="center", vertical="center")
    header_border = Border(
        left=Side(style='thin', color='B4C6E7'),
        right=Side(style='thin', color='B4C6E7'),
        top=Side(style='thin', color='B4C6E7'),
        bottom=Side(style='thin', color='B4C6E7')
    )

    # Write headers
    for col, (field_name, label, required) in enumerate(fields, 1):
        cell = ws.cell(row=1, column=col, value=label)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = header_border

    # Example row
    for col, value in enumerate(example_data, 1):
        cell = ws.cell(row=2, column=col, value=value)
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.border = Border(
            left=Side(style='thin', color='E7E6E6'),
            right=Side(style='thin', color='E7E6E6'),
            top=Side(style='thin', color='E7E6E6'),
            bottom=Side(style='thin', color='E7E6E6')
        )

    # Set column widths dynamically
    default_width = 15
    for idx in range(len(fields)):
        col_letter = ws.cell(row=1, column=idx + 1).column_letter
        # Wider columns for specific field types
        field_name = fields[idx][0]
        if field_name in ['id', 'url', 'external_url', 'internal_url', 'address', 'external_address', 'internal_address']:
            ws.column_dimensions[col_letter].width = 25
        elif field_name == 'credentials':
            ws.column_dimensions[col_letter].width = 20
        elif field_name == 'organization':
            ws.column_dimensions[col_letter].width = 18
        else:
            ws.column_dimensions[col_letter].width = default_width

    # Set row heights
    ws.row_dimensions[1].height = 25
    ws.row_dimensions[2].height = 20

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_host_update_template() -> BytesIO:
    """Generate XLSX template for host update"""
    example_data = [
        "56c4d4cd-42ba-4397-abfa-36ecba64af13", "test-server-01", "CI001", "研发部/服务器组", "Linux",
        "192.168.1.100", "10.0.0.100", "Dell R740", "SN123456", "8 核", "16GB", "500GB SSD", "2TB HDD",
        "192.168.1.100", "admin", "password", "张三",
        "admin:password123\nroot:rootpass",
        "测试服务器"
    ]
    return _generate_template("host", "update", "主机更新模板", HOST_UPDATE_FIELDS, example_data)


# Network templates
def generate_network_create_template() -> BytesIO:
    """Generate XLSX template for network device creation"""
    example_data = [
        "Core-SW-01", "NW001", "研发部/网络设备", "交换机", "Cisco",
        "C9300-48P", "FCW1234D001",
        "10.0.0.1",  # 外网地址
        "192.168.1.1",  # 内网地址
        "admin:ciscopass\nnetadmin:netpass",  # 用户名密码 (多行)
        "启用",  # 状态 (支持：启用/禁用，True/False，1/0)
        "核心交换机"
    ]
    return _generate_template("network", "create", "网络设备导入模板", NETWORK_CREATE_FIELDS, example_data)


def generate_network_update_template() -> BytesIO:
    """Generate XLSX template for network device update"""
    example_data = [
        "56c4d4cd-42ba-4397-abfa-36ecba64af13", "Core-SW-01", "NW001", "研发部/网络设备", "交换机", "Cisco",
        "C9300-48P", "FCW1234D001",
        "10.0.0.1",  # 外网地址
        "192.168.1.1",  # 内网地址
        "admin:ciscopass\nnetadmin:netpass",  # 用户名密码 (多行)
        "启用",  # 状态 (支持：启用/禁用，True/False，1/0)
        "核心交换机"
    ]
    return _generate_template("network", "update", "网络设备更新模板", NETWORK_UPDATE_FIELDS, example_data)


# Database templates
def generate_database_create_template() -> BytesIO:
    """Generate XLSX template for database creation"""
    example_data = [
        "MySQL-Prod-01", "DB001", "研发部/数据库", "MySQL",
        "192.168.1.100:3306",
        "root:mysqlroot123\napp:apppass",
        "8.0.32",
        "生产环境主数据库"
    ]
    return _generate_template("database", "create", "数据库导入模板", DATABASE_CREATE_FIELDS, example_data)


def generate_database_update_template() -> BytesIO:
    """Generate XLSX template for database update"""
    example_data = [
        "56c4d4cd-42ba-4397-abfa-36ecba64af13", "MySQL-Prod-01", "DB001", "研发部/数据库", "MySQL",
        "192.168.1.100:3306",
        "root:mysqlroot123\napp:apppass",
        "8.0.32",
        "生产环境主数据库"
    ]
    return _generate_template("database", "update", "数据库更新模板", DATABASE_UPDATE_FIELDS, example_data)


# Cloud templates
def generate_cloud_create_template() -> BytesIO:
    """Generate XLSX template for cloud resource creation"""
    example_data = [
        "AWS-Prod-Account", "CL001", "研发部/云服务", "AWS",
        "123456789012",
        "AKIAIOSFODNN7EXAMPLE:wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "cn-north-1",
        "生产环境 AWS 账号"
    ]
    return _generate_template("cloud", "create", "云服务导入模板", CLOUD_CREATE_FIELDS, example_data)


def generate_cloud_update_template() -> BytesIO:
    """Generate XLSX template for cloud resource update"""
    example_data = [
        "56c4d4cd-42ba-4397-abfa-36ecba64af13", "AWS-Prod-Account", "CL001", "研发部/云服务", "AWS",
        "123456789012",
        "AKIAIOSFODNN7EXAMPLE:wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "cn-north-1",
        "生产环境 AWS 账号"
    ]
    return _generate_template("cloud", "update", "云服务更新模板", CLOUD_UPDATE_FIELDS, example_data)


# Web templates
def generate_web_create_template() -> BytesIO:
    """Generate XLSX template for web application creation"""
    example_data = [
        "Jira", "WB001", "研发部/应用系统", "https://jira.example.com",
        "http://192.168.1.100:8080",
        "admin:jiraadmin\nreadonly:readonly123",
        "项目管理平台"
    ]
    return _generate_template("web", "create", "网站服务导入模板", WEB_CREATE_FIELDS, example_data)


def generate_web_update_template() -> BytesIO:
    """Generate XLSX template for web application update"""
    example_data = [
        "56c4d4cd-42ba-4397-abfa-36ecba64af13", "Jira", "WB001", "研发部/应用系统",
        "https://jira.example.com",
        "http://192.168.1.100:8080",
        "admin:jiraadmin\nreadonly:readonly123",
        "项目管理平台"
    ]
    return _generate_template("web", "update", "网站服务更新模板", WEB_UPDATE_FIELDS, example_data)


# GPT templates
def generate_gpt_create_template() -> BytesIO:
    """Generate XLSX template for GPT/AI service creation"""
    example_data = [
        "OpenAI-API", "AI001", "研发部/AI 服务", "OpenAI",
        "https://api.openai.com/v1",
        "sk-key:sk-abc123xyz\nclue-key:sk-clue456",
        "AI 服务 API"
    ]
    return _generate_template("gpt", "create", "AI 服务导入模板", GPT_CREATE_FIELDS, example_data)


def generate_gpt_update_template() -> BytesIO:
    """Generate XLSX template for GPT/AI service update"""
    example_data = [
        "56c4d4cd-42ba-4397-abfa-36ecba64af13", "OpenAI-API", "AI001", "研发部/AI 服务", "OpenAI",
        "https://api.openai.com/v1",
        "sk-key:sk-abc123xyz\nclue-key:sk-clue456",
        "AI 服务 API"
    ]
    return _generate_template("gpt", "update", "AI 服务更新模板", GPT_UPDATE_FIELDS, example_data)


async def parse_import_file(
    file_content: bytes,
    category: str,
    mode: str,
    db: AsyncSession
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parse XLSX file and validate data
    Returns: (valid_records, error_records)
    """
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(file_content))
    ws = wb.active

    # Get field mapping based on category and mode
    field_maps = {
        "host": (HOST_CREATE_FIELDS, HOST_UPDATE_FIELDS),
        "network": (NETWORK_CREATE_FIELDS, NETWORK_UPDATE_FIELDS),
        "database": (DATABASE_CREATE_FIELDS, DATABASE_UPDATE_FIELDS),
        "cloud": (CLOUD_CREATE_FIELDS, CLOUD_UPDATE_FIELDS),
        "web": (WEB_CREATE_FIELDS, WEB_UPDATE_FIELDS),
        "gpt": (GPT_CREATE_FIELDS, GPT_UPDATE_FIELDS),
    }

    if category not in field_maps:
        raise ValueError(f"不支持的资产类型：{category}")

    create_fields, update_fields = field_maps[category]
    fields = create_fields if mode == "create" else update_fields

    valid_records = []
    error_records = []

    # Get organizations for name lookup
    org_result = await db.execute(select(Organization))
    organizations = org_result.scalars().all()
    org_name_map = {org.name: org.id for org in organizations}
    org_path_map = {org.path: org.id for org in organizations if org.path}

    # Build display path map (name-based hierarchy like "智昌集团/harvester" or "Default/智昌集团/harvester")
    # Also support " / " separator like frontend uses: "Default / 智昌集团 / harvester"
    org_display_path_map = {}
    id_to_name = {org.id: org.name for org in organizations}

    for org in organizations:
        if org.path:
            # Convert ID path "7/9" to name path "智昌集团/harvester"
            id_parts = org.path.split('/')
            name_parts = []
            for id_part in id_parts:
                if int(id_part) in id_to_name:
                    name_parts.append(id_to_name[int(id_part)])
            if name_parts:
                # Support both " / " and "/" separators
                display_path_with_space = ' / '.join(name_parts)
                display_path_without_space = '/'.join(name_parts)
                org_display_path_map[display_path_with_space] = org.id
                org_display_path_map[display_path_without_space] = org.id

                # Also add "Default/..." prefix versions (frontend shows Default as root)
                default_with_space = f'Default / {display_path_with_space}'
                default_without_space = f'Default/{display_path_without_space}'
                org_display_path_map[default_with_space] = org.id
                org_display_path_map[default_without_space] = org.id

        # Also map simple name
        org_display_path_map[org.name] = org.id

    # Skip header row, process data rows
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
        if not any(row):  # Skip empty rows
            continue

        record = {}
        errors = []

        for col, (field_name, label, required) in enumerate(fields, 1):
            value = row[col - 1] if col <= len(row) else None

            # Clean value
            if value is not None:
                value = str(value).strip() if value else None
                if value == '':
                    value = None

            # Required field validation
            if required and not value:
                errors.append(f"{label}为必填项")

            # Special handling for organization field
            if field_name == "organization" and value:
                # Try: display path (name-based like "智昌集团/harvester"), ID path (like "7/9"), then simple name
                org_id = org_display_path_map.get(value) or org_path_map.get(value) or org_name_map.get(value)
                if not org_id:
                    # Check if value looks like an asset code (e.g., NW00111, CI001) - user might have filled wrong column
                    import re
                    if re.match(r'^[A-Z]+\d+$', value):
                        errors.append(f"组织节点'{value}'不存在（提示：该值看起来像资产编号，请检查是否误填至节点列）")
                    else:
                        errors.append(f"组织节点'{value}'不存在")
                else:
                    record["organization_id"] = org_id

            # Special handling for credentials field (format: username:password, one per line)
            elif field_name == "credentials" and value:
                credentials_list = []
                for line in value.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    if ':' not in line:
                        errors.append("用户名密码格式应为：username:password，每行一个")
                        continue
                    # Split on first colon only
                    idx = line.index(':')
                    username = line[:idx].strip()
                    password = line[idx+1:].strip()
                    if username and password:
                        credentials_list.append({"username": username, "password": password})
                if credentials_list:
                    record["credentials"] = credentials_list

            # Map extra_data fields (oob related fields only)
            elif field_name in ["oob", "oob_username", "oob_password"]:
                if value:
                    if "extra_data" not in record:
                        record["extra_data"] = {}
                    record["extra_data"][field_name] = value
            elif field_name not in ["organization"]:
                # Field name is already clean
                # Convert id to string for UUID format (update mode)
                if field_name == "id" and value:
                    value = str(value).strip()
                    if not value:
                        errors.append("ID 不能为空")
                        value = None
                    elif mode == "update":
                        # Validate UUID format for update mode
                        import re
                        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        if not re.match(uuid_pattern, value.lower()):
                            errors.append(f"ID 格式无效：'{value}'，应为 UUID 格式（如：56c4d4cd-42ba-4397-abfa-36ecba64af13）")
                record[field_name] = value

        if errors:
            error_records.append({
                "row": row_num,
                "errors": errors,
                "data": {"name": record.get("name"), "id": record.get("id")}
            })
        else:
            valid_records.append(record)

    return valid_records, error_records


async def batch_create_hosts(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Batch create host assets
    Returns: (success_count, failed_records)
    """
    from app.models import Credential

    success_count = 0
    failed_records = []

    for record in records:
        try:
            # Check for duplicate name
            existing = await db.execute(
                select(Asset).where(
                    Asset.category == "host",
                    Asset.name == record["name"]
                )
            )
            if existing.scalar_one_or_none():
                failed_records.append({
                    "name": record.get("name"),
                    "error": f"资产名称'{record['name']}'已存在"
                })
                continue

            asset = Asset(
                name=record["name"],
                asset_code=record.get("asset_code"),
                category="host",
                platform=record.get("platform"),
                external_address=record.get("external_address"),
                internal_address=record.get("internal_address"),
                model=record.get("model"),
                serial_number=record.get("serial_number"),
                cpu=record.get("cpu"),
                memory=record.get("memory"),
                system_disk=record.get("system_disk"),
                data_disk=record.get("data_disk"),
                applicant=record.get("applicant"),
                organization_id=record.get("organization_id"),
                notes=record.get("notes"),
                extra_data=record.get("extra_data"),
            )
            db.add(asset)
            await db.flush()  # Get asset ID

            # Handle is_active (status)
            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            # Create credentials if provided
            if record.get("credentials"):
                for cred in record["credentials"]:
                    credential = Credential(
                        asset_id=asset.id,
                        username=cred["username"],
                        password_encrypted=encrypt_value(cred["password"]),
                        credential_type="password"
                    )
                    db.add(credential)

            success_count += 1
        except Exception as e:
            failed_records.append({
                "name": record.get("name"),
                "error": str(e)
            })

    if success_count > 0:
        await db.commit()

    return success_count, failed_records


async def batch_create_networks(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Batch create network assets
    Returns: (success_count, failed_records)
    """
    from app.models import Credential

    success_count = 0
    failed_records = []

    for record in records:
        try:
            # Check for duplicate name
            existing = await db.execute(
                select(Asset).where(
                    Asset.category == "network",
                    Asset.name == record["name"]
                )
            )
            if existing.scalar_one_or_none():
                failed_records.append({
                    "name": record.get("name"),
                    "error": f"资产名称'{record['name']}'已存在"
                })
                continue

            # Parse is_active field (support Chinese: 启用/禁用，and True/False, 1/0)
            is_active = record.get("is_active", True)
            if isinstance(is_active, str):
                is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
            elif isinstance(is_active, bool):
                pass
            elif isinstance(is_active, (int, float)):
                is_active = bool(is_active)
            else:
                is_active = True

            asset = Asset(
                name=record["name"],
                asset_code=record.get("asset_code"),
                category="network",
                device_type=record.get("device_type"),
                vendor=record.get("vendor"),
                model=record.get("model"),
                serial_number=record.get("serial_number"),
                external_address=record.get("external_address"),
                internal_address=record.get("internal_address"),
                applicant=record.get("applicant"),
                organization_id=record.get("organization_id"),
                notes=record.get("notes"),
                is_active=is_active,
            )
            db.add(asset)
            await db.flush()  # Get asset ID

            # Create credentials if provided
            if record.get("credentials"):
                for cred in record["credentials"]:
                    credential = Credential(
                        asset_id=asset.id,
                        username=cred["username"],
                        password_encrypted=encrypt_value(cred["password"]),
                        credential_type="password"
                    )
                    db.add(credential)

            success_count += 1
        except Exception as e:
            failed_records.append({
                "name": record.get("name"),
                "error": str(e)
            })

    if success_count > 0:
        await db.commit()

    return success_count, failed_records


async def batch_update_networks(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Batch update network assets by ID
    Returns: (success_count, failed_records)
    """
    from app.models import Credential
    from sqlalchemy import delete

    success_count = 0
    failed_records = []

    for record in records:
        try:
            result = await db.execute(
                select(Asset).where(Asset.id == record["id"])
            )
            asset = result.scalar_one_or_none()

            if not asset:
                failed_records.append({
                    "id": record.get("id"),
                    "error": "资产不存在"
                })
                continue

            # Update fields
            for field in ["name", "asset_code", "device_type", "vendor", "model",
                          "serial_number", "external_address", "internal_address", "applicant", "notes"]:
                if record.get(field):
                    setattr(asset, field, record[field])

            if record.get("organization_id"):
                asset.organization_id = record["organization_id"]

            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    # Support Chinese: 启用/禁用，is/否，and True/False, 1/0, yes/no
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            # Handle credentials update
            if "credentials" in record:
                await db.execute(
                    delete(Credential).where(Credential.asset_id == asset.id)
                )
                if record["credentials"]:
                    for cred in record["credentials"]:
                        credential = Credential(
                            asset_id=asset.id,
                            username=cred["username"],
                            password_encrypted=encrypt_value(cred["password"]),
                            credential_type="password"
                        )
                        db.add(credential)

            success_count += 1
        except Exception as e:
            failed_records.append({
                "id": record.get("id"),
                "error": str(e)
            })

    if success_count > 0:
        await db.commit()

    return success_count, failed_records


# Database batch operations
async def batch_create_databases(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    from app.models import Credential

    success_count = 0
    failed_records = []

    for record in records:
        try:
            # Check for duplicate name
            existing = await db.execute(
                select(Asset).where(
                    Asset.category == "database",
                    Asset.name == record["name"]
                )
            )
            if existing.scalar_one_or_none():
                failed_records.append({
                    "name": record.get("name"),
                    "error": f"资产名称'{record['name']}'已存在"
                })
                continue

            asset = Asset(
                name=record["name"],
                asset_code=record.get("asset_code"),
                category="database",
                platform=record.get("platform"),
                external_address=record.get("external_address"),
                internal_address=record.get("internal_address"),
                applicant=record.get("applicant"),
                organization_id=record.get("organization_id"),
                notes=record.get("notes"),
                extra_data={
                    k: v for k, v in {
                        "version": record.get("version"),
                        "namespace": record.get("namespace")
                    }.items() if v
                } if record.get("version") or record.get("namespace") else None,
            )
            db.add(asset)
            await db.flush()

            # Handle is_active (status)
            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            if record.get("credentials"):
                for cred in record["credentials"]:
                    credential = Credential(
                        asset_id=asset.id,
                        username=cred["username"],
                        password_encrypted=encrypt_value(cred["password"]),
                        credential_type="password"
                    )
                    db.add(credential)

            success_count += 1
        except Exception as e:
            failed_records.append({"name": record.get("name"), "error": str(e)})

    if success_count > 0:
        await db.commit()
    return success_count, failed_records


async def batch_update_databases(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    from app.models import Credential
    from sqlalchemy import delete

    success_count = 0
    failed_records = []

    for record in records:
        try:
            result = await db.execute(select(Asset).where(Asset.id == record["id"]))
            asset = result.scalar_one_or_none()
            if not asset:
                failed_records.append({"id": record.get("id"), "error": "资产不存在"})
                continue

            for field in ["name", "asset_code", "platform", "external_address", "internal_address", "applicant", "notes"]:
                if record.get(field):
                    setattr(asset, field, record[field])

            if record.get("organization_id"):
                asset.organization_id = record["organization_id"]

            # Handle is_active (status)
            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            # Handle namespace and version in extra_data
            if record.get("version") or record.get("namespace"):
                current_extra = asset.extra_data or {}
                updates = {}
                if record.get("version"):
                    updates["version"] = record["version"]
                if record.get("namespace"):
                    updates["namespace"] = record["namespace"]
                asset.extra_data = {**current_extra, **updates}

            if "credentials" in record:
                await db.execute(delete(Credential).where(Credential.asset_id == asset.id))
                if record["credentials"]:
                    for cred in record["credentials"]:
                        db.add(Credential(
                            asset_id=asset.id,
                            username=cred["username"],
                            password_encrypted=encrypt_value(cred["password"]),
                            credential_type="password"
                        ))

            success_count += 1
        except Exception as e:
            failed_records.append({"id": record.get("id"), "error": str(e)})

    if success_count > 0:
        await db.commit()
    return success_count, failed_records


# Cloud batch operations
async def batch_create_clouds(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    from app.models import Credential

    success_count = 0
    failed_records = []

    for record in records:
        try:
            # Check for duplicate name
            existing = await db.execute(
                select(Asset).where(
                    Asset.category == "cloud",
                    Asset.name == record["name"]
                )
            )
            if existing.scalar_one_or_none():
                failed_records.append({
                    "name": record.get("name"),
                    "error": f"资产名称'{record['name']}'已存在"
                })
                continue

            asset = Asset(
                name=record["name"],
                asset_code=record.get("asset_code"),
                category="cloud",
                platform=record.get("platform"),
                external_address=record.get("external_address"),
                internal_address=record.get("internal_address"),
                applicant=record.get("applicant"),
                organization_id=record.get("organization_id"),
                notes=record.get("notes"),
                extra_data={
                    k: v for k, v in {
                        "resource_id": record.get("resource_id"),
                        "region": record.get("region")
                    }.items() if v
                } if record.get("resource_id") or record.get("region") else None,
            )
            db.add(asset)
            await db.flush()

            # Handle is_active (status)
            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            if record.get("credentials"):
                for cred in record["credentials"]:
                    credential = Credential(
                        asset_id=asset.id,
                        username=cred["username"],  # AKID/SecretId
                        password_encrypted=encrypt_value(cred["password"]),  # Secret/SecretKey
                        credential_type="api_key"
                    )
                    db.add(credential)

            success_count += 1
        except Exception as e:
            failed_records.append({"name": record.get("name"), "error": str(e)})

    if success_count > 0:
        await db.commit()
    return success_count, failed_records


async def batch_update_clouds(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    from app.models import Credential
    from sqlalchemy import delete

    success_count = 0
    failed_records = []

    for record in records:
        try:
            result = await db.execute(select(Asset).where(Asset.id == record["id"]))
            asset = result.scalar_one_or_none()
            if not asset:
                failed_records.append({"id": record.get("id"), "error": "资产不存在"})
                continue

            for field in ["name", "asset_code", "platform", "external_address", "internal_address", "applicant", "notes"]:
                if record.get(field):
                    setattr(asset, field, record[field])

            if record.get("organization_id"):
                asset.organization_id = record["organization_id"]

            # Handle is_active (status)
            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            if record.get("resource_id") or record.get("region"):
                current_extra = asset.extra_data or {}
                updates = {}
                if record.get("resource_id"):
                    updates["resource_id"] = record["resource_id"]
                if record.get("region"):
                    updates["region"] = record["region"]
                asset.extra_data = {**current_extra, **updates}

            if "credentials" in record:
                await db.execute(delete(Credential).where(Credential.asset_id == asset.id))
                if record["credentials"]:
                    for cred in record["credentials"]:
                        db.add(Credential(
                            asset_id=asset.id,
                            username=cred["username"],
                            password_encrypted=encrypt_value(cred["password"]),
                            credential_type="api_key"
                        ))

            success_count += 1
        except Exception as e:
            failed_records.append({"id": record.get("id"), "error": str(e)})

    if success_count > 0:
        await db.commit()
    return success_count, failed_records


# Web batch operations
async def batch_create_webs(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    from app.models import Credential

    success_count = 0
    failed_records = []

    for record in records:
        try:
            # Check for duplicate name
            existing = await db.execute(
                select(Asset).where(
                    Asset.category == "web",
                    Asset.name == record["name"]
                )
            )
            if existing.scalar_one_or_none():
                failed_records.append({
                    "name": record.get("name"),
                    "error": f"资产名称'{record['name']}'已存在"
                })
                continue

            asset = Asset(
                name=record["name"],
                asset_code=record.get("asset_code"),
                category="web",
                external_address=record.get("external_address"),
                internal_address=record.get("internal_address"),
                applicant=record.get("applicant"),
                organization_id=record.get("organization_id"),
                notes=record.get("notes"),
            )
            db.add(asset)
            await db.flush()

            # Handle is_active (status)
            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            if record.get("credentials"):
                for cred in record["credentials"]:
                    credential = Credential(
                        asset_id=asset.id,
                        username=cred["username"],
                        password_encrypted=encrypt_value(cred["password"]),
                        credential_type="password"
                    )
                    db.add(credential)

            success_count += 1
        except Exception as e:
            failed_records.append({"name": record.get("name"), "error": str(e)})

    if success_count > 0:
        await db.commit()
    return success_count, failed_records


async def batch_update_webs(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    from app.models import Credential
    from sqlalchemy import delete

    success_count = 0
    failed_records = []

    for record in records:
        try:
            result = await db.execute(select(Asset).where(Asset.id == record["id"]))
            asset = result.scalar_one_or_none()
            if not asset:
                failed_records.append({"id": record.get("id"), "error": "资产不存在"})
                continue

            for field in ["name", "asset_code", "external_address", "internal_address", "applicant", "notes"]:
                if record.get(field):
                    setattr(asset, field, record[field])

            if record.get("organization_id"):
                asset.organization_id = record["organization_id"]

            # Handle is_active (status)
            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            if "credentials" in record:
                await db.execute(delete(Credential).where(Credential.asset_id == asset.id))
                if record["credentials"]:
                    for cred in record["credentials"]:
                        db.add(Credential(
                            asset_id=asset.id,
                            username=cred["username"],
                            password_encrypted=encrypt_value(cred["password"]),
                            credential_type="password"
                        ))

            success_count += 1
        except Exception as e:
            failed_records.append({"id": record.get("id"), "error": str(e)})

    if success_count > 0:
        await db.commit()
    return success_count, failed_records


# GPT batch operations
async def batch_create_gpts(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    from app.models import Credential

    success_count = 0
    failed_records = []

    for record in records:
        try:
            # Check for duplicate name
            existing = await db.execute(
                select(Asset).where(
                    Asset.category == "gpt",
                    Asset.name == record["name"]
                )
            )
            if existing.scalar_one_or_none():
                failed_records.append({
                    "name": record.get("name"),
                    "error": f"资产名称'{record['name']}'已存在"
                })
                continue

            asset = Asset(
                name=record["name"],
                asset_code=record.get("asset_code"),
                category="gpt",
                platform=record.get("platform"),
                external_address=record.get("external_address"),
                internal_address=record.get("internal_address"),
                applicant=record.get("applicant"),
                organization_id=record.get("organization_id"),
                notes=record.get("notes"),
            )
            db.add(asset)
            await db.flush()

            # Handle is_active (status)
            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            if record.get("credentials"):
                for cred in record["credentials"]:
                    credential = Credential(
                        asset_id=asset.id,
                        username=cred["username"],  # API key name/label
                        password_encrypted=encrypt_value(cred["password"]),  # API key value
                        credential_type="api_key"
                    )
                    db.add(credential)

            success_count += 1
        except Exception as e:
            failed_records.append({"name": record.get("name"), "error": str(e)})

    if success_count > 0:
        await db.commit()
    return success_count, failed_records


async def batch_update_gpts(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    from app.models import Credential
    from sqlalchemy import delete

    success_count = 0
    failed_records = []

    for record in records:
        try:
            result = await db.execute(select(Asset).where(Asset.id == record["id"]))
            asset = result.scalar_one_or_none()
            if not asset:
                failed_records.append({"id": record.get("id"), "error": "资产不存在"})
                continue

            for field in ["name", "asset_code", "platform", "external_address", "internal_address", "applicant", "notes"]:
                if record.get(field):
                    setattr(asset, field, record[field])

            if record.get("organization_id"):
                asset.organization_id = record["organization_id"]

            # Handle is_active (status)
            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            if "credentials" in record:
                await db.execute(delete(Credential).where(Credential.asset_id == asset.id))
                if record["credentials"]:
                    for cred in record["credentials"]:
                        db.add(Credential(
                            asset_id=asset.id,
                            username=cred["username"],
                            password_encrypted=encrypt_value(cred["password"]),
                            credential_type="api_key"
                        ))

            success_count += 1
        except Exception as e:
            failed_records.append({"id": record.get("id"), "error": str(e)})

    if success_count > 0:
        await db.commit()
    return success_count, failed_records


async def batch_update_hosts(
    records: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Batch update host assets by ID
    Returns: (success_count, failed_records)
    """
    from app.models import Credential
    from sqlalchemy import delete

    success_count = 0
    failed_records = []

    for record in records:
        try:
            result = await db.execute(
                select(Asset).where(Asset.id == record["id"])
            )
            asset = result.scalar_one_or_none()

            if not asset:
                failed_records.append({
                    "id": record.get("id"),
                    "error": "资产不存在"
                })
                continue

            # Update fields (only non-null values)
            for field in ["name", "asset_code", "platform", "external_address",
                          "internal_address", "model", "serial_number", "cpu", "memory",
                          "system_disk", "data_disk", "applicant", "notes"]:
                if record.get(field):
                    setattr(asset, field, record[field])

            if record.get("organization_id"):
                asset.organization_id = record["organization_id"]

            # Handle is_active (status)
            if record.get("is_active") is not None:
                is_active = record["is_active"]
                if isinstance(is_active, str):
                    is_active = is_active.lower().strip() in ("true", "1", "yes", "启用", "是")
                elif isinstance(is_active, bool):
                    pass
                elif isinstance(is_active, (int, float)):
                    is_active = bool(is_active)
                asset.is_active = is_active

            if record.get("extra_data"):
                # Merge extra_data
                current_extra = asset.extra_data or {}
                asset.extra_data = {**current_extra, **record["extra_data"]}

            # Handle credentials update (replace all)
            if "credentials" in record:
                # Delete existing credentials
                await db.execute(
                    delete(Credential).where(Credential.asset_id == asset.id)
                )
                # Create new credentials
                if record["credentials"]:
                    for cred in record["credentials"]:
                        credential = Credential(
                            asset_id=asset.id,
                            username=cred["username"],
                            password_encrypted=encrypt_value(cred["password"]),
                            credential_type="password"
                        )
                        db.add(credential)

            success_count += 1
        except Exception as e:
            failed_records.append({
                "id": record.get("id"),
                "error": str(e)
            })

    if success_count > 0:
        await db.commit()

    return success_count, failed_records
