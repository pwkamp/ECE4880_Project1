FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends libtk8.6 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pc_client/requirements.txt backend/pc_client/requirements-dev.txt /tmp/requirements/
RUN python -m pip install --no-cache-dir -r /tmp/requirements/requirements-dev.txt

COPY backend/ /app/backend/
COPY protocol/ /app/protocol/
COPY master_test.py /app/master_test.py
COPY .gitignore ECE4880_Project1.code-workspace /app/
COPY firmware/main/CMakeLists.txt /app/firmware/main/CMakeLists.txt
COPY firmware/.vscode/settings.json /app/firmware/.vscode/settings.json

EXPOSE 8000

CMD ["python", "main.py"]
