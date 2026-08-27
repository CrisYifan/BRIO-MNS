"""XML100/简单坐标数据读取与兼容性检查。"""

import math
import os


def _距离矩阵(点列表):
    # XML100声明EUC_2D，按TSPLIB规则使用int(sqrt+0.5)，避免Python银行家舍入造成边界差异。
    return [
        [int(math.hypot(a[0] - b[0], a[1] - b[1]) + 0.5) for b in 点列表]
        for a in 点列表
    ]


def 读取XML100实例(文件路径):
    """读取TSPLIB CVRP实例，返回坐标、距离矩阵和需求/容量元数据。"""
    with open(文件路径, encoding="utf-8") as 文件:
        行列表 = [行.strip() for 行 in 文件 if 行.strip()]

    头信息 = {}
    坐标 = {}
    需求 = {}
    仓库编号 = None
    区段 = "HEADER"
    for 行 in 行列表:
        if 行 == "NODE_COORD_SECTION":
            区段 = "COORD"
            continue
        if 行 == "DEMAND_SECTION":
            区段 = "DEMAND"
            continue
        if 行 == "DEPOT_SECTION":
            区段 = "DEPOT"
            continue
        if 行 == "EOF":
            break

        if 区段 == "HEADER":
            if ":" in 行:
                键, 值 = 行.split(":", 1)
                头信息[键.strip()] = 值.strip()
        elif 区段 == "COORD":
            编号, x, y = 行.split()[:3]
            坐标[int(编号)] = (int(x), int(y))
        elif 区段 == "DEMAND":
            编号, 值 = 行.split()[:2]
            需求[int(编号)] = int(值)
        elif 区段 == "DEPOT":
            编号 = int(行.split()[0])
            if 编号 != -1:
                仓库编号 = 编号

    维数 = int(头信息["DIMENSION"])
    容量 = int(头信息["CAPACITY"])
    if 头信息.get("TYPE") != "CVRP" or 头信息.get("EDGE_WEIGHT_TYPE") != "EUC_2D":
        raise ValueError(f"当前只支持EUC_2D CVRP: {文件路径}")
    if len(坐标) != 维数 or len(需求) != 维数 or 仓库编号 is None:
        raise ValueError(f"实例区段不完整: {文件路径}")

    客户编号 = [编号 for 编号 in sorted(坐标) if 编号 != 仓库编号]
    点顺序 = [仓库编号] + 客户编号
    点列表 = [list(坐标[编号]) for 编号 in 点顺序]
    客户需求 = [需求[编号] for 编号 in 客户编号]
    元数据 = {
        "名称": 头信息.get("NAME", os.path.splitext(os.path.basename(文件路径))[0]),
        "容量": 容量,
        "客户数": len(客户编号),
        "客户需求": 客户需求,
        "单位需求": all(值 == 1 for 值 in 客户需求),
        "容量整除客户数": len(客户编号) % 容量 == 0,
        "文件路径": os.path.abspath(文件路径),
    }
    return 点列表, _距离矩阵(点列表), 点列表[0], 元数据


def 解析实例名称(名称):
    """解析XML100_ABCD_EF中的生成类型。"""
    主体 = os.path.splitext(os.path.basename(名称))[0]
    前缀, 类型码, 实例号 = 主体.split("_")
    if 前缀 != "XML100" or len(类型码) != 4:
        raise ValueError(f"不是XML100标准名称: {名称}")
    return {
        "仓库位置": int(类型码[0]),
        "客户分布": int(类型码[1]),
        "需求类型": int(类型码[2]),
        "路线规模组": int(类型码[3]),
        "实例号": int(实例号),
        "类型码": 类型码,
    }


def 当前算法兼容(元数据):
    """当前固定块编码只对单位需求且容量整除客户数的实例严格合法。"""
    return 元数据["单位需求"] and 元数据["容量整除客户数"]
