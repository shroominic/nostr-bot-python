FROM ghcr.io/astral-sh/uv:python3.11-alpine

COPY uv.lock pyproject.toml ./

RUN uv sync

WORKDIR /bot

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["/.venv/bin/python", "main.py"]
