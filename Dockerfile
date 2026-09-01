FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml costs.yaml ./
COPY src ./src
COPY tests ./tests
COPY data ./data
RUN pip install --no-cache-dir -e ".[dev]"
CMD ["vanta", "evaluate", "--suite", "development", "--no-llm", "--skip-llm-arm"]
