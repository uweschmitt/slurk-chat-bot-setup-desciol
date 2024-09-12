FROM python:3.11 AS build
COPY . /repo

ARG PROJECT=setup_service

RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir poetry \
    && /venv/bin/poetry self add poetry-multiproject-plugin \
    && /venv/bin/poetry -C /repo/projects/${PROJECT} build-project \
    && /venv/bin/pip install /repo/projects/${PROJECT}/dist/*.whl

FROM python:3.11-slim

COPY --from=build /venv /venv

EXPOSE 80
ENTRYPOINT ["/venv/bin/gunicorn",  \
            "-k", "uvicorn.workers.UvicornWorker", \
            "--capture-output", \
            "--access-logfile", "-", \
            "-b", ":81", \
            "--workers", "4", \
            "slurk_setup_descil.setup_service_api:app"]
