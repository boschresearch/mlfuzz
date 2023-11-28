FROM ubuntu:20.04

ENV MOUNT_PATH "/targets"
# AFL++ is default fuzzer
ENV FUZZER = "aflpp"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y \
	    git wget build-essential python3 make libstdc++-7-dev clang libz-dev autotools-dev \
        automake autoconf autoconf-archive libtool libarchive-dev cmake nasm libpng-dev \
        ragel libglib2.0-dev golang-go curl libbz2-dev libxml2-dev libgss-dev \
        libssl-dev liblzma-dev subversion  libgcrypt20-dev ninja-build g++  nano \
        lsb-release software-properties-common apt-utils zip zlib1g-dev pkg-config \
        bison flex python3-dev python3-pip \
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

# Download and compile afl
RUN git clone https://github.com/google/AFL /afl && \
    cd /afl && \
    git checkout 61037103ae3722c8060ff7082994836a794f978e

# Download afl fuzzing driver for libafl targets
RUN wget https://raw.githubusercontent.com/llvm/llvm-project/5feb80e748924606531ba28c97fe65145c65372e/compiler-rt/lib/fuzzer/afl/afl_driver.cpp -O /afl/afl_driver.cpp

# Build without Python support as we don't need it
# Set AFL_NO_X86 to skip flaky tests
RUN cd /afl && unset CFLAGS && unset CXXFLAGS \
    && export CC=clang && export CXX=clang++ \
    && export AFL_NO_X86=1 && make \
    && $CXX -std=c++11 -O2 -c /afl/afl_driver.cpp \
    && ar r libAFLDriver.a afl_driver.o &&  rm *.o \
    && cd llvm_mode && make

# Download and compile afl++
RUN git clone https://github.com/AFLplusplus/AFLplusplus.git /aflpp && \
    cd /aflpp && \
    git checkout 9e2a94532b7fd5191de905a8464176114ee7d258

# Build without Python support as we don't need it
# Set AFL_NO_X86 to skip flaky tests
RUN cd /aflpp && unset CFLAGS && unset CXXFLAGS && \
    export CC=clang && export AFL_NO_X86=1 && \
    PYTHON_INCLUDE=/ make && make install && \
    make -C utils/aflpp_driver && \
    cp utils/aflpp_driver/libAFLDriver.a /

COPY . /scripts
