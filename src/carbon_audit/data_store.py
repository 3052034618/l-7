"""数据存储模块 - 管理项目数据的存储和读取"""

import os
import json
import pickle
from typing import List, Dict, Optional
from datetime import date, datetime
from .models import (
    EnergyRecord, EnergyCategory, ValidationError,
    AuditLogEntry, AuditAction
)
import pandas as pd


class DataStore:
    """数据存储管理器"""
    
    def __init__(self, project_dir: str):
        self.project_dir = project_dir
        self.raw_dir = os.path.join(project_dir, "data", "raw")
        self.processed_dir = os.path.join(project_dir, "data", "processed")
        self.records_file = os.path.join(self.processed_dir, "records.pkl")
        self.import_errors_file = os.path.join(self.processed_dir, "import_errors.pkl")
        self.import_log_file = os.path.join(self.processed_dir, "import_log.json")
        self.audit_log_file = os.path.join(self.processed_dir, "audit_log.json")
        self.summary_file = os.path.join(self.processed_dir, "summary.json")
        
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
    
    def save_records(self, records: List[EnergyRecord], category: Optional[str] = None) -> None:
        """保存记录"""
        all_records = self.load_records()
        all_records.extend(records)
        
        # 去重（按源文件和行号和类别）
        seen = set()
        unique_records = []
        for r in all_records:
            key = (r.source_file, r.line_number, r.category.value)
            if key not in seen:
                seen.add(key)
                unique_records.append(r)
        
        with open(self.records_file, "wb") as f:
            pickle.dump(unique_records, f)
    
    def load_records(self) -> List[EnergyRecord]:
        """加载所有记录"""
        if not os.path.exists(self.records_file):
            return []
        
        with open(self.records_file, "rb") as f:
            return pickle.load(f)
    
    def get_records_by_category(self, category: EnergyCategory) -> List[EnergyRecord]:
        """按类别获取记录"""
        records = self.load_records()
        return [r for r in records if r.category == category]
    
    def get_records_by_org_unit(self, org_unit: str) -> List[EnergyRecord]:
        """按组织单元获取记录"""
        records = self.load_records()
        return [r for r in records if r.org_unit == org_unit]
    
    def get_records_by_year(self, year: int) -> List[EnergyRecord]:
        """按年份获取记录"""
        records = self.load_records()
        return [r for r in records if r.period.year == year]
    
    def get_records_by_month(self, year: int, month: int) -> List[EnergyRecord]:
        """按月份获取记录"""
        records = self.load_records()
        return [r for r in records if r.period.year == year and r.period.month == month]
    
    def get_categories(self) -> List[str]:
        """获取所有数据类别"""
        records = self.load_records()
        return list(set(r.category.value for r in records))
    
    def get_org_units(self) -> List[str]:
        """获取所有组织单元"""
        records = self.load_records()
        return list(set(r.org_unit for r in records))
    
    def get_years(self) -> List[int]:
        """获取所有年份"""
        records = self.load_records()
        return sorted(set(r.period.year for r in records))
    
    def get_months(self, year: int) -> List[int]:
        """获取指定年份的所有月份"""
        records = self.get_records_by_year(year)
        return sorted(set(r.period.month for r in records))
    
    def clear_category(self, category: str) -> None:
        """清除指定类别的数据"""
        all_records = self.load_records()
        all_records = [r for r in all_records if r.category.value != category]
        
        with open(self.records_file, "wb") as f:
            pickle.dump(all_records, f)
    
    def clear_all(self) -> None:
        """清除所有数据"""
        if os.path.exists(self.records_file):
            os.remove(self.records_file)
    
    def export_to_excel(self, output_path: str) -> None:
        """导出数据到 Excel"""
        records = self.load_records()
        
        data = []
        for r in records:
            data.append({
                "类别": r.category.label_zh,
                "组织单元": r.org_unit,
                "日期": r.period.strftime("%Y-%m-%d"),
                "数量": r.quantity,
                "单位": r.category.unit,
                "子类别": r.subcategory or "",
                "排放量(kgCO2e)": round(r.emission_kg, 4),
                "排放因子": r.emission_factor,
                "因子key": r.factor_key or "",
                "描述": r.description,
                "源文件": r.source_file,
                "行号": r.line_number,
            })
        
        df = pd.DataFrame(data)
        df.to_excel(output_path, index=False)
    
    def get_imported_files(self) -> Dict[str, List[str]]:
        """获取已导入的文件列表（按类别分组）"""
        records = self.load_records()
        files_by_category: Dict[str, set] = {}
        
        for r in records:
            cat = r.category.value
            if cat not in files_by_category:
                files_by_category[cat] = set()
            files_by_category[cat].add(r.source_file)
        
        return {k: sorted(list(v)) for k, v in files_by_category.items()}
    
    # ======== 导入错误持久化 ========
    
    def save_import_errors(self, errors: List[ValidationError], 
                          data_type: str, import_time: Optional[datetime] = None) -> None:
        """保存导入错误记录"""
        all_errors = self.load_import_errors()
        
        if import_time is None:
            import_time = datetime.now()
        
        # 添加时间戳和数据类型信息
        for err in errors:
            # 用字典方式存储额外信息
            if not hasattr(err, 'import_time'):
                err.import_time = import_time
                err.data_type = data_type
        
        all_errors.extend(errors)
        
        with open(self.import_errors_file, "wb") as f:
            pickle.dump(all_errors, f)
        
        # 同时更新导入日志
        self._append_import_log(data_type, len(errors), import_time)
    
    def load_import_errors(self) -> List[ValidationError]:
        """加载所有导入错误"""
        if not os.path.exists(self.import_errors_file):
            return []
        
        with open(self.import_errors_file, "rb") as f:
            return pickle.load(f)
    
    def get_import_errors_by_file(self, file_path: str) -> List[ValidationError]:
        """按文件获取导入错误"""
        all_errors = self.load_import_errors()
        return [e for e in all_errors if e.file == file_path]
    
    def get_import_errors_by_type(self, data_type: str) -> List[ValidationError]:
        """按数据类型获取导入错误"""
        all_errors = self.load_import_errors()
        return [e for e in all_errors if getattr(e, 'data_type', None) == data_type]
    
    def clear_import_errors(self) -> None:
        """清除所有导入错误记录"""
        if os.path.exists(self.import_errors_file):
            os.remove(self.import_errors_file)
        if os.path.exists(self.import_log_file):
            os.remove(self.import_log_file)
    
    def _append_import_log(self, data_type: str, error_count: int, 
                          import_time: datetime) -> None:
        """追加导入日志"""
        log = self._load_import_log()
        
        log.append({
            "time": import_time.strftime("%Y-%m-%d %H:%M:%S"),
            "data_type": data_type,
            "error_count": error_count,
        })
        
        with open(self.import_log_file, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    
    def _load_import_log(self) -> List[Dict]:
        """加载导入日志"""
        if not os.path.exists(self.import_log_file):
            return []
        
        with open(self.import_log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def get_import_log(self) -> List[Dict]:
        """获取导入日志"""
        return self._load_import_log()
    
    # ======== 审计日志 ========
    
    def add_audit_log(self, action: AuditAction, description: str,
                      details: Optional[Dict[str, str]] = None,
                      user: Optional[str] = None) -> None:
        """添加审计日志条目"""
        logs = self._load_audit_log()
        
        entry = AuditLogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            action=action,
            description=description,
            details=details or {},
            user=user,
        )
        
        logs.append({
            "timestamp": entry.timestamp,
            "action": entry.action.value,
            "description": entry.description,
            "details": entry.details,
            "user": entry.user,
        })
        
        with open(self.audit_log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    
    def _load_audit_log(self) -> List[Dict]:
        """加载审计日志"""
        if not os.path.exists(self.audit_log_file):
            return []
        
        with open(self.audit_log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def get_audit_log(self, action: Optional[AuditAction] = None,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      limit: int = 100) -> List[Dict]:
        """获取审计日志（支持过滤）
        
        Args:
            action: 按操作类型过滤
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 最多返回条数
        """
        logs = self._load_audit_log()
        
        # 过滤
        filtered = []
        for log in logs:
            # 按操作类型过滤
            if action and log["action"] != action.value:
                continue
            
            # 按日期过滤
            log_date = log["timestamp"][:10]  # YYYY-MM-DD
            if start_date and log_date < start_date:
                continue
            if end_date and log_date > end_date:
                continue
            
            filtered.append(log)
        
        # 按时间倒序，取最新的
        filtered.reverse()
        return filtered[:limit]
