"""BRIO-MNS structured multi-neighborhood search."""

import itertools
import math
import random
from algorithms import GA求解器

class 预算混合求解器(GA求解器):
    """先遗传搜索、再在同一总评估预算内进行自适应局部精修。"""

    def __init__(
        self, *args, 启用贡献引导=False, 候选批量大小=1,
        自适应算子=False, 统一六算子=False,
        禁用负担引导=False, 匹配随机负担=False,
        复合负担代理=False, 引导使用概率=1.0,
        n6_localization="mixed", n6_neighbor_count=8,
        n6_reorder_probability=0.30, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.启用贡献引导 = 启用贡献引导
        self.候选批量大小 = max(int(候选批量大小), 1)
        self.自适应算子 = 自适应算子

        self.统一六算子 = 统一六算子

        self.禁用负担引导 = 禁用负担引导
        self.匹配随机负担 = 匹配随机负担

        self.复合负担代理 = 复合负担代理

        self.引导使用概率 = min(max(float(引导使用概率), 0.0), 1.0)
        if n6_localization not in {"mixed", "burden", "random", "distance"}:
            raise ValueError(f"Unknown N6 localization: {n6_localization}")
        if n6_neighbor_count not in {0, 8}:
            raise ValueError("N6 nearest-neighbor count must be 0 or 8")
        if not 0.0 <= n6_reorder_probability <= 1.0:
            raise ValueError("N6 reorder probability must be between 0 and 1")
        self.n6_localization = n6_localization
        self.n6_neighbor_count = n6_neighbor_count
        self.n6_reorder_probability = n6_reorder_probability
        self._最近客户 = self._创建最近客户表()

    def _创建最近客户表(self):
        return {
            客户: sorted(
                (其他 for 其他 in range(1, self.客户数量 + 1) if 其他 != 客户),
                key=lambda 其他: self.距离矩阵[客户][其他],
            )
            for 客户 in range(1, self.客户数量 + 1)
        }

    def _路径距离(self, 路径):
        return (self.距离矩阵[0][路径[0]] +
                sum(self.距离矩阵[a][b] for a, b in zip(路径, 路径[1:])) +
                self.距离矩阵[路径[-1]][0])

    def _路径充分统计(self, 路径):
        """返回可增量恢复D、BD和BL的一条路线充分统计量。"""
        容量 = len(路径)
        边长 = [self.距离矩阵[0][路径[0]]]
        边长.extend(self.距离矩阵[a][b] for a, b in zip(路径, 路径[1:]))
        边长.append(self.距离矩阵[路径[-1]][0])
        载荷率 = [(容量 - j) / 容量 for j in range(容量)] + [0.0]
        载荷距离 = [载荷 * 距离 for 载荷, 距离 in zip(载荷率, 边长)]
        return (
            sum(边长),
            sum(距离 * 距离 for 距离 in 边长),
            sum(载荷距离),
            sum(值 * 值 for 值 in 载荷距离),
        )

    def _全局充分统计(self, 个体序列):
        容量 = self.参数["车辆容量"]
        路线统计 = [
            self._路径充分统计(个体序列[起点:起点 + 容量])
            for 起点 in range(0, len(个体序列), 容量)
        ]
        return tuple(sum(统计[列] for 统计 in 路线统计) for 列 in range(4))

    def _统计复合代价(self, 统计):
        """由全局充分统计量计算与正式目标完全同向的无副作用代理。"""
        距离和, 距离平方和, 载荷距离和, 载荷距离平方和 = 统计
        容量 = self.参数["车辆容量"]
        边数 = (len(self.初始种群[0]) // 容量) * (容量 + 1)
        路径均衡 = max(距离平方和 / 边数 - (距离和 / 边数) ** 2, 0.0)
        负载均衡 = max(
            载荷距离平方和 / 边数 - (载荷距离和 / 边数) ** 2,
            0.0,
        )
        if self.参数.get("启用归一化复合目标", False):
            基准 = self.参数["复合目标归一化基准"]
            距离和 /= max(float(基准["路径总长"]), 1e-12)
            路径均衡 /= max(float(基准["路径均衡"]), 1e-12)
            负载均衡 /= max(float(基准["负载均衡"]), 1e-12)
        return (
            self.参数["路径长系数"] * 距离和
            + self.参数["路径均衡系数"] * 路径均衡
            + self.参数["负载均衡系数"] * 负载均衡
        )

    def _替换路线复合代理(self, 全局统计, 原路线列表, 新路线列表):
        新统计 = list(全局统计)
        for 原路线 in 原路线列表:
            原统计 = self._路径充分统计(原路线)
            for 列 in range(4):
                新统计[列] -= 原统计[列]
        for 新路线 in 新路线列表:
            候选统计 = self._路径充分统计(新路线)
            for 列 in range(4):
                新统计[列] += 候选统计[列]
        return self._统计复合代价(tuple(新统计))

    def _本次使用负担排序(self):
        if self.匹配随机负担 or self.引导使用概率 <= 0.0:
            return False
        if self.引导使用概率 >= 1.0:
            return True
        return random.random() < self.引导使用概率

    def _位置负担(self, 个体序列, 位置):
        容量 = self.参数["车辆容量"]
        块起点 = (位置 // 容量) * 容量
        块终点 = 块起点 + 容量
        块内位置 = 位置 - 块起点
        客户 = 个体序列[位置]
        前客户 = 0 if 位置 == 块起点 else 个体序列[位置 - 1]
        后客户 = 0 if 位置 == 块终点 - 1 else 个体序列[位置 + 1]
        入载荷 = (容量 - 块内位置) / 容量
        出载荷 = max(容量 - 块内位置 - 1, 0) / 容量
        return (self.距离矩阵[前客户][客户] * (1.0 + 入载荷) +
                self.距离矩阵[客户][后客户] * (1.0 + 出载荷))

    def _n6_localization_scores(self, 个体序列):
        if self.n6_localization != "distance":
            return [self._位置负担(个体序列, i) for i in range(len(个体序列))]
        容量 = self.参数["车辆容量"]
        scores = []
        for i, 客户 in enumerate(个体序列):
            前客户 = 0 if i % 容量 == 0 else 个体序列[i - 1]
            后客户 = 0 if i % 容量 == 容量 - 1 else 个体序列[i + 1]
            scores.append(self.距离矩阵[前客户][客户] + self.距离矩阵[客户][后客户])
        return scores

    def _n6_use_ranked_localization(self):
        if self.n6_localization == "burden":
            return True
        if self.n6_localization == "random":
            return False
        return self._本次使用负担排序()

    def _随机邻域(self, 个体序列):
        新序列 = 个体序列[:]
        if random.random() < 0.25:
            容量 = self.参数["车辆容量"]
            路径 = random.randrange(len(个体序列) // 容量)
            左, 右 = sorted(random.sample(range(容量), 2))
            起点 = 路径 * 容量
            新序列[起点 + 左:起点 + 右 + 1] = reversed(新序列[起点 + 左:起点 + 右 + 1])
        else:
            i, j = random.sample(range(len(个体序列)), 2)
            新序列[i], 新序列[j] = 新序列[j], 新序列[i]
        return 新序列

    def _按算子生成邻域(self, 个体序列, 算子):
        容量 = self.参数["车辆容量"]
        新序列 = 个体序列[:]
        if 算子 == "任意交换":
            i, j = random.sample(range(len(个体序列)), 2)
            新序列[i], 新序列[j] = 新序列[j], 新序列[i]
        elif 算子 == "跨路径交换":
            i = random.randrange(len(个体序列))
            候选 = [j for j in range(len(个体序列)) if j // 容量 != i // 容量]
            j = random.choice(候选)
            新序列[i], 新序列[j] = 新序列[j], 新序列[i]
        elif 算子 == "路径内反转":
            路径 = random.randrange(len(个体序列) // 容量)
            左, 右 = sorted(random.sample(range(容量), 2))
            起点 = 路径 * 容量
            新序列[起点 + 左:起点 + 右 + 1] = reversed(新序列[起点 + 左:起点 + 右 + 1])
        elif 算子 == "路径内重排":
            路径 = random.randrange(len(个体序列) // 容量)
            起点 = 路径 * 容量
            原路径 = 新序列[起点:起点 + 容量]
            新路径 = random.sample(原路径, len(原路径))
            新序列[起点:起点 + 容量] = 新路径
        elif 算子 == "双客户段交换":
            路径1, 路径2 = random.sample(range(len(个体序列) // 容量), 2)
            起始1 = random.randrange(容量 - 1)
            起始2 = random.randrange(容量 - 1)
            a = 路径1 * 容量 + 起始1
            b = 路径2 * 容量 + 起始2
            片段1 = 新序列[a:a + 2]
            片段2 = 新序列[b:b + 2]
            新序列[a:a + 2], 新序列[b:b + 2] = 片段2, 片段1
        elif 算子 == "负担引导":
            return self._引导邻域(个体序列)
        else:
            raise ValueError(f"未知邻域算子: {算子}")
        return 新序列

    @staticmethod
    def _按权重选择算子(算子权重):
        总权重 = sum(算子权重.values())
        阈值 = random.random() * 总权重
        累计 = 0.0
        for 算子, 权重 in 算子权重.items():
            累计 += 权重
            if 累计 >= 阈值:
                return 算子
        return next(reversed(算子权重))

    def _引导邻域(self, 个体序列):
        容量 = self.参数["车辆容量"]
        if random.random() < self.n6_reorder_probability:

            路径数 = len(个体序列) // 容量
            候选路线 = random.sample(range(路径数), min(5, 路径数))

            定位分数 = self._n6_localization_scores(个体序列)
            路线负担 = {
                r: sum(定位分数[r * 容量 + j] for j in range(容量))
                for r in 候选路线
            }
            路径 = (
                max(候选路线, key=lambda r: 路线负担[r])
                if self._n6_use_ranked_localization()
                else random.choice(候选路线)
            )
            起点 = 路径 * 容量
            当前路径 = 个体序列[起点:起点 + 容量]
            全局统计 = self._全局充分统计(个体序列) if self.复合负担代理 else None

            def 路线候选分数(候选路径):
                if self.复合负担代理:
                    return self._替换路线复合代理(
                        全局统计, [当前路径], [候选路径]
                    )
                return self._路径距离(候选路径)

            if 容量 <= 7:
                最优路径 = list(min(
                    itertools.permutations(当前路径), key=路线候选分数
                ))
            else:

                路径候选 = [当前路径[:]]
                for _ in range(24):
                    左, 右 = sorted(random.sample(range(容量), 2))
                    候选路径 = 当前路径[:]
                    候选路径[左:右 + 1] = reversed(候选路径[左:右 + 1])
                    路径候选.append(候选路径)
                最优路径 = min(路径候选, key=路线候选分数)
            新序列 = 个体序列[:]
            新序列[起点:起点 + 容量] = 最优路径
            return 新序列

        客户到位置 = {客户: 位置 for 位置, 客户 in enumerate(个体序列)}
        位置负担表 = self._n6_localization_scores(个体序列)
        if self._n6_use_ranked_localization():
            重点池 = sorted(
                range(len(个体序列)),
                key=lambda 位置: 位置负担表[位置],
                reverse=True,
            )[:12]
        else:
            重点池 = random.sample(range(len(个体序列)), min(12, len(个体序列)))
        i = random.choice(重点池)
        客户 = 个体序列[i]
        当前块 = i // 容量
        伙伴 = []
        for 其他客户 in self._最近客户[客户][:] if self.n6_neighbor_count else ():
            j = 客户到位置[其他客户]
            if j // 容量 != 当前块:
                伙伴.append(j)
            if len(伙伴) >= self.n6_neighbor_count:
                break
        伙伴.extend(random.sample(
            [j for j in range(len(个体序列)) if j // 容量 != 当前块 and j not in 伙伴],
            12 - len(伙伴),
        ))

        全局统计 = self._全局充分统计(个体序列) if self.复合负担代理 else None

        def 伙伴代理变化(j):
            self.工具.incremental_evaluations += 1
            受影响块 = {当前块, j // 容量}
            原路线 = [
                个体序列[块 * 容量:(块 + 1) * 容量]
                for 块 in 受影响块
            ]
            临时 = 个体序列[:]
            临时[i], 临时[j] = 临时[j], 临时[i]
            新路线 = [
                临时[块 * 容量:(块 + 1) * 容量]
                for 块 in 受影响块
            ]
            if self.复合负担代理:
                return self._替换路线复合代理(全局统计, 原路线, 新路线)
            return (
                sum(self._路径距离(路线) for 路线 in 新路线)
                - sum(self._路径距离(路线) for 路线 in 原路线)
            )

        j = min(伙伴, key=伙伴代理变化)
        新序列 = 个体序列[:]
        新序列[i], 新序列[j] = 新序列[j], 新序列[i]
        return 新序列

    def 运行(self):
        目标预算 = int(self.参数.get("指标评估预算", 32480))
        遗传阶段代数 = int(self.参数.get("遗传阶段代数", 80))
        原代数 = self.参数["迭代次数"]
        原按预算终止 = self.参数.get("GA按有效评价预算终止", True)
        self.参数["迭代次数"] = 遗传阶段代数

        self.参数["GA按有效评价预算终止"] = False
        遗传结果 = super().运行()
        self.参数["迭代次数"] = 原代数
        self.参数["GA按有效评价预算终止"] = 原按预算终止

        当前解 = 遗传结果["最终最优个体"][:]
        当前适应度 = self.工具.适应度计算(当前解, self.距离矩阵)
        最优解, 最优适应度 = 当前解[:], 当前适应度
        历代最优适应度 = 遗传结果["历代最优适应度"][:]
        历代最优个体 = 遗传结果["历代最优个体"][:]
        起始评估 = self.工具.指标评估次数
        无改进次数 = 0
        算子权重 = {
            "任意交换": 1.0,
            "跨路径交换": 1.0,
            "路径内反转": 1.0,
            "路径内重排": 1.0,
            "双客户段交换": 1.0,
            "负担引导": 1.0,
        }
        if self.禁用负担引导:
            del 算子权重["负担引导"]

        next_convergence_checkpoint = (
            (self.工具.指标评估次数 // 250) + 1
        ) * 250

        while self.工具.指标评估次数 < 目标预算:
            已用局部预算 = self.工具.指标评估次数 - 起始评估
            总局部预算 = max(目标预算 - 起始评估, 1)
            进度 = min(已用局部预算 / 总局部预算, 1.0)
            温度 = 0.010 * (1.0 - 进度) + 0.00005

            批量结果 = []
            批量数 = min(self.候选批量大小, 目标预算 - self.工具.指标评估次数)
            for _ in range(批量数):
                if self.自适应算子:
                    算子 = self._按权重选择算子(算子权重)
                    候选解 = self._按算子生成邻域(当前解, 算子)
                elif self.统一六算子:

                    算子 = random.choice(list(算子权重))
                    候选解 = self._按算子生成邻域(当前解, 算子)
                elif self.启用贡献引导 and random.random() < 0.85:
                    算子 = "负担引导"
                    候选解 = self._引导邻域(当前解)
                else:
                    算子 = "任意交换"
                    候选解 = self._随机邻域(当前解)
                候选适应度 = self.工具.适应度计算(候选解, self.距离矩阵)
                批量结果.append((候选适应度, 候选解, 算子))

                if self.自适应算子:

                    if 候选适应度 < 最优适应度 - 1e-12:
                        奖励 = 3.0
                    elif 候选适应度 < 当前适应度 - 1e-12:
                        奖励 = 1.0
                    else:
                        奖励 = 0.0
                    算子权重[算子] = max(0.10, 0.98 * 算子权重[算子] + 0.02 * (0.20 + 奖励))

            候选适应度, 候选解, _ = min(批量结果, key=lambda 项: 项[0])
            差值 = 候选适应度 - 当前适应度
            if 差值 < 0 or random.random() < math.exp(-差值 / max(温度, 1e-12)):
                当前解, 当前适应度 = 候选解, 候选适应度
                self.工具.accepted_moves += 1

            if 当前适应度 < 最优适应度 - 1e-12:
                最优解, 最优适应度 = 当前解[:], 当前适应度
                无改进次数 = 0
            else:
                无改进次数 += 1

            if 无改进次数 >= 1200 and self.工具.指标评估次数 < 目标预算:

                当前解 = 最优解[:]
                for _ in range(2):
                    当前解 = self._随机邻域(当前解)
                当前适应度 = self.工具.适应度计算(当前解, self.距离矩阵)
                无改进次数 = 0

            if self.工具.指标评估次数 >= next_convergence_checkpoint:
                历代最优适应度.append(最优适应度)
                历代最优个体.append(最优解[:])
                指标 = self.工具._路径指标原始计算(最优解, self.距离矩阵)
                self.工具.convergence_checkpoints.append({
                    "evaluations": self.工具.指标评估次数,
                    "F": 最优适应度,
                    "D": 指标[2],
                    "BD": 指标[3],
                    "BL": 指标[4],
                })
                while next_convergence_checkpoint <= self.工具.指标评估次数:
                    next_convergence_checkpoint += 250

        if (
            not self.工具.convergence_checkpoints
            or self.工具.convergence_checkpoints[-1]["evaluations"]
            != self.工具.指标评估次数
        ):
            指标 = self.工具._路径指标原始计算(最优解, self.距离矩阵)
            self.工具.convergence_checkpoints.append({
                "evaluations": self.工具.指标评估次数,
                "F": 最优适应度,
                "D": 指标[2],
                "BD": 指标[3],
                "BL": 指标[4],
            })

        最终种群 = 遗传结果["最终种群"][:]
        最终种群[0] = 最优解[:]
        return {
            "历代最优适应度": 历代最优适应度,
            "历代最优个体": 历代最优个体,
            "历代全部种群": [],
            "最终种群": 最终种群,
            "最终最优个体": 最优解,
            "指标评估次数": self.工具.指标评估次数,
            "算子权重": 算子权重 if self.自适应算子 else {},
        }
