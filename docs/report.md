# 报告生成模块 — `modules/report/`

## 两份 Word

### word_generator.py — 第一份 Word（天气图并排）
- `generate(figure_paths) -> str`
- 输入: `{("obs"/"fcst", time_label, level): (field_path, system_path, system_names)}`
- 结构: 实况(按层次) + 预报(按时次×层次)，每组两张图并排

### analysis_report.py — 第二份 Word（分析报告）
- `generate(trough_analyses, vortex_analyses=None, cold_vortex_analyses=None, subtropical_high_analyses=None, analysis_figures=None) -> str`
- 结构:
  - 一、影响天津的系统列表（高空槽+低涡+冷涡+副高）
  - 二、系统描述（实况+预报）
  - 三、可视化（按层次，实况图+预报追踪图并排）

### 分析结果输入格式

| 参数 | 字段 |
|------|------|
| `trough_analyses` | `trough_num, track_id, location, tilt_type, from_dir, to_dir, impact_time, is_new` |
| `vortex_analyses` | `vortex_num, track_id, level, location, strength, quadrant, from_dir, to_dir, impact_time, is_new` |
| `cold_vortex_analyses` | `cv_num, vortex_id, vortex_type, strength, quadrant, from_dir, to_dir, impact_time, is_new` |
| `subtropical_high_analyses` | `type(obs/fcst), is_affecting, description` |

副高只在 `is_affecting=True` 时显示。

---

## 注意事项
1. 中文加粗: `qn("w:eastAsia")` 设置微软雅黑
2. 图片宽度: 并排各 3.0 英寸，单张 5.5 英寸
3. Word 文件被打开时无法覆盖写入（PermissionError）
