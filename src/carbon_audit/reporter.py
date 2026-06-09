"""报告生成模块 - 生成碳盘查报告"""

import os
from datetime import date
from typing import List, Optional
from .models import EmissionSummary, EnergyCategory, Scope
from .config import ProjectConfig
from .calculator import EmissionCalculator
from .checker import DataChecker


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, config: ProjectConfig, summary: EmissionSummary, 
                 checker: DataChecker, language: Optional[str] = None,
                 unit: Optional[str] = None):
        self.config = config
        self.summary = summary
        self.checker = checker
        self.language = language or config.language
        self.unit = unit or config.unit
        self.calculator = EmissionCalculator(config)
    
    def generate_summary_report(self, output_path: Optional[str] = None, 
                                org_unit: Optional[str] = None,
                                start_date: Optional[date] = None,
                                end_date: Optional[date] = None,
                                output_format: str = "text") -> str:
        """生成摘要报告
        
        Args:
            output_path: 输出文件路径，None 则不保存文件
            org_unit: 按组织单元过滤
            start_date: 开始日期
            end_date: 结束日期
            output_format: 输出格式（text/markdown）
        """
        # 按组织单元和时间范围过滤
        records = self._filter_records(org_unit, start_date, end_date)
        filtered_summary = self.calculator.summarize(records)
        
        if self.language == "zh":
            report_text = self._generate_chinese_report(
                filtered_summary, self.unit, org_unit, start_date, end_date
            )
        else:
            report_text = self._generate_english_report(
                filtered_summary, self.unit, org_unit, start_date, end_date
            )
        
        # 转换格式
        if output_format == "markdown":
            report_text = self._to_markdown(report_text)
        
        # 保存文件
        if output_path:
            output_dir = os.path.dirname(os.path.abspath(output_path))
            os.makedirs(output_dir, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report_text)
        
        return report_text
    
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
    
    def _convert(self, value: float) -> float:
        """单位转换（使用当前单位）"""
        return self.calculator.convert_unit(value, self.unit)
    
    def _generate_chinese_report(self, summary: EmissionSummary, unit: str,
                                 org_unit: Optional[str],
                                 start_date: Optional[date],
                                 end_date: Optional[date]) -> str:
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
            else:
                period += f"{self.config.reporting_year}年01月01日"
            period += " 至 "
            if end_date:
                period += end_date.strftime("%Y年%m月%d日")
            else:
                period += f"{self.config.reporting_year}年12月31日"
            lines.append(f"  统计范围：{period}")
        lines.append(f"  报告单位：{unit}")
        lines.append(f"  电力因子：{self.config.electricity_region} 区域")
        lines.append("")
        
        # 排放总量
        total = self._convert(summary.total)
        lines.append("二、排放总量")
        lines.append("-" * 40)
        lines.append(f"  总排放量：{total:,.2f} {unit}")
        lines.append("")
        
        # 按范围分类
        scope1 = self._convert(summary.scope1)
        scope2 = self._convert(summary.scope2)
        scope3 = self._convert(summary.scope3)
        total_conv = self._convert(summary.total)
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
            
            emission_conv = self._convert(emission)
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
                emission_conv = self._convert(emission)
                lines.append(f"  {ou}：{emission_conv:,.2f} {unit}  "
                             f"({emission_conv/total_for_pct*100:.1f}%)")
            lines.append("")
        
        # 月度趋势
        if summary.by_month:
            section_num = "六" if not org_unit or not summary.by_org_unit else "五"
            lines.append(f"{section_num}、月度排放趋势")
            lines.append("-" * 40)
            
            sorted_months = sorted(summary.by_month.items())
            max_emission = max(summary.by_month.values()) if summary.by_month else 1
            
            for month, emission in sorted_months:
                emission_conv = self._convert(emission)
                bar_len = int(emission / max_emission * 20) if max_emission > 0 else 0
                bar = "█" * bar_len
                lines.append(f"  {month}  {bar} {emission_conv:,.2f} {unit}")
            lines.append("")
        
        # 数据质量说明
        lines.append("七、数据质量说明")
        lines.append("-" * 40)
        
        missing_data, warnings = self.checker.check_all()
        # 按组织单元过滤
        if org_unit:
            missing_data = [m for m in missing_data if m.org_unit == org_unit]
            warnings = [w for w in warnings if org_unit in w]
        
        if missing_data:
            lines.append(f"  缺失数据项：{len(missing_data)} 项")
        if warnings:
            lines.append(f"  数据异常提醒：{len(warnings)} 条")
        
        if not missing_data and not warnings:
            lines.append("  数据完整，无异常")
        lines.append("")
        
        # 补充材料清单
        lines.append("八、补充材料清单")
        lines.append("-" * 40)
        materials = self._get_supplementary_materials_zh(missing_data, warnings)
        for mat in materials:
            lines.append(f"  {mat}")
        lines.append("")
        
        # 页脚
        lines.append("=" * 60)
        lines.append(f"  生成时间：{date.today().strftime('%Y年%m月%d日')}")
        lines.append(f"  排放因子：基于常用排放因子数据库（含自定义因子）")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _generate_english_report(self, summary: EmissionSummary, unit: str,
                                 org_unit: Optional[str],
                                 start_date: Optional[date],
                                 end_date: Optional[date]) -> str:
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
            else:
                period += f"{self.config.reporting_year}-01-01"
            period += " to "
            if end_date:
                period += end_date.strftime("%Y-%m-%d")
            else:
                period += f"{self.config.reporting_year}-12-31"
            lines.append(f"  Period: {period}")
        lines.append(f"  Unit: {unit}")
        lines.append(f"  Electricity Factor: {self.config.electricity_region} region")
        lines.append("")
        
        # Total Emissions
        total = self._convert(summary.total)
        lines.append("2. Total Emissions")
        lines.append("-" * 40)
        lines.append(f"  Total Emissions: {total:,.2f} {unit}")
        lines.append("")
        
        # By Scope
        scope1 = self._convert(summary.scope1)
        scope2 = self._convert(summary.scope2)
        scope3 = self._convert(summary.scope3)
        total_conv = self._convert(summary.total)
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
            
            emission_conv = self._convert(emission)
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
                emission_conv = self._convert(emission)
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
                emission_conv = self._convert(emission)
                bar_len = int(emission / max_emission * 20) if max_emission > 0 else 0
                bar = "█" * bar_len
                lines.append(f"  {month}  {bar} {emission_conv:,.2f} {unit}")
            lines.append("")
        
        # Data Quality
        lines.append("7. Data Quality Notes")
        lines.append("-" * 40)
        
        missing_data, warnings = self.checker.check_all()
        if org_unit:
            missing_data = [m for m in missing_data if m.org_unit == org_unit]
            warnings = [w for w in warnings if org_unit in w]
        
        if missing_data:
            lines.append(f"  Missing data items: {len(missing_data)}")
        if warnings:
            lines.append(f"  Data warnings: {len(warnings)}")
        
        if not missing_data and not warnings:
            lines.append("  Data complete, no issues found")
        lines.append("")
        
        # Supplementary Materials
        lines.append("8. Supplementary Materials")
        lines.append("-" * 40)
        materials = self._get_supplementary_materials_en(missing_data, warnings)
        for mat in materials:
            lines.append(f"  {mat}")
        lines.append("")
        
        # Footer
        lines.append("=" * 60)
        lines.append(f"  Generated: {date.today().strftime('%Y-%m-%d')}")
        lines.append(f"  Emission Factors: Standard database (with custom factors)")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _get_supplementary_materials_zh(self, missing_data, warnings) -> List[str]:
        """中文补充材料清单"""
        materials = []
        
        if missing_data:
            materials.append("缺失数据月份清单：")
            by_cat_org = {}
            for m in missing_data:
                key = f"{m.category.label_zh} - {m.org_unit}"
                if key not in by_cat_org:
                    by_cat_org[key] = []
                by_cat_org[key].append(m.period.strftime("%Y年%m月"))
            
            for key, months in by_cat_org.items():
                materials.append(f"    {key}: {', '.join(sorted(months))}")
            materials.append("")
        
        if warnings:
            materials.append("需要确认的数据：")
            for w in warnings[:10]:
                materials.append(f"    - {w}")
            if len(warnings) > 10:
                materials.append(f"    ... 还有 {len(warnings) - 10} 条")
            materials.append("")
        
        materials.append("建议收集的证明材料：")
        materials.append("  1. 电费账单/缴费凭证")
        materials.append("  2. 燃气费账单/缴费凭证")
        materials.append("  3. 燃油采购发票")
        materials.append("  4. 冷媒采购/充装记录")
        materials.append("  5. 差旅报销凭证")
        materials.append("  6. 组织架构图")
        materials.append("  7. 设备清单及使用记录")
        
        return materials
    
    def _get_supplementary_materials_en(self, missing_data, warnings) -> List[str]:
        """英文补充材料清单"""
        materials = []
        
        if missing_data:
            materials.append("Missing data by month:")
            by_cat_org = {}
            for m in missing_data:
                try:
                    cat_label = EnergyCategory(m.category.value).label_en
                except ValueError:
                    cat_label = m.category.value
                key = f"{cat_label} - {m.org_unit}"
                if key not in by_cat_org:
                    by_cat_org[key] = []
                by_cat_org[key].append(m.period.strftime("%Y-%m"))
            
            for key, months in by_cat_org.items():
                materials.append(f"    {key}: {', '.join(sorted(months))}")
            materials.append("")
        
        if warnings:
            materials.append("Data to confirm:")
            for w in warnings[:10]:
                materials.append(f"    - {w}")
            if len(warnings) > 10:
                materials.append(f"    ... {len(warnings) - 10} more")
            materials.append("")
        
        materials.append("Recommended supporting documents:")
        materials.append("  1. Electricity bills / payment receipts")
        materials.append("  2. Gas bills / payment receipts")
        materials.append("  3. Fuel purchase invoices")
        materials.append("  4. Refrigerant purchase / recharge records")
        materials.append("  5. Travel expense reports")
        materials.append("  6. Organizational chart")
        materials.append("  7. Equipment list and usage records")
        
        return materials
    
    def _to_markdown(self, text: str) -> str:
        """将文本报告转换为 Markdown 格式"""
        lines = text.split("\n")
        md_lines = []
        
        for line in lines:
            # 等号线 -> 一级标题
            if line.startswith("=" * 40):
                # 跳过等号线，下一行作为标题
                continue
            
            # 短横线 -> 二级标题分隔
            if line.startswith("-" * 30):
                md_lines.append("")
                continue
            
            # 章节标题
            if line.strip().startswith("一、") or line.strip().startswith("二、") or \
               line.strip().startswith("三、") or line.strip().startswith("四、") or \
               line.strip().startswith("五、") or line.strip().startswith("六、") or \
               line.strip().startswith("七、") or line.strip().startswith("八、") or \
               line.strip().startswith("九、") or line.strip().startswith("十、"):
                md_lines.append(f"## {line.strip()}")
                continue
            
            # 英文数字标题
            import re
            if re.match(r"^\d+\. ", line.strip()):
                md_lines.append(f"## {line.strip()}")
                continue
            
            # 项目符号
            stripped = line.strip()
            if stripped.startswith("  - ") or stripped.startswith("    - "):
                md_lines.append(stripped)
                continue
            
            md_lines.append(line)
        
        return "\n".join(md_lines)
    
    def get_default_filename(self, year: int, org_unit: Optional[str] = None,
                            output_format: str = "text") -> str:
        """获取默认报告文件名"""
        ext = "md" if output_format == "markdown" else "txt"
        
        if self.language == "zh":
            filename = f"碳盘查报告_{year}"
            if org_unit:
                filename += f"_{org_unit}"
            filename += f".{ext}"
        else:
            filename = f"emission_report_{year}"
            if org_unit:
                filename += f"_{org_unit.replace(' ', '_')}"
            filename += f".{ext}"
        
        return filename
