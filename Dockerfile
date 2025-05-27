# meta-analysis-bot用Dockerfile
FROM python:3.12-slim

# 環境変数を設定
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# システム依存関係をインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    # R関連
    r-base \
    r-base-dev \
    # システムライブラリ
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libfontconfig1-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libfreetype6-dev \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    # その他
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリを設定
WORKDIR /app

# Rパッケージをインストール
RUN Rscript -e "install.packages(c('metafor', 'rmarkdown', 'knitr', 'tinytex','ggplot2','pyreadr','logger'), repos='https://cloud.r-project.org/')"

# Python要件をコピーして依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# ポート3000を公開（Slack Socket Modeではポートは不要だが、将来的なHTTP接続のため）
EXPOSE 3000

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# アプリケーションを実行
CMD ["python", "main.py"]
