"""数据导入模块 - 支持 CSV 和 Excel 文件导入"""

import os
import pandas as pd
from datetime import datetime
from typing import List, Tuple, Optional
from .models import EnergyRecord, EnergyCategory, ValidationError
from .emission_factors import REFRIGERANT_TYPES


class DataImporter:
    """数据导入器基类"""
    
    def __init__(self, category: EnergyCategory):
        self.category = category
        self.errors: List[ValidationError] = []
        self.records: List[EnergyRecord] = []
    
    def import_file(self, file_path: str, org_unit: str = "总部") -> Tuple[List[EnergyRecord], List[ValidationError]]:
        """导入文件"""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".csv":
            return self._import_csv(file_path, org_unit)
        elif ext in [".xlsx", ".xls"]:
            return self._import_excel(file_path, org_unit)
        else:
            error = ValidationError(
                file=file_path,
                sheet=None,
                line_number=0,
                error_type="format_error",
                message=f"不支持的文件格式: {ext}",
            )
            return [], [error]
    
    def _import_csv(self, file_path: str, org_unit: str) -> Tuple[List[EnergyRecord], List[ValidationError]]:
        """导入 CSV 文件"""
        try:
            df = pd.read_csv(file_path, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding="gbk")
        
        return self._parse_dataframe(df, file_path, None, org_unit)
    
    def _import_excel(self, file_path: str, org_unit: str) -> Tuple[List[EnergyRecord], List[ValidationError]]:
        """导入 Excel 文件"""
        xls = pd.ExcelFile(file_path)
        all_records: List[EnergyRecord] = []
        all_errors: List[ValidationError] = []
        
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            records, errors = self._parse_dataframe(df, file_path, sheet_name, org_unit)
            all_records.extend(records)
            all_errors.extend(errors)
        
        return all_records, all_errors
    
    def _parse_dataframe(
        self, df: pd.DataFrame, file_path: str, sheet_name: Optional[str], org_unit: str
    ) -> Tuple[List[EnergyRecord], List[ValidationError]]:
        """解析 DataFrame"""
        records: List[EnergyRecord] = []
        errors: List[ValidationError] = []
        
        # 标准化列名
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # 检查必需列
        required_cols = self._get_required_columns()
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            error = ValidationError(
                file=file_path,
                sheet=sheet_name,
                line_number=1,
                error_type="missing_column",
                message=f"缺少必需列: {', '.join(missing_cols)}",
            )
            errors.append(error)
            return records, errors
        
        # 解析每一行
        for idx, row in df.iterrows():
            line_num = idx + 2  # Excel 行号，包含表头
            
            try:
                record = self._parse_row(row, file_path, sheet_name, line_num, org_unit)
                records.append(record)
            except Exception as e:
                error = ValidationError(
                    file=file_path,
                    sheet=sheet_name,
                    line_number=line_num,
                    error_type="parse_error",
                    message=str(e),
                )
                errors.append(error)
        
        return records, errors
    
    def _get_required_columns(self) -> List[str]:
        """获取必需列名列表"""
        raise NotImplementedError
    
    def _parse_row(
        self, row: pd.Series, file_path: str, sheet_name: Optional[str], 
        line_num: int, org_unit: str
    ) -> EnergyRecord:
        """解析单行数据"""
        raise NotImplementedError
    
    def _parse_date(self, date_val) -> datetime.date:
        """解析日期"""
        if pd.isna(date_val):
            raise ValueError("日期不能为空")
        
        if isinstance(date_val, datetime):
            return date_val.date()
        if isinstance(date_val, pd.Timestamp):
            return date_val.date()
        
        date_str = str(date_val).strip()
        
        # 尝试多种日期格式
        formats = [
            "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日",
            "%Y-%m", "%Y/%m", "%Y年%m月",
            "%Y.%m.%d", "%Y.%m",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.date()
            except ValueError:
                continue
        
        raise ValueError(f"无法解析日期: {date_str}")
    
    def _parse_quantity(self, qty_val) -> float:
        """解析数量"""
        if pd.isna(qty_val):
            raise ValueError("数量不能为空")
        
        try:
            qty = float(qty_val)
            if qty < 0:
                raise ValueError("数量不能为负数")
            return qty
        except (ValueError, TypeError):
            raise ValueError(f"无法解析数量: {qty_val}")
    
    def _parse_org_unit(self, ou_val, default: str) -> str:
        """解析组织单元"""
        if pd.isna(ou_val) or str(ou_val).strip() == "":
            return default
        return str(ou_val).strip()


class ElectricityImporter(DataImporter):
    """电力数据导入器"""
    
    def __init__(self):
        super().__init__(EnergyCategory.ELECTRICITY)
    
    def _get_required_columns(self) -> List[str]:
        return ["日期", "用电量"]
    
    def _parse_row(self, row, file_path, sheet_name, line_num, org_unit) -> EnergyRecord:
        period = self._parse_date(row.get("日期"))
        quantity = self._parse_quantity(row.get("用电量"))
        ou = self._parse_org_unit(row.get("组织单元"), org_unit)
        
        return EnergyRecord(
            category=self.category,
            org_unit=ou,
            period=period,
            quantity=quantity,
            description=str(row.get("描述", "")),
            source_file=file_path,
            line_number=line_num,
        )


class GasImporter(DataImporter):
    """燃气数据导入器（天然气）"""
    
    def __init__(self):
        super().__init__(EnergyCategory.NATURAL_GAS)
    
    def _get_required_columns(self) -> List[str]:
        return ["日期", "用气量"]
    
    def _parse_row(self, row, file_path, sheet_name, line_num, org_unit) -> EnergyRecord:
        period = self._parse_date(row.get("日期"))
        quantity = self._parse_quantity(row.get("用气量"))
        ou = self._parse_org_unit(row.get("组织单元"), org_unit)
        
        return EnergyRecord(
            category=self.category,
            org_unit=ou,
            period=period,
            quantity=quantity,
            description=str(row.get("描述", "")),
            source_file=file_path,
            line_number=line_num,
        )


class FuelImporter(DataImporter):
    """燃油数据导入器（汽油、柴油等）"""
    
    def __init__(self, fuel_type: str = "gasoline"):
        category_map = {
            "gasoline": EnergyCategory.GASOLINE,
            "diesel": EnergyCategory.DIESEL,
            "lpg": EnergyCategory.LPG,
        }
        super().__init__(category_map.get(fuel_type, EnergyCategory.GASOLINE))
        self.fuel_type = fuel_type
    
    def _get_required_columns(self) -> List[str]:
        return ["日期", "用量"]
    
    def _parse_row(self, row, file_path, sheet_name, line_num, org_unit) -> EnergyRecord:
        period = self._parse_date(row.get("日期"))
        quantity = self._parse_quantity(row.get("用量"))
        ou = self._parse_org_unit(row.get("组织单元"), org_unit)
        
        return EnergyRecord(
            category=self.category,
            org_unit=ou,
            period=period,
            quantity=quantity,
            subcategory=self.fuel_type,
            description=str(row.get("描述", "")),
            source_file=file_path,
            line_number=line_num,
        )


class RefrigerantImporter(DataImporter):
    """冷媒数据导入器"""
    
    def __init__(self):
        super().__init__(EnergyCategory.REFRIGERANT)
    
    def _get_required_columns(self) -> List[str]:
        return ["日期", "冷媒类型", "泄漏量"]
    
    def _parse_row(self, row, file_path, sheet_name, line_num, org_unit) -> EnergyRecord:
        period = self._parse_date(row.get("日期"))
        quantity = self._parse_quantity(row.get("泄漏量"))
        refrigerant_type = str(row.get("冷媒类型", "")).strip()
        ou = self._parse_org_unit(row.get("组织单元"), org_unit)
        
        if not refrigerant_type:
            raise ValueError("冷媒类型不能为空")
        
        # 标准化冷媒类型
        factor_key = REFRIGERANT_TYPES.get(refrigerant_type)
        if not factor_key:
            raise ValueError(f"未知的冷媒类型: {refrigerant_type}")
        
        return EnergyRecord(
            category=self.category,
            org_unit=ou,
            period=period,
            quantity=quantity,
            subcategory=refrigerant_type,
            factor_key=factor_key,
            description=str(row.get("描述", "")),
            source_file=file_path,
            line_number=line_num,
        )


class TravelImporter(DataImporter):
    """差旅数据导入器"""
    
    def __init__(self, travel_type: str = "air"):
        category_map = {
            "air": EnergyCategory.AIR_TRAVEL,
            "rail": EnergyCategory.RAIL_TRAVEL,
            "road": EnergyCategory.ROAD_TRAVEL,
        }
        super().__init__(category_map.get(travel_type, EnergyCategory.AIR_TRAVEL))
        self.travel_type = travel_type
    
    def _get_required_columns(self) -> List[str]:
        return ["日期", "人公里数"]
    
    def _parse_row(self, row, file_path, sheet_name, line_num, org_unit) -> EnergyRecord:
        period = self._parse_date(row.get("日期"))
        quantity = self._parse_quantity(row.get("人公里数"))
        ou = self._parse_org_unit(row.get("组织单元"), org_unit)
        subcategory = str(row.get("类别", "")).strip() or None
        
        return EnergyRecord(
            category=self.category,
            org_unit=ou,
            period=period,
            quantity=quantity,
            subcategory=subcategory,
            description=str(row.get("描述", "")),
            source_file=file_path,
            line_number=line_num,
        )


class HotelImporter(DataImporter):
    """酒店住宿数据导入器"""
    
    def __init__(self):
        super().__init__(EnergyCategory.HOTEL_STAY)
    
    def _get_required_columns(self) -> List[str]:
        return ["日期", "间夜数"]
    
    def _parse_row(self, row, file_path, sheet_name, line_num, org_unit) -> EnergyRecord:
        period = self._parse_date(row.get("日期"))
        quantity = self._parse_quantity(row.get("间夜数"))
        ou = self._parse_org_unit(row.get("组织单元"), org_unit)
        
        return EnergyRecord(
            category=self.category,
            org_unit=ou,
            period=period,
            quantity=quantity,
            description=str(row.get("描述", "")),
            source_file=file_path,
            line_number=line_num,
        )


def get_importer(data_type: str) -> DataImporter:
    """根据数据类型获取导入器"""
    importers = {
        "electricity": ElectricityImporter,
        "gas": GasImporter,
        "gasoline": lambda: FuelImporter("gasoline"),
        "diesel": lambda: FuelImporter("diesel"),
        "lpg": lambda: FuelImporter("lpg"),
        "refrigerant": RefrigerantImporter,
        "air_travel": lambda: TravelImporter("air"),
        "rail_travel": lambda: TravelImporter("rail"),
        "road_travel": lambda: TravelImporter("road"),
        "hotel": HotelImporter,
    }
    
    importer_class = importers.get(data_type)
    if not importer_class:
        raise ValueError(f"未知的数据类型: {data_type}")
    
    return importer_class()
