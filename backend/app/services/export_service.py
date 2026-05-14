"""
Asset Export Service
Handles Excel and CSV export functionality
"""
from io import BytesIO
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


# Column definitions for export by asset category
# Each category exports only its relevant fields
CATEGORY_COLUMNS: Dict[str, List[tuple]] = {
    "host": [
        ("id", "ID"),
        ("name", "资产名称"),
        ("asset_code", "资产编号"),
        ("internal_address", "内网地址"),
        ("external_address", "外网地址"),
        ("platform", "平台"),
        ("organization_name", "节点"),
        ("model", "型号"),
        ("serial_number", "序列号"),
        ("cpu", "CPU"),
        ("memory", "内存"),
        ("system_disk", "系统盘"),
        ("data_disk", "数据盘"),
        ("credentials", "用户名密码"),
        ("oob", "OOB 地址"),
        ("oob_username", "OOB 用户名"),
        ("oob_password", "OOB 密码"),
        ("applicant", "申请人"),
        ("notes", "描述"),
        ("is_active", "状态"),
        ("created_at", "创建时间"),
        ("updated_at", "更新时间"),
    ],
    "network": [
        ("id", "ID"),
        ("name", "资产名称"),
        ("asset_code", "资产编号"),
        ("internal_address", "内网地址"),
        ("external_address", "外网地址"),
        ("device_type", "设备类型"),
        ("vendor", "厂商"),
        ("model", "型号"),
        ("serial_number", "序列号"),
        ("organization_name", "节点"),
        ("credentials", "用户名密码"),
        ("notes", "描述"),
        ("is_active", "状态"),
        ("created_at", "创建时间"),
        ("updated_at", "更新时间"),
    ],
    "database": [
        ("id", "ID"),
        ("name", "资产名称"),
        ("asset_code", "资产编号"),
        ("internal_address", "内网地址"),
        ("external_address", "外网地址"),
        ("platform", "平台"),
        ("db_type", "数据库类型"),
        ("version", "版本"),
        ("namespace", "命名空间"),
        ("organization_name", "节点"),
        ("applicant", "申请人"),
        ("credentials", "用户名密码"),
        ("notes", "描述"),
        ("is_active", "状态"),
        ("created_at", "创建时间"),
        ("updated_at", "更新时间"),
    ],
    "cloud": [
        ("id", "ID"),
        ("name", "资产名称"),
        ("asset_code", "资产编号"),
        ("internal_address", "内网地址"),
        ("external_address", "外网地址"),
        ("platform", "平台"),
        ("organization_name", "节点"),
        ("credentials", "用户名密码"),
        ("notes", "描述"),
        ("is_active", "状态"),
        ("created_at", "创建时间"),
        ("updated_at", "更新时间"),
    ],
    "web": [
        ("id", "ID"),
        ("name", "资产名称"),
        ("asset_code", "资产编号"),
        ("internal_address", "内网地址"),
        ("external_address", "外网地址"),
        ("platform", "平台"),
        ("organization_name", "节点"),
        ("applicant", "申请人"),
        ("credentials", "用户名密码"),
        ("notes", "描述"),
        ("is_active", "状态"),
        ("created_at", "创建时间"),
        ("updated_at", "更新时间"),
    ],
    "gpt": [
        ("id", "ID"),
        ("name", "资产名称"),
        ("asset_code", "资产编号"),
        ("internal_address", "内网地址"),
        ("external_address", "外网地址"),
        ("platform", "平台"),
        ("organization_name", "节点"),
        ("credentials", "用户名密码"),
        ("notes", "描述"),
        ("is_active", "状态"),
        ("created_at", "创建时间"),
        ("updated_at", "更新时间"),
    ],
}

# Default columns for mixed exports (all categories)
DEFAULT_COLUMNS = [
    ("id", "ID"),
    ("name", "资产名称"),
    ("asset_code", "资产编号"),
    ("category", "资产类型"),
    ("internal_address", "内网地址"),
    ("external_address", "外网地址"),
    ("platform", "平台"),
    ("organization_name", "节点"),
    ("device_type", "设备类型"),
    ("vendor", "厂商"),
    ("db_type", "数据库类型"),
    ("model", "型号"),
    ("serial_number", "序列号"),
    ("cpu", "CPU"),
    ("memory", "内存"),
    ("system_disk", "系统盘"),
    ("data_disk", "数据盘"),
    ("credentials", "用户名密码"),
    ("oob", "OOB 地址"),
    ("oob_username", "OOB 用户名"),
    ("oob_password", "OOB 密码"),
    ("applicant", "申请人"),
    ("notes", "描述"),
    ("is_active", "状态"),
    ("created_at", "创建时间"),
    ("updated_at", "更新时间"),
]

# UTC+8 timezone offset
UTC8_OFFSET_HOURS = 8

CATEGORY_LABELS = {
    "host": "主机",
    "network": "网络设备",
    "database": "数据库",
    "cloud": "云服务",
    "web": "Web 应用",
    "gpt": "GPT 服务",
}


def export_assets_to_excel(data: List[Dict[str, Any]], category: Optional[str] = None) -> BytesIO:
    """
    Export assets to Excel format

    Args:
        data: List of asset dictionaries
        category: Asset category (host/network/database/cloud/web/gpt). If None, uses all columns.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "资产导出"

    # Determine columns based on category
    if category and category in CATEGORY_COLUMNS:
        export_columns = CATEGORY_COLUMNS[category]
    else:
        export_columns = DEFAULT_COLUMNS

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
    for col, (field, label) in enumerate(export_columns, 1):
        cell = ws.cell(row=1, column=col, value=label)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = header_border

    # Write data rows
    cell_border = Border(
        left=Side(style='thin', color='E7E6E6'),
        right=Side(style='thin', color='E7E6E6'),
        top=Side(style='thin', color='E7E6E6'),
        bottom=Side(style='thin', color='E7E6E6')
    )

    for row_idx, asset in enumerate(data, 2):
        for col_idx, (field, _) in enumerate(export_columns, 1):
            value = asset.get(field)

            # Format specific fields
            if field == "category" and value:
                value = CATEGORY_LABELS.get(value, value)
            elif field == "is_active":
                value = "启用" if value else "禁用"
            elif field == "vendor" and value is None:
                # If vendor is empty, use platform value (for host/database assets)
                value = asset.get("platform")
            elif field in ["created_at", "updated_at"] and value:
                # Convert to UTC+8 and format as "年 - 月-日 时：分:秒"
                if isinstance(value, datetime):
                    # If naive datetime, assume UTC and add 8 hours
                    if value.tzinfo is None:
                        value = value + timedelta(hours=UTC8_OFFSET_HOURS)
                    else:
                        # Convert to UTC+8
                        value = value.astimezone(timezone(timedelta(hours=UTC8_OFFSET_HOURS)))
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(value, str):
                    # Parse ISO format string and convert
                    try:
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        if dt.tzinfo is None:
                            dt = dt + timedelta(hours=UTC8_OFFSET_HOURS)
                        else:
                            dt = dt.astimezone(timezone(timedelta(hours=UTC8_OFFSET_HOURS)))
                        value = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        value = str(value)
            elif field == "credentials":
                # Join multiple credentials as "username:password" lines
                creds = asset.get("credentials", [])
                if creds:
                    value = "\n".join([f"{c.get('username')}:{c.get('password', '')}" for c in creds if c.get('username')])
                else:
                    value = ""
            elif field in ["oob", "oob_username", "oob_password", "version"]:
                # Extract from extra_data (metadata)
                extra_data = asset.get("extra_data") or {}
                value = extra_data.get(field)
            elif field == "extra_data":
                # Skip extra_data as it's JSON
                continue

            cell = ws.cell(row=row_idx, column=col_idx, value=value if value else "")
            cell.border = cell_border
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # Column widths
    column_widths = {
        "id": 10,
        "name": 20,
        "asset_code": 15,
        "category": 12,
        "internal_address": 20,
        "external_address": 20,
        "organization_name": 20,
        "device_type": 12,
        "vendor": 15,
        "model": 20,
        "serial_number": 20,
        "cpu": 12,
        "memory": 12,
        "system_disk": 15,
        "data_disk": 15,
        "credentials": 25,
        "oob": 20,
        "oob_username": 15,
        "oob_password": 15,
        "applicant": 12,
        "notes": 30,
        "is_active": 10,
        "created_at": 20,
        "updated_at": 20,
    }

    for col_idx, (field, _) in enumerate(export_columns, 1):
        col_letter = ws.cell(row=1, column=col_idx).column_letter
        ws.column_dimensions[col_letter].width = column_widths.get(field, 15)

    # Set row height
    ws.row_dimensions[1].height = 25

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def export_assets_to_csv(data: List[Dict[str, Any]], category: Optional[str] = None) -> BytesIO:
    """
    Export assets to CSV format

    Args:
        data: List of asset dictionaries
        category: Asset category (host/network/database/cloud/web/gpt). If None, uses all columns.
    """
    buffer = BytesIO()

    # Determine columns based on category
    if category and category in CATEGORY_COLUMNS:
        export_columns = CATEGORY_COLUMNS[category]
    else:
        export_columns = DEFAULT_COLUMNS

    writer = csv.writer(buffer, lineterminator='\n')

    # Write header
    header = [label for _, label in export_columns]
    writer.writerow(header)

    # Write data
    for asset in data:
        row = []
        for field, _ in export_columns:
            value = asset.get(field)

            # Format specific fields
            if field == "category" and value:
                value = CATEGORY_LABELS.get(value, value)
            elif field == "is_active":
                value = "启用" if value else "禁用"
            elif field == "vendor" and value is None:
                # If vendor is empty, use platform value (for host/database assets)
                value = asset.get("platform")
            elif field in ["created_at", "updated_at"] and value:
                # Convert to UTC+8 and format as "年 - 月-日 时：分:秒"
                if isinstance(value, datetime):
                    # If naive datetime, assume UTC and add 8 hours
                    if value.tzinfo is None:
                        value = value + timedelta(hours=UTC8_OFFSET_HOURS)
                    else:
                        # Convert to UTC+8
                        value = value.astimezone(timezone(timedelta(hours=UTC8_OFFSET_HOURS)))
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(value, str):
                    # Parse ISO format string and convert
                    try:
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        if dt.tzinfo is None:
                            dt = dt + timedelta(hours=UTC8_OFFSET_HOURS)
                        else:
                            dt = dt.astimezone(timezone(timedelta(hours=UTC8_OFFSET_HOURS)))
                        value = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        value = str(value)
            elif field == "credentials":
                # Join multiple credentials as "username:password" lines
                creds = asset.get("credentials", [])
                if creds:
                    value = "\n".join([f"{c.get('username')}:{c.get('password', '')}" for c in creds if c.get('username')])
                else:
                    value = ""
            elif field in ["oob", "oob_username", "oob_password", "version"]:
                # Extract from extra_data (metadata)
                extra_data = asset.get("extra_data") or {}
                value = extra_data.get(field)
            elif field == "extra_data":
                value = ""

            row.append(value if value else "")
        writer.writerow(row)

    # Add BOM for Excel compatibility with Chinese characters
    buffer.seek(0)
    content = b'\xef\xbb\xbf' + buffer.read()
    buffer = BytesIO(content)
    return buffer
