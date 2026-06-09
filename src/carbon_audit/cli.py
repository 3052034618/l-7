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
    
    click.echo("")
    click.echo(f"✓ 导入完成")
    click.echo(f"  成功导入: {total_records} 条记录")
    click.echo(f"  错误: {total_errors} 条")
    
    if all_errors:
        click.echo("")
        click.echo("错误详情：")
        for err in all_errors[:20]:  # 只显示前20条
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
@click.option("--format-only", is_flag=True, help="只检查文件格式")
@click.option("--output", "-O", type=click.Path(), help="输出检查报告到文件")
def check(year, org_unit, format_only, output):
    """检查数据完整性和格式问题
    
    按月份检查缺项和格式问题，列出异常行位置。
    """
    project_dir = require_project()
    config = ProjectConfig.load(project_dir)
    data_store = DataStore(project_dir)
    
    check_year = year or config.reporting_year
    
    checker = DataChecker(config, data_store)
    
    # 检查已导入的文件
    imported_files = data_store.get_imported_files()
    
    lines = []
    lines.append("=" * 60)
    lines.append(f"  数据质量检查报告 - {check_year}年")
    lines.append("=" * 60)
    lines.append("")
    
    # 已导入文件
    lines.append("一、已导入文件")
    lines.append("-" * 40)
    
    if imported_files:
        for cat, files in imported_files.items():
            try:
                cat_label = EnergyCategory(cat).label_zh
            except ValueError:
                cat_label = cat
            lines.append(f"  {cat_label}:")
            for f in files:
                lines.append(f"    - {os.path.basename(f)}")
    else:
        lines.append("  （暂无导入数据）")
    lines.append("")
    
    # 数据完整性检查
    if not format_only:
        missing, warnings = checker.check_all()
        
        # 过滤年度
        missing = [m for m in missing if m.period.year == check_year]
        
        lines.append("二、缺失数据（按月份）")
        lines.append("-" * 40)
        
        if missing:
            # 按类别和组织单元分组
            by_key = {}
            for m in missing:
                key = (m.category.label_zh, m.org_unit)
                if key not in by_key:
                    by_key[key] = []
                by_key[key].append(m.period.strftime("%m月"))
            
            for (cat, ou), months in sorted(by_key.items()):
                lines.append(f"  {cat} - {ou}:")
                lines.append(f"    缺失月份: {', '.join(sorted(months))}")
            
            lines.append(f"  总计: {len(missing)} 项缺失")
        else:
            lines.append("  ✓ 数据完整，无缺失")
        lines.append("")
        
        # 数据异常
        lines.append("三、数据异常提醒")
        lines.append("-" * 40)
        
        if warnings:
            for w in warnings[:20]:
                lines.append(f"  ⚠ {w}")
            if len(warnings) > 20:
                lines.append(f"  ... 还有 {len(warnings) - 20} 条提醒")
        else:
            lines.append("  ✓ 未发现数据异常")
        lines.append("")
        
        # 补充材料清单
        lines.append("四、补充材料清单")
        lines.append("-" * 40)
        materials = checker.get_supplementary_materials()
        for mat in materials:
            lines.append(f"  {mat}")
        lines.append("")
    
    lines.append("=" * 60)
    
    report_text = "\n".join(lines)
    
    # 输出
    if output:
        os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", 
                    exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write(report_text)
        click.echo(f"✓ 检查报告已保存到: {output}")
    else:
        click.echo(report_text)


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
    reporter = ReportGenerator(config, summary, checker, report_language)
    
    # 确定输出路径
    if not output:
        report_dir = os.path.join(project_dir, "reports")
        os.makedirs(report_dir, exist_ok=True)
        
        filename = f"碳盘查报告_{report_year}"
        if org_unit:
            filename += f"_{org_unit}"
        filename += f".{output_format}"
        
        output = os.path.join(report_dir, filename)
    
    # 生成报告
    report_text = reporter.generate_summary_report(
        output_path=output,
        org_unit=org_unit,
        start_date=start_dt,
        end_date=end_dt,
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


if __name__ == "__main__":
    main()
