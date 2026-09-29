# CPE Video — single image: FastAPI backend + Remotion render + built web editor.
# The backend spawns `npx remotion render` and `node scripts/gen-audio.mjs`, so
# Python, Node, a headless Chrome and CJK fonts all live in one image.
FROM python:3.12-bookworm

# ── Node.js 22 (NodeSource) ──────────────────────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Headless Chrome runtime libs + CJK / emoji fonts (for zh-TW subtitles) ───
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libdbus-1-3 libatk1.0-0 libgbm1 libasound2 libxrandr2 \
    libxkbcommon0 libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 \
    libpango-1.0-0 libcairo2 libcups2 libx11-6 libxcb1 libxext6 libxi6 \
    fonts-noto-cjk fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# ── uv (Python package manager) ──────────────────────────────────────────────
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# ── Node deps (root remotion project + web workspace) ────────────────────────
COPY package.json package-lock.json ./
COPY web/package.json ./web/
RUN npm ci

# ── Python deps (backend) ────────────────────────────────────────────────────
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen

# ── App source ───────────────────────────────────────────────────────────────
COPY . .

# Build the web editor (served by the backend as static files)
RUN npm run web:build

# Pre-download Chrome Headless Shell so the first render isn't slow (best-effort)
RUN npx remotion browser ensure || true

ENV PYTHONUNBUFFERED=1 \
    NODE_ENV=production

WORKDIR /app/backend
EXPOSE 8080
CMD ["sh", "-c", "uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
