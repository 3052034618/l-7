"""项目配置管理"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class OrgUnit:
    """组织单元"""
    id: str
    name: str
    parent: Optional[str] = None
    description: str = ""


@dataclass
class CustomFactorConfig:
    """自定义排放因子配置"""
    value: float
    source: str = ""
    version: str = ""
    effective_date: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "source": self.source,
            "version": self.version,
            "effective_date": self.effective_date,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Any) -> "CustomFactorConfig":
        """从字典或数值创建（兼容旧格式）"""
        if isinstance(data, (int, float)):
            # 旧格式：只有数值
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return cls(
                value=float(data),
                created_at=now,
                updated_at=now,
            )
        
        # 新格式：字典
        return cls(
            value=float(data.get("value", 0)),
            source=data.get("source", ""),
            version=data.get("version", ""),
            effective_date=data.get("effective_date", ""),
            notes=data.get("notes", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


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
    custom_factors: Dict[str, CustomFactorConfig] = field(default_factory=dict)
    
    def get_factor_value(self, key: str, default: float = 0.0) -> float:
        """获取自定义因子值"""
        if key in self.custom_factors:
            return self.custom_factors[key].value
        return default
    
    def has_custom_factor(self, key: str) -> bool:
        """检查是否有自定义因子"""
        return key in self.custom_factors

    @classmethod
    def load(cls, project_dir: str) -> "ProjectConfig":
        """从项目目录加载配置"""
        config_path = os.path.join(project_dir, "config", "project.yaml")
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"项目配置文件不存在: {config_path}")
        
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        org_units = [OrgUnit(**ou) for ou in data.get("org_units", [])]
        
        # 加载自定义因子（兼容旧格式）
        custom_factors_raw = data.get("custom_factors", {})
        custom_factors = {}
        for key, value in custom_factors_raw.items():
            custom_factors[key] = CustomFactorConfig.from_dict(value)
        
        return cls(
            name=data.get("name", "未命名项目"),
            reporting_year=data.get("reporting_year", 2024),
            base_year=data.get("base_year"),
            description=data.get("description", ""),
            language=data.get("language", "zh"),
            unit=data.get("unit", "tCO2e"),
            electricity_region=data.get("electricity_region", "national"),
            org_units=org_units,
            custom_factors=custom_factors,
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
            "custom_factors": {
                key: factor.to_dict()
                for key, factor in self.custom_factors.items()
            },
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
