# 多 Sheet 对比功能 - 使用指南

## 🎯 新功能概述

### 1. 多 Sheet 独立配置
- 每个 Sheet 组合的匹配条件独立保存
- 切换 Sheet 时，之前配置的条件不会消失
- 可以为不同的 Sheet 组合配置不同的匹配规则

### 2. 多 Sheet 批量对比
- 一次性对比所有配置过的 Sheet 组合
- 结果展示支持多个 Sheet 标签页切换
- 每个 Sheet 组合的结果独立显示

### 3. 修复分页功能
- 上一页/下一页按钮正常工作
- 每页行数选择器正常工作
- 支持后端分页（大数据集）

---

## 📋 使用流程

### 步骤 1：上传文件
```
1. 上传源文件 (A) - 例如：sales_2023.xlsx
2. 上传目标文件 (B) - 例如：sales_2024.xlsx
```

### 步骤 2：配置第一个 Sheet 组合
```
1. 选择 Sheet1（例如：Q1 数据）
2. 点击"+ 添加条件"
3. 选择匹配列：
   - 列A：订单ID
   - 操作：等于
   - 列B：订单ID
4. 观察右侧匹配数量（例如：1000 项）
```

### 步骤 3：配置第二个 Sheet 组合
```
1. 切换到 Sheet2（例如：Q2 数据）
2. 点击"+ 添加条件"
3. 选择匹配列：
   - 列A：客户编号
   - 操作：等于
   - 列B：客户编号
4. 添加第二个条件：
   - 列A：产品名称
   - 操作：包含
   - 列B：关键词
5. 观察匹配数量
```

### 步骤 4：配置第三个 Sheet 组合（可选）
```
1. 切换到 Sheet3（例如：Q3 数据）
2. 重复配置过程...
```

### 步骤 5：预览所有结果
```
1. 点击"预览结果"按钮
2. 系统会批量处理所有配置过的 Sheet 组合
3. 弹出结果预览窗口
```

### 步骤 6：查看多 Sheet 结果
```
结果窗口顶部显示 Sheet 标签页：
┌─────────────────────────────────────┐
│ [Q1数据 ↔ Q1数据] [Q2数据 ↔ Q2数据] [Q3数据 ↔ Q3数据] │
└─────────────────────────────────────┘

点击不同的标签页查看对应的对比结果
```

### 步骤 7：使用分页功能
```
底部分页栏：
┌──────────────────────────────────────────┐
│ 总计：1000 行  [50 / 页 ▼]  [< 上一页] 第 1 页 / 共 20 页 [下一页 >] │
└──────────────────────────────────────────┘

- 点击"上一页"/"下一页"切换页面
- 选择"10 / 页"、"20 / 页"、"50 / 页"、"100 / 页"
```

### 步骤 8：下载结果
```
1. 点击"下载完整结果"按钮
2. 下载当前 Sheet 组合的完整数据（Excel 格式）
```

---

## 🔄 工作流程示例

### 场景：对比三个季度的销售数据

#### 文件结构
```
sales_2023.xlsx
├── Q1 (第一季度)
├── Q2 (第二季度)
└── Q3 (第三季度)

sales_2024.xlsx
├── Q1 (第一季度)
├── Q2 (第二季度)
└── Q3 (第三季度)
```

#### 配置过程
```
1. 配置 Q1 对比
   - Sheet: Q1 ↔ Q1
   - 条件: 订单ID 等于 订单ID
   - 结果: 500 项匹配

2. 配置 Q2 对比
   - Sheet: Q2 ↔ Q2
   - 条件: 订单ID 等于 订单ID
   - 条件: 状态 不等于 状态
   - 结果: 50 项匹配（状态变化的订单）

3. 配置 Q3 对比
   - Sheet: Q3 ↔ Q3
   - 条件: 客户编号 等于 客户编号
   - 结果: 300 项匹配
```

#### 预览结果
```
点击"预览结果"后，看到三个标签页：
[Q1 ↔ Q1] [Q2 ↔ Q2] [Q3 ↔ Q3]

切换标签页查看不同季度的对比结果
```

---

## 🎨 界面说明

### 主界面布局
```
┌─────────────────────────────────────────────────────────┐
│  源文件 (A)                    │  目标文件 (B)            │
│  [上传文件]                    │  [上传文件]              │
│  [Sheet1] [Sheet2] [Sheet3]    │  [Sheet1] [Sheet2]       │
│  ┌─────────────────────┐       │  ┌─────────────────────┐ │
│  │  数据预览表格        │       │  │  数据预览表格        │ │
│  └─────────────────────┘       │  └─────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│  匹配条件配置                                            │
│  [+ 添加条件]                                            │
│  [-- 请选择列 --] [等于] [-- 请选择列 --]  [1000 项] [×] │
│  [订单ID        ] [等于] [订单ID        ]  [1000 项] [×] │
│  [状态          ] [不等于] [状态        ]  [50 项]   [×] │
│                                                          │
│  模式: [交集 (Matched) ▼]                                │
│  最终匹配: 50 项                                         │
│  [预览结果]                                              │
└─────────────────────────────────────────────────────────┘
```

### 结果预览窗口
```
┌─────────────────────────────────────────────────────────┐
│  对比结果预览                    [下载完整结果] [×]       │
├─────────────────────────────────────────────────────────┤
│  [Q1数据 ↔ Q1数据] 模式: 交集  订单ID 等于 订单ID        │
│  [Q1 ↔ Q1] [Q2 ↔ Q2] [Q3 ↔ Q3]  ← Sheet 标签页          │
├─────────────────────────────────────────────────────────┤
│  #  │ 订单ID │ 客户名称 │ 金额  │ 状态  │ ...           │
│  1  │ 10001  │ 张三     │ 1000  │ 完成  │ ...           │
│  2  │ 10002  │ 李四     │ 2000  │ 待付款│ ...           │
│  ... │ ...    │ ...      │ ...   │ ...   │ ...           │
├─────────────────────────────────────────────────────────┤
│  总计：1000 行  [50/页▼]  [<上一页] 第1页/共20页 [下一页>] │
└─────────────────────────────────────────────────────────┘
```

---

## ⚙️ 技术实现

### 1. 条件存储机制
```javascript
// 每个条件行都有 dataset.sheetPair 属性
<div data-sheet-pair="Sheet1-Sheet1">
    <select class="cond-col-a">...</select>
    <select class="cond-op">...</select>
    <select class="cond-col-b">...</select>
</div>

// 切换 Sheet 时，只显示/隐藏对应的条件
if (div.dataset.sheetPair === currentSheetPair) {
    div.style.display = 'flex';
} else {
    div.style.display = 'none';
}
```

### 2. 批量对比流程
```javascript
// 收集所有配置过的 Sheet 组合
const sheetPairConfigs = {};
document.querySelectorAll('#diff-conditions-list > div').forEach(div => {
    const sheetPair = div.dataset.sheetPair;
    // 按 sheetPair 分组条件
    sheetPairConfigs[sheetPair].push(condition);
});

// 批量调用后端 API
for (const sheetPair of Object.keys(sheetPairConfigs)) {
    const result = await fetch('/api/doc/diff/run', {...});
    allResults[sheetPair] = result;
}

// 显示多 Sheet 结果
showMultiSheetDiffResultModal(allResults);
```

### 3. 分页事件绑定
```javascript
// 使用 addEventListener 而不是 onclick 属性
const prevBtn = document.getElementById(`${module}-prev-page`);
prevBtn.addEventListener('click', function() {
    changePage(module, -1);
});

const nextBtn = document.getElementById(`${module}-next-page`);
nextBtn.addEventListener('click', function() {
    changePage(module, 1);
});
```

---

## 🐛 已修复的问题

### 问题 1：切换 Sheet 后条件消失 ✅
**修复前：**
- 切换到 Sheet2 后，Sheet1 的条件被删除
- 无法为多个 Sheet 配置条件

**修复后：**
- 条件按 sheetPair 分组存储
- 切换 Sheet 时只是隐藏/显示，不删除
- 支持多个 Sheet 独立配置

### 问题 2：无法查看多 Sheet 结果 ✅
**修复前：**
- 只能预览当前 Sheet 的结果
- 切换 Sheet 后需要重新点击"预览结果"

**修复后：**
- 一次性对比所有配置过的 Sheet
- 结果窗口显示多个 Sheet 标签页
- 点击标签页切换查看不同 Sheet 的结果

### 问题 3：分页功能无法使用 ✅
**修复前：**
- 点击"上一页"/"下一页"无反应
- 修改"每页行数"无反应

**修复后：**
- 使用 addEventListener 绑定事件
- 分页按钮正常工作
- 支持后端分页（大数据集）

---

## 📝 注意事项

1. **条件独立性**
   - 每个 Sheet 组合的条件是独立的
   - 不同 Sheet 可以有不同数量的条件
   - 不同 Sheet 可以使用不同的匹配模式

2. **性能考虑**
   - 配置多个 Sheet 时，预览会依次处理
   - 大数据集建议使用"下载完整结果"而不是预览
   - 分页功能支持后端分页，不会一次性加载所有数据

3. **数据一致性**
   - 确保两个文件的 Sheet 名称对应
   - 确保匹配列的数据类型一致
   - 空值会被正确处理

---

## 🔄 重启项目

⚠️ **修改代码后必须重启项目！**

```bash
# 停止当前项目（Ctrl+C）
# 重新启动
python main.py
```

---

## 📊 测试场景

### 测试 1：基本多 Sheet 对比
1. 上传包含 3 个 Sheet 的文件
2. 为 Sheet1 配置条件
3. 切换到 Sheet2，配置不同的条件
4. 切换回 Sheet1，确认条件还在
5. 点击"预览结果"
6. 确认看到 2 个 Sheet 标签页

### 测试 2：分页功能
1. 配置一个匹配结果超过 50 行的条件
2. 点击"预览结果"
3. 点击"下一页"，确认显示第 2 页数据
4. 修改"每页行数"为 100
5. 确认显示更新

### 测试 3：Sheet 标签页切换
1. 配置 3 个 Sheet 组合
2. 点击"预览结果"
3. 点击不同的 Sheet 标签页
4. 确认数据和条件正确切换

---

## 🎉 功能亮点

✅ **多 Sheet 独立配置** - 每个 Sheet 组合独立管理
✅ **批量对比** - 一次性处理所有配置
✅ **标签页切换** - 方便查看不同 Sheet 的结果
✅ **分页功能** - 支持大数据集浏览
✅ **条件持久化** - 切换 Sheet 不丢失配置
✅ **友好提示** - 清晰的状态提示信息

---

## 🔧 代码修改总结

### 修改的文件
- `static/js/doc.js` - 前端逻辑（3 处主要修改）

### 主要修改点

#### 1. startDiff() 函数（第 612-712 行）
**修改前：** 只处理当前 Sheet 组合
**修改后：** 收集所有配置过的 Sheet 组合，批量对比

```javascript
// 收集所有配置过的 Sheet 组合
const sheetPairConfigs = {};
document.querySelectorAll('#diff-conditions-list > div').forEach(div => {
    const sheetPair = div.dataset.sheetPair;
    if (colA && colB) {
        if (!sheetPairConfigs[sheetPair]) {
            sheetPairConfigs[sheetPair] = [];
        }
        sheetPairConfigs[sheetPair].push(condition);
    }
});

// 批量处理
for (const sheetPair of configuredPairs) {
    const result = await fetch('/api/doc/diff/run', {...});
    allResults[sheetPair] = result;
}

// 显示多 Sheet 结果
showMultiSheetDiffResultModal(allResults, mode);
```

#### 2. 新增函数（第 759-861 行）
- `showMultiSheetDiffResultModal()` - 显示多 Sheet 结果模态框
- `switchResultSheet()` - 切换结果 Sheet 标签页
- `displayResultForSheetPair()` - 显示指定 Sheet 组合的结果

#### 3. 分页事件绑定（第 197-239 行）
**修改前：** 使用 onclick 属性（可能被转义）
**修改后：** 使用 addEventListener（更安全）

```javascript
// 使用 ID 和 addEventListener
const prevBtn = document.getElementById(`${module}-prev-page`);
prevBtn.addEventListener('click', function() {
    changePage(module, -1);
});
```

---

## 📋 测试清单

### ✅ 基本功能测试
- [ ] 上传多 Sheet 文件
- [ ] 为 Sheet1 配置条件
- [ ] 切换到 Sheet2 配置条件
- [ ] 切换回 Sheet1 确认条件还在
- [ ] 点击"预览结果"
- [ ] 确认看到多个 Sheet 标签页

### ✅ 分页功能测试
- [ ] 点击"下一页"按钮
- [ ] 点击"上一页"按钮
- [ ] 修改"每页行数"
- [ ] 确认页码正确显示
- [ ] 确认数据正确加载

### ✅ Sheet 切换测试
- [ ] 点击不同的 Sheet 标签页
- [ ] 确认数据正确切换
- [ ] 确认条件摘要正确显示
- [ ] 确认下载按钮正常工作

### ✅ 边界情况测试
- [ ] 只配置一个 Sheet 组合
- [ ] 配置 5+ 个 Sheet 组合
- [ ] 某个 Sheet 匹配结果为 0
- [ ] 某个 Sheet 匹配结果超过 10000 行

---

## 🚀 下一步优化建议

1. **并行处理**
   - 当前是串行处理每个 Sheet 组合
   - 可以改为并行处理，提高速度

2. **进度提示**
   - 处理多个 Sheet 时显示进度条
   - 例如："正在处理 Sheet 2/5..."

3. **结果缓存**
   - 缓存已处理的 Sheet 结果
   - 切换标签页时不需要重新加载

4. **批量下载**
   - 支持一次性下载所有 Sheet 的结果
   - 生成包含多个 Sheet 的 Excel 文件

5. **条件模板**
   - 支持保存常用的条件配置
   - 快速应用到其他 Sheet 组合


