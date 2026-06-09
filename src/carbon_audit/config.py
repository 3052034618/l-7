"""项目配置管理"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class OrgUnit:
    """组织单元"""
    id: str
    name: str
    parent: Optional[str] = None
    description: str = ""


@dataclass
class ProjectConfig:
    """项目配置"""
    name: str
    reporting_year: int
    base_year: Optional[int] = None
    description: str = ""
    language: str = "zh"
    unit: str = "tCO2e"
    electricity_region: str = "national"
    org_units: List[OrgUnit] = field(default_factory=list)
    custom_factors: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def load(cls, project_dir: str) -> "ProjectConfig":
        """从项目目录加载配置"""
        config_path = os.path.join(project_dir, "config", "project.yaml")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"项目配置文件不存在: {config_path}")
        
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        org_units = [OrgUnit(**ou) for ou in data.get("org_units", [])]
        
        return cls(
            name=data.get("name", "未命名项目"),
            reporting_year=data.get("reporting_year", 2024),
            base_year=data.get("base_year"),
            description=data.get("description", ""),
            language=data.get("language", "zh"),
            unit=data.get("unit", "tCO2e"),
            electricity_region=data.get("electricity_region", "national"),
            org_units=org_units,
            custom_factors=data.get("custom_factors", {}),
        )

    def save(self, project_dir: str) -> None:
        """保存配置到项目目录"""
        config_path = os.path.join(project_dir, "config", "project.yaml")
        
        data = {
            "name": self.name,
            "reporting_year": self.reporting_year,
            "base_year": self.base_year,
            "description": self.description,
            "language": self.language,
            "unit": self.unit,
            "electricity_region": self.electricity_region,
            "org_units": [
                {
                    "id": ou.id,
                    "name": ou.name,
                    "parent": ou.parent,
                    "description": ou.description,
                }
                for ou in self.org_units
            ],
            "custom_factors": self.custom_factors,
        }
        
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def get_project_dir() -> str:
    """获取当前项目目录（当前工作目录）"""
    return os.getcwd()


def is_project_dir(path: str) -> bool:
    """检查路径是否为有效项目目录"""
    config_path = os.path.join(path, "config", "project.yaml")
    return os.path.exists(config_path)
