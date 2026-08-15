#stage1 
FROM python:3.12-slim AS builder
WORKDIR /build
COPY src/requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt 

#stage2
FROM python:3.12-slim
ARG APP_VERSION=0.1.0
ENV APP_VERSION=$APP_VERSION

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/*.whl

COPY src/ .

RUN useradd -m postie
USER postie

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

