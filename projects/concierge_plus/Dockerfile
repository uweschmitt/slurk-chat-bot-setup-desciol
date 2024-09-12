FROM python:3.11 AS build
COPY . /repo

ARG PROJECT=concierge_plus

RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir poetry \
    && /venv/bin/poetry self add poetry-multiproject-plugin \
    && /venv/bin/poetry -C /repo/projects/${PROJECT} build-project \
    && /venv/bin/pip install /repo/projects/${PROJECT}/dist/*.whl

FROM python:3.11-slim

COPY --from=build /venv /venv

EXPOSE 80
ENTRYPOINT ["/venv/bin/gunicorn", "--log-level", "DEBUG", "--error-logfile", "-", "--capture-output", "--access-logfile", "-", "-b", "0.0.0.0:82", "--worker-class", "aiohttp.GunicornWebWorker", "slurk_setup_descil.concierge_plus_api:app"]
