# 🧬 K8-Quant 智能量化终端 Docker 容器镜像 (Hugging Face Spaces / 云端通用)
FROM python:3.11-slim

# 设置工作目录与 Python 环境
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HOST=0.0.0.0

# 安装系统基础依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单并安装
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有项目代码及静态资源
COPY . /app/

# 创建必要目录并设置权限 (适配 Hugging Face user 1000)
RUN useradd -m -u 1000 user && \
    mkdir -p /app/logs /app/cache /app/outputs /app/reports && \
    chown -R user:user /app

USER user

# 暴露端口 (Hugging Face Spaces 默认 7860)
EXPOSE 7860

# 启动量化大屏后端服务
CMD ["python", "run_server.py"]
