FROM python:3.11
RUN apt-get update && apt-get install -y vim

WORKDIR /
COPY ./dist/*.whl /
RUN python -m venv venv
RUN venv/bin/pip install --no-cache-dir /*.whl

EXPOSE 80
ENTRYPOINT ["/venv/bin/gunicorn", "--log-level", "DEBUG", "--error-logfile", "-", "--capture-output", "--access-logfile", "-", "-b", "0.0.0.0:84", "--worker-class", "aiohttp.GunicornWebWorker", "slurk_setup_descil.chatbot_api:app"]
