# 飞牛影视监控服务

一个轻量级的飞牛影视观看监控面板，支持实时观看状态、历史记录、访问日志分析。

<img src="https://raw.githubusercontent.com/deepvoce/fnmedia-monitor/master/assets/preview-light.jpeg" width="904" alt="浅色模式预览"><br>
<img src="https://raw.githubusercontent.com/deepvoce/fnmedia-monitor/master/assets/preview-dark.jpeg" width="904" alt="深色模式预览">

基于 Flask 的轻量级媒体库监控服务，实时展示飞牛影视数据库中的媒体信息、下载进度和存储统计。

> **V2.0 全新发布** — 采用 Bento 网格 + 渐变光晕风格重设计，新增类型分布环形图、用户排行榜、访客日志表、IP 地理位置地图四大模块，搭配错落入场、计数动画、骨架屏、滚动揭示等 10+ 动画效果。并在首轮基础上完成深度视觉精修：Carousel 阻尼翻页、浅色主题统一、LOGO 透明化双版本、用户排行皇冠、侧边栏 scroll spy 导航。详见 [更新日志](CHANGELOG.md)。

---

## 📦 更新日志

### v2.0 (2026-07-11) 🎨 Bento Dashboard 重设计版 + 视觉精修

> 本次更新聚焦视觉焕新与动画体验，接入后端已有但前端未使用的全部数据，并完成深度视觉精修

**首轮 Bento 重设计**

- **Bento 网格布局** — 12 列模块化卡片错落排列，视觉层次丰富
- **渐变光晕背景** — 紫/青/绿三色 aurora 流动光晕缓慢漂移
- **新增 4 大功能模块** — 类型分布环形图、用户排行榜（金/银/铜徽章）、访客日志表、IP 地理位置地图（Leaflet）
- **10+ 动画效果** — 错落入场、计数动画、骨架屏、悬停微交互、滚动揭示、实时脉冲、主题平滑过渡等
- **可访问性** — 支持 `prefers-reduced-motion`

**深度视觉精修**

- **Carousel 阻尼翻页** — 收藏/下载/系统状态三处列表固定 4 条/页，滚轮 + 箭头 + 圆点三种翻页，350ms 锁定 + 500ms 阻尼过渡
- **浅色主题统一** — 纯淡蓝白渐变背景，sidebar / topbar / brand 透明衔接，消除色块割裂
- **LOGO 透明化 + 双版本** — PIL 移除深蓝背景并裁剪，生成 logo-light.png，深浅主题自动切换 LOGO
- **用户排行皇冠** — 第一名头像叠加金色皇冠 SVG + 呼吸光晕
- **侧边栏导航增强** — 可点击锚点跳转 + scroll spy 高亮 + scroll-margin-top 防遮挡
- **hover 效果去浮夸** — 收敛为 scale(1.02) + 轻微发光

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

- 📊 **数据概览** — 总用户、活跃用户、今日播放、今日观看时长（带计数动画）
- 👀 **当前观看** — 实时显示正在观看的用户、节目与播放进度，LIVE 脉冲指示
- 📈 **播放时段** — 24 小时播放分布柱状图，掌握观看高峰
- 🧾 **观看历史** — 带进度条的详细播放记录，支持按用户筛选
- 🍩 **类型分布** — 环形图直观展示媒体类型占比（V2.0 新增）
- 🏆 **用户排行** — 近 7 天播放排行，前 3 名金/银/铜徽章（V2.0 新增）
- 🗺️ **访客地图** — IP 地理位置地图可视化，圆点大小反映访问次数（V2.0 新增）
- 📡 **访客日志** — Nginx 日志解析表，含 IP/位置/设备/路径/时间（V2.0 新增）
- 📥 **下载监控** — 实时追踪下载任务状态（等待中/下载中/已完成/失败）
- ❤️ **收藏管理** — 查看所有用户的收藏内容
- 🎨 **主题切换** — 深色/浅色主题一键切换，自动记忆偏好，地图瓦片与 LOGO 图源同步切换（双版本 LOGO 适配深浅背景）
- 🎬 **丰富动画** — 错落入场、骨架屏、悬停微交互、滚动揭示等 10+ 动画效果
- 🎠 **Carousel 阻尼翻页** — 收藏/下载/系统状态列表固定 4 条/页，滚轮 + 箭头 + 圆点三种翻页方式
- 🧭 **侧边栏导航** — 可点击锚点跳转 + scroll spy 滚动高亮定位
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
│   └── index.html       # 前端页面（单文件架构，含全部 CSS/JS）
├── static/
│   ├── logo.png         # 深色主题 LOGO（透明背景）
│   └── logo-light.png   # 浅色主题 LOGO（深色文字）
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
