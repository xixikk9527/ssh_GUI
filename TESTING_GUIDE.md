# Excel 对比功能测试指南

## 修复内容总结

### 1. 后端修复（app/routers/doc.py）
- ✅ 修复 `contains` 和 `not_contains` 逻辑（使用 apply 逐行比较）
- ✅ 修复匹配数量显示（为所有条件正确设置计数）
- ✅ 修复差集模式结果缓存（支持分页）
- ✅ 统一 stats 和 run_diff 的 merge 策略（都使用 outer join + mode 过滤）

### 2. 前端修复（static/js/doc.js）
- ✅ 切换 sheet 后自动添加条件（如果当前 sheet pair 没有条件）
- ✅ 显示友好提示信息

## 测试场景

### 场景 1：基本匹配功能
**步骤：**
1. 上传两个 Excel 文件（文件A 和 文件B）
2. 添加条件：列A.ID 等于 列B.ID
3. 观察右侧匹配数量是否显示
4. 点击"预览结果"查看匹配结果

**预期结果：**
- 条件右侧显示匹配数量（例如："100 项"）
- 底部显示"最终匹配: 100 项"
- 预览结果正确显示匹配的行

### 场景 2：多条件匹配
**步骤：**
1. 添加第一个条件：列A.ID 等于 列B.ID
2. 添加第二个条件：列A.Name 不等于 列B.Name
3. 观察每个条件右侧的匹配数量

**预期结果：**
- 第一个条件显示初始匹配数量（例如："100 项"）
- 第二个条件显示过滤后的数量（例如："5 项"）
- 底部显示"最终匹配: 5 项"

### 场景 3：包含/不包含条件
**步骤：**
1. 添加条件：列A.ID 等于 列B.ID
2. 添加条件：列A.Description 包含 列B.Keyword
3. 点击"预览结果"

**预期结果：**
- 不报错
- 正确过滤出 Description 包含 Keyword 的行
- 匹配数量正确显示

### 场景 4：切换 Sheet
**步骤：**
1. 上传包含多个 Sheet 的 Excel 文件
2. 在 Sheet1 上添加条件并查看匹配结果
3. 切换到 Sheet2
4. 观察条件列表

**预期结果：**
- 切换到 Sheet2 后，自动添加一个新条件
- 或显示提示"请添加匹配条件"
- Sheet1 的条件被隐藏，不影响 Sheet2 的匹配

### 场景 5：差集模式
**步骤：**
1. 选择模式为"仅源文件 (A-B)"
2. 添加条件：列A.ID 等于 列B.ID
3. 点击"预览结果"
4. 尝试分页查看结果

**预期结果：**
- 正确显示只在 A 中存在的行
- 支持分页查看
- 可以导出完整结果

### 场景 6：交集模式
**步骤：**
1. 选择模式为"交集 (Matched)"
2. 添加条件：列A.ID 等于 列B.ID
3. 添加条件：列A.Status 不等于 列B.Status
4. 点击"预览结果"

**预期结果：**
- 只显示在两个文件中都存在且 Status 不同的行
- 匹配数量与 stats 显示一致

## 已知问题和限制

### 1. 必须有至少一个"等于"条件
- **原因**：需要通过"等于"条件进行表连接
- **解决方案**：如果没有"等于"条件，显示错误提示

### 2. 第一个条件必须是"等于"
- **原因**：需要先建立基础连接，才能应用其他过滤条件
- **建议**：UI 可以自动将"等于"条件排序到前面

### 3. 大文件性能
- **限制**：包含/不包含条件使用 apply 逐行比较，大文件可能较慢
- **建议**：对于超过 10 万行的文件，谨慎使用包含/不包含条件

## 调试技巧

### 查看后端日志
```bash
# 后端会输出详细的 DEBUG 信息
DEBUG: Stats - Merging with 1 equals conditions, mode=intersection...
DEBUG: Stats - Left columns: ['ID']
DEBUG: Stats - Right columns: ['ID']
DEBUG: Stats - Initial merge done, shape=(100, 20)
DEBUG: Stats - After mode filtering, shape=(100, 20)
```

### 查看前端控制台
```javascript
// 打开浏览器开发者工具 (F12)
// 查看 Console 标签页
console.log("DEBUG: Diff Result Init. Total Rows:", data.total_rows);
```

### 常见错误信息
- **"需要至少一个'等于'条件来开始"**：添加一个"等于"条件
- **"源文件(A)中找不到列: XXX"**：检查列名是否正确
- **"文件已过期"**：重新上传文件

## 重启项目

⚠️ **修改代码后必须重启项目！**

```bash
# 停止当前项目 (Ctrl+C)
# 重新启动
python main.py
```

## 测试数据示例

### 文件 A (test_a.xlsx)
| ID | Name | Status | Description |
|----|------|--------|-------------|
| 1  | Alice | Active | User account for Alice |
| 2  | Bob | Inactive | User account for Bob |
| 3  | Charlie | Active | User account for Charlie |

### 文件 B (test_b.xlsx)
| ID | Name | Status | Description |
|----|------|--------|-------------|
| 1  | Alice | Active | User account for Alice |
| 2  | Bob | Active | User account for Bob (updated) |
| 4  | David | Active | User account for David |

### 测试结果预期

**交集模式 + ID 等于：**
- 匹配 3 行（ID: 1, 2）

**交集模式 + ID 等于 + Status 不等于：**
- 匹配 1 行（ID: 2，Status 不同）

**差集A模式 + ID 等于：**
- 匹配 1 行（ID: 3，只在 A 中）

**差集B模式 + ID 等于：**
- 匹配 1 行（ID: 4，只在 B 中）

