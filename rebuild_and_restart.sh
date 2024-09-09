set -e

source venv/bin/activate
./build_all_wheels.sh

docker compose build
docker compose up -d
