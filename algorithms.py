"""Population initialization and genetic search."""

import copy
import random
import math
from utils import 工具类

class 基础求解器:
    """基础求解器类"""

    def __init__(self, 参数配置, 点列表, 距离矩阵, 仓库坐标, 初始种群=None):
        self.参数 = 参数配置
        self.点列表 = 点列表
        self.距离矩阵 = 距离矩阵
        self.仓库坐标 = 仓库坐标
        self.工具 = 工具类(参数配置)
        self.客户数量 = len(点列表) - 1

        self.禁忌表 = list(range(1, self.客户数量 + 1))
        self.节约值矩阵 = self._创建节约值矩阵()

        self.初始种群 = (copy.deepcopy(初始种群)
                         if 初始种群 is not None else self._初始化种群())

    def _创建节约值矩阵(self):
        """创建节约值矩阵"""
        节约值矩阵 = []
        for 索引自身, 距离 in enumerate(self.距离矩阵[1:self.客户数量 + 1]):
            节约值子列表 = []
            for 索引, 距 in enumerate(距离):
                节约值 = self.距离矩阵[0][索引自身 + 1] + self.距离矩阵[0][索引] - 距
                if 节约值 < 0:
                    节约值 = 0
                节约值子列表.append(节约值)
            节约值矩阵.append(节约值子列表)
        return 节约值矩阵

    def _初始化种群(self):
        """初始化种群"""
        初始种群 = []
        随机种群数 = int(self.参数["初始种群数量"] * self.参数["随机种群比例"])


        for _ in range(随机种群数):
            随机个体 = random.sample(range(1, self.客户数量 + 1), self.客户数量)
            初始种群.append(随机个体)


        插入种群数 = int(self.参数["初始种群数量"] * self.参数["插入种群比例"])
        for _ in range(插入种群数):
            子个体 = []
            种群禁忌表 = copy.deepcopy(self.禁忌表)
            起点禁忌表 = copy.deepcopy(self.禁忌表)

            for _ in range((len(self.距离矩阵) - 1) // self.参数["车辆容量"]):
                环路 = []
                起点 = random.choice(起点禁忌表)
                环路.append(起点)


                节约值排序列表 = []
                for k in range(1, len(self.节约值矩阵[起点 - 1])):
                    节约值排序列表.append((k, self.节约值矩阵[起点 - 1][k]))


                for k in range(len(种群禁忌表)):
                    if 种群禁忌表[k] == -1:
                        节约值排序列表[k] = list(节约值排序列表[k])
                        节约值排序列表[k][1] = -1
                        节约值排序列表[k] = tuple(节约值排序列表[k])

                排序数据 = sorted(节约值排序列表, key=lambda x: x[1], reverse=True)


                for k in range(len(排序数据)):
                    if 排序数据[k][0] == 起点:
                        del 排序数据[k]
                        break


                for k in range(self.参数["车辆容量"] - 1):
                    环路.append(排序数据[k][0])


                for k in range(len(环路)):
                    种群禁忌表[环路[k] - 1] = -1

                for k in range(len(环路)):
                    if 环路[k] in 起点禁忌表:
                        起点禁忌表.remove(环路[k])

                for k in range(len(环路)):
                    子个体.append(环路[k])

            初始种群.append(子个体)

        return 初始种群

    def _选择交叉(self, 种群, 精英数量, 父代数量):
        """选择和交叉操作"""
        交叉后种群 = []


        排序种群 = []
        for 个体 in 种群:
            适应度值 = self.工具.适应度计算(个体, self.距离矩阵)
            排序种群.append((个体, 适应度值))

        排序种群.sort(key=lambda x: x[1])


        for i in range(min(精英数量, len(排序种群))):
            交叉后种群.append(排序种群[i][0])


        父代列表 = []
        for i in range(min(父代数量, len(排序种群))):
            父代列表.append(排序种群[i][0])


        for _ in range((len(种群) - 精英数量) // 2):
            选择索引 = random.sample(range(len(父代列表)), 2)
            父代1 = 父代列表[选择索引[0]]
            父代2 = 父代列表[选择索引[1]]

            子代对 = self.工具.OX交叉(父代1, 父代2, self.禁忌表)
            交叉后种群.append(子代对[0])
            交叉后种群.append(子代对[1])

        return 交叉后种群

    def _获取最优个体(self, 种群):
        """获取种群中的最优个体"""
        最优适应度 = float('inf')
        最优个体 = 种群[0] if 种群 else None

        for 个体 in 种群:
            适应度值 = self.工具.适应度计算(个体, self.距离矩阵)
            if 适应度值 < 最优适应度:
                最优适应度 = 适应度值
                最优个体 = 个体

        return 最优个体

class GA求解器(基础求解器):
    """标准遗传算法求解器"""

    def _变异操作(self, 个体序列):
        """GA变异操作（随机交换）"""
        if random.random() < self.参数["变异概率"]:
            i, j = random.sample(range(len(个体序列)), 2)
            个体序列[i], 个体序列[j] = 个体序列[j], 个体序列[i]
        return 个体序列

    def _运行发布级协议(self):
        """缓存适应度并以有效新解评价数控制预算，排除日志和重复染色体评价。"""
        目标预算 = int(self.参数.get("指标评估预算", 32480))
        按预算终止 = bool(self.参数.get("GA按有效评价预算终止", True))
        最大代数 = int(self.参数["迭代次数"])
        精英数量 = int(self.参数["精英保留数量"])
        父代数量 = int(self.参数["父代选择数量"])
        种群 = copy.deepcopy(self.初始种群)
        历代最优适应度 = []
        历代最优个体 = []
        历代全部种群 = []

        已评价种群 = []
        for 个体 in 种群:
            if self.工具.指标评估次数 >= 目标预算 and not self.工具.已缓存(个体):
                break
            已评价种群.append((个体, self.工具.适应度计算(个体, self.距离矩阵)))
        if not 已评价种群:
            raise RuntimeError("GA在评价初始种群前已耗尽预算")

        全局最优个体, 全局最优适应度 = min(已评价种群, key=lambda 项: 项[1])
        全局最优个体 = 全局最优个体[:]
        代数 = 0
        连续无新解代数 = 0

        安全代数上限 = max(5000, 最大代数 * 25)

        while self.工具.指标评估次数 < 目标预算:
            if not 按预算终止 and 代数 >= 最大代数:
                break

            排序种群 = sorted(已评价种群, key=lambda 项: 项[1])
            父代列表 = [
                个体 for 个体, _ in 排序种群[:min(父代数量, len(排序种群))]
            ]
            if len(父代列表) < 2:
                break

            新种群 = [
                个体[:] for 个体, _ in 排序种群[:min(精英数量, len(排序种群))]
            ]
            while len(新种群) + 1 < len(种群):
                父代1, 父代2 = random.sample(父代列表, 2)
                子代1, 子代2 = self.工具.OX交叉(父代1, 父代2, self.禁忌表)
                新种群.extend([子代1, 子代2])
            if len(新种群) < len(种群):
                父代1, 父代2 = random.sample(父代列表, 2)
                新种群.append(self.工具.OX交叉(父代1, 父代2, self.禁忌表)[0])

            for i in range(min(精英数量, len(新种群)), len(新种群)):
                新种群[i] = self._变异操作(新种群[i])

            评价前 = self.工具.指标评估次数
            下一代 = []
            for 个体 in 新种群:
                if self.工具.指标评估次数 >= 目标预算 and not self.工具.已缓存(个体):
                    continue
                适应度 = self.工具.适应度计算(个体, self.距离矩阵)
                下一代.append((个体, 适应度))

            if not 下一代:
                break
            已评价种群 = 下一代
            种群 = [个体 for 个体, _ in 已评价种群]
            本代最优个体, 本代最优适应度 = min(已评价种群, key=lambda 项: 项[1])
            if 本代最优适应度 < 全局最优适应度 - 1e-12:
                全局最优个体 = 本代最优个体[:]
                全局最优适应度 = 本代最优适应度

            历代最优个体.append(全局最优个体[:])
            历代最优适应度.append(全局最优适应度)
            if self.参数.get("记录全部种群", False):
                历代全部种群.append(copy.deepcopy(种群))

            if self.工具.指标评估次数 == 评价前:
                连续无新解代数 += 1
            else:
                连续无新解代数 = 0
            if 连续无新解代数 >= 20 and self.工具.指标评估次数 < 目标预算:

                for _ in range(100):
                    随机个体 = random.sample(range(1, self.客户数量 + 1), self.客户数量)
                    if not self.工具.已缓存(随机个体):
                        随机适应度 = self.工具.适应度计算(随机个体, self.距离矩阵)
                        已评价种群[-1] = (随机个体, 随机适应度)
                        种群[-1] = 随机个体
                        连续无新解代数 = 0
                        break

            if (
                按预算终止
                and 代数 >= 安全代数上限
                and self.工具.指标评估次数 < 目标预算
            ):

                剩余预算 = 目标预算 - self.工具.指标评估次数
                保底数量 = min(len(种群), 剩余预算)
                保底个体 = []
                for _ in range(保底数量):
                    for _ in range(1000):
                        随机个体 = random.sample(
                            range(1, self.客户数量 + 1), self.客户数量
                        )
                        if not self.工具.已缓存(随机个体):
                            随机适应度 = self.工具.适应度计算(
                                随机个体, self.距离矩阵
                            )
                            保底个体.append((随机个体, 随机适应度))
                            break
                    else:
                        raise RuntimeError("GA安全注入未能生成未缓存排列")

                保留数量 = max(0, len(种群) - len(保底个体))
                已评价种群 = (
                    sorted(已评价种群, key=lambda 项: 项[1])[:保留数量]
                    + 保底个体
                )
                种群 = [个体 for 个体, _ in 已评价种群]
                注入最优个体, 注入最优适应度 = min(
                    保底个体, key=lambda 项: 项[1]
                )
                if 注入最优适应度 < 全局最优适应度 - 1e-12:
                    全局最优个体 = 注入最优个体[:]
                    全局最优适应度 = 注入最优适应度
                连续无新解代数 = 0

            代数 += 1
            if self.参数.get("输出逐代日志", False):
                print(
                    f"GA 第{代数:3d}代｜F={全局最优适应度:.6f} | "
                    f"unique={self.工具.指标评估次数}/{目标预算}"
                )

        if not 历代最优个体:
            历代最优个体.append(全局最优个体[:])
            历代最优适应度.append(全局最优适应度)
        return {
            "历代最优适应度": 历代最优适应度,
            "历代最优个体": 历代最优个体,
            "历代全部种群": 历代全部种群,
            "最终种群": copy.deepcopy(种群),
            "最终最优个体": 全局最优个体,
            "指标评估次数": self.工具.指标评估次数,
            "实际GA代数": 代数,
        }

    def 运行(self):
        """运行GA算法"""
        if self.参数.get("发布级评价协议", False):
            return self._运行发布级协议()
        种群 = copy.deepcopy(self.初始种群)
        历代最优适应度 = []
        历代最优个体 = []
        历代全部种群 = []

        for 代数 in range(self.参数["迭代次数"]):

            种群 = self._选择交叉(种群,
                                  self.参数["精英保留数量"],
                                  self.参数["父代选择数量"])

            for i in range(self.参数["精英保留数量"], len(种群)):
                种群[i] = self._变异操作(种群[i])
            if self.参数.get("记录全部种群", False):
                历代全部种群.append(copy.deepcopy(种群))


            最优个体 = self._获取最优个体(种群)
            历代最优个体.append(最优个体)

            最优适应度 = self.工具.适应度计算(最优个体, self.距离矩阵)
            历代最优适应度.append(最优适应度)

            指标 = self.工具.路径指标计算(最优个体, self.距离矩阵)
            if self.参数.get("输出逐代日志", True):
                print(f"GA 第{代数 + 1:3d}代｜适应度={最优适应度:10.2f} | "
                      f"路径长={指标[2]:6d}  路径均衡={指标[3]:9.2f}  "
                      f"负载均衡={指标[4]:9.2f}")

        return {
            "历代最优适应度": 历代最优适应度,
            "历代最优个体": 历代最优个体,
            "历代全部种群": 历代全部种群,
            "最终种群": copy.deepcopy(种群),
            "最终最优个体": self._获取最优个体(种群),
            "指标评估次数": self.工具.指标评估次数,
        }
