"""碳盘查命令行工具 - 主入口"""

import os
import sys
import click
from datetime import datetime, date

from .config import ProjectConfig, is_project_dir, get_project_dir
from .data_store import DataStore
from .importers import get_importer
from .calculator import EmissionCalculator
from .checker import DataChecker
from .reporter import ReportGenerator
from .comparator import YearComparator
from .models import EnergyCategory
from . import __version__


# 自定义异常类，用于优雅地处理错误
class CarbonAuditError(click.ClickException):
    pass


def require_project():
    """检查是否在项目目录中"""
    project_dir = get_project_dir()
    if not is_project_dir(project_dir):
        raise CarbonAuditError(
            "未找到项目配置文件，请先运行 'carbon-audit init' 创建项目"
        )
    return project_dir


@click.group()
@click.version_option(version=__version__, prog_name="carbon-audit")
def main():
    """企业碳盘查命令行工具
    
    用于批量整理客户提供的能耗文件，计算温室气体排放。
    
    命令列表：
      init     初始化碳盘查项目
      import   导入能耗数据文件
      check    检查数据完整性和格式
      calc     计算排放量
      report   生成盘查报告
      compare  比较不同年度数据
    """
    pass


# ==================== init 命令 ====================
@main.command()
@click.option("--name", "-n", required=True, help="项目名称")
@click.option("--year", "-y", type=int, default=datetime.now().year, 
              help="报告年度 (默认: 当前年份)")
@click.option("--base-year", type=int, default=None, help="基准年度")
@click.option("--language", "-l", type=click.Choice(["zh", "en"]), 
              default="zh", help="报告语言 (默认: zh)")
@click.option("--unit", "-u", type=click.Choice(["tCO2e", "kgCO2e", "gCO2e"]),
              default="tCO2e", help="排放单位 (默认: tCO2e)")
@click.option("--electricity-region", "-r", 
              type=click.Choice([
                  "national", "north", "northeast", "east", 
                  "central", "south", "southwest", "northwest"
              ]),
              default="national", help="电力区域排放因子 (默认: national)")
@click.option("--force", "-f", is_flag=True, help="强制覆盖现有项目")
def init(name, year, base_year, language, unit, electricity_region, force):
    """初始化一个新的碳盘查项目
    
    创建项目目录结构和配置文件。
    """
    project_dir = get_project_dir()
    
    # 检查是否已存在项目
    if is_project_dir(project_dir) and not force:
        raise CarbonAuditError(
            "当前目录已存在项目，使用 --force 选项覆盖"
        )
    
    # 创建目录结构
    dirs = [
        "config",
        "data/raw",
        "data/processed",
        "reports",
        "templates",
    ]
    
    for d in dirs:
        dir_path = os.path.join(project_dir, d)
        os.makedirs(dir_path, exist_ok=True)
    
    # 创建配置
    config = ProjectConfig(
        name=name,
        reporting_year=year,
        base_year=base_year,
        language=language,
        unit=unit,
        electricity_region=electricity_region,
    )
    
    # 添加默认组织单元
    from .config import OrgUnit
    config.org_units = [
        OrgUnit(id="hq", name="总部", description="公司总部"),
    ]
    
    config.save(project_dir)
    
    # 创建示例数据目录说明
    readme_path = os.path.join(project_dir, "data", "raw", "README.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("""能耗数据文件存放目录

支持的文件格式：CSV、Excel (.xlsx, .xls)

支持的数据类型：
  - electricity  电力（电费）
  - gas          天然气（燃气）
  - gasoline     汽油
  - diesel       柴油
  - lpg          液化石油气
  - refrigerant  冷媒/制冷剂
  - air_travel   航空差旅
  - rail_travel  铁路差旅
  - road_travel  公路差旅
  - hotel        酒店住宿

文件格式要求（CSV/Excel）：
  电力: 日期, 用电量, [组织单元], [描述]
  燃气: 日期, 用气量, [组织单元], [描述]
  燃油: 日期, 用量, [组织单元], [描述]
  冷媒: 日期, 冷媒类型, 泄漏量, [组织单元], [描述]
  差旅: 日期, 人公里数, [类别], [组织单元], [描述]
  酒店: 日期, 间夜数, [组织单元], [描述]
""")
    
    click.echo(f"✓ 项目 '{name}' 已创建")
    click.echo(f"  目录: {project_dir}")
    click.echo(f"  报告年度: {year}")
    click.echo(f"  语言: {language}")
    click.echo(f"  单位: {unit}")
    click.echo("")
    click.echo("下一步：")
    click.echo("  1. 将能耗文件放入 data/raw/ 目录")
    click.echo("  2. 使用 'carbon-audit import' 命令导入数据")
    click.echo("  3. 使用 'carbon-audit check' 检查数据质量")
    click.echo("  4. 使用 'carbon-audit calc' 计算排放量")
    click.echo("  5. 使用 'carbon-audit report' 生成报告")


# ==================== import 命令 ====================
@main.command("import")
@click.argument("files", nargs=-1, type=click.Path(exists=True))
@click.option("--type", "-t", "data_type", required=True,
              type=click.Choice([
                  "electricity", "gas", "gasoline", "diesel", "lpg",
                  "refrigerant", "air_travel", "rail_travel", 
                  "road_travel", "hotel"
              ]),
              help="数据类型")
@click.option("--org-unit", "-o", default="总部", help="组织单元 (默认: 总部)")
@click.option("--dir", "-d", "directory", type=click.Path(exists=True, file_okay=False),
              help="从目录批量导入所有支持的文件")
def import_cmd(files, data_type, org_unit, directory):
    """导入能耗数据文件
    
    支持导入 CSV 和 Excel 格式的能耗数据文件。
    
    示例：
      carbon-audit import -t electricity 电费.csv
      carbon-audit import -t gas 燃气账单.xlsx
      carbon-audit import -t gasoline -d data/raw/
    """
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    data_store = DataStore(project_dir)
    
    # 收集所有文件
    all_files = list(files) if files else []
    
    if directory:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                ext = os.path.splitext(filename)[1].lower()
                if ext in [".csv", ".xlsx", ".xls"]:
                    all_files.append(filepath)
    
    if not all_files:
        raise CarbonAuditError("未指定要导入的文件")
    
    # 去重
    all_files = list(set(all_files))
    
    importer = get_importer(data_type)
    
    total_records = 0
    total_errors = 0
    all_errors = []
    
    with click.progressbar(all_files, label="导入中") as bar:
        for file_path in bar:
            records, errors = importer.import_file(file_path, org_unit)
            data_store.save_records(records, data_type)
            total_records += len(records)
            total_errors += len(errors)
            all_errors.extend(errors)
    
    # 持久化保存导入错误
    if all_errors:
        data_store.save_import_errors(all_errors, data_type)
    
    click.echo("")
    click.echo(f"✓ 导入完成")
    click.echo(f"  成功导入: {total_records} 条记录")
    click.echo(f"  错误: {total_errors} 条")
    
    if all_errors:
        click.echo("")
        click.echo("错误详情（已保存，可运行 check 命令查看）：")
        for err in all_errors[:20]:
            location = f"{err.file}"
            if err.sheet:
                location += f" [{err.sheet}]"
            if err.line_number > 0:
                location += f" 第{err.line_number}行"
            click.echo(f"  - {location}: {err.message}")
        
        if len(all_errors) > 20:
            click.echo(f"  ... 还有 {len(all_errors) - 20} 条错误")
    
    click.echo("")
    click.echo(f"提示：运行 'carbon-audit check' 检查数据完整性")


# ==================== check 命令 ====================
@main.command()
@click.option("--year", "-y", type=int, help="检查年度 (默认: 项目报告年度)")
@click.option("--org-unit", "-o", help="按组织单元过滤")
@click.option("--include-errors/--no-errors", default=True, 
              help="是否显示导入错误 (默认: 显示)")
@click.option("--output", "-O", type=click.Path(), help="输出检查报告到文件")
@click.option("--format", "-f", "output_format", 
              type=click.Choice(["text", "markdown", "excel"]),
              default="text", help="输出格式 (默认: text)")
def check(year, org_unit, include_errors, output, output_format):
    """检查数据完整性和格式问题
    
    按月份检查缺项和格式问题，列出异常行位置，
    支持导出 Markdown 或 Excel 格式的检查清单。
    """
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    data_store = DataStore(project_dir)
    
    check_year = year or config.reporting_year
    checker = DataChecker(config, data_store)
    
    # 数据完整性检查
    missing, warnings = checker.check_all()
    missing = [m for m in missing if m.period.year == check_year]
    
    # 按组织单元过滤
    if org_unit:
        missing = [m for m in missing if m.org_unit == org_unit]
        warnings = [w for w in warnings if org_unit in w]
    
    # 获取导入错误
    import_errors = []
    if include_errors:
        import_errors = data_store.load_import_errors()
        if org_unit:
            import_errors = [e for e in import_errors if org_unit in e.message]
    
    # 生成报告
    if output_format == "excel":
        # Excel 格式导出
        _export_check_excel(
            output or f"data_quality_check_{check_year}.xlsx",
            missing, warnings, import_errors, check_year, org_unit, data_store
        )
        click.echo(f"✓ 检查报告已导出到: {output or f'data_quality_check_{check_year}.xlsx'}")
        return
    
    # 文本/Markdown 格式
    report_text = _generate_check_report(
        check_year, org_unit, missing, warnings, import_errors, 
        data_store, output_format == "markdown"
    )
    
    # 输出
    if output:
        output_dir = os.path.dirname(os.path.abspath(output))
        os.makedirs(output_dir, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write(report_text)
        click.echo(f"✓ 检查报告已保存到: {output}")
    else:
        click.echo(report_text)


def _generate_check_report(year, org_unit, missing, warnings, import_errors,
                          data_store, is_markdown=False) -> str:
    """生成检查报告文本"""
    lines = []
    
    title = f"数据质量检查报告 - {year}年"
    if org_unit:
        title += f"（{org_unit}）"
    
    if is_markdown:
        lines.append(f"# {title}")
        lines.append("")
    else:
        lines.append("=" * 60)
        lines.append(f"  {title}")
        lines.append("=" * 60)
        lines.append("")
    
    # 一、已导入文件
    h2_prefix = "## " if is_markdown else ""
    sep = "---" if is_markdown else "-" * 40
    
    imported_files = data_store.get_imported_files()
    
    lines.append(f"{h2_prefix}一、已导入文件")
    lines.append(sep)
    lines.append("")
    
    if imported_files:
        for cat, files in sorted(imported_files.items()):
            try:
                cat_label = EnergyCategory(cat).label_zh
            except ValueError:
                cat_label = cat
            lines.append(f"**{cat_label}**：" if is_markdown else f"  {cat_label}:")
            for f in files:
                lines.append(f"  - {os.path.basename(f)}")
            lines.append("")
    else:
        lines.append("  （暂无导入数据）")
        lines.append("")
    
    # 二、缺失数据
    lines.append(f"{h2_prefix}二、缺失数据（按月份）")
    lines.append(sep)
    lines.append("")
    
    if missing:
        by_key = {}
        for m in missing:
            key = (m.category.label_zh, m.org_unit)
            if key not in by_key:
                by_key[key] = []
            by_key[key].append(m.period.strftime("%m月"))
        
        for (cat, ou), months in sorted(by_key.items()):
            lines.append(f"  **{cat} - {ou}**：" if is_markdown else f"  {cat} - {ou}:")
            lines.append(f"    缺失月份: {', '.join(sorted(months))}")
            lines.append("")
        
        lines.append(f"  总计: {len(missing)} 项缺失")
    else:
        lines.append("  ✓ 数据完整，无缺失")
    lines.append("")
    
    # 三、数据异常
    lines.append(f"{h2_prefix}三、数据异常提醒")
    lines.append(sep)
    lines.append("")
    
    if warnings:
        for w in warnings[:30]:
            lines.append(f"  ⚠ {w}")
        if len(warnings) > 30:
            lines.append(f"  ... 还有 {len(warnings) - 30} 条提醒")
    else:
        lines.append("  ✓ 未发现数据异常")
    lines.append("")
    
    # 四、导入错误记录
    lines.append(f"{h2_prefix}四、导入错误记录")
    lines.append(sep)
    lines.append("")
    
    if import_errors:
        # 按文件分组
        by_file = {}
        for e in import_errors:
            key = e.file
            if key not in by_file:
                by_file[key] = []
            by_file[key].append(e)
        
        for file_path, errors in sorted(by_file.items()):
            lines.append(f"  **{os.path.basename(file_path)}**：" 
                        if is_markdown else f"  {os.path.basename(file_path)}:")
            
            for e in errors[:10]:
                location = ""
                if e.sheet:
                    location += f"[{e.sheet}] "
                if e.line_number > 0:
                    location += f"第{e.line_number}行 "
                lines.append(f"    - {location}{e.message}")
            
            if len(errors) > 10:
                lines.append(f"    ... 还有 {len(errors) - 10} 条错误")
            lines.append("")
        
        lines.append(f"  总计: {len(import_errors)} 条导入错误")
    else:
        lines.append("  ✓ 无导入错误记录")
    lines.append("")
    
    # 五、补充材料清单
    lines.append(f"{h2_prefix}五、补充材料清单")
    lines.append(sep)
    lines.append("")
    
    materials = _get_supplementary_materials_list(missing, warnings)
    for mat in materials:
        lines.append(f"  {mat}")
    lines.append("")
    
    if not is_markdown:
        lines.append("=" * 60)
    
    return "\n".join(lines)


def _get_supplementary_materials_list(missing, warnings) -> list:
    """获取补充材料清单"""
    materials = []
    
    if missing:
        materials.append("**待补数据文件：**" if False else "待补数据文件：")
        by_cat = {}
        for m in missing:
            cat = m.category.label_zh
            if cat not in by_cat:
                by_cat[cat] = set()
            by_cat[cat].add(m.period.strftime("%Y年%m月"))
        
        for cat, months in sorted(by_cat.items()):
            materials.append(f"  - {cat}：{', '.join(sorted(months))} 数据")
    
    if warnings:
        materials.append("")
        materials.append("**需核实的数据：**" if False else "需核实的数据：")
        for w in warnings[:10]:
            materials.append(f"  - {w}")
    
    materials.append("")
    materials.append("**建议收集的证明材料：**" if False else "建议收集的证明材料：")
    materials.append("  1. 电费账单/缴费凭证")
    materials.append("  2. 燃气费账单/缴费凭证")
    materials.append("  3. 燃油采购发票")
    materials.append("  4. 冷媒采购/充装记录")
    materials.append("  5. 差旅报销凭证")
    materials.append("  6. 组织架构图")
    materials.append("  7. 设备清单及使用记录")
    
    return materials


def _export_check_excel(output_path, missing, warnings, import_errors,
                       year, org_unit, data_store):
    """导出检查报告到 Excel"""
    import pandas as pd
    from datetime import datetime
    
    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Sheet 1: 概览
        overview_data = {
            "项目": ["报告年度", "组织单元", "缺失数据项", "异常提醒数", "导入错误数", "生成时间"],
            "内容": [
                f"{year}年",
                org_unit or "全部",
                len(missing),
                len(warnings),
                len(import_errors),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
        }
        pd.DataFrame(overview_data).to_excel(writer, sheet_name="概览", index=False)
        
        # Sheet 2: 缺失数据
        if missing:
            missing_data = []
            for m in missing:
                missing_data.append({
                    "能源类别": m.category.label_zh,
                    "组织单元": m.org_unit,
                    "缺失月份": m.period.strftime("%Y年%m月"),
                    "原因": m.reason,
                })
            pd.DataFrame(missing_data).to_excel(writer, sheet_name="缺失数据", index=False)
        
        # Sheet 3: 异常提醒
        if warnings:
            warn_data = [{"序号": i+1, "异常描述": w} for i, w in enumerate(warnings)]
            pd.DataFrame(warn_data).to_excel(writer, sheet_name="异常提醒", index=False)
        
        # Sheet 4: 导入错误
        if import_errors:
            err_data = []
            for e in import_errors:
                err_data.append({
                    "文件": os.path.basename(e.file),
                    "工作表": e.sheet or "",
                    "行号": e.line_number,
                    "错误类型": e.error_type,
                    "错误信息": e.message,
                })
            pd.DataFrame(err_data).to_excel(writer, sheet_name="导入错误", index=False)
        
        # Sheet 5: 补充材料清单
        materials = _get_supplementary_materials_list(missing, warnings)
        mat_data = [{"序号": i+1, "材料/事项": m} for i, m in enumerate(materials)]
        pd.DataFrame(mat_data).to_excel(writer, sheet_name="补充材料清单", index=False)


# ==================== calc 命令 ====================
@main.command()
@click.option("--year", "-y", type=int, help="计算年度 (默认: 项目报告年度)")
@click.option("--org-unit", "-o", help="按组织单元过滤")
@click.option("--export", "-e", type=click.Path(), 
              help="导出计算结果到 Excel 文件")
@click.option("--unit", "-u", 
              type=click.Choice(["tCO2e", "kgCO2e", "gCO2e", "t", "kg", "g"]),
              help="输出单位 (默认: 项目配置)")
def calc(year, org_unit, export, unit):
    """计算温室气体排放量
    
    批量换算排放量，按范围一、范围二、范围三汇总。
    """
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    data_store = DataStore(project_dir)
    
    calc_year = year or config.reporting_year
    output_unit = unit or config.unit
    
    calculator = EmissionCalculator(config)
    
    # 获取记录
    records = data_store.get_records_by_year(calc_year)
    
    if org_unit:
        records = [r for r in records if r.org_unit == org_unit]
    
    if not records:
        raise CarbonAuditError(
            f"未找到{calc_year}年的数据，请先导入数据"
        )
    
    # 计算排放量
    records = calculator.calculate_emissions(records)
    
    # 保存更新后的记录（带排放量）
    # 获取所有记录，更新这部分
    all_records = data_store.load_records()
    
    # 更新对应年份的记录
    record_map = {}
    for r in records:
        key = (r.source_file, r.line_number, r.category.value)
        record_map[key] = r
    
    updated_records = []
    for r in all_records:
        key = (r.source_file, r.line_number, r.category.value)
        if key in record_map:
            updated_records.append(record_map[key])
        else:
            updated_records.append(r)
    
    # 保存
    import pickle
    with open(data_store.records_file, "wb") as f:
        pickle.dump(updated_records, f)
    
    # 生成汇总
    summary = calculator.summarize(records)
    
    # 显示结果
    def conv(value):
        return calculator.convert_unit(value, output_unit)
    
    click.echo("=" * 60)
    click.echo(f"  排放计算结果 - {calc_year}年")
    click.echo("=" * 60)
    click.echo("")
    
    total = conv(summary.total)
    click.echo(f"  总排放量: {total:,.2f} {output_unit}")
    click.echo("")
    
    click.echo("按排放范围：")
    click.echo(f"  范围一: {conv(summary.scope1):,.2f} {output_unit} "
               f"({summary.scope1/summary.total*100:.1f}%)" if summary.total > 0 else "")
    click.echo(f"  范围二: {conv(summary.scope2):,.2f} {output_unit} "
               f"({summary.scope2/summary.total*100:.1f}%)" if summary.total > 0 else "")
    click.echo(f"  范围三: {conv(summary.scope3):,.2f} {output_unit} "
               f"({summary.scope3/summary.total*100:.1f}%)" if summary.total > 0 else "")
    click.echo("")
    
    click.echo("按能源类别：")
    for cat, emission in sorted(summary.by_category.items(), key=lambda x: x[1], reverse=True):
        try:
            cat_label = EnergyCategory(cat).label_zh
        except ValueError:
            cat_label = cat
        click.echo(f"  {cat_label}: {conv(emission):,.2f} {output_unit} "
                   f"({emission/summary.total*100:.1f}%)" if summary.total > 0 else "")
    click.echo("")
    
    click.echo(f"共处理 {len(records)} 条记录")
    click.echo("")
    
    # 导出
    if export:
        data_store.export_to_excel(export)
        click.echo(f"✓ 结果已导出到: {export}")
    
    click.echo("提示：运行 'carbon-audit report' 生成详细报告")


# ==================== report 命令 ====================
@main.command()
@click.option("--year", "-y", type=int, help="报告年度 (默认: 项目报告年度)")
@click.option("--org-unit", "-o", help="按组织单元过滤")
@click.option("--language", "-l", type=click.Choice(["zh", "en"]),
              help="报告语言 (默认: 项目配置)")
@click.option("--unit", "-u", 
              type=click.Choice(["tCO2e", "kgCO2e", "gCO2e", "t", "kg", "g"]),
              help="排放单位 (默认: 项目配置)")
@click.option("--start-date", type=str, help="开始日期 (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="结束日期 (YYYY-MM-DD)")
@click.option("--output", "-O", type=click.Path(), help="输出文件路径")
@click.option("--with-materials", is_flag=True, help="包含补充材料清单")
@click.option("--format", "-f", "output_format", 
              type=click.Choice(["text", "markdown"]),
              default="text", help="输出格式 (默认: text)")
def report(year, org_unit, language, unit, start_date, end_date, 
           output, with_materials, output_format):
    """生成碳盘查报告
    
    生成可发送给客户的盘查摘要，支持按组织单元过滤，
    输出补充材料清单。
    """
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    data_store = DataStore(project_dir)
    
    report_year = year or config.reporting_year
    report_language = language or config.language
    report_unit = unit or config.unit
    
    # 解析日期
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise CarbonAuditError(f"无效的开始日期格式: {start_date}，请使用 YYYY-MM-DD")
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise CarbonAuditError(f"无效的结束日期格式: {end_date}，请使用 YYYY-MM-DD")
    
    # 获取记录并计算
    calculator = EmissionCalculator(config)
    records = data_store.get_records_by_year(report_year)
    
    if not records:
        raise CarbonAuditError(
            f"未找到{report_year}年的数据，请先导入并计算"
        )
    
    # 确保排放量已计算
    records = calculator.calculate_emissions(records)
    summary = calculator.summarize(records)
    
    # 生成报告
    checker = DataChecker(config, data_store)
    reporter = ReportGenerator(config, summary, checker, 
                            language=report_language, unit=report_unit)
    
    # 确定输出路径
    if not output:
        report_dir = os.path.join(project_dir, "reports")
        os.makedirs(report_dir, exist_ok=True)
        filename = reporter.get_default_filename(report_year, org_unit, output_format)
        output = os.path.join(report_dir, filename)
    
    # 生成报告
    report_text = reporter.generate_summary_report(
        output_path=output,
        org_unit=org_unit,
        start_date=start_dt,
        end_date=end_dt,
        output_format=output_format,
    )
    
    click.echo(f"✓ 报告已生成: {output}")
    click.echo("")
    click.echo(report_text)


# ==================== compare 命令 ====================
@main.command()
@click.argument("year1", type=int)
@click.argument("year2", type=int)
@click.option("--org-unit", "-o", help="按组织单元过滤")
@click.option("--language", "-l", type=click.Choice(["zh", "en"]),
              help="报告语言 (默认: 项目配置)")
@click.option("--unit", "-u", 
              type=click.Choice(["tCO2e", "kgCO2e", "gCO2e", "t", "kg", "g"]),
              help="排放单位 (默认: 项目配置)")
@click.option("--output", "-O", type=click.Path(), help="输出文件路径")
def compare(year1, year2, org_unit, language, unit, output):
    """比较两个年度的排放数据
    
    比较不同年度的变化，分析增减趋势。
    
    示例：
      carbon-audit compare 2023 2024
      carbon-audit compare 2023 2024 -o 总部
    """
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    data_store = DataStore(project_dir)
    
    report_language = language or config.language
    report_unit = unit or config.unit
    
    comparator = YearComparator(config, data_store)
    
    # 执行比较
    comparison = comparator.compare_years(year1, year2, org_unit)
    
    # 格式化报告
    report_text = comparator.format_comparison_report(
        comparison, report_language, report_unit
    )
    
    # 输出
    if output:
        os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", 
                    exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write(report_text)
        click.echo(f"✓ 对比报告已保存到: {output}")
    
    click.echo(report_text)


# ==================== 辅助命令 ====================
@main.command("list")
@click.option("--type", "-t", "list_type", 
              type=click.Choice(["files", "categories", "org-units", "years"]),
              default="files", help="列出类型")
def list_cmd(list_type):
    """列出项目中的数据信息"""
    project_dir = require_project()
    data_store = DataStore(project_dir)
    
    if list_type == "files":
        files = data_store.get_imported_files()
        click.echo("已导入的文件：")
        if files:
            for cat, file_list in files.items():
                try:
                    cat_label = EnergyCategory(cat).label_zh
                except ValueError:
                    cat_label = cat
                click.echo(f"  {cat_label}:")
                for f in file_list:
                    click.echo(f"    - {f}")
        else:
            click.echo("  （暂无）")
    
    elif list_type == "categories":
        categories = data_store.get_categories()
        click.echo("数据类别：")
        for cat in categories:
            try:
                cat_label = EnergyCategory(cat).label_zh
            except ValueError:
                cat_label = cat
            click.echo(f"  - {cat_label} ({cat})")
    
    elif list_type == "org-units":
        org_units = data_store.get_org_units()
        click.echo("组织单元：")
        for ou in org_units:
            click.echo(f"  - {ou}")
    
    elif list_type == "years":
        years = data_store.get_years()
        click.echo("数据年份：")
        for y in years:
            click.echo(f"  - {y}年")


# ==================== factors 命令组 ====================
@main.group()
def factors():
    """排放因子库管理
    
    查看和管理项目中的排放因子，支持自定义因子。
    """
    pass


@factors.command("list")
@click.option("--scope", "-s", 
              type=click.Choice(["all", "scope1", "scope2", "scope3"]),
              default="all", help="按范围筛选 (默认: all)")
@click.option("--include-custom/--no-custom", default=True,
              help="是否显示自定义因子 (默认: 显示)")
def factors_list(scope, include_custom):
    """列出所有排放因子"""
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    
    from .emission_factors import (
        SCOPE1_FACTORS, SCOPE2_FACTORS, SCOPE3_FACTORS,
        REFRIGERANT_TYPES
    )
    
    all_factors = {}
    if scope in ["all", "scope1"]:
        for k, v in SCOPE1_FACTORS.items():
            all_factors[k] = {"value": v, "scope": "scope1", "custom": False}
    if scope in ["all", "scope2"]:
        for k, v in SCOPE2_FACTORS.items():
            all_factors[k] = {"value": v, "scope": "scope2", "custom": False}
    if scope in ["all", "scope3"]:
        for k, v in SCOPE3_FACTORS.items():
            all_factors[k] = {"value": v, "scope": "scope3", "custom": False}
    
    # 标记自定义因子
    custom_factors = config.custom_factors or {}
    for key, value in custom_factors.items():
        if key in all_factors:
            all_factors[key]["custom"] = True
            all_factors[key]["custom_value"] = value
        else:
            all_factors[key] = {"value": value, "scope": "custom", "custom": True}
    
    click.echo("=" * 70)
    click.echo(f"  排放因子列表 - {config.name}")
    click.echo("=" * 70)
    click.echo("")
    
    # 按范围分组显示
    scopes = ["scope1", "scope2", "scope3", "custom"]
    scope_labels = {
        "scope1": "范围一（直接排放）",
        "scope2": "范围二（间接排放）",
        "scope3": "范围三（其他间接）",
        "custom": "自定义因子",
    }
    
    for s in scopes:
        scope_factors = {k: v for k, v in all_factors.items() if v["scope"] == s}
        if not scope_factors:
            continue
        
        click.echo(f"【{scope_labels[s]}】")
        click.echo("-" * 50)
        
        for key in sorted(scope_factors.keys()):
            info = scope_factors[key]
            default_val = info["value"]
            custom_mark = ""
            current_val = default_val
            
            if info.get("custom") and include_custom:
                custom_mark = " *"
                current_val = info.get("custom_value", default_val)
            
            # 格式化显示
            if current_val >= 100:
                val_str = f"{current_val:,.1f}"
            else:
                val_str = f"{current_val:.4f}".rstrip('0').rstrip('.')
            
            click.echo(f"  {key:<35s} {val_str:>10s}{custom_mark}")
        
        click.echo("")
    
    # 当前电力区域
    click.echo("-" * 50)
    elec_key = f"electricity_{config.electricity_region}"
    elec_factor = all_factors.get(elec_key, {}).get("value", 0)
    click.echo(f"当前电力区域：{config.electricity_region}")
    click.echo(f"电力排放因子：{elec_factor} kgCO2e/kWh")
    click.echo("")
    
    if include_custom and custom_factors:
        click.echo("  * 标记表示已设置为自定义值")
        click.echo("")
    
    click.echo("提示：使用 'carbon-audit factors set <因子名> <值>' 设置自定义因子")
    click.echo("      使用 'carbon-audit factors reset <因子名>' 恢复默认值")


@factors.command("set")
@click.argument("factor_key")
@click.argument("value", type=float)
def factors_set(factor_key, value):
    """设置自定义排放因子
    
    FACTOR_KEY: 因子名称（如 electricity_national, natural_gas, refrigerant_r22）
    VALUE: 排放因子值（kgCO2e/单位）
    """
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    
    # 验证因子名称
    from .emission_factors import (
        SCOPE1_FACTORS, SCOPE2_FACTORS, SCOPE3_FACTORS
    )
    all_known = {**SCOPE1_FACTORS, **SCOPE2_FACTORS, **SCOPE3_FACTORS}
    
    if factor_key not in all_known:
        click.echo(f"⚠  警告：因子 '{factor_key}' 不在标准因子库中，将作为自定义因子保存")
    
    # 保存自定义因子
    if not config.custom_factors:
        config.custom_factors = {}
    
    old_value = config.custom_factors.get(factor_key, all_known.get(factor_key, 0))
    config.custom_factors[factor_key] = value
    config.save(project_dir)
    
    click.echo(f"✓ 已设置排放因子")
    click.echo(f"  因子名称：{factor_key}")
    click.echo(f"  原值：{old_value}")
    click.echo(f"  新值：{value}")
    click.echo("")
    click.echo("提示：运行 'carbon-audit calc' 重新计算排放量")


@factors.command("reset")
@click.argument("factor_key", required=False)
@click.option("--all", "-a", "reset_all", is_flag=True, help="重置所有自定义因子")
def factors_reset(factor_key, reset_all):
    """重置排放因子为默认值
    
    FACTOR_KEY: 要重置的因子名称（可选，不指定则需 --all）
    """
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    
    if not config.custom_factors:
        click.echo("当前没有自定义因子，无需重置")
        return
    
    if reset_all:
        count = len(config.custom_factors)
        config.custom_factors = {}
        config.save(project_dir)
        click.echo(f"✓ 已重置所有 {count} 个自定义因子")
        return
    
    if not factor_key:
        raise CarbonAuditError("请指定要重置的因子名称，或使用 --all 重置全部")
    
    if factor_key not in config.custom_factors:
        click.echo(f"因子 '{factor_key}' 没有自定义值，无需重置")
        return
    
    del config.custom_factors[factor_key]
    config.save(project_dir)
    click.echo(f"✓ 已重置因子 '{factor_key}' 为默认值")


@factors.command("electricity")
@click.argument("region", type=click.Choice([
    "national", "north", "northeast", "east", 
    "central", "south", "southwest", "northwest"
]))
def factors_electricity(region):
    """设置电力排放因子区域
    
    REGION: 电网区域（national/north/northeast/east/central/south/southwest/northwest）
    """
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    
    old_region = config.electricity_region
    config.electricity_region = region
    config.save(project_dir)
    
    from .emission_factors import SCOPE2_FACTORS
    
    old_factor = SCOPE2_FACTORS.get(f"electricity_{old_region}", 0)
    new_factor = SCOPE2_FACTORS.get(f"electricity_{region}", 0)
    
    click.echo(f"✓ 已切换电力排放因子区域")
    click.echo(f"  原区域：{old_region} ({old_factor} kgCO2e/kWh)")
    click.echo(f"  新区域：{region} ({new_factor} kgCO2e/kWh)")
    click.echo("")
    click.echo("提示：运行 'carbon-audit calc' 重新计算排放量")


@factors.command("refrigerants")
def factors_refrigerants():
    """列出所有冷媒排放因子（GWP值）"""
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    
    from .emission_factors import REFRIGERANT_TYPES, SCOPE1_FACTORS
    
    click.echo("=" * 60)
    click.echo("  冷媒排放因子（GWP值）")
    click.echo("=" * 60)
    click.echo("")
    
    click.echo(f"{'冷媒型号':<15s} {'因子Key':<25s} {'GWP值':>10s}")
    click.echo("-" * 60)
    
    for refrigerant, factor_key in sorted(REFRIGERANT_TYPES.items()):
        gwp = SCOPE1_FACTORS.get(factor_key, 0)
        
        # 检查是否有自定义值
        if config.custom_factors and factor_key in config.custom_factors:
            gwp = config.custom_factors[factor_key]
            mark = " *"
        else:
            mark = ""
        
        click.echo(f"{refrigerant:<15s} {factor_key:<25s} {gwp:>10,.0f}{mark}")
    
    click.echo("")
    if config.custom_factors:
        click.echo("  * 标记为自定义值")
    click.echo("")
    click.echo("提示：使用 'carbon-audit factors set refrigerant_r22 1800' 修改冷媒GWP值")


if __name__ == "__main__":
    main()
