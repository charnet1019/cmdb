"""Shared asset category label mapping."""
from typing import Optional

ASSET_CATEGORY_LABELS = {
    "host": "主机",
    "network": "网络设备",
    "database": "数据库",
    "cloud": "云服务",
    "web": "网站服务",
    "gpt": "AI服务",
}


def asset_category_label(category: Optional[str]) -> str:
    return ASSET_CATEGORY_LABELS.get(category or "", category or "全部")
