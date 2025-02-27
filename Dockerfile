FROM python:3.12-slim AS base
ARG GIT_REV=development
RUN pip install --no-cache uv && \
    apt-get update && apt-get install -y make && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

FROM base AS dev
RUN apt-get update && apt-get install -y git fish make vim && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

FROM dev AS prod
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV GIT_REV=${GIT_REV}
EXPOSE 5000/tcp
COPY . /app
WORKDIR /app
