FROM python:3.11

WORKDIR /
COPY ./dist/*.whl /
RUN python -m venv venv
RUN venv/bin/pip install --no-cache-dir /*.whl

RUN apt-get update && apt-get install -y vim
EXPOSE 80
ENTRYPOINT ["/venv/bin/gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--access-logfile", "-", "-b", ":81", "--workers", "4", "slurk_setup_descil.setup_client_api:app"]
