"""Run BRIO-MNS on one compatible XML100 instance."""
import argparse
import copy
import json
import math
from pathlib import Path
import random
import statistics
import time
import zlib

from algorithms import GA求解器
from brio_mns import 预算混合求解器
from dataset_tools import 读取XML100实例, 当前算法兼容
from utils import 工具类


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path, help="Path to an XML100 .vrp file")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--budget", type=int, default=32480)
    args = parser.parse_args()
    if args.budget < 80:
        parser.error("--budget must be at least 80")
    points, distances, depot, meta = 读取XML100实例(str(args.instance))
    if meta["客户数"] != 100 or not 当前算法兼容(meta) or not 1 < meta["容量"] < 100:
        parser.error("Expected 100 unit-demand customers and capacity dividing 100 (1 < Q < 100)")

    params = {
        "车辆容量": meta["容量"],
        "初始种群数量": 80,
        "随机种群比例": 0.4,
        "插入种群比例": 0.6,
        "迭代次数": 200,
        "遗传阶段代数": 20,
        "精英保留数量": 4,
        "父代选择数量": 20,
        "变异概率": 0.30,
        "路径长系数": 0.50,
        "路径均衡系数": 0.25,
        "负载均衡系数": 0.25,
        "指标评估预算": args.budget,
        "发布级评价协议": True,
        "GA按有效评价预算终止": True,
        "启用归一化复合目标": True,
        "输出逐代日志": False,
        "记录全部种群": False,
    }
    calibration_params = copy.deepcopy(params)
    calibration_params.update({"初始种群数量": 500, "启用归一化复合目标": False})
    calibration_seed = 314159 + zlib.crc32(meta["名称"].encode("utf-8")) % 1_000_000
    random.seed(calibration_seed)
    calibration_pool = GA求解器(calibration_params, points, distances, depot).初始种群
    calibration_evaluator = 工具类(calibration_params)
    metrics = [calibration_evaluator.路径指标计算(p, distances) for p in calibration_pool]
    scales = {name: statistics.median(row[column] for row in metrics)
              for name, column in (("路径总长", 2), ("路径均衡", 3), ("负载均衡", 4))}
    params["复合目标归一化基准"] = scales

    random.seed(args.seed)
    initial_params = copy.deepcopy(params)
    initial_params["启用归一化复合目标"] = False
    population = GA求解器(initial_params, points, distances, depot).初始种群
    random.seed(args.seed + 100000)
    solver = 预算混合求解器(
        params, points, distances, depot, population,
        候选批量大小=16, 自适应算子=True,
        复合负担代理=True, 引导使用概率=0.25,
    )
    started = time.perf_counter()
    result = solver.运行()
    elapsed = time.perf_counter() - started
    solution = result["最终最优个体"]
    if len(solution) != 100 or set(solution) != set(range(1, 101)):
        raise RuntimeError("Solver returned an invalid customer permutation")
    evaluator = 工具类(params)
    objective = evaluator.适应度计算(solution, distances)
    distance, bd, bl = evaluator.路径指标计算(solution, distances)[2:]
    if not all(math.isfinite(v) for v in (objective, distance, bd, bl)):
        raise RuntimeError("Non-finite objective")
    capacity = meta["容量"]
    print(json.dumps({
        "instance": meta["名称"], "seed": args.seed,
        "F": objective, "D": distance, "BD": bd, "BL": bl,
        "full_evaluations": result["指标评估次数"],
        "runtime_seconds": elapsed,
        "routes": [solution[i:i + capacity] for i in range(0, 100, capacity)],
    }, indent=2))


if __name__ == "__main__":
    main()
