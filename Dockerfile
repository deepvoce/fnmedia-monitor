FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 5000

# 单 worker + 线程：stats/logs/locations 的进程内缓存与 IP 查询 lru_cache 才能跨请求生效，
# 同时把内存占用压到 200m 限制的一半以下
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5000", "main:app"]
