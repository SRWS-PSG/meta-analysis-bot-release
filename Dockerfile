# meta-analysis-bot用Dockerfile
FROM python:3.12-slim

# 環境変数を設定
ENV PYTHONUNBUFFERED=1
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
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

# ポートを公開 (Herokuが$PORT環境変数を設定)
# EXPOSE $PORT # HerokuではCMDで直接$PORTを使用するため、EXPOSEは必須ではない

# ヘルスチェックはHerokuの機能に任せるため削除
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#    CMD python -c "import sys; sys.exit(0)"

# アプリケーションを実行 (Herokuは$PORTにバインドすることを期待)
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:${PORT}", "--workers", "4", "--timeout", "120"]
