"""数据模型"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Dict, List
from enum import Enum


class Scope(str, Enum):
    """排放范围"""
    SCOPE1 = "scope1"
    SCOPE2 = "scope2"
    SCOPE3 = "scope3"

    @property
    def label_zh(self) -> str:
        labels = {"scope1": "范围一", "scope2": "范围二", "scope3": "范围三"}
        return labels[self.value]

    @property
    def label_en(self) -> str:
        labels = {"scope1": "Scope 1", "scope2": "Scope 2", "scope3": "Scope 3"}
        return labels[self.value]


class EnergyCategory(str, Enum):
    """能源类别"""
    ELECTRICITY = "electricity"
    NATURAL_GAS = "natural_gas"
    GASOLINE = "gasoline"
    DIESEL = "diesel"
    LPG = "liquefied_petroleum_gas"
    COAL = "coal"
    REFRIGERANT = "refrigerant"
    AIR_TRAVEL = "air_travel"
    RAIL_TRAVEL = "rail_travel"
    ROAD_TRAVEL = "road_travel"
    HOTEL_STAY = "hotel_stay"

    @property
    def scope(self) -> Scope:
        mapping = {
            "electricity": Scope.SCOPE2,
            "natural_gas": Scope.SCOPE1,
            "gasoline": Scope.SCOPE1,
            "diesel": Scope.SCOPE1,
            "liquefied_petroleum_gas": Scope.SCOPE1,
            "coal": Scope.SCOPE1,
            "refrigerant": Scope.SCOPE1,
            "air_travel": Scope.SCOPE3,
            "rail_travel": Scope.SCOPE3,
            "road_travel": Scope.SCOPE3,
            "hotel_stay": Scope.SCOPE3,
        }
        return mapping[self.value]

    @property
    def unit(self) -> str:
        mapping = {
            "electricity": "kWh",
            "natural_gas": "m³",
            "gasoline": "L",
            "diesel": "L",
            "liquefied_petroleum_gas": "kg",
            "coal": "kg",
            "refrigerant": "kg",
            "air_travel": "人·km",
            "rail_travel": "人·km",
            "road_travel": "人·km",
            "hotel_stay": "间·晚",
        }
        return mapping[self.value]

    @property
    def label_zh(self) -> str:
        mapping = {
            "electricity": "电力",
            "natural_gas": "天然气",
            "gasoline": "汽油",
            "diesel": "柴油",
            "liquefied_petroleum_gas": "液化石油气",
            "coal": "煤炭",
            "refrigerant": "冷媒",
            "air_travel": "航空差旅",
            "rail_travel": "铁路差旅",
            "road_travel": "公路差旅",
            "hotel_stay": "酒店住宿",
        }
        return mapping[self.value]

    @property
    def label_en(self) -> str:
        mapping = {
            "electricity": "Electricity",
            "natural_gas": "Natural Gas",
            "gasoline": "Gasoline",
            "diesel": "Diesel",
            "liquefied_petroleum_gas": "LPG",
            "coal": "Coal",
            "refrigerant": "Refrigerant",
            "air_travel": "Air Travel",
            "rail_travel": "Rail Travel",
            "road_travel": "Road Travel",
            "hotel_stay": "Hotel Stay",
        }
        return mapping[self.value]


@dataclass
class EnergyRecord:
    """能耗记录"""
    category: EnergyCategory
    org_unit: str
    period: date
    quantity: float
    subcategory: Optional[str] = None
    description: str = ""
    source_file: str = ""
    line_number: int = 0
    emission_kg: float = 0.0
    emission_factor: float = 0.0
    factor_key: str = ""


@dataclass
class ValidationError:
    """数据校验错误"""
    file: str
    sheet: Optional[str]
    line_number: int
    error_type: str
    message: str
    column: Optional[str] = None


@dataclass
class MissingData:
    """缺失数据"""
    category: EnergyCategory
    org_unit: str
    period: date
    reason: str


@dataclass
class EmissionSummary:
    """排放汇总"""
    scope1: float = 0.0
    scope2: float = 0.0
    scope3: float = 0.0
    total: float = 0.0
    by_category: Dict[str, float] = field(default_factory=dict)
    by_org_unit: Dict[str, float] = field(default_factory=dict)
    by_month: Dict[str, float] = field(default_factory=dict)
    records: List[EnergyRecord] = field(default_factory=list)
