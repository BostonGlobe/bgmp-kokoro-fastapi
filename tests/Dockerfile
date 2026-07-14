FROM ubuntu:20.04 AS builder

# Install build dependencies
RUN apt-get update -y && \
    apt-get install -y siege

ARG TEST_TYPE=baseline

WORKDIR /tests
COPY . .

CMD ["bash", "./siege_$TEST_TYPE.sh"]
