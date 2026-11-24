# FastAPI 추론 서버 (YOLO + MediaPipe heavy + Random Forest)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# OpenCV·MediaPipe가 쓰는 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
# torch는 CPU 버전을 먼저 설치 (GPU 버전은 수 GB) → 나머지 설치 시 이미 만족된 것으로 처리
RUN TORCH=$(grep -E "^torch==" requirements.txt || echo torch) \
 && VISION=$(grep -E "^torchvision==" requirements.txt || echo torchvision) \
 && pip install --no-cache-dir "$TORCH" "$VISION" --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
