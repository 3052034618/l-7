"""碳排放因子数据 - 基于常用排放因子数据库

排放因子单位说明：
- 电力：kg CO2e/kWh
- 天然气：kg CO2e/m³
- 汽油：kg CO2e/L
- 柴油：kg CO2e/L
- 冷媒：kg CO2e/kg
- 航空差旅：kg CO2e/人·km
- 铁路差旅：kg CO2e/人·km
- 公路差旅：kg CO2e/人·km
"""

# 范围一：直接排放
SCOPE1_FACTORS = {
    "natural_gas": 2.1622,      # 天然气 kg CO2e/m³
    "gasoline": 2.361,          # 汽油 kg CO2e/L
    "diesel": 2.639,            # 柴油 kg CO2e/L
    "liquefied_petroleum_gas": 3.101,  # 液化石油气 kg CO2e/kg
    "coal": 2.53,               # 煤炭 kg CO2e/kg
    "refrigerant_r22": 1700,    # R22 冷媒 GWP
    "refrigerant_r134a": 1430,  # R134a 冷媒 GWP
    "refrigerant_r410a": 2088,  # R410A 冷媒 GWP
    "refrigerant_r404a": 3922,  # R404A 冷媒 GWP
    "refrigerant_r32": 675,     # R32 冷媒 GWP
}

# 范围二：间接排放（电力）
SCOPE2_FACTORS = {
    "electricity_national": 0.5810,  # 全国电网平均排放因子 kg CO2e/kWh
    "electricity_north": 0.7003,     # 华北区域
    "electricity_northeast": 0.8155, # 东北区域
    "electricity_east": 0.5308,      # 华东区域
    "electricity_central": 0.5221,   # 华中区域
    "electricity_south": 0.4222,     # 华南区域
    "electricity_southwest": 0.3254, # 西南区域
    "electricity_northwest": 0.6151, # 西北区域
}

# 范围三：其他间接排放
SCOPE3_FACTORS = {
    "air_travel_domestic": 0.184,     # 国内航空 kg CO2e/人·km
    "air_travel_international": 0.169, # 国际航空 kg CO2e/人·km
    "rail_travel": 0.028,             # 铁路 kg CO2e/人·km
    "road_travel_bus": 0.032,         # 公路大巴 kg CO2e/人·km
    "road_travel_taxi": 0.121,        # 出租车 kg CO2e/人·km
    "hotel_stay": 18.5,               # 酒店住宿 kg CO2e/间·晚
}

# 冷媒类型映射
REFRIGERANT_TYPES = {
    "R22": "refrigerant_r22",
    "R-22": "refrigerant_r22",
    "R134a": "refrigerant_r134a",
    "R-134a": "refrigerant_r134a",
    "R410A": "refrigerant_r410a",
    "R-410A": "refrigerant_r410a",
    "R404A": "refrigerant_r404a",
    "R-404A": "refrigerant_r404a",
    "R32": "refrigerant_r32",
    "R-32": "refrigerant_r32",
}

# 能源类型分类
ENERGY_CATEGORIES = {
    "electricity": "scope2",
    "natural_gas": "scope1",
    "gasoline": "scope1",
    "diesel": "scope1",
    "liquefied_petroleum_gas": "scope1",
    "coal": "scope1",
    "refrigerant": "scope1",
    "air_travel": "scope3",
    "rail_travel": "scope3",
    "road_travel": "scope3",
    "hotel_stay": "scope3",
}

def get_emission_factor(factor_key: str) -> float:
    """获取排放因子"""
    all_factors = {**SCOPE1_FACTORS, **SCOPE2_FACTORS, **SCOPE3_FACTORS}
    return all_factors.get(factor_key, 0.0)

def get_scope(category: str) -> str:
    """获取排放范围"""
    return ENERGY_CATEGORIES.get(category, "scope3")
