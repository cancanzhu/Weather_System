# 已知问题与踩坑记录 — `docs/known_issues.md`

新接手的开发者（包括 AI）请优先阅读此文档，避免重复踩坑。

---

## 1. numpy 兼容性 — `np.float` 已移除
meteva 使用了 `np.float` 等旧别名。在导入 meteva 前补回: `np.float = float`。
文件: `micaps4_reader.py`, `micaps14_reader.py`

## 2. metdig `graphy` 数据不可拆解
`mdgcal.trough()` 返回的 `caldata["graphy"]` 不能用 `np.array()` 拆解，必须原样传给 `meb.add_solid_lines()`。

## 3. `meb.creat_axs()` 布局问题
只用 `ax.plot()` 不会触发布局调整，必须用 `meb.add_solid_lines()` 等 meteva 方法。无数据时用 dummy 线触发。

## 4. `ax.text()` 超范围撑大图片
MICAPS14 符号坐标可能在地图外，`bbox_inches="tight"` 会撑大图片。解决: 范围过滤或 `clip_on=True`。

## 5. python-docx 中文加粗
`run.font.name` 只设西文字体，中文需: `run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")`

## 6. MICAPS4 数据范围与地图不匹配
数据覆盖 105-135°E, 20-50°N，`MapConfig` 必须匹配。

## 7. TMP 实况数据可能不存在
`meb.read_micaps14()` 对 TMP 返回 None，TMP 缺失会导致实况冷中心无法识别,需确保 TMP 文件存在

## 8. tkinter 警告
`main.py` 最前面加 `matplotlib.use('Agg')` 消除。

## 9. python-docx run 拆分
不用 `cell.text` 赋值，直接用 `p.add_run(text)` 创建完整 run。

## 10. Word 图片并排超宽
两张图各 3.0 英寸，或改横向页面。

## 11. contour `collections` 属性移除
新版 matplotlib 用 `cs.allsegs[0]` 替代 `cs.collections`。文件: `subtropical_high.py`

## 12. Java fatal error
meteva/metdig 的 tkinter 与 JPype 冲突。`matplotlib.use('Agg')` 解决。

## 13. 追踪不做统一抽象的理由
不同系统追踪逻辑差异大，强行统一增加复杂度。每个系统独立 `xxx_analysis.py`。

## 14. caldata 必须从识别器传递
追踪器需要 metdig 原始返回值，存在识别结果的 `properties["caldata"]` 中。

## 15. MICAPS14 字典值为 None 的处理
`graphy_data.get("lines")` 可能返回 None（键存在但值为 None）。用 `(val or {}).get(key)` 代替 `.get(key, {}).get(key2)`。文件: `micaps14_reader.py`

## 16. 冷涡分析重复调用 `mdgcal.high_low_center`
Step 3 识别和 Step 6 追踪都会调用，产生重复缓存到 `C:\Users\xxx\.metdig\cache\`。第二次读缓存不重复计算，不影响功能。后续可优化为复用识别结果。

## 17. 副高 588 线仅影响时显示
`analysis_plotter.py` 中 588 线最北纬度 < 36°N 时不绘制，`analysis_report.py` 中不影响时不写文字。修改时注意 `SUBTROPICAL_HIGH_LAT_THRESHOLD` 的检查位置。

## 18. 大模型 API 免费额度耗尽

**现象：** `Error code: 403 - AllocationQuota.FreeTierOnly`

**解决：** 登录阿里云 DashScope 控制台关闭"仅使用免费额度"开通付费，或在 `settings.py` 中换模型（如 `qwen-turbo`）。

**降级机制：** 大模型不可用时自动返回坐标描述（如 `(115.0°E, 42.0°N)附近`），不影响程序运行。

## 19. 大模型只在实况匹配的系统影响天津时调用

新生系统（`is_new=True`）的位置描述为"新生成"，不调用大模型。只有已匹配的实况系统才需要根据实况坐标判断省份。当前需要大模型的系统：高空槽（整条线坐标）、低涡（中心坐标）。冷涡和副高不调用大模型。

## 20. 后续替换 LangChain 的改动范围

只需修改 `modules/llm/llm_client.py`。`location_service.py` 的函数签名不变，所有调用方（`trough_analysis.py`、`vortex_analysis.py`）零改动。

## 21. MICAPS4 读取阶段平滑（已修正）

历史版本 `Micaps4Reader.read()` 默认 `smooth=True, smooth_points=5`，而 `DataManager` 调用时未传参，导致数据被"读取5点 → 识别50点 → 绘图10点"三重叠加平滑，小尺度槽线/低涡可能被抹掉。

**修正（2026-06）：** 读取默认改为 `smooth=False`，平滑职责下放：识别用 `SMOOTH_POINTS_DETECT`，绘图用 `SMOOTH_POINTS_PLOT`，互不叠加。调参时只动对应常量，单一变量可控。注意此修正会改变识别结果（一般是识别出更多小系统），升级后请用历史个例对比验证一轮。

## 22. API Key 安全策略（2026-06 新增）

`LLM_API_KEY` 从环境变量 `DASHSCOPE_API_KEY` 读取，禁止硬编码。历史版本曾将真实 Key 写入 `settings.py` 并随工程分发，该 Key 视为已泄露，必须在 DashScope 控制台吊销更换。未设置环境变量时自动降级为坐标描述，不影响流程。同时新增 `LLM_TIMEOUT_SECONDS=10` 超时与客户端复用、位置描述缓存（只缓存成功结果）。

## 23. 追踪器缺测容忍（2026-06 新增）

`TroughTracker` / `VortexTracker` 在单个时次识别结果为空时不再立即清空前序状态，最多容忍连续 `MAX_MISS=1` 个空时次，超过才断开轨迹。低涡速度约束的时间间隔改为按相邻有效时次 `fcst_time` 差值实际计算（跨缺测时次自动放宽），不再硬编码 3 小时。注意：槽线匹配距离阈值 `TROUGH_TRACK_DISTANCE_MAX` 未按间隔缩放，跨 6h 接轨时偏保守（宁断勿错接），如需放宽可在 update 中按间隔比例放大阈值。

## 24. 实况-预报匹配一对一约束（2026-06 新增）

三个 analysis 模块的 `_match_obs_with_forecast` 改为"全局收集候选 → 按距离排序 → 贪心一对一分配"，避免多条实况匹配同一轨迹导致报告重复条目。槽线匹配距离统一改用 `haversine_distance`（旧版平面近似在 40°N 高估东西向距离约 30%）。槽线/低涡轨迹首位置非 +000h 时输出 warning（提示 +000h 数据可能缺失，匹配基准偏移）。冷涡轨迹首位置晚于 +000h 属正常（配合后期才成功），不做检查。

## 25. 陆地底图多部分多边形与缓存（2026-06 新增）

`draw_ocean_land` 旧版每张图重读 shapefile 且只绘制每个 shape 的第一个 part（岛屿环丢失）。已改为模块级缓存坐标（磁盘只读一次）并遍历全部 parts。PatchCollection 不能跨 figure 复用，故每次重建 Polygon 对象。
