"""Composite objective evaluation and permutation crossover."""

import copy
import random
import os

class 工具类:
    """工具类 - 包含数据加载、适应度计算、文件操作等通用功能"""

    def __init__(self, 参数配置):
        self.参数 = 参数配置

        self.指标评估次数 = 0

        self.发布级评价协议 = bool(self.参数.get("发布级评价协议", False))
        self.目标函数调用次数 = 0
        self.评价缓存命中次数 = 0
        self._评价缓存 = {}

        self.incremental_evaluations = 0
        self.accepted_moves = 0
        self.convergence_checkpoints = []

    def 加载数据(self, 数据文件路径):
        """加载VRP数据文件"""
        print(f"正在加载数据: {数据文件路径}")
        with open(数据文件路径, "r") as 文件:
            行列表 = 文件.readlines()

        点列表 = []
        for 行 in 行列表:
            行分割 = 行.split()
            坐标 = [int(行分割[1]), int(行分割[2])]
            点列表.append(坐标)

        仓库坐标 = 点列表[0]


        距离矩阵 = []
        for 点 in 点列表:
            距离子列表 = []
            for 其他点 in 点列表:
                距离 = round((((点[0] - 其他点[0]) ** 2 + (点[1] - 其他点[1]) ** 2)) ** 0.5)
                距离子列表.append(距离)
            距离矩阵.append(距离子列表)

        return 点列表, 距离矩阵, 仓库坐标

    def 适应度计算(self, 个体序列, 距离矩阵):
        """计算个体的适应度值"""
        self.目标函数调用次数 += 1
        缓存键 = tuple(个体序列)
        if self.发布级评价协议 and 缓存键 in self._评价缓存:
            self.评价缓存命中次数 += 1
            return self._评价缓存[缓存键][0]

        if self.发布级评价协议:
            指标 = self._路径指标原始计算(个体序列, 距离矩阵)
            self.指标评估次数 += 1
        else:
            指标 = self.路径指标计算(个体序列, 距离矩阵)
        路径总长, 路径均衡, 负载均衡 = 指标[2], 指标[3], 指标[4]

        if self.参数.get("启用归一化复合目标", False):
            基准 = self.参数.get("复合目标归一化基准")
            if not 基准:
                raise ValueError("启用归一化复合目标前必须设置复合目标归一化基准")

            路径长归一值 = 路径总长 / max(float(基准["路径总长"]), 1e-12)
            路径均衡归一值 = 路径均衡 / max(float(基准["路径均衡"]), 1e-12)
            负载均衡归一值 = 负载均衡 / max(float(基准["负载均衡"]), 1e-12)
            适应度 = (self.参数["路径长系数"] * 路径长归一值 +
                    self.参数["路径均衡系数"] * 路径均衡归一值 +
                    self.参数["负载均衡系数"] * 负载均衡归一值)
        else:
            适应度 = (self.参数["路径长系数"] * 路径总长 +
                    self.参数["路径均衡系数"] * 路径均衡 +
                    self.参数["负载均衡系数"] * 负载均衡)

        if self.发布级评价协议:
            self._评价缓存[缓存键] = (适应度, 指标)
        return 适应度

    def 路径指标计算(self, 个体序列, 距离矩阵):
        """计算路径指标；发布级协议下该接口只用于报告，不消耗搜索预算。"""
        if not self.发布级评价协议:
            self.指标评估次数 += 1
        return self._路径指标原始计算(个体序列, 距离矩阵)

    def _路径指标原始计算(self, 个体序列, 距离矩阵):
        """无副作用地计算路径指标，作为搜索评价、校准和结果报告的共同事实来源。"""
        路径总长 = 0
        路径均衡 = 0
        负载均衡 = 0

        路径段列表 = []
        负载率列表 = []
        车辆容量 = self.参数["车辆容量"]

        for i in range(len(个体序列) // 车辆容量):
            子路径长 = 0

            for j in range(车辆容量):
                if j == 0:
                    子路径长 += 距离矩阵[0][个体序列[i * 车辆容量 + j]]
                    路径段列表.append(距离矩阵[0][个体序列[i * 车辆容量 + j]])
                else:
                    子路径长 += 距离矩阵[个体序列[i * 车辆容量 + j - 1]][个体序列[i * 车辆容量 + j]]
                    路径段列表.append(距离矩阵[个体序列[i * 车辆容量 + j - 1]][个体序列[i * 车辆容量 + j]])

                剩余负载率 = (车辆容量 - j) / 车辆容量
                负载率列表.append(剩余负载率)

                if (j + 1) == 车辆容量:
                    子路径长 += 距离矩阵[个体序列[i * 车辆容量 + j]][0]
                    路径段列表.append(距离矩阵[个体序列[i * 车辆容量 + j]][0])
                    负载率列表.append(0.0)

            路径总长 += 子路径长


        if 路径段列表:
            平均路径长 = sum(路径段列表) / len(路径段列表)
            for 段长 in 路径段列表:
                路径均衡 += (段长 - 平均路径长) ** 2
            路径均衡 = 路径均衡 / len(路径段列表)


        if 路径段列表:
            负载距离乘积列表 = []
            总负载距离 = 0
            for i in range(len(路径段列表)):
                负载距离 = 负载率列表[i] * 路径段列表[i]
                负载距离乘积列表.append(负载距离)
                总负载距离 += 负载距离

            平均负载距离 = 总负载距离 / len(路径段列表)
            for 负载距离 in 负载距离乘积列表:
                负载均衡 += (负载距离 - 平均负载距离) ** 2
            负载均衡 = 负载均衡 / len(路径段列表)

        return 路径段列表, 负载率列表, 路径总长, 路径均衡, 负载均衡

    def 已缓存(self, 个体序列):
        """发布级GA在严格预算边界处判断候选是否可无成本复用。"""
        return tuple(个体序列) in self._评价缓存

    def 评价统计(self):
        return {
            "有效新解评价次数": self.指标评估次数,
            "目标函数调用次数": self.目标函数调用次数,
            "评价缓存命中次数": self.评价缓存命中次数,
            "不同染色体缓存数": len(self._评价缓存),
            "incremental_evaluations": self.incremental_evaluations,
            "accepted_moves": self.accepted_moves,
            "convergence_checkpoints": self.convergence_checkpoints,
        }

    def OX交叉(self, 父代1, 父代2, 禁忌表):
        """
        OX交叉操作（修复版）
        使用更安全的方式处理基因移除
        """
        子代1 = [0] * len(父代1)
        子代2 = [0] * len(父代2)


        交叉点1 = random.randint(0, len(父代1) - 2)
        交叉点2 = random.randint(交叉点1 + 1, len(父代1) - 1)


        if 交叉点1 > 交叉点2:
            交叉点1, 交叉点2 = 交叉点2, 交叉点1


        片段1 = []
        片段2 = []

        for i in range(交叉点1, 交叉点2):
            片段1.append(父代1[i])
            片段2.append(父代2[i])
            子代1[i] = 父代1[i]
            子代2[i] = 父代2[i]


        父代1剩余 = []
        父代2剩余 = []


        for 基因 in 父代1:
            if 基因 not in 片段2:
                父代1剩余.append(基因)

        for 基因 in 父代2:
            if 基因 not in 片段1:
                父代2剩余.append(基因)


        if len(父代1剩余) != len(子代1) - (交叉点2 - 交叉点1):

            父代1剩余 = [基因 for 基因 in 父代1 if 基因 not in 片段2]
            父代2剩余 = [基因 for 基因 in 父代2 if 基因 not in 片段1]


        索引1 = 0
        索引2 = 0

        for i in range(len(子代1)):
            if 子代1[i] == 0:
                if 索引1 < len(父代2剩余):
                    子代1[i] = 父代2剩余[索引1]
                    索引1 += 1

        for i in range(len(子代2)):
            if 子代2[i] == 0:
                if 索引2 < len(父代1剩余):
                    子代2[i] = 父代1剩余[索引2]
                    索引2 += 1


        for i in range(len(子代1)):
            if 子代1[i] == 0:
                子代1[i] = random.choice([g for g in range(1, 101) if g not in 子代1])

        for i in range(len(子代2)):
            if 子代2[i] == 0:
                子代2[i] = random.choice([g for g in range(1, 101) if g not in 子代2])

        return 子代1, 子代2

    def 保存结果(self, 文件路径, 数据字典):
        """保存结果到文件"""
        with open(文件路径, "w", encoding="utf-8") as 文件:
            for 键, 值 in 数据字典.items():
                if isinstance(值, (list, dict, tuple)):
                    文件.write(f"{键}:{值}\n")
                else:
                    文件.write(f"{键}:{值}\n")
