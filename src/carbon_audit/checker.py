"""数据检查模块 - 检查数据完整性和格式问题"""

import os
from typing import List, Dict, Tuple
from datetime import date, timedelta
from calendar import monthrange
from .models import EnergyRecord, EnergyCategory, ValidationError, MissingData, Scope
from .data_store import DataStore
from .config import ProjectConfig


class DataChecker:
    """数据检查器"""
    
    def __init__(self, config: ProjectConfig, data_store: DataStore):
        self.config = config
        self.data_store = data_store
    
    def check_all(self) -> Tuple[List[MissingData], List[str]]:
        """全面检查"""
        all_missing: List[MissingData] = []
        all_warnings: List[str] = []
        
        year = self.config.reporting_year
        
        # 检查每月数据完整性
        missing, warnings = self.check_monthly_completeness(year)
        all_missing.extend(missing)
        all_warnings.extend(warnings)
        
        # 检查数据合理性
        warnings2 = self.check_data_reasonableness()
        all_warnings.extend(warnings2)
        
        # 检查组织单元覆盖
        warnings3 = self.check_org_unit_coverage()
        all_warnings.extend(warnings3)
        
        return all_missing, all_warnings
    
    def check_monthly_completeness(self, year: int) -> Tuple[List[MissingData], List[str]]:
        """检查每月数据完整性"""
        missing: List[MissingData] = []
        warnings: List[str] = []
        
        # 获取所有类别
        categories = self._get_required_categories()
        org_units = self._get_org_units()
        
        for month in range(1, 13):
            month_date = date(year, month, 1)
            
            for category in categories:
                for ou in org_units:
                    records = self.data_store.get_records_by_month(year, month)
                    cat_records = [r for r in records if r.category == category and r.org_unit == ou]
                    
                    if not cat_records:
                        missing.append(MissingData(
                            category=category,
                            org_unit=ou,
                            period=month_date,
                            reason="缺少该月数据"
                        ))
                    else:
                        # 检查数据量是否异常低
                        total_qty = sum(r.quantity for r in cat_records)
                        if total_qty == 0:
                            warnings.append(
                                f"{year}年{month}月 {ou} {category.label_zh} 数据为零"
                            )
        
        return missing, warnings
    
    def check_data_reasonableness(self) -> List[str]:
        """检查数据合理性"""
        warnings: List[str] = []
        records = self.data_store.load_records()
        
        # 按类别分组检查
        by_category: Dict[str, List[EnergyRecord]] = {}
        for r in records:
            key = r.category.value
            if key not in by_category:
                by_category[key] = []
            by_category[key].append(r)
        
        for cat, cat_records in by_category.items():
            if not cat_records:
                continue
            
            # 计算平均值和标准差
            quantities = [r.quantity for r in cat_records]
            if len(quantities) < 3:
                continue
            
            avg = sum(quantities) / len(quantities)
            
            # 检查异常值（超过平均值3倍）
            for r in cat_records:
                if r.quantity > avg * 3 and r.quantity > 0:
                    warnings.append(
                        f"数据异常偏高: {r.source_file} 第{r.line_number}行 "
                        f"{r.category.label_zh} {r.quantity}{r.category.unit} "
                        f"(平均值约为{avg:.2f}{r.category.unit}"
                    )
        
        return warnings
    
    def check_org_unit_coverage(self) -> List[str]:
        """检查组织单元覆盖"""
        warnings: List[str] = []
        
        configured_orgs = {ou.id: ou.name for ou in self.config.org_units}
        data_orgs = set(self.data_store.get_org_units())
        
        # 检查配置中但无数据的组织单元
        for ou_id, ou_name in configured_orgs.items():
            if ou_id not in data_orgs and ou_name not in data_orgs:
                warnings.append(f"组织单元 '{ou_name}' 无数据记录")
        
        # 检查有数据但未配置的组织单元
        configured_names = set(configured_orgs.values())
        for ou in data_orgs:
            if ou not in configured_names and ou not in configured_orgs:
                if ou != "总部":
                    warnings.append(f"数据中存在未配置的组织单元: {ou}")
        
        return warnings
    
    def check_format(self, file_path: str) -> List[ValidationError]:
        """检查文件格式（通过导入器检查）"""
        errors: List[ValidationError] = []
        
        if not os.path.exists(file_path):
            errors.append(ValidationError(
                file=file_path,
                sheet=None,
                line_number=0,
                error_type="file_not_found",
                message="文件不存在",
            ))
            return errors
        
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in [".csv", ".xlsx", ".xls"]:
            errors.append(ValidationError(
                file=file_path,
                sheet=None,
                line_number=0,
                error_type="unsupported_format",
                message=f"不支持的文件格式: {ext}",
            ))
        
        # 检查文件大小
        try:
            size = os.path.getsize(file_path)
            if size == 0:
                errors.append(ValidationError(
                    file=file_path,
                    sheet=None,
                    line_number=0,
                    error_type="empty_file",
                    message="文件为空",
                ))
        except OSError:
            pass
        
        return errors
    
    def _get_required_categories(self) -> List[EnergyCategory]:
        """获取需要检查的类别（至少有数据的类别都检查完整性"""
        categories = set()
        records = self.data_store.load_records()
        for r in records:
            categories.add(r.category)
        
        if not categories:
            # 如果没有数据，检查所有类别
            categories = {
                EnergyCategory.ELECTRICITY,
                EnergyCategory.NATURAL_GAS,
            }
        
        return sorted(categories, key=lambda c: c.value)
    
    def _get_org_units(self) -> List[str]:
        """获取组织单元列表"""
        if self.config.org_units:
            return [ou.name for ou in self.config.org_units]
        
        # 如果没有配置组织单元，使用数据中的组织单元
        data_orgs = self.data_store.get_org_units()
        return data_orgs if data_orgs else ["总部"]
    
    def get_supplementary_materials(self) -> List[str]:
        """生成补充材料清单"""
        materials = []
        missing, warnings = self.check_all()
        
        if missing:
            materials.append("缺失数据月份清单：")
            by_cat_org: Dict[str, List[str]] = {}
            for m in missing:
                key = f"{m.category.label_zh} - {m.org_unit}"
                if key not in by_cat_org:
                    by_cat_org[key] = []
                by_cat_org[key].append(m.period.strftime("%Y年%m月"))
            
            for key, months in by_cat_org.items():
                materials.append(f"  {key}: {', '.join(months)}")
        
        if warnings:
            materials.append("\n需要确认的数据：")
            for w in warnings[:10]:  # 只显示前10条
                materials.append(f"  - {w}")
        
        materials.append("\n建议收集的证明材料：")
        materials.append("  1. 电费账单/缴费凭证")
        materials.append("  2. 燃气费账单/缴费凭证")
        materials.append("  3. 燃油采购发票")
        materials.append("  4. 冷媒采购/充装记录")
        materials.append("  5. 差旅报销凭证")
        materials.append("  6. 组织架构图")
        materials.append("  7. 设备清单及使用记录")
        
        return materials
