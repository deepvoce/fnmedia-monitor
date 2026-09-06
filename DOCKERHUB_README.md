# 飞牛影视监控服务

一个轻量级的飞牛影视观看监控面板，支持实时观看状态、历史记录、访问日志分析。

<img src="https://iili.io/C1mFyIn.png" width="904" alt="浅色模式预览"><br>
<img src="https://iili.io/C1mKK22.png" width="904" alt="深色模式预览">

基于 Flask 的轻量级媒体库监控服务，实时展示飞牛影视数据库中的媒体信息、播放状态和访客统计。前端资源（Chart.js / Leaflet / 字体）全部本地化，部署无需访问外网。

---

## 📦 更新日志

### v2.1 (2026-09-07) 🐛 正确性修复 + ⚡ 性能优化

> 修复几处长期数据错误，全面本地化前端资源，国内 NAS 无外网也能秒开

**数据修复**

- **时区修复** — 播放时段趋势与周活动热力图此前按 UTC 分桶，整体偏移 8 小时，现按本地时区统计
- **播放时长分布改为真实数据** — 旧版图表数值有误，现按单次观看秒数真实分桶（<30m / 30-60m / 1-2h / 2-4h / >4h）
- **热门内容按条目聚合** — 不同剧集的同名集（如"第1集"）不再被错误合并，剧集显示"剧名 · 集名"
- **访客地图修复** — 更换地图瓦片源，解决原瓦片服务要求 API Key 导致地图无法显示的问题

**性能与体验**

- **完全离线可用** — Chart.js / Leaflet / 字体全部内置，移除 Google Fonts 与公共 CDN 外链
- **大日志不再卡顿** — 访问日志只读末尾 256KB
- **图表原地更新** — 30 秒轮询不再重建图表，无闪烁
- **gunicorn 单 worker 多线程** — 缓存真正生效，外部 IP 查询量减半，内存占用更低
- **统计卡趋势图真实化** — 四张小图分别显示近 7 天累计用户 / 活跃 / 播放 / 时长
- **系统状态卡真实数据** — 数据库大小、同步时间、运行时长、累计播放
- **移动端适配** — 新增抽屉式导航菜单（原小屏下无法打开导航）
- **访客日志降噪** — 自动过滤静态资源请求

### v2.0 (2026-07-11) 🎨 Bento Dashboard 重设计

> 全面视觉焕新，玻璃拟态 + 渐变光晕风格

- **Bento 网格布局** — 模块化卡片错落排列，视觉层次丰富
- **渐变光晕背景** — 紫/青/粉三色 aurora 流动光晕
- **新增模块** — 内容类型环形图、用户排行榜（金银铜徽章）、访客日志表、IP 地理位置地图
- **丰富动效** — 错落入场、数字计数、骨架屏、滚动揭示，支持 prefers-reduced-motion
- **深浅双主题** — 深色/浅色完整适配，LOGO 随主题自动切换

### v1.1 (2026-04-01) ⚡ 性能优化版

> 本次更新聚焦性能优化，页面刷新体验大幅提升

- **页面秒开** — API 响应缓存（30s），刷新不再等待
- **DB 查询 ↓90%** — 批量层级查询替代逐条递归，大幅减少数据库压力
- **响应 ↑50-98%** — IP 查询去重 + 缓存，地理位置可视化秒开
- **主动刷新机制** — 点「刷新」按钮强制获取最新数据，自动轮询走缓存
- **新增 Dockerfile** — 支持直接 `docker build`，不再依赖挂载代码目录
- **CACHE_TTL 环境变量** — 可自定义缓存时间（默认 30 秒）


### v1.0 (2026-03-17) 🎉 首个发布

> 飞牛影视监控面板正式上线

- 实时监控当前观看状态与播放进度
- 播放历史记录，支持按用户筛选
- 统计图表：类型分布、用户排行、热门内容
- 24 小时播放时段分布图
- 存储使用情况可视化
- Nginx 访客日志分析与 IP 地理位置地图
- 收藏与下载任务管理
- 深色/浅色主题切换，自动记忆偏好
- Docker 一键部署，低资源占用（~50MB RAM）

---

## ✨ 功能特性

- 📊 **数据概览** — 总用户、活跃用户、今日播放、今日观看时长
- 👀 **当前观看** — 实时显示正在观看的用户、节目与播放进度
- 📈 **播放时段** — 24 小时播放分布柱状图，掌握观看高峰
- 🧾 **观看历史** — 带进度条的详细播放记录，支持按用户筛选
- 🌍 **访客分析** — Nginx 日志解析，IP 地理位置地图可视化
- 📥 **下载监控** — 实时追踪下载任务状态（等待中/下载中/已完成/失败）
- ❤️ **收藏管理** — 查看所有用户的收藏内容
- 🎨 **主题切换** — 深色/浅色主题一键切换，自动记忆偏好
- 🐳 **Docker 部署** — 一键部署，低资源占用（~50MB RAM）

---

## 🚀 快速开始

### 方式一：使用构建镜像（推荐）

```bash
docker run -d \
  --name fnmedia-monitor \
  -p 5000:5000 \
  -v /path/to/trimmedia.db:/app/database/trimmedia.db:ro \
  -e FNMEDIA_DB_PATH=/app/database/trimmedia.db \
  --restart unless-stopped \
  deepvoce/fnmedia-monitor:latest
```

### 方式二：Docker Compose

```yaml
version: '3.8'
services:
  fnmedia-monitor:
    image: deepvoce/fnmedia-monitor:latest
    container_name: fnmedia-monitor
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - FNMEDIA_DB_PATH=/app/database/trimmedia.db
      - LOG_ENABLED=1
      - CACHE_TTL=30
      - TZ=Asia/Shanghai
    volumes:
      - /path/to/trimmedia.db:/app/database/trimmedia.db:ro
    mem_limit: 200m
```

启动后访问 `http://localhost:5000` 即可查看面板。

---

## ⚙️ 配置

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `FNMEDIA_DB_PATH` | `/app/database/trimmedia.db` | 飞牛影视数据库路径（必须） |
| `LOG_PATH` | `/app/logs` | 访问日志目录 |
| `LOG_ENABLED` | `0` | 是否记录访问日志（0/1） |
| `CACHE_TTL` | `30` | API 响应缓存时间（秒） |
| `DB_COPY_TTL` | `60` | 数据库副本刷新间隔（秒） |
| `PORT` | `5000` | Web 服务端口 |
| `IPINFO_TOKEN` | - | ipinfo.io Token（可选，更精准的 IP 归属地查询） |
| `TZ` | - | 建议设置为 `Asia/Shanghai`，时段统计按本地时区分桶 |

> ⚠️ **升级到 v2.1 提示**：请设置 `TZ=Asia/Shanghai`（或你的本地时区），播放时段与热力图将按该时区统计。

### 飞牛影视数据库路径

飞牛影视默认数据库位置：

```
/usr/local/apps/@appdata/trim.media/database/trimmedia.db
```

如路径不同，请修改 `FNMEDIA_DB_PATH` 环境变量。

---

## 📁 项目结构

```
├── main.py              # Flask 主应用
├── config.py            # 配置管理
├── templates/
│   └── index.html       # 前端页面
├── static/              # 本地静态资源（logo、字体、Chart.js/Leaflet）
├── Dockerfile           # Docker 构建文件
├── docker-compose.yml   # Docker Compose 配置
└── requirements.txt     # Python 依赖
```

---

## 🔗 相关链接

- **GitHub**: https://github.com/deepvoce/fnmedia-monitor
- **Docker Hub**: https://hub.docker.com/r/deepvoce/fnmedia-monitor
- **Issue 反馈**: https://github.com/deepvoce/fnmedia-monitor/issues

---

## 📄 许可证

MIT License — 自由使用、修改和分发
