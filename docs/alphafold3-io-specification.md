# AlphaFold 3 推理服务输入输出规范

## 文档信息

| 字段 | 内容 |
|------|------|
| 文档版本 | v2.0 |
| 创建日期 | 2026-06-25 |
| 最后更新 | 2026-06-25 |
| 基于版本 | AlphaFold 3 (dialect: alphafold3, version: 4) |

---

## 1. 顶层参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | ✅ | - | 任务名称，用于命名输出文件 |
| `modelSeeds` | int[] | ✅ | - | 随机种子列表，至少 1 个 |
| `sequences` | array | ✅ | - | 分子序列定义，至少 1 个 |
| `dialect` | string | ✅ | - | 固定值 `"alphafold3"` |
| `version` | int | ✅ | - | 固定值 `4` |
| `bondedAtomPairs` | array | ❌ | null | 共价键定义 |
| `userCCD` | string | ❌ | null | 用户自定义 CCD（内联） |
| `userCCDPath` | string | ❌ | null | 用户自定义 CCD（文件路径） |

### version 字段说明

| 版本 | 新增功能 |
|------|----------|
| 1 | 初始 AlphaFold 3 输入格式 |
| 2 | 支持外部 MSA 和模板（`unpairedMsaPath`、`pairedMsaPath`、`mmcifPath`） |
| 3 | 支持外部用户 CCD（`userCCDPath`） |
| 4 | 支持文本描述字段（`description`） |

---

## 2. 序列类型参数

### 2.1 Protein（蛋白质）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string \| string[] | ✅ | 链 ID，大写字母。列表表示同源多聚体 |
| `sequence` | string | ✅ | 氨基酸序列（单字母代码） |
| `modifications` | array | ❌ | 翻译后修饰 `[{ptmType, ptmPosition}]` |
| `description` | string | ❌ | 链描述 |
| `unpairedMsa` | string | ❌ | 未配对 MSA（A3M 格式） |
| `unpairedMsaPath` | string | ❌ | 未配对 MSA 文件路径 |
| `pairedMsa` | string | ❌ | 配对 MSA（A3M 格式） |
| `pairedMsaPath` | string | ❌ | 配对 MSA 文件路径 |
| `templates` | array | ❌ | 结构模板 `[{mmcif, queryIndices, templateIndices}]` |

#### Protein Modification 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ptmType` | string | ✅ | CCD 修饰代码（如 `HY3`、`P1L`） |
| `ptmPosition` | int | ✅ | 1-based 残基位置 |

#### Template 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mmcif` | string | ✅* | 单链蛋白模板的 mmCIF 格式，与 `mmcifPath` 互斥 |
| `mmcifPath` | string | ✅* | 模板 mmCIF 文件路径，与 `mmcif` 互斥 |
| `queryIndices` | int[] | ✅ | 查询序列的 0-based 残基索引 |
| `templateIndices` | int[] | ✅ | 模板序列的 0-based 残基索引，与 `queryIndices` 等长 |

### 2.2 RNA

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string \| string[] | ✅ | 链 ID |
| `sequence` | string | ✅ | RNA 序列（A/C/G/U） |
| `modifications` | array | ❌ | 修饰 `[{modificationType, basePosition}]` |
| `description` | string | ❌ | 链描述 |
| `unpairedMsa` | string | ❌ | MSA（A3M 格式） |
| `unpairedMsaPath` | string | ❌ | MSA 文件路径 |

#### RNA Modification 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `modificationType` | string | ✅ | CCD 修饰代码（如 `2MG`、`5MC`） |
| `basePosition` | int | ✅ | 1-based 碱基位置 |

### 2.3 DNA

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string \| string[] | ✅ | 链 ID |
| `sequence` | string | ✅ | DNA 序列（A/C/G/T） |
| `modifications` | array | ❌ | 修饰 `[{modificationType, basePosition}]` |
| `description` | string | ❌ | 链描述 |

#### DNA Modification 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `modificationType` | string | ✅ | CCD 修饰代码（如 `6OG`、`6MA`） |
| `basePosition` | int | ✅ | 1-based 碱基位置 |

### 2.4 Ligand（配体）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string \| string[] | ✅ | 配体 ID |
| `ccdCodes` | string[] | ✅* | CCD 代码，与 `smiles` 二选一 |
| `smiles` | string | ✅* | SMILES 字符串，与 `ccdCodes` 二选一 |
| `description` | string | ❌ | 配体描述 |

> **注意**：`ccdCodes` 和 `smiles` 互斥，只能使用其中之一。

#### SMILES 转义要求

SMILES 字符串必须正确进行 JSON 转义，反斜杠必须转义为 `\\`：

```json
// 错误
{"smiles": "CC\C=C\CO"}

// 正确
{"smiles": "CC\\C=C\\CO"}
```

### 2.5 BondedAtomPairs（共价键）

每个键由两个原子定义，每个原子包含三个字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| chain_id | string | 链 ID |
| res_id | int | 1-based 残基索引 |
| atom_name | string | 残基内的唯一原子名称 |

示例：`[["A", 145, "SG"], ["L", 1, "C04"]]`

**限制**：SMILES 定义的配体不能参与共价键。

---

## 3. 任务类型速查表

| 任务类型 | sequences 组合 | 最简参数 |
|----------|----------------|----------|
| 蛋白质单体 | 1 × protein | `id` + `sequence` |
| 蛋白质同源多聚体 | 1 × protein (多 id) | `id: ["A","B"]` + `sequence` |
| 蛋白质异源复合物 | N × protein | 每个 `id` + `sequence` |
| 蛋白质-配体 | protein + ligand | 蛋白 + `ccdCodes` 或 `smiles` |
| 蛋白质-DNA | protein + dna | 蛋白 + DNA `sequence` |
| 蛋白质-RNA | protein + rna | 蛋白 + RNA `sequence` |
| DNA 结构 | 1 × dna | `id` + `sequence` |
| RNA 结构 | 1 × rna | `id` + `sequence` |
| 配体构象 | 1 × ligand | `id` + `ccdCodes` |
| 糖基化修饰 | protein + ligand + bonds | + `bondedAtomPairs` |

---

## 4. 不同任务的请求 JSON 示例

### 4.1 蛋白质单体预测

```json
{
  "name": "single_protein",
  "modelSeeds": [42],
  "sequences": [
    {"protein": {"id": "A", "sequence": "MKFLILLFNILCLFPVLAAD"}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 4.2 蛋白质同源二聚体

```json
{
  "name": "homodimer",
  "modelSeeds": [42],
  "sequences": [
    {"protein": {"id": ["A", "B"], "sequence": "MKFLILLFNILCLFPVLAAD"}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 4.3 蛋白质异源复合物

```json
{
  "name": "heterodimer",
  "modelSeeds": [42],
  "sequences": [
    {"protein": {"id": "A", "sequence": "MKFLILLFNILCLFPVLAAD"}},
    {"protein": {"id": "B", "sequence": "MVHLTPEEKSAVTALWGKV"}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 4.4 蛋白质-配体复合物

```json
{
  "name": "protein_ligand",
  "modelSeeds": [42],
  "sequences": [
    {"protein": {"id": "A", "sequence": "MKFLILLFNILCLFPVLAAD"}},
    {"ligand": {"id": "B", "ccdCodes": ["ATP"]}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 4.5 蛋白质-DNA 复合物

```json
{
  "name": "protein_dna",
  "modelSeeds": [42],
  "sequences": [
    {"protein": {"id": "A", "sequence": "MKFLILLFNILCLFPVLAAD"}},
    {"dna": {"id": "B", "sequence": "GACCTCTGACCTCT"}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 4.6 蛋白质-RNA 复合物

```json
{
  "name": "protein_rna",
  "modelSeeds": [42],
  "sequences": [
    {"protein": {"id": "A", "sequence": "MKFLILLFNILCLFPVLAAD"}},
    {"rna": {"id": "B", "sequence": "AGCUAGCUAGCU"}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 4.7 DNA 结构预测

```json
{
  "name": "dna_structure",
  "modelSeeds": [42],
  "sequences": [
    {"dna": {"id": "A", "sequence": "GACCTCTGACCTCT"}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 4.8 RNA 结构预测

```json
{
  "name": "rna_structure",
  "modelSeeds": [42],
  "sequences": [
    {"rna": {"id": "A", "sequence": "AGCUAGCUAGCU"}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 4.9 抗体-抗原复合物

```json
{
  "name": "antibody_antigen",
  "modelSeeds": [42],
  "sequences": [
    {"protein": {"id": "H", "sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTF"}},
    {"protein": {"id": "L", "sequence": "DIQMTQSPSSLSASVGDRVTITC"}},
    {"protein": {"id": "A", "sequence": "KTNDQVHFGNEIFNADIE"}}
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 4.10 糖基化蛋白（含共价键）

```json
{
  "name": "glycoprotein",
  "modelSeeds": [42],
  "sequences": [
    {"protein": {"id": "A", "sequence": "MKFLILLFNILCLFPVLAAD"}},
    {"ligand": {"id": ["B", "C"], "ccdCodes": ["NAG", "MAN"]}}
  ],
  "bondedAtomPairs": [
    [["A", 1, "ND2"], ["B", 1, "C1"]],
    [["B", 1, "O4"], ["C", 1, "C1"]]
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

---

## 5. 输出文件规范

### 5.1 输出目录结构

```
<job_name>/
├── seed-<seed>_sample-<sample>/
│   ├── <job_name>_seed-<seed>_sample-<sample>_confidences.json
│   ├── <job_name>_seed-<seed>_sample-<sample>_model.cif
│   └── <job_name>_seed-<seed>_sample-<sample>_summary_confidences.json
├── <job_name>_model.cif                  # 最佳预测结构
├── <job_name>_confidences.json           # 最佳预测置信度
├── <job_name>_summary_confidences.json   # 最佳预测摘要置信度
├── <job_name>_data.json                  # 包含 MSA 和模板的输入数据
└── <job_name>_ranking_scores.csv         # 所有预测的排名分数
```

### 5.2 摘要置信度指标

| 指标 | 类型 | 范围 | 说明 |
|------|------|------|------|
| `ptm` | float | 0-1 | 预测的模板建模分数，衡量整体结构准确性 |
| `iptm` | float | 0-1 | 接口预测的模板建模分数，衡量亚基间相互作用准确性 |
| `fraction_disordered` | float | 0-1 | 预测结构中无序区域的比例 |
| `has_clash` | bool | - | 是否存在显著原子冲突 |
| `ranking_score` | float | -100~1.5 | 排名分数，计算公式：`0.8 × ipTM + 0.2 × pTM + 0.5 × disorder - 100 × has_clash` |
| `chain_ptm` | float[] | 0-1 | 每条链的 pTM 分数 |
| `chain_iptm` | float[] | 0-1 | 每条链与其他所有链的平均接口 pTM |
| `chain_pair_iptm` | float[][] | 0-1 | 链对之间的 ipTM 分数矩阵 |
| `chain_pair_pae_min` | float[][] | 0-100 | 链对之间的最小 PAE 值矩阵 |

### 5.3 完整置信度指标

| 指标 | 类型 | 维度 | 说明 |
|------|------|------|------|
| `pae` | float[][] | [num_tokens, num_tokens] | 预测的对齐误差 |
| `atom_plddts` | float[] | [num_atoms] | 每个原子的 pLDDT 分数（0-100） |
| `contact_probs` | float[][] | [num_tokens, num_tokens] | 接触概率矩阵 |
| `token_chain_ids` | string[] | [num_tokens] | 每个 token 对应的链 ID |
| `atom_chain_ids` | string[] | [num_atoms] | 每个原子对应的链 ID |

### 5.4 指标解读

| 指标范围 | 含义 |
|----------|------|
| pTM/ipTM > 0.8 | 高置信度，预测结构可能接近真实结构 |
| pTM/ipTM 0.6-0.8 | 中等置信度，需要结合其他证据验证 |
| pTM/ipTM < 0.6 | 低置信度，谨慎使用 |
| ranking_score > 1.0 | 高质量预测 |
| ranking_score 0.8-1.0 | 良好预测 |
| ranking_score < 0.5 | 低质量预测 |

---

## 6. 快速填写模板

```json
{
  "name": "任务名称",
  "modelSeeds": [42],
  "sequences": [
    {
      "分子类型": {
        "id": "链ID",
        "sequence": "序列"
      }
    }
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

**分子类型**：`protein` / `rna` / `dna` / `ligand`

**链 ID**：大写字母 `A`-`Z`，或多聚体用 `["A", "B", "C"]`

**序列**：
- 蛋白质：氨基酸单字母代码（如 `MKFLILL...`）
- RNA：`A`/`C`/`G`/`U`
- DNA：`A`/`C`/`G`/`T`
- 配体：用 `ccdCodes` 或 `smiles`

---

## 7. API 请求格式

### 请求方式

```bash
curl -X POST "http://localhost:8000/api/v1/predict" \
  -H "Content-Type: application/json" \
  -d @input.json
```

### 成功响应

```json
{
  "task_id": "uuid",
  "status": "completed",
  "job_name": "任务名称",
  "created_at": "2026-06-25T10:00:00Z",
  "completed_at": "2026-06-25T10:05:30Z",
  "duration_seconds": 330,
  "best_prediction": {
    "seed": 42,
    "sample": 0,
    "ranking_score": 0.85,
    "ptm": 0.75,
    "iptm": 0.82
  },
  "files": {
    "best_model_cif": "/api/v1/tasks/uuid/files/model.cif",
    "download_zip": "/api/v1/tasks/uuid/download"
  }
}
```

### 错误响应

```json
{
  "task_id": "uuid",
  "status": "failed",
  "error_message": "错误信息"
}
```

---

## 8. 常见 CCD 代码参考

### 配体

| CCD 代码 | 名称 | 说明 |
|----------|------|------|
| ATP | 腺苷三磷酸 | 能量分子 |
| GTP | 鸟苷三磷酸 | 信号分子 |
| NAD | 烟酰胺腺嘌呤二核苷酸 | 辅酶 |
| HEM | 血红素 | 金属辅因子 |
| MG | 镁离子 | 金属离子 |
| ZN | 锌离子 | 金属离子 |

### 蛋白质修饰

| CCD 代码 | 修饰名称 |
|----------|----------|
| HY3 | 脯氨酸羟基化 |
| SEP | 磷酸丝氨酸 |
| TPO | 磷酸苏氨酸 |
| PTR | 磷酸酪氨酸 |

### RNA 修饰

| CCD 代码 | 修饰名称 |
|----------|----------|
| 2MG | 2-甲基鸟苷 |
| 5MC | 5-甲基胞苷 |
| PSU | 假尿苷 |

---

## 9. 参考资料

- [AlphaFold 3 论文](https://doi.org/10.1038/s41586-024-07487-w)
- [AlphaFold 3 官方仓库](https://github.com/google-deepmind/alphafold3)
- [化学组件字典 (CCD)](https://www.wwpdb.org/data/ccd)
