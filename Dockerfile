# Satu image = aplikasi utuh (SPA + API). `docker run` -> app jalan di satu URL.
#
# Nilai image ini bukan kerapian, melainkan BUKTI: dependency canggung produk ini
# (Java untuk PlantUML, pandoc untuk docx, plantuml.jar) memang bisa dibundel. Itu
# yang biasanya diam-diam meruntuhkan klaim "tinggal deploy" — di sini dibuktikan
# terbundel, bukan diasumsikan ada di host.

# ---------- Stage 1: build frontend (Vite -> static) --------------------------
FROM node:20-slim AS frontend
WORKDIR /fe

# Config Supabase frontend adalah COMPILE-TIME untuk Vite (di-inline ke bundle).
# Keduanya PUBLIK (anon key memang dirancang untuk dikirim ke browser), jadi aman
# lewat build-arg. Kosong = frontend jalan mode dev tanpa login (cermin backend).
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
# VITE_API_BASE_URL sengaja TIDAK diset: build produksi memakai same-origin ('')
# karena API disajikan dari container yang sama (lihat App.jsx).

COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # -> /fe/dist

# ---------- Stage 2: runtime (backend + tool + SPA) ---------------------------
FROM python:3.13-slim AS runtime

# Versi tool dipatok supaya image reproducible (bukan "apa pun yang terbaru").
ARG PANDOC_VERSION=3.1.11
ARG PLANTUML_VERSION=1.2024.7

# Dependency SISTEM: Java (PlantUML butuh JRE 17+, layout smetana bawaan jar jadi
# tak butuh Graphviz), plus curl untuk mengunduh tool saat build.
#
# libharfbuzz0b + libfreetype6 + fontconfig + font DejaVu: PlantUML MERASTER teks
# ke PNG lewat java.awt, yang butuh native lib font. `default-jre-headless` di
# image slim TIDAK membawanya, jadi tanpa baris ini PlantUML mati dengan
# `UnsatisfiedLinkError: libharfbuzz.so.0` DAN tak ada font untuk digambar.
# Bug ini tak terlihat di mesin dev (Java + font lengkap) — hanya di container
# ramping, dan ketahuannya dari menjalankan #17 sungguhan, bukan membaca kode.
RUN apt-get update && apt-get install -y --no-install-recommends \
        default-jre-headless \
        libharfbuzz0b \
        libfreetype6 \
        fontconfig \
        fonts-dejavu-core \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# pandoc: .deb resmi dipatok (Debian punya versi lebih lama; docx bisa beda halus).
RUN curl -fsSL -o /tmp/pandoc.deb \
        "https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-1-amd64.deb" \
    && dpkg -i /tmp/pandoc.deb \
    && rm /tmp/pandoc.deb

# plantuml.jar dipatok ke tools/ (dibaca lewat env PLANTUML_JAR di bawah).
RUN mkdir -p /app/tools \
    && curl -fsSL -o /app/tools/plantuml.jar \
        "https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar"

WORKDIR /app

# Dependency Python di-cache terpisah dari kode: layer ini hanya rebuild kalau
# requirements berubah.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Kode aplikasi + SPA hasil build stage 1.
COPY app/ ./app/
COPY --from=frontend /fe/dist ./frontend/dist

# PLANTUML_JAR & FRONTEND_DIST menunjuk ke lokasi di dalam image; sisanya
# (ANTHROPIC_API_KEY, SUPABASE_URL, dst.) diberikan saat RUN, bukan di-bake.
ENV PLANTUML_JAR=/app/tools/plantuml.jar \
    FRONTEND_DIST=/app/frontend/dist \
    DATABASE_PATH=/data/jobs.db \
    TEMPLATES_STORE_PATH=/data/templates

# Data yang harus bertahan melewati restart (DB job, dokumen, template terkompilasi).
# Tanpa volume di-mount ke sini, isinya hilang saat container dibuat ulang.
VOLUME ["/data"]

EXPOSE 8000

# Satu proses uvicorn. Multi-worker JALAN (state di SQLite file, lihat CLAUDE.md),
# tapi default 1 worker paling sederhana & cukup untuk satu instance. Skala
# horizontal = worker queue terpisah (lihat DEPLOY.md), bukan menambah worker.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
