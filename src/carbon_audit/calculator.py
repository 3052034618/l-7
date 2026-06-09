"""排放计算模块 - 计算温室气体排放量"""

from typing import List
from .models import EnergyRecord, EnergyCategory, EmissionSummary, Scope
from .emission_factors import (
    SCOPE1_FACTORS, SCOPE2_FACTORS, SCOPE3_FACTORS,
    get_emission_factor, REFRIGERANT_TYPES
)
from .config import ProjectConfig


class EmissionCalculator:
    """排放计算器"""
    
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.custom_factors = config.custom_factors or {}
    
    def calculate_emissions(self, records: List[EnergyRecord]) -> List[EnergyRecord]:
        """计算所有记录的排放量"""
        for record in records:
            factor = self._get_factor(record)
            record.emission_factor = factor
            record.emission_kg = record.quantity * factor
        
        return records
    
    def _get_factor(self, record: EnergyRecord) -> float:
        """获取记录的排放因子"""
        # 优先使用自定义因子 - 按 factor_key
        if record.factor_key and record.factor_key in self.custom_factors:
            return self.custom_factors[record.factor_key]
        
        # 按类别和子类别组合的 key
        custom_key = f"{record.category.value}_{record.subcategory or 'default'}"
        if custom_key in self.custom_factors:
            return self.custom_factors[custom_key]
        
        # 根据类别确定 factor_key
        factor_key = self._get_factor_key(record)
        
        # 检查 factor_key 是否在自定义因子中
        if factor_key and factor_key in self.custom_factors:
            return self.custom_factors[factor_key]
        
        # 使用默认因子
        if factor_key:
            return get_emission_factor(factor_key)
        
        return 0.0
    
    def _get_factor_key(self, record: EnergyRecord) -> str:
        """获取记录对应的排放因子 key"""
        category = record.category
        
        if category == EnergyCategory.ELECTRICITY:
            return f"electricity_{self.config.electricity_region}"
        
        if category == EnergyCategory.REFRIGERANT:
            if record.factor_key:
                return record.factor_key
            subcategory = record.subcategory or ""
            return REFRIGERANT_TYPES.get(subcategory, "")
        
        if category == EnergyCategory.AIR_TRAVEL:
            subcategory = (record.subcategory or "").lower()
            if "international" in subcategory or "国际" in subcategory:
                return "air_travel_international"
            return "air_travel_domestic"
        
        if category == EnergyCategory.ROAD_TRAVEL:
            subcategory = (record.subcategory or "").lower()
            if "taxi" in subcategory or "出租" in subcategory:
                return "road_travel_taxi"
            return "road_travel_bus"
        
        # 其他类别
        if category == EnergyCategory.LPG:
            return "liquefied_petroleum_gas"
        
        return category.value
    
    def _get_electricity_factor(self) -> float:
        """获取电力排放因子"""
        region = self.config.electricity_region
        factor_key = f"electricity_{region}"
        factor = get_emission_factor(factor_key)
        
        if factor == 0:
            return get_emission_factor("electricity_national")
        return factor
    
    def _get_refrigerant_factor(self, record: EnergyRecord) -> float:
        """获取冷媒排放因子"""
        if record.factor_key:
            return get_emission_factor(record.factor_key)
        
        subcategory = record.subcategory or ""
        factor_key = REFRIGERANT_TYPES.get(subcategory, "")
        if factor_key:
            return get_emission_factor(factor_key)
        
        return 0.0
    
    def _get_air_travel_factor(self, record: EnergyRecord) -> float:
        """获取航空差旅排放因子"""
        subcategory = (record.subcategory or "").lower()
        if "international" in subcategory or "国际" in subcategory:
            return get_emission_factor("air_travel_international")
        return get_emission_factor("air_travel_domestic")
    
    def _get_road_travel_factor(self, record: EnergyRecord) -> float:
        """获取公路差旅排放因子"""
        subcategory = (record.subcategory or "").lower()
        if "taxi" in subcategory or "出租" in subcategory:
            return get_emission_factor("road_travel_taxi")
        return get_emission_factor("road_travel_bus")
    
    def summarize(self, records: List[EnergyRecord]) -> EmissionSummary:
        """生成排放汇总"""
        summary = EmissionSummary()
        summary.records = records
        
        for record in records:
            emission = record.emission_kg
            
            # 按范围汇总
            scope = record.category.scope
            if scope == Scope.SCOPE1:
                summary.scope1 += emission
            elif scope == Scope.SCOPE2:
                summary.scope2 += emission
            else:
                summary.scope3 += emission
            
            summary.total += emission
            
            # 按类别汇总
            cat_key = record.category.value
            summary.by_category[cat_key] = summary.by_category.get(cat_key, 0) + emission
            
            # 按组织单元汇总
            ou_key = record.org_unit
            summary.by_org_unit[ou_key] = summary.by_org_unit.get(ou_key, 0) + emission
            
            # 按月份汇总
            month_key = record.period.strftime("%Y-%m")
            summary.by_month[month_key] = summary.by_month.get(month_key, 0) + emission
        
        return summary
    
    def convert_unit(self, value_kg: float, target_unit: str) -> float:
        """单位转换"""
        unit = target_unit.lower()
        if unit == "kgco2e" or unit == "kg":
            return value_kg
        elif unit == "tco2e" or unit == "t":
            return value_kg / 1000
        elif unit == "gco2e" or unit == "g":
            return value_kg * 1000
        else:
            return value_kg
