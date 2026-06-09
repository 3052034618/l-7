"""年度比较模块 - 比较不同年度的排放变化"""

from typing import Dict, Tuple, Optional
from datetime import date
from .models import EmissionSummary, EnergyRecord
from .data_store import DataStore
from .config import ProjectConfig
from .calculator import EmissionCalculator


class YearComparator:
    """年度比较器"""
    
    def __init__(self, config: ProjectConfig, data_store: DataStore):
        self.config = config
        self.data_store = data_store
        self.calculator = EmissionCalculator(config)
    
    def compare_years(self, year1: int, year2: int,
                     org_unit: Optional[str] = None) -> Dict:
        """比较两个年度的数据"""
        
        # 获取两个年度的记录
        records1 = self.data_store.get_records_by_year(year1)
        records2 = self.data_store.get_records_by_year(year2)
        
        # 按组织单元过滤
        if org_unit:
            records1 = [r for r in records1 if r.org_unit == org_unit]
            records2 = [r for r in records2 if r.org_unit == org_unit]
        
        # 计算排放
        records1 = self.calculator.calculate_emissions(records1)
        records2 = self.calculator.calculate_emissions(records2)
        
        # 生成汇总
        summary1 = self.calculator.summarize(records1)
        summary2 = self.calculator.summarize(records2)
        
        # 计算变化
        result = {
            "year1": year1,
            "year2": year2,
            "summary1": summary1,
            "summary2": summary2,
            "total_change": summary2.total - summary1.total,
            "total_change_pct": self._pct_change(summary1.total, summary2.total),
            "scope1_change": summary2.scope1 - summary1.scope1,
            "scope1_change_pct": self._pct_change(summary1.scope1, summary2.scope1),
            "scope2_change": summary2.scope2 - summary1.scope2,
            "scope2_change_pct": self._pct_change(summary1.scope2, summary2.scope2),
            "scope3_change": summary2.scope3 - summary1.scope3,
            "scope3_change_pct": self._pct_change(summary1.scope3, summary2.scope3),
            "by_category": self._compare_by_category(summary1, summary2),
            "by_org_unit": self._compare_by_org_unit(summary1, summary2),
        }
        
        return result
    
    def _pct_change(self, old: float, new: float) -> float:
        """计算百分比变化"""
        if old == 0:
            return float('inf') if new > 0 else 0
        return (new - old) / old * 100
    
    def _compare_by_category(self, summary1: EmissionSummary, 
                            summary2: EmissionSummary) -> Dict[str, Dict]:
        """按类别比较"""
        result = {}
        all_cats = set(summary1.by_category.keys()) | set(summary2.by_category.keys())
        
        for cat in all_cats:
            val1 = summary1.by_category.get(cat, 0)
            val2 = summary2.by_category.get(cat, 0)
            result[cat] = {
                "year1": val1,
                "year2": val2,
                "change": val2 - val1,
                "change_pct": self._pct_change(val1, val2),
            }
        
        return result
    
    def _compare_by_org_unit(self, summary1: EmissionSummary,
                            summary2: EmissionSummary) -> Dict[str, Dict]:
        """按组织单元比较"""
        result = {}
        all_orgs = set(summary1.by_org_unit.keys()) | set(summary2.by_org_unit.keys())
        
        for ou in all_orgs:
            val1 = summary1.by_org_unit.get(ou, 0)
            val2 = summary2.by_org_unit.get(ou, 0)
            result[ou] = {
                "year1": val1,
                "year2": val2,
                "change": val2 - val1,
                "change_pct": self._pct_change(val1, val2),
            }
        
        return result
    
    def format_comparison_report(self, comparison: Dict, 
                                 language: str = "zh",
                                 unit: str = "tCO2e") -> str:
        """格式化比较报告"""
        if language == "zh":
            return self._format_chinese(comparison, unit)
        else:
            return self._format_english(comparison, unit)
    
    def _conv(self, value: float, unit: str) -> float:
        return self.calculator.convert_unit(value, unit)
    
    def _format_chinese(self, comparison: Dict, unit: str) -> str:
        """中文格式化"""
        lines = []
        year1 = comparison["year1"]
        year2 = comparison["year2"]
        
        lines.append("=" * 60)
        lines.append(f"  {year1}年 vs {year2}年 排放对比分析")
        lines.append("=" * 60)
        lines.append("")
        
        # 总体变化
        total_change = self._conv(comparison["total_change"], unit)
        total_pct = comparison["total_change_pct"]
        arrow = "↑" if total_change > 0 else "↓" if total_change < 0 else "→"
        
        lines.append("一、总体变化")
        lines.append("-" * 40)
        lines.append(f"  {year1}年总量：{self._conv(comparison['summary1'].total, unit):,.2f} {unit}")
        lines.append(f"  {year2}年总量：{self._conv(comparison['summary2'].total, unit):,.2f} {unit}")
        lines.append(f"  变化量：{arrow} {abs(total_change):,.2f} {unit}")
        lines.append(f"  变化率：{total_pct:+.2f}%")
        lines.append("")
        
        # 按范围
        lines.append("二、按排放范围对比")
        lines.append("-" * 40)
        
        scopes = [
            ("范围一", "scope1"),
            ("范围二", "scope2"),
            ("范围三", "scope3"),
        ]
        
        for label, key in scopes:
            change_key = f"{key}_change"
            pct_key = f"{key}_change_pct"
            change = self._conv(comparison[change_key], unit)
            pct = comparison[pct_key]
            arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
            
            lines.append(f"  {label}：{arrow} {abs(change):,.2f} {unit} ({pct:+.2f}%)")
        lines.append("")
        
        # 按类别
        lines.append("三、按能源类别对比")
        lines.append("-" * 40)
        
        by_cat = comparison["by_category"]
        sorted_cats = sorted(by_cat.items(), key=lambda x: abs(x[1]["change"]), reverse=True)
        
        for cat, data in sorted_cats:
            try:
                from .models import EnergyCategory
                cat_label = EnergyCategory(cat).label_zh
            except ValueError:
                cat_label = cat
            
            change = self._conv(data["change"], unit)
            pct = data["change_pct"]
            arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
            
            lines.append(f"  {cat_label}：{arrow} {abs(change):,.2f} {unit} ({pct:+.2f}%)")
        lines.append("")
        
        # 按组织单元
        if comparison["by_org_unit"]:
            lines.append("四、按组织单元对比")
            lines.append("-" * 40)
            
            by_org = comparison["by_org_unit"]
            sorted_orgs = sorted(by_org.items(), key=lambda x: abs(x[1]["change"]), reverse=True)
            
            for ou, data in sorted_orgs:
                change = self._conv(data["change"], unit)
                pct = data["change_pct"]
                arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
                
                lines.append(f"  {ou}：{arrow} {abs(change):,.2f} {unit} ({pct:+.2f}%)")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _format_english(self, comparison: Dict, unit: str) -> str:
        """英文格式化"""
        lines = []
        year1 = comparison["year1"]
        year2 = comparison["year2"]
        
        lines.append("=" * 60)
        lines.append(f"  {year1} vs {year2} Emissions Comparison")
        lines.append("=" * 60)
        lines.append("")
        
        # Overall
        total_change = self._conv(comparison["total_change"], unit)
        total_pct = comparison["total_change_pct"]
        arrow = "↑" if total_change > 0 else "↓" if total_change < 0 else "→"
        
        lines.append("1. Overall Change")
        lines.append("-" * 40)
        lines.append(f"  {year1} Total: {self._conv(comparison['summary1'].total, unit):,.2f} {unit}")
        lines.append(f"  {year2} Total: {self._conv(comparison['summary2'].total, unit):,.2f} {unit}")
        lines.append(f"  Change: {arrow} {abs(total_change):,.2f} {unit}")
        lines.append(f"  Change %: {total_pct:+.2f}%")
        lines.append("")
        
        # By Scope
        lines.append("2. Comparison by Scope")
        lines.append("-" * 40)
        
        scopes = [
            ("Scope 1", "scope1"),
            ("Scope 2", "scope2"),
            ("Scope 3", "scope3"),
        ]
        
        for label, key in scopes:
            change_key = f"{key}_change"
            pct_key = f"{key}_change_pct"
            change = self._conv(comparison[change_key], unit)
            pct = comparison[pct_key]
            arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
            
            lines.append(f"  {label}: {arrow} {abs(change):,.2f} {unit} ({pct:+.2f}%)")
        lines.append("")
        
        # By Category
        lines.append("3. Comparison by Category")
        lines.append("-" * 40)
        
        by_cat = comparison["by_category"]
        sorted_cats = sorted(by_cat.items(), key=lambda x: abs(x[1]["change"]), reverse=True)
        
        for cat, data in sorted_cats:
            try:
                from .models import EnergyCategory
                cat_label = EnergyCategory(cat).label_en
            except ValueError:
                cat_label = cat
            
            change = self._conv(data["change"], unit)
            pct = data["change_pct"]
            arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
            
            lines.append(f"  {cat_label}: {arrow} {abs(change):,.2f} {unit} ({pct:+.2f}%)")
        lines.append("")
        
        # By Org Unit
        if comparison["by_org_unit"]:
            lines.append("4. Comparison by Organizational Unit")
            lines.append("-" * 40)
            
            by_org = comparison["by_org_unit"]
            sorted_orgs = sorted(by_org.items(), key=lambda x: abs(x[1]["change"]), reverse=True)
            
            for ou, data in sorted_orgs:
                change = self._conv(data["change"], unit)
                pct = data["change_pct"]
                arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
                
                lines.append(f"  {ou}: {arrow} {abs(change):,.2f} {unit} ({pct:+.2f}%)")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
