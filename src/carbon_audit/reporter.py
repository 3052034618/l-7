"""报告生成模块 - 生成碳盘查报告"""

import os
from datetime import date
from typing import List, Optional
from .models import EmissionSummary, EnergyCategory
from .config import ProjectConfig
from .calculator import EmissionCalculator
from .checker import DataChecker


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, config: ProjectConfig, summary: EmissionSummary, 
                 checker: DataChecker, language: Optional[str] = None):
        self.config = config
        self.summary = summary
        self.checker = checker
        self.language = language or config.language
        self.calculator = EmissionCalculator(config)
    
    def generate_summary_report(self, output_path: str, 
                                org_unit: Optional[str] = None,
                                start_date: Optional[date] = None,
                                end_date: Optional[date] = None) -> str:
        """生成摘要报告"""
        
        # 按组织单元和时间范围过滤
        records = self._filter_records(org_unit, start_date, end_date)
        filtered_summary = self.calculator.summarize(records)
        
        unit = self.config.unit
        
        if self.language == "zh":
            return self._generate_chinese_report(filtered_summary, unit, org_unit, 
                                                start_date, end_date, output_path)
        else:
            return self._generate_english_report(filtered_summary, unit, org_unit,
                                                start_date, end_date, output_path)
    
    def _filter_records(self, org_unit: Optional[str], 
                       start_date: Optional[date], 
                       end_date: Optional[date]):
        """过滤记录"""
        records = self.summary.records.copy()
        
        if org_unit:
            records = [r for r in records if r.org_unit == org_unit]
        
        if start_date:
            records = [r for r in records if r.period >= start_date]
        
        if end_date:
            records = [r for r in records if r.period <= end_date]
        
        return records
    
    def _convert(self, value: float, unit: str) -> float:
        """单位转换"""
        return self.calculator.convert_unit(value, unit)
    
    def _generate_chinese_report(self, summary: EmissionSummary, unit: str,
                                 org_unit: Optional[str],
                                 start_date: Optional[date],
                                 end_date: Optional[date],
                                 output_path: str) -> str:
        """生成中文报告"""
        lines = []
        
        # 标题
        lines.append("=" * 60)
        lines.append(f"  {self.config.name} - 温室气体排放盘查摘要")
        lines.append("=" * 60)
        lines.append("")
        
        # 基本信息
        lines.append("一、基本信息")
        lines.append("-" * 40)
        lines.append(f"  报告年度：{self.config.reporting_year}年")
        if self.config.base_year:
            lines.append(f"  基准年度：{self.config.base_year}年")
        if org_unit:
            lines.append(f"  组织单元：{org_unit}")
        if start_date or end_date:
            period = ""
            if start_date:
                period += start_date.strftime("%Y年%m月%d日")
            period += " 至 "
            if end_date:
                period += end_date.strftime("%Y年%m月%d日")
            lines.append(f"  统计范围：{period}")
        lines.append(f"  报告单位：{unit}")
        lines.append("")
        
        # 排放总量
        total = self._convert(summary.total, unit)
        lines.append("二、排放总量")
        lines.append("-" * 40)
        lines.append(f"  总排放量：{total:,.2f} {unit}")
        lines.append("")
        
        # 按范围分类
        scope1 = self._convert(summary.scope1, unit)
        scope2 = self._convert(summary.scope2, unit)
        scope3 = self._convert(summary.scope3, unit)
        total_conv = self._convert(summary.total, unit)
        total_for_pct = total_conv if total_conv > 0 else 1
        
        lines.append("三、按排放范围分类")
        lines.append("-" * 40)
        lines.append(f"  范围一（直接排放）：{scope1:,.2f} {unit}  "
                     f"({scope1/total_for_pct*100:.1f}%)")
        lines.append(f"  范围二（间接排放）：{scope2:,.2f} {unit}  "
                     f"({scope2/total_for_pct*100:.1f}%)")
        lines.append(f"  范围三（其他间接）：{scope3:,.2f} {unit}  "
                     f"({scope3/total_for_pct*100:.1f}%)")
        lines.append("")
        
        # 按能源类别
        lines.append("四、按能源类别分类")
        lines.append("-" * 40)
        
        sorted_categories = sorted(
            summary.by_category.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        for cat_key, emission in sorted_categories:
            try:
                category = EnergyCategory(cat_key)
                cat_label = category.label_zh
            except ValueError:
                cat_label = cat_key
            
            emission_conv = self._convert(emission, unit)
            lines.append(f"  {cat_label}：{emission_conv:,.2f} {unit}  "
                         f"({emission_conv/total_for_pct*100:.1f}%)")
        lines.append("")
        
        # 按组织单元
        if not org_unit and summary.by_org_unit:
            lines.append("五、按组织单元分类")
            lines.append("-" * 40)
            
            sorted_orgs = sorted(
                summary.by_org_unit.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for ou, emission in sorted_orgs:
                emission_conv = self._convert(emission, unit)
                lines.append(f"  {ou}：{emission_conv:,.2f} {unit}  "
                             f"({emission_conv/total_for_pct*100:.1f}%)")
            lines.append("")
        
        # 月度趋势
        if summary.by_month:
            lines.append("六、月度排放趋势")
            lines.append("-" * 40)
            
            sorted_months = sorted(summary.by_month.items())
            for month, emission in sorted_months:
                emission_conv = self._convert(emission, unit)
                bar_len = int(emission / max(summary.by_month.values()) * 20) if summary.by_month else 0
                bar = "█" * bar_len
                lines.append(f"  {month}  {bar} {emission_conv:,.2f} {unit}")
            lines.append("")
        
        # 数据质量说明
        lines.append("七、数据质量说明")
        lines.append("-" * 40)
        
        missing_data, warnings = self.checker.check_all()
        if missing_data:
            lines.append(f"  缺失数据项：{len(missing_data)} 项")
        if warnings:
            lines.append(f"  数据异常提醒：{len(warnings)} 条")
        
        if not missing_data and not warnings:
            lines.append("  数据完整，无异常")
        lines.append("")
        
        # 补充材料清单
        materials = self.checker.get_supplementary_materials()
        if materials:
            lines.append("八、补充材料清单")
            lines.append("-" * 40)
            for mat in materials:
                lines.append(f"  {mat}")
            lines.append("")
        
        # 页脚
        lines.append("=" * 60)
        lines.append(f"  生成时间：{date.today().strftime('%Y年%m月%d日')}")
        lines.append(f"  排放因子：基于常用排放因子数据库")
        lines.append("=" * 60)
        
        report_text = "\n".join(lines)
        
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report_text)
        
        return report_text
    
    def _generate_english_report(self, summary: EmissionSummary, unit: str,
                                 org_unit: Optional[str],
                                 start_date: Optional[date],
                                 end_date: Optional[date],
                                 output_path: str) -> str:
        """生成英文报告"""
        lines = []
        
        # Title
        lines.append("=" * 60)
        lines.append(f"  {self.config.name} - GHG Emissions Audit Summary")
        lines.append("=" * 60)
        lines.append("")
        
        # Basic Info
        lines.append("1. Basic Information")
        lines.append("-" * 40)
        lines.append(f"  Reporting Year: {self.config.reporting_year}")
        if self.config.base_year:
            lines.append(f"  Base Year: {self.config.base_year}")
        if org_unit:
            lines.append(f"  Organizational Unit: {org_unit}")
        if start_date or end_date:
            period = ""
            if start_date:
                period += start_date.strftime("%Y-%m-%d")
            period += " to "
            if end_date:
                period += end_date.strftime("%Y-%m-%d")
            lines.append(f"  Period: {period}")
        lines.append(f"  Unit: {unit}")
        lines.append("")
        
        # Total Emissions
        total = self._convert(summary.total, unit)
        lines.append("2. Total Emissions")
        lines.append("-" * 40)
        lines.append(f"  Total Emissions: {total:,.2f} {unit}")
        lines.append("")
        
        # By Scope
        scope1 = self._convert(summary.scope1, unit)
        scope2 = self._convert(summary.scope2, unit)
        scope3 = self._convert(summary.scope3, unit)
        total_conv = self._convert(summary.total, unit)
        total_for_pct = total_conv if total_conv > 0 else 1
        
        lines.append("3. Emissions by Scope")
        lines.append("-" * 40)
        lines.append(f"  Scope 1 (Direct): {scope1:,.2f} {unit}  "
                     f"({scope1/total_for_pct*100:.1f}%)")
        lines.append(f"  Scope 2 (Indirect): {scope2:,.2f} {unit}  "
                     f"({scope2/total_for_pct*100:.1f}%)")
        lines.append(f"  Scope 3 (Other Indirect): {scope3:,.2f} {unit}  "
                     f"({scope3/total_for_pct*100:.1f}%)")
        lines.append("")
        
        # By Category
        lines.append("4. Emissions by Category")
        lines.append("-" * 40)
        
        sorted_categories = sorted(
            summary.by_category.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        for cat_key, emission in sorted_categories:
            try:
                category = EnergyCategory(cat_key)
                cat_label = category.label_en
            except ValueError:
                cat_label = cat_key
            
            emission_conv = self._convert(emission, unit)
            lines.append(f"  {cat_label}: {emission_conv:,.2f} {unit}  "
                         f"({emission_conv/total_for_pct*100:.1f}%)")
        lines.append("")
        
        # By Organizational Unit
        if not org_unit and summary.by_org_unit:
            lines.append("5. Emissions by Organizational Unit")
            lines.append("-" * 40)
            
            sorted_orgs = sorted(
                summary.by_org_unit.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for ou, emission in sorted_orgs:
                emission_conv = self._convert(emission, unit)
                lines.append(f"  {ou}: {emission_conv:,.2f} {unit}  "
                             f"({emission_conv/total_for_pct*100:.1f}%)")
            lines.append("")
        
        # Monthly Trend
        if summary.by_month:
            lines.append("6. Monthly Trend")
            lines.append("-" * 40)
            
            sorted_months = sorted(summary.by_month.items())
            max_emission = max(summary.by_month.values()) if summary.by_month else 1
            
            for month, emission in sorted_months:
                emission_conv = self._convert(emission, unit)
                bar_len = int(emission / max_emission * 20) if max_emission > 0 else 0
                bar = "█" * bar_len
                lines.append(f"  {month}  {bar} {emission_conv:,.2f} {unit}")
            lines.append("")
        
        # Data Quality
        lines.append("7. Data Quality Notes")
        lines.append("-" * 40)
        
        missing_data, warnings = self.checker.check_all()
        if missing_data:
            lines.append(f"  Missing data items: {len(missing_data)}")
        if warnings:
            lines.append(f"  Data warnings: {len(warnings)}")
        
        if not missing_data and not warnings:
            lines.append("  Data complete, no issues found")
        lines.append("")
        
        # Supplementary Materials
        materials = self.checker.get_supplementary_materials()
        if materials:
            lines.append("8. Supplementary Materials")
            lines.append("-" * 40)
            for mat in materials:
                lines.append(f"  {mat}")
            lines.append("")
        
        # Footer
        lines.append("=" * 60)
        lines.append(f"  Generated: {date.today().strftime('%Y-%m-%d')}")
        lines.append(f"  Emission Factors: Standard database")
        lines.append("=" * 60)
        
        report_text = "\n".join(lines)
        
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report_text)
        
        return report_text
