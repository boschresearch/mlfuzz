FROM tensorflow/tensorflow:2.7.1-gpu

# Hack the new CUDA public keys (Apr 2022)
RUN apt install wget \
    && sed -i '/developer\.download\.nvidia\.com\/compute\/cuda\/repos/d' /etc/apt/sources.list.d/* \
    && sed -i '/developer\.download\.nvidia\.com\/compute\/machine-learning\/repos/d' /etc/apt/sources.list.d/* \
    && apt-key del 7fa2af80 \
    && wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-keyring_1.0-1_all.deb \
    && dpkg -i cuda-keyring_1.0-1_all.deb

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-pip make clang gdb zip unzip nano libssl-dev liblzma-dev \
    git build-essential python3-venv make libstdc++-7-dev libz-dev autotools-dev \
    automake autoconf autoconf-archive libtool libarchive-dev cmake libgss-dev\
	libglib2.0-dev libfdt-dev libpixman-1-dev zlib1g-dev ninja-build \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://apt.llvm.org/llvm.sh \
    && chmod +x llvm.sh \
    && export CC=clang && CXX=clang++ \
    && ./llvm.sh 12

RUN update-alternatives --install /usr/bin/clangd clangd /usr/bin/clangd-12 100 \
    && update-alternatives --install /usr/bin/clang clang /usr/bin/clang-12 100 \
    && update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-12 100 \
    && update-alternatives --install /usr/bin/llvm-config llvm-config /usr/bin/llvm-config-12 100

# Set up MLFuzz
RUN mkdir /mlfuzz
COPY scripts /mlfuzz/scripts/
COPY README.md /mlfuzz/

# Download AFL
RUN git clone https://github.com/google/AFL /afl && \
    cd /afl && \
    git checkout 61037103ae3722c8060ff7082994836a794f978e

# Download AFL++
RUN git clone https://github.com/AFLplusplus/AFLplusplus.git /aflpp && \
    cd /aflpp && \
    git checkout 9e2a94532b7fd5191de905a8464176114ee7d258

# Download AFL fuzzing driver for libafl targets
RUN wget https://raw.githubusercontent.com/llvm/llvm-project/5feb80e748924606531ba28c97fe65145c65372e/compiler-rt/lib/fuzzer/afl/afl_driver.cpp -O /afl/afl_driver.cpp

# Build AFL++; use AFL_NO_X86 to skip flaky tests.
RUN cd /aflpp && unset CFLAGS && unset CXXFLAGS && \
    export CC=clang && export AFL_NO_X86=1 && \
    PYTHON_INCLUDE=/ make && make install && \
    make -C utils/aflpp_driver && \
    cp utils/aflpp_driver/libAFLDriver.a /
COPY fuzzers/aflpp_experiments/run_aflpp.py /aflpp/

# Build AFL; use AFL_NO_X86 to skip flaky tests
COPY fuzzers/afl_experiments/* /afl/
RUN cd /afl && unset CFLAGS && unset CXXFLAGS \
    && patch afl-fuzz.c < afl-fuzz.c_fixed_seed.patch \
    && export CC=clang && export CXX=clang++ \
    && export AFL_NO_X86=1 && make \
    && cd llvm_mode && make

# Set up Neuzz++
RUN git clone https://github.com/boschresearch/neuzzplusplus.git /neuzzpp
WORKDIR "/neuzzpp"
RUN python -m venv /venv && source /venv/bin/activate && pip install poetry && \
    poetry run pip install --upgrade pip && poetry install --no-dev --no-interaction

# Build Neuzz++ plugin for AFL++
ENV PATH=/venv/bin:$PATH
ENV AFL_PATH=/aflpp
ENV NEUZZPP_PATH=/neuzzpp
RUN cd /neuzzpp/aflpp-plugins && make
COPY fuzzers/neuzzpp_experiments/run_neuzzpp.py /neuzzpp/

# Install Havoc MAB
RUN git clone https://github.com/MagicHavoc/Havoc-Study /havoc \
    && cd /havoc \
    && git checkout 7ed4805a2e09cc734ec47f88b3dab144db7195c8 \
    && mv fuzzers/Havoc_DMA/* .

WORKDIR "/havoc"
COPY fuzzers/havoc_experiments/* .
RUN chmod -R a+rwX . \
    && patch afl-fuzz.c < afl-fuzz.c_fixed_seed.patch \
    && make -j

# Install Neuzz
# Use Ammar's repo with patch for ASan and other bug fixes.
# See https://github.com/Dongdongshe/neuzz/pull/16.
RUN git clone https://github.com/ammaraskar/neuzz.git /neuzz \
    && cd /neuzz \
    && git checkout e93c7a4c625aa1a17ae2f99e5902d62a46eaa068

WORKDIR "/neuzz"
COPY fuzzers/neuzz_experiments/* .
RUN chmod -R a+rwX . \
    && patch neuzz.c < neuzz.c_fixed_seed.patch \
    && clang -O3 -funroll-loops ./neuzz.c -o neuzz \
    && patch nn.py < nn.py_tf2.patch

# Install Darwin
RUN git clone https://github.com/TUDA-SSL/DARWIN.git /darwin
WORKDIR "/darwin"
COPY fuzzers/darwin_experiments/* .
RUN chmod -R a+rwX . \
    && patch afl-fuzz.c < afl-fuzz.c_fixed_seed.patch \
    && make \
    && make install

# Install MOPT (based on AFL)
RUN git clone https://github.com/puppet-meteor/MOpt-AFL.git /mopt \
    && cd /mopt \
    && mv MOpt/* .

WORKDIR "/mopt"
COPY fuzzers/mopt_experiments/* .
RUN chmod -R a+rwX . \
    && patch afl-fuzz.c < afl-fuzz.c_fixed_seed.patch \
    && make \
    && make install

# Install MOPT++ (based on AFL++)
RUN git clone https://github.com/kupl/SeamFuzz-Artifact.git /moptpp \
    && cd /moptpp \
    && mv fuzzers/aflppmopt/afl/* .

WORKDIR "/moptpp"
COPY fuzzers/moptpp_experiments/run_moptpp.py .
RUN chmod -R a+rwX . \
    && make \
    && make install

# Install PreFuzz
RUN git clone https://github.com/PoShaung/program-smoothing-fuzzing.git /prefuzz \
    && cd /prefuzz \
    && git checkout 60d1c2cd1ee460dcc6facdab92e96df7f44fdb3a \
    && mv fuzzers/RESuzz/RESuzz/* .

# We need to run the prefuzz python script in the prefuzz folder :/
WORKDIR "/prefuzz"
COPY fuzzers/prefuzz_experiments/* .
# Patch Prefuzz to fix port number for modules comms
RUN chmod -R a+rwX . \
    && patch nn.py < nn.py_add_asan.patch \
    && patch fuzz.c < fuzz.c_all.patch \
    && patch utils/utils.py < utils.py_add_asan.patch \
    && clang -O3 -funroll-loops ./fuzz.c -o prefuzz
