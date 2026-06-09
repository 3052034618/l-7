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
    
    def generate_full_report(self, output_path: Optional[str] = None,
                            org_unit: Optional[str] = None,
                            start_date: Optional[date] = None,
                            end_date: Optional[date] = None,
                            output_format: str = "text") -> str:
        """生成顾问交付版完整报告
        
        包含：封面、盘查边界说明、方法学说明、范围一二三明细表、数据质量附录
        """
        # 按组织单元和时间范围过滤
        records = self._filter_records(org_unit, start_date, end_date)
        filtered_summary = self.calculator.summarize(records)
        
        if self.language == "zh":
            report_text = self._generate_full_chinese_report(
                filtered_summary, records, self.unit, 
                org_unit, start_date, end_date
            )
        else:
            report_text = self._generate_full_english_report(
                filtered_summary, records, self.unit,
                org_unit, start_date, end_date
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
    
    def get_full_report_filename(self, year: int, 
                                  org_unit: Optional[str] = None,
                                  output_format: str = "text") -> str:
        """获取完整版报告默认文件名"""
        ext = "md" if output_format == "markdown" else "txt"
        
        if self.language == "zh":
            filename = f"碳盘查完整报告_{year}"
            if org_unit:
                filename += f"_{org_unit}"
            filename += f".{ext}"
        else:
            filename = f"full_emission_report_{year}"
            if org_unit:
                filename += f"_{org_unit.replace(' ', '_')}"
            filename += f".{ext}"
        
        return filename
    
    # ======== 完整版报告 - 中文 ========
    
    def _generate_full_chinese_report(self, summary: EmissionSummary, 
                                       records: list, unit: str,
                                       org_unit: Optional[str],
                                       start_date: Optional[date],
                                       end_date: Optional[date]) -> str:
        """生成中文完整版报告（顾问交付版）"""
        lines = []
        
        # ===== 封面 =====
        lines.extend(self._full_cover_zh(summary, org_unit, start_date, end_date))
        lines.append("")
        lines.append("\\newpage")
        lines.append("")
        
        # ===== 一、盘查边界说明 =====
        lines.extend(self._full_boundary_zh(summary, org_unit, start_date, end_date))
        lines.append("")
        
        # ===== 二、核算方法学 =====
        lines.extend(self._full_methodology_zh())
        lines.append("")
        
        # ===== 三、排放总量 =====
        lines.extend(self._full_total_zh(summary, unit))
        lines.append("")
        
        # ===== 四、范围一明细表 =====
        lines.extend(self._full_scope_detail_zh(summary, records, Scope.SCOPE1, unit))
        lines.append("")
        
        # ===== 五、范围二明细表 =====
        lines.extend(self._full_scope_detail_zh(summary, records, Scope.SCOPE2, unit))
        lines.append("")
        
        # ===== 六、范围三明细表 =====
        lines.extend(self._full_scope_detail_zh(summary, records, Scope.SCOPE3, unit))
        lines.append("")
        
        # ===== 七、月度趋势分析 =====
        lines.extend(self._full_monthly_trend_zh(summary, unit))
        lines.append("")
        
        # ===== 八、组织单元分布 =====
        if not org_unit:
            lines.extend(self._full_org_unit_zh(summary, unit))
            lines.append("")
        
        # ===== 附录：数据质量说明 =====
        lines.extend(self._full_quality_appendix_zh(summary, org_unit, start_date, end_date))
        lines.append("")
        
        # ===== 页脚 =====
        lines.extend(self._full_footer_zh())
        
        return "\n".join(lines)
    
    def _full_cover_zh(self, summary: EmissionSummary, 
                       org_unit: Optional[str],
                       start_date: Optional[date],
                       end_date: Optional[date]) -> list:
        """封面 - 中文"""
        lines = []
        
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"              {self.config.name}")
        lines.append("")
        lines.append("       温室气体排放盘查报告")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")
        lines.append("")
        
        # 从参数或数据中获取期间文本
        period_text, report_year = self._get_period_text_zh(start_date, end_date, summary)
        
        lines.append(f"  报告类型：温室气体排放盘查报告")
        lines.append(f"  报告期间：{period_text}")
        if org_unit:
            lines.append(f"  组织单元：{org_unit}")
        lines.append(f"  报告单位：{self.unit}")
        lines.append("")
        lines.append("")
        lines.append("")
        lines.append("  编制单位：________________________")
        lines.append("")
        lines.append("  编制日期：________________________")
        lines.append("")
        lines.append("  版本号：V1.0")
        lines.append("")
        lines.append("")
        lines.append("=" * 70)
        
        return lines
    
    def _full_boundary_zh(self, summary: EmissionSummary,
                           org_unit: Optional[str],
                           start_date: Optional[date],
                           end_date: Optional[date]) -> list:
        """盘查边界说明 - 中文"""
        lines = []
        
        lines.append("一、盘查边界说明")
        lines.append("-" * 50)
        lines.append("")
        
        period_text, report_year = self._get_period_text_zh(start_date, end_date, summary)
        
        lines.append("1. 时间边界")
        if start_date and end_date:
            lines.append(f"   本次盘查的时间边界为 {period_text}。")
        else:
            s = start_date.strftime("%Y年%m月%d日") if start_date else f"{report_year}年01月01日"
            e = end_date.strftime("%Y年%m月%d日") if end_date else f"{report_year}年12月31日"
            lines.append(f"   本次盘查的时间边界为 {s} 至 {e}。")
        lines.append("")
        
        lines.append("2. 组织边界")
        if org_unit:
            lines.append(f"   本次盘查的组织边界为：{org_unit}。")
        else:
            lines.append("   本次盘查的组织边界涵盖报告主体的所有运营设施。")
            orgs = list(summary.by_org_unit.keys()) if summary.by_org_unit else ["总部"]
            lines.append(f"   涉及组织单元：{', '.join(orgs)}")
        lines.append("")
        
        lines.append("3. 排放源边界")
        lines.append("   本次盘查包含以下类别的排放源：")
        lines.append("")
        lines.append("   范围一（直接排放）：")
        
        scope1_cats = self._get_categories_by_scope(summary, Scope.SCOPE1)
        scope2_cats = self._get_categories_by_scope(summary, Scope.SCOPE2)
        scope3_cats = self._get_categories_by_scope(summary, Scope.SCOPE3)
        
        for cat in scope1_cats:
            try:
                label = EnergyCategory(cat).label_zh
            except ValueError:
                label = cat
            lines.append(f"     - {label}")
        
        lines.append("")
        lines.append("   范围二（间接排放）：")
        for cat in scope2_cats:
            try:
                label = EnergyCategory(cat).label_zh
            except ValueError:
                label = cat
            lines.append(f"     - {label}")
        
        lines.append("")
        lines.append("   范围三（其他间接）：")
        if scope3_cats:
            for cat in scope3_cats:
                try:
                    label = EnergyCategory(cat).label_zh
                except ValueError:
                    label = cat
                lines.append(f"     - {label}")
        else:
            lines.append("     - （暂未纳入）")
        
        lines.append("")
        
        return lines
    
    def _full_methodology_zh(self) -> list:
        """核算方法学 - 中文"""
        lines = []
        
        lines.append("二、核算方法学")
        lines.append("-" * 50)
        lines.append("")
        
        lines.append("1. 核算标准")
        lines.append("   本次盘查遵循《温室气体议定书》(GHG Protocol) 核算框架，")
        lines.append("   涵盖范围一（直接排放）、范围二（间接排放）和范围三（其他间接排放）。")
        lines.append("")
        
        lines.append("2. 计算公式")
        lines.append("   排放量 = 活动数据 × 排放因子")
        lines.append("")
        
        lines.append("3. 排放因子来源")
        elec_factor = self.calculator.get_factor_info(
            f"electricity_{self.config.electricity_region}"
        )
        
        lines.append(f"   - 电力排放因子：{self.config.electricity_region} 区域电网排放因子")
        lines.append(f"     数值：{elec_factor['value']} kgCO2e/kWh")
        lines.append(f"     来源：{elec_factor['source']}")
        lines.append("")
        
        lines.append("   - 其他排放因子：基于常用排放因子数据库")
        lines.append("     （含自定义因子，详见排放因子说明）")
        
        # 统计自定义因子数量
        custom_count = len(self.config.custom_factors) if self.config.custom_factors else 0
        if custom_count > 0:
            lines.append("")
            lines.append(f"   项目中使用了 {custom_count} 个自定义排放因子，")
            lines.append("   具体清单详见附录。")
        
        lines.append("")
        
        return lines
    
    def _full_total_zh(self, summary: EmissionSummary, unit: str) -> list:
        """排放总量 - 中文"""
        lines = []
        
        total = self._convert(summary.total)
        scope1 = self._convert(summary.scope1)
        scope2 = self._convert(summary.scope2)
        scope3 = self._convert(summary.scope3)
        total_for_pct = total if total > 0 else 1
        
        lines.append("三、排放总量")
        lines.append("-" * 50)
        lines.append("")
        
        lines.append(f"  总排放量：{total:,.2f} {unit}")
        lines.append("")
        
        lines.append(f"  范围一（直接排放）：{scope1:,.2f} {unit}  ({scope1/total_for_pct*100:.1f}%)")
        lines.append(f"  范围二（间接排放）：{scope2:,.2f} {unit}  ({scope2/total_for_pct*100:.1f}%)")
        lines.append(f"  范围三（其他间接）：{scope3:,.2f} {unit}  ({scope3/total_for_pct*100:.1f}%)")
        lines.append("")
        
        return lines
    
    def _full_scope_detail_zh(self, summary: EmissionSummary, 
                               records: list, scope: Scope, 
                               unit: str) -> list:
        """范围明细表 - 中文"""
        lines = []
        
        scope_num = scope.value[-1]
        section_map = {
            "scope1": "四",
            "scope2": "五",
            "scope3": "六",
        }
        section_num = section_map.get(scope.value, "四")
        
        lines.append(f"{section_num}、{scope.label_zh}明细")
        lines.append("-" * 50)
        lines.append("")
        
        # 按类别汇总
        scope_categories = self._get_categories_by_scope(summary, scope)
        
        if not scope_categories:
            lines.append("  （本范围暂无数据）")
            return lines
        
        total_scope = self._convert(
            summary.scope1 if scope == Scope.SCOPE1 else 
            summary.scope2 if scope == Scope.SCOPE2 else summary.scope3
        )
        total_for_pct = total_scope if total_scope > 0 else 1
        
        # 类别汇总表
        lines.append(f"  序号 | 排放源类别 | 排放量 ({unit}) | 占比")
        lines.append("  " + "-" * 50)
        
        for i, cat_key in enumerate(sorted(scope_categories)):
            try:
                cat_label = EnergyCategory(cat_key).label_zh
            except ValueError:
                cat_label = cat_key
            
            emission = summary.by_category.get(cat_key, 0)
            emission_conv = self._convert(emission)
            
            lines.append(
                f"   {i+1:2d}  | {cat_label:<10s} | {emission_conv:>14,.2f} | {emission_conv/total_for_pct*100:.1f}%"
            )
        
        lines.append("")
        
        # 月度明细
        lines.append("  月度分布：")
        lines.append("")
        lines.append(f"  月份   | 排放量 ({unit}) | 环比变化")
        lines.append("  " + "-" * 45)
        
        # 按范围过滤记录，计算月度数据
        scope_records = [r for r in records if r.category.scope == scope]
        scope_by_month = {}
        for r in scope_records:
            month_key = r.period.strftime("%Y-%m")
            scope_by_month[month_key] = scope_by_month.get(month_key, 0) + r.emission_kg
        
        sorted_months = sorted(scope_by_month.items())
        prev_emission = None
        
        for month, emission in sorted_months:
            emission_conv = self._convert(emission)
            
            # 计算环比
            change_text = "-"
            if prev_emission and prev_emission > 0:
                change = (emission - prev_emission) / prev_emission * 100
                change_text = f"{change:+.1f}%"
            
            lines.append(f"  {month} | {emission_conv:>14,.2f} | {change_text}")
            prev_emission = emission
        
        lines.append("")
        
        return lines
    
    def _full_monthly_trend_zh(self, summary: EmissionSummary, unit: str) -> list:
        """月度趋势分析 - 中文"""
        lines = []
        
        lines.append("七、月度排放趋势")
        lines.append("-" * 50)
        lines.append("")
        
        if summary.by_month:
            sorted_months = sorted(summary.by_month.items())
            max_emission = max(summary.by_month.values()) if summary.by_month else 1
            
            for month, emission in sorted_months:
                emission_conv = self._convert(emission)
                bar_len = int(emission / max_emission * 30) if max_emission > 0 else 0
                bar = "█" * bar_len
                lines.append(f"  {month}  {bar} {emission_conv:,.2f} {unit}")
        else:
            lines.append("  （无月度数据）")
        
        lines.append("")
        
        return lines
    
    def _full_org_unit_zh(self, summary: EmissionSummary, unit: str) -> list:
        """组织单元分布 - 中文"""
        lines = []
        
        lines.append("八、组织单元排放分布")
        lines.append("-" * 50)
        lines.append("")
        
        total = self._convert(summary.total)
        total_for_pct = total if total > 0 else 1
        
        if summary.by_org_unit:
            sorted_orgs = sorted(summary.by_org_unit.items(), key=lambda x: x[1], reverse=True)
            
            lines.append(f"  序号 | 组织单元 | 排放量 ({unit}) | 占比")
            lines.append("  " + "-" * 50)
            
            for i, (ou, emission) in enumerate(sorted_orgs):
                emission_conv = self._convert(emission)
                lines.append(
                    f"   {i+1:2d}  | {ou:<8s} | {emission_conv:>14,.2f} | {emission_conv/total_for_pct*100:.1f}%"
                )
        else:
            lines.append("  （无组织单元数据）")
        
        lines.append("")
        
        return lines
    
    def _full_quality_appendix_zh(self, summary: EmissionSummary,
                                    org_unit: Optional[str],
                                    start_date: Optional[date],
                                    end_date: Optional[date]) -> list:
        """数据质量附录 - 中文"""
        lines = []
        
        lines.append("附录A：数据质量说明")
        lines.append("-" * 50)
        lines.append("")
        
        # 检查数据质量
        missing_data, warnings = self.checker.check_all()
        
        # 按时间范围过滤
        if start_date:
            missing_data = [m for m in missing_data if m.period >= start_date]
        if end_date:
            missing_data = [m for m in missing_data if m.period <= end_date]
        
        # 按组织单元过滤
        if org_unit:
            missing_data = [m for m in missing_data if m.org_unit == org_unit]
            warnings = [w for w in warnings if org_unit in w]
        
        lines.append("A.1 数据完整性")
        lines.append("")
        lines.append(f"  缺失数据项：{len(missing_data)} 项")
        if missing_data:
            lines.append("")
            lines.append("  缺失明细：")
            by_cat_org = {}
            for m in missing_data:
                key = f"{m.category.label_zh} - {m.org_unit}"
                if key not in by_cat_org:
                    by_cat_org[key] = []
                by_cat_org[key].append(m.period.strftime("%Y年%m月"))
            
            for key, months in sorted(by_cat_org.items()):
                lines.append(f"    - {key}：{', '.join(sorted(months))}")
        
        lines.append("")
        
        lines.append("A.2 数据质量提醒")
        lines.append("")
        lines.append(f"  异常提醒：{len(warnings)} 条")
        if warnings:
            lines.append("")
            for i, w in enumerate(warnings[:20]):
                lines.append(f"    {i+1}. {w}")
            if len(warnings) > 20:
                lines.append(f"    ... 还有 {len(warnings) - 20} 条")
        
        lines.append("")
        
        lines.append("A.3 建议补充材料")
        lines.append("")
        materials = self._get_supplementary_materials_zh(missing_data, warnings)
        for mat in materials:
            lines.append(f"  {mat}")
        
        lines.append("")
        
        # 附录B：排放因子清单
        lines.append("附录B：排放因子清单")
        lines.append("-" * 50)
        lines.append("")
        
        # 从实际记录中获取使用到的因子
        used_factors = {}
        for record in summary.records:
            if record.factor_key:
                key = record.factor_key
                if key not in used_factors:
                    used_factors[key] = {
                        "factor_key": key,
                        "value": record.emission_factor,
                        "categories": set(),
                    }
                used_factors[key]["categories"].add(record.category.label_zh)
        
        # 加上电力因子（如果没在记录中）
        elec_key = f"electricity_{self.config.electricity_region}"
        if elec_key not in used_factors:
            info = self.calculator.get_factor_info(elec_key)
            used_factors[elec_key] = {
                "factor_key": elec_key,
                "value": info["value"],
                "categories": {"电力"},
            }
        
        lines.append(f"  序号 | 因子名称 | 数值 | 来源 | 版本 | 适用类别")
        lines.append("  " + "-" * 65)
        
        for i, (factor_key, factor_info) in enumerate(sorted(used_factors.items())):
            info = self.calculator.get_factor_info(factor_key)
            source = info["source"] or "标准因子库"
            version = info["version"] or "default"
            value = f"{info['value']:.4f}" if isinstance(info["value"], float) else str(info["value"])
            categories = ", ".join(sorted(factor_info.get("categories", set())))
            
            lines.append(f"   {i+1:2d}  | {factor_key:<22s} | {value:>10s} | {source:<10s} | {version:<8s} | {categories}")
        
        lines.append("")
        
        return lines
    
    def _full_footer_zh(self) -> list:
        """页脚 - 中文"""
        lines = []
        
        lines.append("=" * 70)
        lines.append(f"  生成时间：{date.today().strftime('%Y年%m月%d日')}")
        lines.append(f"  报告版本：V1.0")
        lines.append(f"  排放因子：基于常用排放因子数据库（含自定义因子）")
        lines.append(f"  报告工具：carbon-audit 碳盘查工具")
        lines.append("=" * 70)
        
        return lines
    
    def _get_period_text_zh(self, start_date: Optional[date], 
                            end_date: Optional[date], 
                            summary: EmissionSummary) -> tuple:
        """获取中文期间文本和报告年度"""
        # 从数据中推断年度
        report_year = self.config.reporting_year
        if summary.records:
            report_year = summary.records[0].period.year
        
        if start_date and end_date:
            period_text = f"{start_date.strftime('%Y年%m月%d日')} 至 {end_date.strftime('%Y年%m月%d日')}"
            report_year = start_date.year
        elif start_date:
            period_text = f"{start_date.strftime('%Y年%m月%d日')} 至 {report_year}年12月31日"
            report_year = start_date.year
        elif end_date:
            period_text = f"{report_year}年01月01日 至 {end_date.strftime('%Y年%m月%d日')}"
            report_year = end_date.year
        else:
            period_text = f"{report_year}年度"
        
        return period_text, report_year
    
    def _get_period_text_en(self, start_date: Optional[date], 
                            end_date: Optional[date], 
                            summary: EmissionSummary) -> tuple:
        """获取英文期间文本和报告年度"""
        # 从数据中推断年度
        report_year = self.config.reporting_year
        if summary.records:
            report_year = summary.records[0].period.year
        
        if start_date and end_date:
            period_text = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            report_year = start_date.year
        elif start_date:
            period_text = f"{start_date.strftime('%Y-%m-%d')} to {report_year}-12-31"
            report_year = start_date.year
        elif end_date:
            period_text = f"{report_year}-01-01 to {end_date.strftime('%Y-%m-%d')}"
            report_year = end_date.year
        else:
            period_text = f"Year {report_year}"
        
        return period_text, report_year
    
    def _get_categories_by_scope(self, summary: EmissionSummary, scope: Scope) -> list:
        """获取指定范围的排放源类别"""
        result = []
        for cat_key in summary.by_category.keys():
            try:
                cat = EnergyCategory(cat_key)
                if cat.scope == scope:
                    result.append(cat_key)
            except ValueError:
                pass
        return result
    
    # ======== 完整版报告 - 英文 ========
    
    def _generate_full_english_report(self, summary: EmissionSummary, 
                                       records: list, unit: str,
                                       org_unit: Optional[str],
                                       start_date: Optional[date],
                                       end_date: Optional[date]) -> str:
        """生成英文完整版报告（简化版）"""
        lines = []
        
        # 封面
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"         {self.config.name}")
        lines.append("")
        lines.append("   Greenhouse Gas Emissions Audit Report")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")
        
        report_year = self.config.reporting_year
        period_text = f"Year {report_year}"
        if start_date or end_date:
            s = start_date.strftime("%Y-%m-%d") if start_date else f"{report_year}-01-01"
            e = end_date.strftime("%Y-%m-%d") if end_date else f"{report_year}-12-31"
            period_text = f"{s} to {e}"
        
        lines.append(f"  Report Period: {period_text}")
        if org_unit:
            lines.append(f"  Organizational Unit: {org_unit}")
        lines.append(f"  Unit: {self.unit}")
        lines.append(f"  Version: V1.0")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")
        
        # 排放总量
        total = self._convert(summary.total)
        scope1 = self._convert(summary.scope1)
        scope2 = self._convert(summary.scope2)
        scope3 = self._convert(summary.scope3)
        total_for_pct = total if total > 0 else 1
        
        lines.append("Total Emissions")
        lines.append("-" * 50)
        lines.append("")
        lines.append(f"  Total: {total:,.2f} {unit}")
        lines.append(f"  Scope 1 (Direct): {scope1:,.2f} {unit} ({scope1/total_for_pct*100:.1f}%)")
        lines.append(f"  Scope 2 (Indirect): {scope2:,.2f} {unit} ({scope2/total_for_pct*100:.1f}%)")
        lines.append(f"  Scope 3 (Other): {scope3:,.2f} {unit} ({scope3/total_for_pct*100:.1f}%)")
        lines.append("")
        
        # 按类别
        lines.append("Emissions by Category")
        lines.append("-" * 50)
        lines.append("")
        
        sorted_cats = sorted(summary.by_category.items(), key=lambda x: x[1], reverse=True)
        for cat_key, emission in sorted_cats:
            try:
                cat_label = EnergyCategory(cat_key).label_en
            except ValueError:
                cat_label = cat_key
            emission_conv = self._convert(emission)
            lines.append(f"  {cat_label}: {emission_conv:,.2f} {unit} ({emission_conv/total_for_pct*100:.1f}%)")
        
        lines.append("")
        
        # 月度趋势
        if summary.by_month:
            lines.append("Monthly Trend")
            lines.append("-" * 50)
            lines.append("")
            
            sorted_months = sorted(summary.by_month.items())
            max_emission = max(summary.by_month.values()) if summary.by_month else 1
            
            for month, emission in sorted_months:
                emission_conv = self._convert(emission)
                bar_len = int(emission / max_emission * 25) if max_emission > 0 else 0
                bar = "█" * bar_len
                lines.append(f"  {month}  {bar} {emission_conv:,.2f} {unit}")
            
            lines.append("")
        
        # 数据质量
        lines.append("Data Quality Appendix")
        lines.append("-" * 50)
        lines.append("")
        
        missing_data, warnings = self.checker.check_all()
        if org_unit:
            missing_data = [m for m in missing_data if m.org_unit == org_unit]
            warnings = [w for w in warnings if org_unit in w]
        
        lines.append(f"  Missing data items: {len(missing_data)}")
        lines.append(f"  Data warnings: {len(warnings)}")
        lines.append("")
        
        # 页脚
        lines.append("=" * 70)
        lines.append(f"  Generated: {date.today().strftime('%Y-%m-%d')}")
        lines.append(f"  Emission Factors: Standard database (with custom factors)")
        lines.append("=" * 70)
        
        return "\n".join(lines)
