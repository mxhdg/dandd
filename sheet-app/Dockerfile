FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

# Match these to your host user (id -u / id -g) so the bind-mounted
# data/ and state/ directories stay writable without running as root.
# Override at build time: docker compose build --build-arg APP_UID=$(id -u) --build-arg APP_GID=$(id -g)
ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid "${APP_GID}" appuser \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Declared after the pip install layer so a version bump doesn't bust the
# dependency-install cache; CI passes the real values as build-args.
ARG APP_VERSION=dev
ARG APP_COMMIT_SHA=unknown
ENV APP_VERSION=${APP_VERSION} \
    APP_COMMIT_SHA=${APP_COMMIT_SHA}

COPY app.py .
COPY gunicorn.conf.py .
COPY templates/ templates/
COPY static/ static/
COPY data/ data/

RUN mkdir -p /app/state \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
