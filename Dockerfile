FROM python:3.12-slim AS base
ARG GIT_REV=development
RUN pip install --no-cache uv

FROM base AS dev
RUN apt-get update && apt-get install -y git fish vim && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

FROM base AS bot
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV GIT_REV=${GIT_REV}
COPY . /app
WORKDIR /app
CMD ["uv", "run", "relay.py"]
