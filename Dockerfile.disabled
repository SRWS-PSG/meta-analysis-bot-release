FROM python:3.11-slim

# R環境のインストール
RUN apt-get update && apt-get install -y \
    r-base \
    r-base-dev \
    && rm -rf /var/lib/apt/lists/*

# Rパッケージのインストール
RUN R -e "install.packages(c('metafor', 'meta', 'forestplot'), repos='https://cran.rstudio.com/')"

# Pythonワーキングディレクトリ
WORKDIR /app

# 依存関係インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコピー
COPY . .

# Heroku用のポート設定
EXPOSE $PORT

# Gunicorn起動（Heroku対応）
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 main:application
