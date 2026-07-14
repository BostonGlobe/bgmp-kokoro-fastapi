FROM ubuntu:20.04 AS builder

# Install build dependencies
RUN apt-get update -y && \
    apt-get install -y siege

WORKDIR /tests
COPY . .

CMD ["bash", "./siege_baseline.sh"]
