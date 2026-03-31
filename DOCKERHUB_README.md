# 飞牛影视监控服务

一个轻量级的飞牛影视观看监控面板，支持实时观看状态、历史记录、访问日志分析。

<img src="https://raw.githubusercontent.com/deepvoce/fnmedia-monitor/master/assets/preview-light.jpeg" width="904" alt="浅色模式预览"><br>
<img src="https://raw.githubusercontent.com/deepvoce/fnmedia-monitor/master/assets/preview-dark.jpeg" width="904" alt="深色模式预览">

基于 Flask 的轻量级媒体库监控服务，实时展示飞牛影视数据库中的媒体信息、下载进度和存储统计。

---

## 📦 更新日志

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
