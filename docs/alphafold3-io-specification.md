# AlphaFold 3 推理服务输入输出规范

## 文档信息

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-06-25 |
| 最后更新 | 2026-06-25 |
| 基于版本 | AlphaFold 3 (dialect: alphafold3, version: 4) |

---

## 1. 概述

AlphaFold 3 是 Google DeepMind 开发的生物分子结构预测模型，能够预测蛋白质、RNA、DNA、配体及其复合物的三维结构。本文档详细说明推理服务的输入 JSON 格式和输出文件结构。

### 1.1 支持的分子类型

| 类型 | 说明 | 典型应用 |
|------|------|----------|
| **Protein** | 蛋白质链 | 单体蛋白、蛋白复合物 |
| **RNA** | RNA 链 | RNA 结构、RNA-蛋白复合物 |
| **DNA** | DNA 链 | DNA 结构、DNA-蛋白复合物 |
| **Ligand** | 配体（含离子） | 小分子药物、金属离子、辅因子 |

---

## 2. 输入 JSON 规范

### 2.1 顶层结构

```json
{
  "name": "任务名称",
  "modelSeeds": [42],
  "sequences": [
    {"protein": {...}},
    {"rna": {...}},
    {"dna": {...}},
    {"ligand": {...}}
  ],
  "bondedAtomPairs": [...],
  "userCCD": "...",
  "userCCDPath": "...",
  "dialect": "alphafold3",
  "version": 4
}
```

### 2.2 顶层字段详细说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | ✅ 是 | - | 任务名称，用于命名输出文件。必须包含至少一个有效字符（字母、数字、点、破折号、下划线） |
| `modelSeeds` | int[] | ✅ 是 | - | 随机种子列表，至少一个。每个种子生成一个独立的预测结果 |
| `sequences` | array | ✅ 是 | - | 分子序列定义列表，至少一个元素 |
| `bondedAtomPairs` | array | ❌ 否 | null | 共价键定义列表，用于连接不同实体或定义糖基化修饰 |
| `userCCD` | string | ❌ 否 | null | 用户自定义化学组件字典（CIF 格式字符串），与 `userCCDPath` 互斥 |
| `userCCDPath` | string | ❌ 否 | null | 用户自定义化学组件字典文件路径，与 `userCCD` 互斥 |
| `dialect` | string | ✅ 是 | - | 必须为 `"alphafold3"` |
| `version` | int | ✅ 是 | - | 输入格式版本，支持 `1`、`2`、`3`、`4` |

#### version 字段说明

| 版本 | 新增功能 |
|------|----------|
| 1 | 初始 AlphaFold 3 输入格式 |
| 2 | 支持外部 MSA 和模板（`unpairedMsaPath`、`pairedMsaPath`、`mmcifPath`） |
| 3 | 支持外部用户 CCD（`userCCDPath`） |
| 4 | 支持文本描述字段（`description`） |

---

### 2.3 Protein（蛋白质）序列定义

```json
{
  "protein": {
    "id": "A",
    "sequence": "PVLSCGEWQL",
    "modifications": [
      {"ptmType": "HY3", "ptmPosition": 1},
      {"ptmType": "P1L", "ptmPosition": 5}
    ],
    "description": "10 残基蛋白质，含 2 个修饰",
    "unpairedMsa": "...",
    "pairedMsa": "",
    "templates": [...]
  }
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | string \| string[] | ✅ 是 | - | 链 ID，大写字母。列表表示同源多聚体（如 `["A", "B", "C"]`） |
| `sequence` | string | ✅ 是 | - | 氨基酸序列，使用单字母标准氨基酸代码 |
| `modifications` | array | ❌ 否 | [] | 翻译后修饰（PTM）列表 |
| `description` | string | ❌ 否 | null | 链的文本描述（仅用于 JSON 格式，不参与计算） |
| `unpairedMsa` | string | ❌ 否 | null | 未配对的 A3M 格式 MSA，与 `unpairedMsaPath` 互斥 |
| `unpairedMsaPath` | string | ❌ 否 | null | 未配对 MSA 文件路径，与 `unpairedMsa` 互斥 |
| `pairedMsa` | string | ❌ 否 | null | 配对的 A3M 格式 MSA，与 `pairedMsaPath` 互斥 |
| `pairedMsaPath` | string | ❌ 否 | null | 配对 MSA 文件路径，与 `pairedMsa` 互斥 |
| `templates` | array | ❌ 否 | null | 结构模板列表，最多 20 个 |

#### Protein Modification 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `ptmType` | string | ✅ 是 | CCD 修饰代码（如 `HY3`、`P1L`） |
| `ptmPosition` | int | ✅ 是 | 1-based 残基位置 |

#### Protein MSA 配置组合

| unpairedMsa | pairedMsa | templates | 行为 |
|-------------|-----------|-----------|------|
| null | null | null | 自动构建 MSA 和搜索模板（推荐） |
| A3M 字符串 | `""` | [] | 使用自定义 MSA，无模板 |
| A3M 字符串 | `""` | null | 使用自定义 MSA，自动搜索模板 |
| `""` | `""` | [] | 完全无 MSA，无模板 |
| A3M 字符串 | A3M 字符串 | ... | 使用自定义配对和未配对 MSA（专家模式） |

#### Template 结构

```json
{
  "mmcif": "...",
  "mmcifPath": "...",
  "queryIndices": [0, 1, 2, 4, 5, 6],
  "templateIndices": [0, 1, 2, 3, 4, 8]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mmcif` | string | ✅* | 单链蛋白模板的 mmCIF 格式字符串，与 `mmcifPath` 互斥 |
| `mmcifPath` | string | ✅* | 模板 mmCIF 文件路径，与 `mmcif` 互斥 |
| `queryIndices` | int[] | ✅ 是 | 查询序列的 0-based 残基索引 |
| `templateIndices` | int[] | ✅ 是 | 模板序列的 0-based 残基索引，与 `queryIndices` 等长 |

> *注：`mmcif` 和 `mmcifPath` 二选一

---

### 2.4 RNA 序列定义

```json
{
  "rna": {
    "id": "A",
    "sequence": "AGCU",
    "modifications": [
      {"modificationType": "2MG", "basePosition": 1},
      {"modificationType": "5MC", "basePosition": 4}
    ],
    "description": "4 碱基 RNA",
    "unpairedMsa": "..."
  }
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | string \| string[] | ✅ 是 | - | 链 ID，大写字母。列表表示同源多聚体 |
| `sequence` | string | ✅ 是 | - | RNA 序列，仅使用 `A`、`C`、`G`、`U` |
| `modifications` | array | ❌ 否 | [] | RNA 修饰列表 |
| `description` | string | ❌ 否 | null | 链的文本描述 |
| `unpairedMsa` | string | ❌ 否 | null | A3M 格式 MSA，与 `unpairedMsaPath` 互斥 |
| `unpairedMsaPath` | string | ❌ 否 | null | MSA 文件路径，与 `unpairedMsa` 互斥 |

#### RNA Modification 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `modificationType` | string | ✅ 是 | CCD 修饰代码（如 `2MG`、`5MC`） |
| `basePosition` | int | ✅ 是 | 1-based 碱基位置 |

#### RNA MSA 配置

| unpairedMsa | 行为 |
|-------------|------|
| null | 自动构建 MSA（推荐） |
| `""` | 无 MSA（MSA-free 模式） |
| A3M 字符串 | 使用自定义 MSA |

---

### 2.5 DNA 序列定义

```json
{
  "dna": {
    "id": "A",
    "sequence": "GACCTCT",
    "modifications": [
      {"modificationType": "6OG", "basePosition": 1},
      {"modificationType": "6MA", "basePosition": 2}
    ],
    "description": "7 碱基 DNA"
  }
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | string \| string[] | ✅ 是 | - | 链 ID，大写字母。列表表示同源多聚体 |
| `sequence` | string | ✅ 是 | - | DNA 序列，仅使用 `A`、`C`、`G`、`T` |
| `modifications` | array | ❌ 否 | [] | DNA 修饰列表 |
| `description` | string | ❌ 否 | null | 链的文本描述 |

#### DNA Modification 结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `modificationType` | string | ✅ 是 | CCD 修饰代码（如 `6OG`、`6MA`） |
| `basePosition` | int | ✅ 是 | 1-based 碱基位置 |

---

### 2.6 Ligand（配体）序列定义

配体支持三种指定方式：

#### 方式 1：CCD 代码（推荐）

```json
{
  "ligand": {
    "id": ["G", "H", "I"],
    "ccdCodes": ["ATP"],
    "description": "ATP 分子，3 个拷贝"
  }
}
```

#### 方式 2：SMILES 字符串

```json
{
  "ligand": {
    "id": "J",
    "smiles": "CC(=O)OC1C[NH+]2CCC1CC2",
    "description": "自定义配体"
  }
}
```

#### 方式 3：用户自定义 CCD

```json
{
  "ligand": {
    "id": "K",
    "ccdCodes": ["LIG-1"],
    "description": "用户 CCD 中定义的配体"
  }
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | string \| string[] | ✅ 是 | - | 配体 ID，大写字母。列表表示多个拷贝 |
| `ccdCodes` | string[] | ✅* | - | CCD 代码列表，与 `smiles` 互斥 |
| `smiles` | string | ✅* | - | SMILES 字符串，与 `ccdCodes` 互斥 |
| `description` | string | ❌ 否 | null | 配体的文本描述 |

> *注：`ccdCodes` 和 `smiles` 二选一

#### SMILES 字符串转义要求

SMILES 字符串必须正确进行 JSON 转义，特别是反斜杠字符必须转义为两个反斜杠：

```json
// 错误示例
{"smiles": "CCC[C@@H](O)CC\C=C\C=C\C#CC#C\C=C\CO"}

// 正确示例
{"smiles": "CCC[C@@H](O)CC\\C=C\\C=C\\C#CC#C\\C=C\\CO"}
```

#### 离子处理

离子被视为配体，例如镁离子：

```json
{
  "ligand": {
    "id": "M",
    "ccdCodes": ["MG"],
    "description": "镁离子"
  }
}
```

---

### 2.7 BondedAtomPairs（共价键）定义

```json
{
  "bondedAtomPairs": [
    [["A", 145, "SG"], ["L", 1, "C04"]],
    [["J", 1, "O6"], ["J", 2, "C1"]]
  ]
}
```

每个键由两个原子定义，每个原子包含三个字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| chain_id | string | 链 ID（对应序列的 `id` 字段） |
| res_id | int | 1-based 残基索引 |
| atom_name | string | 残基内的唯一原子名称 |

#### 使用场景

- **共价配体**：连接配体与蛋白质（如 `["A", 145, "SG"]` 连接 `["L", 1, "C04"]`）
- **糖基化修饰**：定义糖链内部连接（如 `["J", 1, "O6"]` 连接 `["J", 2, "C1"]`）

#### 限制

- SMILES 定义的配体不能参与共价键（因为 SMILES 不定义唯一原子名称）
- 所有键默认为共价键，不支持其他键型

---

### 2.8 UserCCD（用户自定义 CCD）定义

用户自定义 CCD 用于定义 CCD 中不存在的自定义分子，支持两种提供方式：

#### 方式 1：内联字符串（userCCD）

```json
{
  "userCCD": "data_MY-X7F\n#\n_chem_comp.id MY-X7F\n..."
}
```

#### 方式 2：文件路径（userCCDPath）

```json
{
  "userCCDPath": "/path/to/my_ccd.cif"
}
```

> *注：`userCCD` 和 `userCCDPath` 互斥

#### 必需字段

**单值字段：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `_chem_comp.id` | ✅ 是 | 组件 ID，必须与 `data_` 记录匹配 |
| `_chem_comp.name` | ❌ 否 | 组件全名，未知设为 `?` |
| `_chem_comp.type` | ✅ 是 | 组件类型，通常为 `non-polymer` |
| `_chem_comp.formula` | ❌ 否 | 化学式，未知设为 `?` |
| `_chem_comp.mon_nstd_parent_comp_id` | ❌ 否 | 母体组件 ID，未知设为 `?` |
| `_chem_comp.pdbx_synonyms` | ❌ 否 | 同义词，未知设为 `?` |
| `_chem_comp.formula_weight` | ❌ 否 | 分子量，未知设为 `?` |

**原子字段（每原子一行）：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `_chem_comp_atom.comp_id` | ✅ 是 | 组件 ID |
| `_chem_comp_atom.atom_id` | ✅ 是 | 原子 ID |
| `_chem_comp_atom.type_symbol` | ✅ 是 | 元素符号 |
| `_chem_comp_atom.charge` | ✅ 是 | 原子电荷 |
| `_chem_comp_atom.pdbx_leaving_atom_flag` | ❌ 否 | 离去原子标志，默认为 `N` |
| `_chem_comp_atom.pdbx_model_Cartn_x_ideal` | ✅ 是 | 理想 x 坐标 |
| `_chem_comp_atom.pdbx_model_Cartn_y_ideal` | ✅ 是 | 理想 y 坐标 |
| `_chem_comp_atom.pdbx_model_Cartn_z_ideal` | ✅ 是 | 理想 z 坐标 |

**键字段（每键一行）：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `_chem_comp_bond.atom_id_1` | ✅ 是 | 第一个原子 ID |
| `_chem_comp_bond.atom_id_2` | ✅ 是 | 第二个原子 ID |
| `_chem_comp_bond.value_order` | ✅ 是 | 键级（SING/DOUB/TRIP） |
| `_chem_comp_bond.pdbx_aromatic_flag` | ✅ 是 | 芳香键标志（Y/N） |

---

## 3. 任务组合类型

根据 `sequences` 字段中分子类型的不同组合，AlphaFold 3 支持以下任务类型：

### 3.1 单链预测

| 任务类型 | sequences 组合 | 典型应用 |
|----------|----------------|----------|
| 单体蛋白预测 | 1 × protein | 单链蛋白结构预测 |
| 单链 RNA 预测 | 1 × rna | RNA 二级/三级结构预测 |
| 单链 DNA 预测 | 1 × dna | DNA 结构预测 |
| 单配体预测 | 1 × ligand | 小分子构象预测 |

### 3.2 同源多聚体预测

| 任务类型 | sequences 组合 | 典型应用 |
|----------|----------------|----------|
| 蛋白同源二聚体 | 1 × protein (id: ["A", "B"]) | 同源二聚体结构 |
| 蛋白同源三聚体 | 1 × protein (id: ["A", "B", "C"]) | 同源三聚体结构 |
| RNA 同源二聚体 | 1 × rna (id: ["A", "B"]) | RNA 二聚体 |

### 3.3 异源复合物预测

| 任务类型 | sequences 组合 | 典型应用 |
|----------|----------------|----------|
| 蛋白异源二聚体 | 2 × protein | 蛋白-蛋白相互作用 |
| 蛋白-配体复合物 | protein + ligand | 药物-靶点结合 |
| 蛋白-核酸复合物 | protein + rna/dna | 转录因子-DNA 结合 |
| 抗体-抗原复合物 | 2 × protein | 抗体-抗原结合模式 |
| 核酸-配体复合物 | rna/dna + ligand | 核酸-小分子相互作用 |

### 3.4 多组分复合物预测

| 任务类型 | sequences 组合 | 典型应用 |
|----------|----------------|----------|
| 蛋白-RNA-配体复合物 | protein + rna + ligand | 核糖体结构 |
| 蛋白-DNA-配体复合物 | protein + dna + ligand | 转录因子复合物 |
| 多蛋白-多核酸复合物 | 多 × protein + 多 × rna/dna | 核糖体、剪接体 |
| 全分子复合物 | protein + rna + dna + ligand | 复杂生物分子机器 |

### 3.5 特殊任务类型

| 任务类型 | 配置方式 | 典型应用 |
|----------|----------|----------|
| 糖基化蛋白预测 | protein + ligand (糖链) + bondedAtomPairs | 糖蛋白结构 |
| 共价配体预测 | protein + ligand + bondedAtomPairs | 共价抑制剂结合 |
| 翻译后修饰蛋白预测 | protein (含 modifications) | 磷酸化、糖基化蛋白 |
| MSA-free 预测 | protein (unpairedMsa: "", pairedMsa: "") | 无同源序列蛋白 |
| 模板-free 预测 | protein (templates: []) | 无已知结构蛋白 |

---

## 4. 输出文件规范

### 4.1 输出目录结构

对于每个输入任务，AlphaFold 3 在以任务名称命名的目录中写入所有输出：

```
<job_name>/
├── seed-<seed>_sample-<sample>/          # 每个种子和样本的子目录
│   ├── <job_name>_seed-<seed>_sample-<sample>_confidences.json
│   ├── <job_name>_seed-<seed>_sample-<sample>_model.cif
│   └── <job_name>_seed-<seed>_sample-<sample>_summary_confidences.json
├── seed-<seed>_distogram/                # 仅当 --save_distogram=true
│   └── <job_name>_seed-<seed>_distogram.npz
├── seed-<seed>_embeddings/               # 仅当 --save_embeddings=true
│   └── <job_name>_seed-<seed>_embeddings.npz
├── <job_name>_model.cif                  # 最佳预测结构
├── <job_name>_confidences.json           # 最佳预测置信度
├── <job_name>_summary_confidences.json   # 最佳预测摘要置信度
├── <job_name>_data.json                  # 包含 MSA 和模板的输入数据
├── <job_name>_ranking_scores.csv         # 所有预测的排名分数
└── TERMS_OF_USE.md                       # 使用条款
```

### 4.2 输出文件说明

| 文件 | 说明 |
|------|------|
| `*_model.cif` | 预测的三维结构，mmCIF 格式 |
| `*_confidences.json` | 完整置信度指标（包含 1D/2D 数组） |
| `*_summary_confidences.json` | 摘要置信度指标（标量和小数组） |
| `*_data.json` | 包含 MSA 和模板数据的完整输入 |
| `*_ranking_scores.csv` | 所有预测的排名分数 |
| `*_distogram.npz` | 距离直方图（可选） |
| `*_embeddings.npz` | 嵌入向量（可选） |

---

## 5. 置信度指标详解

### 5.1 摘要指标（summary_confidences.json）

| 指标 | 类型 | 范围 | 说明 |
|------|------|------|------|
| `ptm` | float | 0-1 | 预测的模板建模分数，衡量整体结构准确性 |
| `iptm` | float | 0-1 | 接口预测的模板建模分数，衡量亚基间相互作用准确性 |
| `fraction_disordered` | float | 0-1 | 预测结构中无序区域的比例 |
| `has_clash` | bool | - | 是否存在显著原子冲突（>50% 链或 >100 个冲突原子） |
| `ranking_score` | float | -100~1.5 | 排名分数，用于选择最佳预测。计算公式：`0.8 × ipTM + 0.2 × pTM + 0.5 × disorder - 100 × has_clash` |
| `chain_ptm` | float[] | 0-1 | 每条链的 pTM 分数 |
| `chain_iptm` | float[] | 0-1 | 每条链与其他所有链的平均接口 pTM |
| `chain_pair_iptm` | float[][] | 0-1 | 链对之间的 ipTM 分数矩阵，对角线为链的 pTM |
| `chain_pair_pae_min` | float[][] | 0-100 | 链对之间的最小 PAE 值矩阵，低值表示链间相互作用 |

### 5.2 完整指标（confidences.json）

| 指标 | 类型 | 维度 | 说明 |
|------|------|------|------|
| `pae` | float[][] | [num_tokens, num_tokens] | 预测的对齐误差，(i,j) 表示 token j 相对于 token i 帧的位置误差 |
| `atom_plddts` | float[] | [num_atoms] | 每个原子的 pLDDT 分数（0-100），值越高置信度越高 |
| `contact_probs` | float[][] | [num_tokens, num_tokens] | 接触概率矩阵，(i,j) 表示 token i 和 j 接触（<8Å）的概率 |
| `token_chain_ids` | string[] | [num_tokens] | 每个 token 对应的链 ID |
| `atom_chain_ids` | string[] | [num_atoms] | 每个原子对应的链 ID |

### 5.3 指标解读指南

| 指标范围 | pTM/ipTM 解读 | 建议 |
|----------|---------------|------|
| > 0.8 | 高置信度，预测结构可能接近真实结构 | 可以信赖预测结果 |
| 0.6-0.8 | 中等置信度，预测可能正确 | 需要结合其他证据验证 |
| < 0.6 | 低置信度，预测可能不正确 | 谨慎使用，考虑增加种子数 |
| < 0.05 | pTM 特殊情况（<20 tokens） | 使用 PAE 或 pLDDT 评估 |

### 5.4 排名分数解读

| 排名分数 | 含义 |
|----------|------|
| > 1.0 | 高质量预测，无冲突，高 ipTM |
| 0.8-1.0 | 良好预测，可能存在轻微无序 |
| 0.5-0.8 | 中等质量，可能存在无序或轻微冲突 |
| < 0.5 | 低质量预测，可能存在冲突或低 ipTM |
| < 0 | 存在严重冲突 |

---

## 6. 完整输入示例

### 6.1 蛋白质单体预测

```json
{
  "name": "single_protein",
  "modelSeeds": [42],
  "sequences": [
    {
      "protein": {
        "id": "A",
        "sequence": "GMRESYANENQFGFKTINSDIHKIVIVGGYGKLGGLFARYLRASGYPISILDREDWAVAESILANADVVIVSVPINLTLETIERLKPYLTENMLLADLTSVKREPLAKMLEVHTGAVLGLHPMFGADIASMAKQVVVRCDGRFPERYEWLLEQIQIWGAKIYQTNATEHDHNMTYIQALRHFSTFANGLHLSKQPINLANLLALSSPIYRLELAMIGRLFAQDAELYADIIMDKSENLAVIETLKQTYDEALTFFENNDRQGFIDAFHKVRDWFGDYSEQFLKESRQLLQQANDLKQG"
      }
    }
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 6.2 蛋白质-配体复合物预测

```json
{
  "name": "protein_ligand_complex",
  "modelSeeds": [42, 123],
  "sequences": [
    {
      "protein": {
        "id": "A",
        "sequence": "PVLSCGEWQL",
        "description": "靶蛋白"
      }
    },
    {
      "ligand": {
        "id": "B",
        "ccdCodes": ["ATP"],
        "description": "ATP 配体"
      }
    }
  ],
  "bondedAtomPairs": [
    [["A", 1, "CA"], ["B", 1, "C04"]]
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 6.3 抗体-抗原复合物预测

```json
{
  "name": "antibody_antigen",
  "modelSeeds": [42],
  "sequences": [
    {
      "protein": {
        "id": "H",
        "sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFTF...",
        "description": "重链"
      }
    },
    {
      "protein": {
        "id": "L",
        "sequence": "DIQMTQSPSSLSASVGDRVTITC...",
        "description": "轻链"
      }
    },
    {
      "protein": {
        "id": "A",
        "sequence": "KTNDQVHFGNEIFNADIE...",
        "description": "抗原"
      }
    }
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 6.4 蛋白质-RNA 复合物预测

```json
{
  "name": "protein_rna_complex",
  "modelSeeds": [42],
  "sequences": [
    {
      "protein": {
        "id": "A",
        "sequence": "MVHLTPEEKSAVTALWGKV...",
        "description": "RNA 结合蛋白"
      }
    },
    {
      "rna": {
        "id": "B",
        "sequence": "AGCUAGCUAGCU",
        "description": "RNA 链"
      }
    }
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 6.5 糖基化蛋白预测

```json
{
  "name": "glycoprotein",
  "modelSeeds": [42],
  "sequences": [
    {
      "protein": {
        "id": "A",
        "sequence": "MVHLTPEEKSAVTALWGKV...",
        "description": "糖基化蛋白"
      }
    },
    {
      "ligand": {
        "id": ["B", "C", "D"],
        "ccdCodes": ["NAG", "MAN", "Glc"],
        "description": "糖链"
      }
    }
  ],
  "bondedAtomPairs": [
    [["A", 1, "ND2"], ["B", 1, "C1"]],
    [["B", 1, "O4"], ["C", 1, "C1"]],
    [["C", 1, "O6"], ["D", 1, "C1"]]
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

### 6.6 使用自定义 MSA 和模板

```json
{
  "name": "custom_msa_template",
  "modelSeeds": [42],
  "sequences": [
    {
      "protein": {
        "id": "A",
        "sequence": "PVLSCGEWQL",
        "unpairedMsa": ">query\nPVLSCGEWQL\n>hit1\nPVL--EWQL\n>hit2\nPVLSC-EWQ",
        "pairedMsa": "",
        "templates": [
          {
            "mmcif": "...",
            "queryIndices": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            "templateIndices": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
          }
        ]
      }
    }
  ],
  "dialect": "alphafold3",
  "version": 4
}
```

---

## 7. API 请求/响应格式

### 7.1 请求格式（POST /api/v1/predict）

使用 `multipart/form-data` 格式上传 JSON 文件：

```bash
curl -X POST "http://localhost:8000/api/v1/predict" \
  -F "file=@input.json"
```

### 7.2 成功响应格式

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "job_name": "test_protein",
  "created_at": "2026-06-25T10:00:00Z",
  "completed_at": "2026-06-25T10:05:30Z",
  "duration_seconds": 330,
  "input_summary": {
    "name": "test_protein",
    "sequences": [
      {
        "type": "protein",
        "id": "A",
        "length": 200
      }
    ],
    "num_seeds": 1,
    "num_samples": 5
  },
  "best_prediction": {
    "seed": 42,
    "sample": 0,
    "ranking_score": 0.85,
    "ptm": 0.75,
    "iptm": 0.82,
    "fraction_disordered": 0.05,
    "has_clash": false,
    "chain_ptm": [0.78],
    "chain_iptm": [0.81],
    "chain_pair_iptm": [[0.78]],
    "chain_pair_pae_min": [[0.5]]
  },
  "all_predictions": [
    {
      "seed": 42,
      "sample": 0,
      "ranking_score": 0.85,
      "ptm": 0.75,
      "iptm": 0.82
    },
    {
      "seed": 42,
      "sample": 1,
      "ranking_score": 0.82,
      "ptm": 0.73,
      "iptm": 0.80
    }
  ],
  "files": {
    "best_model_cif": "/api/v1/tasks/550e8400-e29b-41d4-a716-446655440000/files/model.cif",
    "data_json": "/api/v1/tasks/550e8400-e29b-41d4-a716-446655440000/files/data.json",
    "ranking_scores_csv": "/api/v1/tasks/550e8400-e29b-41d4-a716-446655440000/files/ranking_scores.csv",
    "download_zip": "/api/v1/tasks/550e8400-e29b-41d4-a716-446655440000/download"
  }
}
```

### 7.3 错误响应格式

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "job_name": "test_protein",
  "created_at": "2026-06-25T10:00:00Z",
  "completed_at": "2026-06-25T10:01:00Z",
  "duration_seconds": 60,
  "error_message": "GPU out of memory: sequence too long"
}
```

---

## 8. 附录

### 8.1 支持的 CCD 修饰代码示例

#### 蛋白质翻译后修饰（PTM）

| CCD 代码 | 修饰名称 | 说明 |
|----------|----------|------|
| HY3 | 羟基化 | 脯氨酸羟基化 |
| P1L | 磷酸化 | 丝氨酸/苏氨酸磷酸化 |
| SEP | 磷酸丝氨酸 | 磷酸化丝氨酸 |
| TPO | 磷酸苏氨酸 | 磷酸化苏氨酸 |
| PTR | 磷酸酪氨酸 | 磷酸化酪氨酸 |

#### RNA 修饰

| CCD 代码 | 修饰名称 | 说明 |
|----------|----------|------|
| 2MG | 2-甲基鸟苷 | RNA 修饰 |
| 5MC | 5-甲基胞苷 | RNA 修饰 |
| PSU | 假尿苷 | RNA 修饰 |
| M7G | 7-甲基鸟苷 | RNA 帽结构 |

#### DNA 修饰

| CCD 代码 | 修饰名称 | 说明 |
|----------|----------|------|
| 6OG | 8-氧鸟嘌呤 | DNA 损伤标记 |
| 6MA | 6-甲基腺嘌呤 | DNA 甲基化 |

#### 常见配体

| CCD 代码 | 名称 | 说明 |
|----------|------|------|
| ATP | 腺苷三磷酸 | 能量分子 |
| GTP | 鸟苷三磷酸 | 信号分子 |
| NAD | 烟酰胺腺嘌呤二核苷酸 | 辅酶 |
| FAD | 黄素腺嘌呤二核苷酸 | 辅酶 |
| HEM | 血红素 | 金属辅因子 |
| MG | 镁离子 | 金属离子 |
| ZN | 锌离子 | 金属离子 |
| CA | 钙离子 | 金属离子 |
| FE | 铁离子 | 金属离子 |

### 8.2 常见错误及解决方案

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| `JSONDecodeError` | JSON 格式错误 | 检查 JSON 语法，特别是 SMILES 转义 |
| `Sequence ID must be uppercase letters` | ID 格式错误 | 使用大写字母作为链 ID |
| `Duplicate IDs` | 链 ID 重复 | 确保每个链有唯一 ID |
| `Ligand must have one of CCD ID or SMILES` | 配体定义不完整 | 指定 `ccdCodes` 或 `smiles` 之一 |
| `Failed to construct RDKit reference structure` | SMILES 构象生成失败 | 使用 CCD 代码或提供用户 CCD |
| `GPU out of memory` | 序列过长 | 缩短序列或使用更多 GPU |

### 8.3 性能参考

| 序列长度（tokens） | 推理时间（单个种子） | GPU 内存需求 |
|-------------------|---------------------|-------------|
| < 500 | 1-5 分钟 | ~8 GB |
| 500-1000 | 5-15 分钟 | ~16 GB |
| 1000-2000 | 15-30 分钟 | ~32 GB |
| 2000-5000 | 30-90 分钟 | ~64 GB |
| > 5000 | > 90 分钟 | > 80 GB |

> *注：实际时间取决于 GPU 型号、序列复杂度和数据库搜索时间*

---

## 9. 参考资料

- [AlphaFold 3 论文](https://doi.org/10.1038/s41586-024-07487-w)
- [AlphaFold 3 官方仓库](https://github.com/google-deepmind/alphafold3)
- [化学组件字典 (CCD)](https://www.wwpdb.org/data/ccd)
- [SMILES 格式说明](https://en.wikipedia.org/wiki/Simplified_Molecular_Input_Line_Entry_System)
- [mmCIF 格式说明](https://www.iucr.org/resources/cif)
