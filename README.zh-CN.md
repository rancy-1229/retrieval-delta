# Retrieval Delta

项目名称：**Retrieval Delta**（`retrieval-delta`）。Python 模块仍为 `evidiff`，安装后两种 CLI 命令均可用。源码见 [GitHub 仓库](https://github.com/rancy-1229/retrieval-delta)。

**找出检索器丢掉的证据。**

修改分块、Embedding 或 reranker 后，导出改动前后的检索结果，Retrieval Delta 显示哪些问题丢了哪段原文，并通过退出码拦住退化。

这是早期版本 v0.1.0，尚未发布到 PyPI。零运行时依赖，需要 Python 3.10+，不需要模型 API。

```sh
git clone https://github.com/rancy-1229/retrieval-delta.git
cd retrieval-delta
python -m evidiff diff examples/baseline.json examples/candidate.json --html report.html
```

示例故意产生两项退化，退出码为 1。用浏览器打开 `report.html` 可查看缺失的原文。再运行修复结果：

```sh
python -m evidiff diff examples/baseline.json examples/fixed.json
```

退出码为 0。四个示例问题是合成样例，不是公开数据集上的效果证明。

核心规则：

- 按原文位置计算证据覆盖率，重复、重叠片段不重复计分。
- 每个问题单独检查，平均分改善不能掩盖单题退化。
- 原文、问题或正确证据发生变化时拒绝比较，要求重新建立基线。
- 输出离线 HTML 和 JSON，不上传源文档。
- 支持中文 Unicode 字符位置，区间为 `[start, end)`。

它检查“标注的证据是否被检索到”，不判断答案是否正确，也不判断改写后的段落是否语义等价。字符覆盖率对关键词的重要性没有加权，不能代替人工判断或语义评估。

接入方式、指标定义和限制见 [英文 README](README.md)，数据契约见 [format.md](docs/format.md)。
