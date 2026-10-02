# One container holding EMANE (built from source, so it also works on arm64)
# plus the Part 1 scheduler. Build from the repository root:
#   docker build -t tdma-emane -f emane/Dockerfile .
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git build-essential autoconf automake libtool pkg-config \
        libxml2-dev libprotobuf-dev protobuf-compiler libpcap-dev libpcre3-dev uuid-dev \
        python3 python3-dev python3-pip python3-setuptools python3-protobuf python3-lxml \
        iproute2 iputils-ping procps \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch v1.5.3 https://github.com/adjacentlink/emane.git /opt/emane-src \
    && cd /opt/emane-src \
    && ./autogen.sh && ./configure --prefix=/usr \
    && make -j"$(nproc)" && make install && ldconfig

# "make install" puts EMANE's Python bindings here, which Ubuntu's python3 does not search.
ENV PYTHONPATH=/usr/lib/python3.10/site-packages

RUN pip3 install --no-cache-dir "networkx>=3.0"

WORKDIR /work
COPY src ./src
COPY data ./data
COPY emane ./emane
CMD ["bash", "emane/run_demo.sh"]
