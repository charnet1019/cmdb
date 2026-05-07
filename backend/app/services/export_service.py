"""
Asset Export Service
Handles Excel and CSV export functionality
"""
from io import BytesIO
import csv
from typing import List, Dict, Any
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


# Column definitions for export
EXPORT_COLUMNS = [
    ("id", "ID"),
    ("name", "资产名称"),
    ("asset_code", "资产编号"),
    ("category", "资产类型"),
    ("address", "地址"),
    ("internal_address", "内网地址"),
    ("external_address", "外网地址"),
    ("platform", "平台"),
    ("organization_name", "节点"),
    ("device_type", "设备类型"),
    ("vendor", "厂商"),
    ("model", "型号"),
    ("serial_number", "序列号"),
    ("cpu", "CPU"),
    ("memory", "内存"),
    ("system_disk", "系统盘"),
    ("data_disk", "数据盘"),
    ("url", "URL"),  # Legacy field
    ("external_url", "外网 URL"),
    ("internal_url", "内网 URL"),
    ("credentials", "用户名密码"),  # Multiple credentials joined by newlines
    ("oob", "OOB 地址"),
    ("oob_username", "OOB 用户名"),
    ("oob_password", "OOB 密码"),
    ("applicant", "申请人"),
    ("notes", "描述"),
    ("is_active", "状态"),
    ("created_at", "创建时间"),
]

CATEGORY_LABELS = {
    "host": "主机",
    "network": "网络设备",
    "database": "数据库",
    "cloud": "云服务",
    "web": "Web 应用",
    "gpt": "GPT 服务",
}


def export_assets_to_excel(data: List[Dict[str, Any]]) -> BytesIO:
    """
    Export assets to Excel format
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "资产导出"

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
    for col, (field, label) in enumerate(EXPORT_COLUMNS, 1):
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
        for col_idx, (field, _) in enumerate(EXPORT_COLUMNS, 1):
            value = asset.get(field)

            # Format specific fields
            if field == "category" and value:
                value = CATEGORY_LABELS.get(value, value)
            elif field == "is_active":
                value = "启用" if value else "禁用"
            elif field == "created_at" and value:
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    value = str(value)
            elif field == "credentials":
                # Join multiple credentials as "username:password" lines
                creds = asset.get("credentials", [])
                if creds:
                    value = "\n".join([f"{c.get('username')}:{c.get('password', '')}" for c in creds if c.get('username')])
                else:
                    value = ""
            elif field in ["oob", "oob_username", "oob_password", "applicant"]:
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
        "address": 20,
        "internal_address": 20,
        "external_address": 20,
        "platform": 15,
        "organization_name": 20,
        "device_type": 12,
        "vendor": 15,
        "model": 20,
        "serial_number": 20,
        "cpu": 12,
        "memory": 12,
        "system_disk": 15,
        "data_disk": 15,
        "url": 30,
        "external_url": 40,
        "internal_url": 40,
        "credentials": 25,
        "oob": 20,
        "oob_username": 15,
        "oob_password": 15,
        "applicant": 12,
        "notes": 30,
        "is_active": 10,
        "created_at": 20,
    }

    for col_idx, (field, _) in enumerate(EXPORT_COLUMNS, 1):
        col_letter = ws.cell(row=1, column=col_idx).column_letter
        ws.column_dimensions[col_letter].width = column_widths.get(field, 15)

    # Set row height
    ws.row_dimensions[1].height = 25

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def export_assets_to_csv(data: List[Dict[str, Any]]) -> BytesIO:
    """
    Export assets to CSV format
    """
    buffer = BytesIO()

    # Add BOM for Excel compatibility with Chinese characters
    buffer.write(b'\xef\xbb\xbf')

    writer = csv.writer(buffer, lineterminator='\n')

    # Write header
    header = [label for _, label in EXPORT_COLUMNS]
    writer.writerow(header)

    # Write data
    for asset in data:
        row = []
        for field, _ in EXPORT_COLUMNS:
            value = asset.get(field)

            # Format specific fields
            if field == "category" and value:
                value = CATEGORY_LABELS.get(value, value)
            elif field == "is_active":
                value = "启用" if value else "禁用"
            elif field == "created_at" and value:
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    value = str(value)
            elif field == "credentials":
                # Join multiple credentials as "username:password" lines
                creds = asset.get("credentials", [])
                if creds:
                    value = "\n".join([f"{c.get('username')}:{c.get('password', '')}" for c in creds if c.get('username')])
                else:
                    value = ""
            elif field in ["oob", "oob_username", "oob_password", "applicant"]:
                # Extract from extra_data (metadata)
                extra_data = asset.get("extra_data") or {}
                value = extra_data.get(field)
            elif field == "extra_data":
                value = ""

            row.append(value if value else "")
        writer.writerow(row)

    buffer.seek(0)
    return buffer
