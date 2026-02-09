# 使用 Python 3.11 官方镜像作为基础
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir torch==2.6.0+cpu -i https://pypi.tuna.tsinghua.edu.cn/simple --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 将本地文件拷贝到容器中
COPY . /app

ENV TZ=Asia/Shanghai

# 暴露端口
EXPOSE 10066

# 运行应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10066", "--workers", "4"]
