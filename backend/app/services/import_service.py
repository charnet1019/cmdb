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
    ("credentials", "用户名密码", False),  # 格式：username:password，每行一个
    ("notes", "描述", False),
]


def generate_host_create_template() -> BytesIO:
    """Generate XLSX template for host creation"""
    wb = Workbook()
    ws = wb.active
    ws.title = "主机导入模板"

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
    for col, (field_name, label, required) in enumerate(HOST_CREATE_FIELDS, 1):
        cell = ws.cell(row=1, column=col, value=label)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = header_border

    # Example row
    example_data = [
        "test-server-01", "CI001", "研发部/服务器组", "Linux",
        "192.168.1.100", "10.0.0.100", "Dell R740",
        "SN123456", "8 核", "16GB", "500GB SSD", "2TB HDD",
        "192.168.1.100", "admin", "password", "张三",
        "admin:password123\nroot:rootpass",
        "测试服务器"
    ]
    for col, value in enumerate(example_data, 1):
        cell = ws.cell(row=2, column=col, value=value)
        cell.alignment = Alignment(horizontal="left", vertical="center")
        cell.border = Border(
            left=Side(style='thin', color='E7E6E6'),
            right=Side(style='thin', color='E7E6E6'),
            top=Side(style='thin', color='E7E6E6'),
            bottom=Side(style='thin', color='E7E6E6')
        )

    # Column widths
    column_widths = [15, 12, 18, 12, 18, 18, 15, 15, 10, 10, 12, 12, 15, 12, 12, 12, 15, 20]
    for idx, width in enumerate(column_widths, 1):
        col_letter = ws.cell(row=1, column=idx).column_letter
        ws.column_dimensions[col_letter].width = width

    # Set row height
    ws.row_dimensions[1].height = 25
    ws.row_dimensions[2].height = 20

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_host_update_template() -> BytesIO:
    """Generate XLSX template for host update"""
    wb = Workbook()
    ws = wb.active
    ws.title = "主机更新模板"

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
    for col, (field_name, label, required) in enumerate(HOST_UPDATE_FIELDS, 1):
        cell = ws.cell(row=1, column=col, value=label)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = header_border

    # Example row
    example_data = [
        "1", "test-server-01", "CI001", "研发部/服务器组", "Linux",
        "192.168.1.100", "10.0.0.100", "Dell R740",
        "SN123456", "8 核", "16GB", "500GB SSD", "2TB HDD",
        "192.168.1.100", "admin", "password", "张三",
        "admin:password123\nroot:rootpass",
        "测试服务器"
    ]
    for col, value in enumerate(example_data, 1):
        cell = ws.cell(row=2, column=col, value=value)
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.border = Border(
            left=Side(style='thin', color='E7E6E6'),
            right=Side(style='thin', color='E7E6E6'),
            top=Side(style='thin', color='E7E6E6'),
            bottom=Side(style='thin', color='E7E6E6')
        )

    # Column widths
    column_widths = [8, 15, 12, 18, 12, 18, 18, 15, 15, 10, 10, 12, 12, 15, 12, 12, 12, 15, 20]
    for idx, width in enumerate(column_widths, 1):
        col_letter = ws.cell(row=1, column=idx).column_letter
        ws.column_dimensions[col_letter].width = width

    # Set row height
    ws.row_dimensions[1].height = 25
    ws.row_dimensions[2].height = 20

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


async def parse_import_file(
    file_content: bytes,
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

    # Get field mapping based on mode
    fields = HOST_CREATE_FIELDS if mode == "create" else HOST_UPDATE_FIELDS

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

            # Map extra_data fields
            elif field_name in ["oob", "oob_username", "oob_password", "applicant"]:
                if value:
                    if "extra_data" not in record:
                        record["extra_data"] = {}
                    record["extra_data"][field_name] = value
            elif field_name not in ["organization"]:
                # Field name is already clean
                # Convert id to int for update mode
                if field_name == "id" and value:
                    try:
                        value = int(float(value))
                    except (ValueError, TypeError):
                        errors.append("ID必须为数字")
                        value = None
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
                organization_id=record.get("organization_id"),
                notes=record.get("notes"),
                extra_data=record.get("extra_data"),
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
                          "system_disk", "data_disk", "notes"]:
                if record.get(field):
                    setattr(asset, field, record[field])

            if record.get("organization_id"):
                asset.organization_id = record["organization_id"]

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
