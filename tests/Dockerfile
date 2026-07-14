FROM ubuntu:20.04 AS builder

# Install build dependencies
RUN apt-get update -y && \
    apt-get install -y siege

ARG TEST_TYPE=baseline

WORKDIR /tests
COPY . .

RUN ln -s ./siege_${TEST_TYPE}.sh ./siege_test.sh
CMD ["bash", "./siege_test.sh"]
