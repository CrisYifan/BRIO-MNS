"""Paired experiment runner with fixed scales and unique-solution budgets."""

import argparse
import copy
import csv
import json
import os
import random
import statistics
import zlib
from datetime import datetime

from algorithms import GA求解器
from dataset_tools import 读取XML100实例, 当前算法兼容
from experiment_v2 import 基础参数, 计算共享归一化基准, 运行一次


默认算法 = "GA,SA-F,ACO-F,TS-F,DPSO-F,BRIO-MNS"


def 保存CSV(路径, 行列表):
    if not 行列表:
        return
    os.makedirs(os.path.dirname(路径), exist_ok=True)
    with open(路径, "w", newline="", encoding="utf-8-sig") as 文件:
        写入器 = csv.DictWriter(文件, fieldnames=list(行列表[0]))
        写入器.writeheader()
        写入器.writerows(行列表)


def 实例固定尺度(参数, 点列表, 距离矩阵, 仓库坐标, 实例名, 校准数量, 基础种子):
    """使用算法运行之外的确定性校准种群，为一个实例冻结三个尺度。"""
    校准种子 = 基础种子 + zlib.crc32(实例名.encode("utf-8")) % 1_000_000
    random.seed(校准种子)
    校准参数 = copy.deepcopy(参数)
    校准参数.update({
        "初始种群数量": 校准数量,
        "父代选择数量": min(max(10, 校准数量 // 4), 校准数量),
        "启用归一化复合目标": False,
        "发布级评价协议": True,
    })
    初始化器 = GA求解器(校准参数, 点列表, 距离矩阵, 仓库坐标)
    尺度 = 计算共享归一化基准(
        校准参数, copy.deepcopy(初始化器.初始种群), 距离矩阵
    )
    return 尺度, 校准种子


def 汇总结果(全部运行):
    分组 = {}
    for 行 in 全部运行:
        分组.setdefault((行["数据集"], 行["算法"]), []).append(行)

    GA均值 = {}
    A16均值 = {}
    for (数据集, 算法), 行组 in 分组.items():
        均值 = statistics.mean(float(行["复合目标"]) for 行 in 行组)
        if 算法 == "GA":
            GA均值[数据集] = 均值
        elif 算法 == "BRIO-MNS":
            A16均值[数据集] = 均值

    汇总 = []
    for (数据集, 算法), 行组 in sorted(分组.items()):
        F值 = [float(行["复合目标"]) for 行 in 行组]
        均值 = statistics.mean(F值)
        汇总.append({
            "数据集": 数据集,
            "容量": 行组[0]["容量"],
            "算法": 算法,
            "运行次数": len(行组),
            "F均值": 均值,
            "F标准差": statistics.stdev(F值) if len(F值) > 1 else 0.0,
            "F最优": min(F值),
            "D均值": statistics.mean(float(行["路径总长"]) for 行 in 行组),
            "BD均值": statistics.mean(float(行["路径均衡"]) for 行 in 行组),
            "BL均值": statistics.mean(float(行["负载均衡"]) for 行 in 行组),
            "有效新解评价均值": statistics.mean(
                float(行["有效新解评价次数"]) for 行 in 行组
            ),
            "函数调用均值": statistics.mean(
                float(行["目标函数调用次数"]) for 行 in 行组
            ),
            "缓存命中均值": statistics.mean(
                float(行["评价缓存命中次数"]) for 行 in 行组
            ),
            "耗时均值": statistics.mean(float(行["耗时秒"]) for 行 in 行组),
            "相对GA改善率": (
                (GA均值[数据集] - 均值) / GA均值[数据集]
                if 数据集 in GA均值 else ""
            ),
            "相对BRIO-MNS差距": (
                (均值 - A16均值[数据集]) / A16均值[数据集]
                if 数据集 in A16均值 else ""
            ),
        })
    return 汇总


def 总体分析(汇总, 全部运行):
    数据集列表 = sorted({行["数据集"] for 行 in 汇总})
    算法列表 = sorted({行["算法"] for 行 in 汇总})
    查找 = {(行["数据集"], 行["算法"]): 行 for 行 in 汇总}
    平均排名 = {算法: [] for 算法 in 算法列表}
    for 数据集 in 数据集列表:
        排序 = sorted(
            (float(查找[(数据集, 算法)]["F均值"]), 算法)
            for 算法 in 算法列表 if (数据集, 算法) in 查找
        )
        for 排名, (_, 算法) in enumerate(排序, 1):
            平均排名[算法].append(排名)

    GA改善 = []
    匹配差距 = []
    ALNS差距 = []
    for 数据集 in 数据集列表:
        a键 = (数据集, "BRIO-MNS")
        g键 = (数据集, "GA")
        if a键 in 查找 and g键 in 查找:
            a = float(查找[a键]["F均值"])
            g = float(查找[g键]["F均值"])
            GA改善.append((g - a) / g)
        else:
            a = None
        if a is not None and (数据集, "Matched-Random16") in 查找:
            m = float(查找[(数据集, "Matched-Random16")]["F均值"])
            匹配差距.append((m - a) / a)
        if a is not None and (数据集, "ALNS-F") in 查找:
            n = float(查找[(数据集, "ALNS-F")]["F均值"])
            ALNS差距.append((n - a) / a)

    配对 = {}
    for 对手 in ["GA", "ALNS-F", "Static-VNS16", "No-N6-16", "Matched-Random16"]:
        胜 = 平 = 负 = 0
        键映射 = {
            (行["数据集"], int(行["运行序号"]), 行["算法"]): float(行["复合目标"])
            for 行 in 全部运行
        }
        for 数据集 in 数据集列表:
            运行号 = sorted({
                int(行["运行序号"]) for 行 in 全部运行 if 行["数据集"] == 数据集
            })
            for r in 运行号:
                a键 = (数据集, r, "BRIO-MNS")
                o键 = (数据集, r, 对手)
                if a键 not in 键映射 or o键 not in 键映射:
                    continue
                差 = 键映射[o键] - 键映射[a键]
                if 差 > 1e-12:
                    胜 += 1
                elif 差 < -1e-12:
                    负 += 1
                else:
                    平 += 1
        配对[对手] = {"BRIO-MNS胜": 胜, "平": 平, "BRIO-MNS负": 负}

    return {
        "数据集数": len(数据集列表),
        "每实例运行次数": max(
            max(
                sum(
                    1 for 行 in 全部运行
                    if 行["数据集"] == 数据集 and 行["算法"] == 算法
                )
                for 算法 in 算法列表
            )
            for 数据集 in 数据集列表
        ),
        "BRIO-MNS相对GA平均改善率": (
            statistics.mean(GA改善) if GA改善 else None
        ),
        "BRIO-MNS相对GA最小改善率": min(GA改善) if GA改善 else None,
        "BRIO-MNS相对GA最大改善率": max(GA改善) if GA改善 else None,
        "MatchedRandom相对BRIO-MNS平均差距": (
            statistics.mean(匹配差距) if 匹配差距 else None
        ),
        "ALNS相对BRIO-MNS平均差距": (
            statistics.mean(ALNS差距) if ALNS差距 else None
        ),
        "平均排名": {
            算法: statistics.mean(排名) for 算法, 排名 in 平均排名.items()
        },
        "配对胜负": 配对,
    }


def main():
    解析器 = argparse.ArgumentParser()
    解析器.add_argument("--suite", required=True)
    解析器.add_argument("--runs", type=int, default=3)
    解析器.add_argument("--population", type=int, default=40)
    解析器.add_argument("--ga-generations", type=int, default=100)
    解析器.add_argument("--ga-phase-generations", type=int, default=10)
    解析器.add_argument("--budget", type=int, default=8240)
    解析器.add_argument("--seed", type=int, default=20260822)
    解析器.add_argument("--calibration-seed", type=int, default=314159)
    解析器.add_argument("--calibration-size", type=int, default=500)
    解析器.add_argument("--only", default=默认算法)
    解析器.add_argument(
        "--names", default="",
        help="仅运行指定实例名，多个名称用逗号分隔。",
    )
    解析器.add_argument(
        "--dataset-seed-stride", type=int, default=10000,
        help="相邻实例的配对基础种子增量；设为0可复现旧9实例的共享种子映射。",
    )
    解析器.add_argument(
        "--limit", type=int, default=0,
        help="仅运行排序后的前N个实例；0表示运行全部实例。",
    )
    解析器.add_argument(
        "--legacy-evaluation-counting", action="store_true",
        help="按旧协议把每次目标函数调用都计入预算，用于协议分解。",
    )
    解析器.add_argument(
        "--paired-scales", action="store_true",
        help="按旧协议从每次运行的共享初始种群重算尺度，用于协议分解。",
    )
    参数项 = 解析器.parse_args()

    算法集合 = {名称.strip() for 名称 in 参数项.only.split(",") if 名称.strip()}
    实例文件 = sorted(
        os.path.join(参数项.suite, 文件名)
        for 文件名 in os.listdir(参数项.suite)
        if 文件名.lower().endswith(".vrp")
    )
    if not 实例文件:
        raise ValueError("审计数据集目录中没有.vrp实例")

    指定名称 = {名称.strip() for 名称 in 参数项.names.split(",") if 名称.strip()}
    if 指定名称:
        实例文件 = [
            路径 for 路径 in 实例文件
            if os.path.splitext(os.path.basename(路径))[0] in 指定名称
        ]
        已找到 = {os.path.splitext(os.path.basename(路径))[0] for 路径 in 实例文件}
        缺失名称 = 指定名称 - 已找到
        if 缺失名称:
            raise ValueError(f"数据集目录中缺少指定实例: {sorted(缺失名称)}")

    if 参数项.limit > 0:
        实例文件 = 实例文件[:参数项.limit]

    时间戳 = datetime.now().strftime("%Y%m%d_%H%M%S")
    输出目录 = os.path.join("experiment_runs", 时间戳)
    os.makedirs(输出目录, exist_ok=True)
    全部运行 = []
    尺度记录 = []

    for 数据序号, 文件路径 in enumerate(实例文件, 1):
        点列表, 距离矩阵, 仓库坐标, 元数据 = 读取XML100实例(文件路径)
        if not 当前算法兼容(元数据):
            raise ValueError(f"实例与当前固定块编码不兼容: {元数据['名称']}")
        参数 = copy.deepcopy(基础参数)
        参数.update({
            "车辆容量": 元数据["容量"],
            "初始种群数量": 参数项.population,
            "迭代次数": 参数项.ga_generations,
            "父代选择数量": min(max(10, 参数项.population // 4), 参数项.population),
            "指标评估预算": 参数项.budget,
            "遗传阶段代数": 参数项.ga_phase_generations,
            "数据文件": 文件路径,
            "发布级评价协议": not 参数项.legacy_evaluation_counting,
            "GA按有效评价预算终止": not 参数项.legacy_evaluation_counting,
            "ALNS移除比例": 0.10,
        })
        固定尺度, 校准种子 = 实例固定尺度(
            参数, 点列表, 距离矩阵, 仓库坐标, 元数据["名称"],
            参数项.calibration_size, 参数项.calibration_seed,
        )
        尺度记录.append({
            "数据集": 元数据["名称"],
            "容量": 元数据["容量"],
            "校准种子": 校准种子,
            "校准种群数量": 参数项.calibration_size,
            "sD": 固定尺度["路径总长"],
            "sBD": 固定尺度["路径均衡"],
            "sBL": 固定尺度["负载均衡"],
        })
        print(
            f"\n### experiment run {数据序号}/{len(实例文件)}: "
            f"{元数据['名称']} Q={元数据['容量']} scales={固定尺度}",
            flush=True,
        )
        for 运行序号 in range(1, 参数项.runs + 1):
            结果, 使用尺度 = 运行一次(
                运行序号, 参数, 点列表, 距离矩阵, 仓库坐标,
                参数项.seed + 数据序号 * 参数项.dataset_seed_stride, 算法集合,
                固定归一化基准=(None if 参数项.paired_scales else 固定尺度),
            )
            for 行 in 结果:
                全部运行.append({
                    "数据集": 元数据["名称"],
                    "容量": 元数据["容量"],
                    "校准种子": 校准种子,
                    "sD": 使用尺度["路径总长"],
                    "sBD": 使用尺度["路径均衡"],
                    "sBL": 使用尺度["负载均衡"],
                    **行,
                })
        保存CSV(os.path.join(输出目录, "all_runs.csv"), 全部运行)
        保存CSV(os.path.join(输出目录, "summary.csv"), 汇总结果(全部运行))
        保存CSV(os.path.join(输出目录, "fixed_scales.csv"), 尺度记录)

    汇总 = 汇总结果(全部运行)
    分析 = 总体分析(汇总, 全部运行)
    with open(os.path.join(输出目录, "analysis.json"), "w", encoding="utf-8") as 文件:
        json.dump(分析, 文件, ensure_ascii=False, indent=2)
    with open(os.path.join(输出目录, "metadata.json"), "w", encoding="utf-8") as 文件:
        json.dump({
            **vars(参数项),
            "algorithms": sorted(算法集合),
            "datasets": [
                os.path.splitext(os.path.basename(路径))[0] for 路径 in 实例文件
            ],
            "protocol": {
                "scales": (
                    "paired-initial-population" if 参数项.paired_scales
                    else "fixed-per-instance"
                ),
                "budget": (
                    "objective-calls" if 参数项.legacy_evaluation_counting
                    else "unique-solutions"
                ),
            },
        }, 文件, ensure_ascii=False, indent=2)

    print("\n=== experiment run summary ===")
    print(json.dumps(分析, ensure_ascii=False, indent=2))
    print(f"结果目录: {os.path.abspath(输出目录)}")


if __name__ == "__main__":
    main()
