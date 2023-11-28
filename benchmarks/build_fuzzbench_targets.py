#!/usr/bin/env python3
# Copyright (c) 2023 Robert Bosch GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
This script is intended to work only within the given Docker image.
To build all target binaries and copy them in the subfolder `binaries`,
execute `make dockerbenchmarkimage`.
"""
import os
import pathlib

from build_benchmark_targets import flatten_and_trim_files_in_folder


def main():
    if os.path.exists("/fuzzbench"):
        os.system("rm -rf /fuzzbench")

    ex("mkdir -p ${MOUNT_PATH}/seeds")
    ex("mkdir -p ${MOUNT_PATH}/dicts")

    ex("git clone https://github.com/google/fuzzbench.git /fuzzbench")
    ex("cd /fuzzbench && git checkout 93ecfbdd102e447c2bb7caf22d5bfab5de99efbc")

    print("Check for compiler")
    if os.environ.get("FUZZER") == "afl":
        os.environ["CC"] = "/afl/afl-clang-fast"
        os.environ["CXX"] = "/afl/afl-clang-fast++"
        os.environ["LIB_FUZZING_ENGINE"] = "/afl/libAFLDriver.a"
        os.environ["FUZZER_LIB"] = "/afl/libAFLDriver.a"
        print(f'Using {os.environ.get("CC")}')
    elif os.environ.get("FUZZER") == "aflpp":
        os.environ["CC"] = "/aflpp/afl-clang-fast"
        os.environ["CXX"] = "/aflpp/afl-clang-fast++"
        os.environ["LIB_FUZZING_ENGINE"] = "/aflpp/libAFLDriver.a"
        os.environ["FUZZER_LIB"] = "/aflpp/libAFLDriver.a"
        print(f'Using {os.environ.get("CXX")}')

    os.environ["CFLAGS"] = "-O2 -fsanitize=address"
    os.environ["CXXFLAGS"] = "-O2 -fsanitize=address"

    os.environ["ARCHITECTURE"] = ""
    os.environ["SANITIZER"] = ""

    build_bloaty()
    build_curl()
    build_libpcap()
    # build_libxlst()
    # build_mbed_tls()
    # build_openh264()
    build_stb()
    build_zlib()

    ex("chmod -R a+w $MOUNT_PATH/* ")


def ex(cmd: str) -> None:
    exitcode = os.system(cmd)
    if exitcode != 0:
        breakpoint()


def build_bloaty():
    src = "/fuzzbench/benchmarks/bloaty_fuzz_target"
    work = "/fuzzbench/benchmarks/bloaty_fuzz_target/b"
    out = os.environ["MOUNT_PATH"]
    os.environ["SRC"] = src
    os.environ["WORK"] = work
    os.environ["OUT"] = out

    print(f"Build {src} to {out}")
    ex(
        "cd /fuzzbench/benchmarks/bloaty_fuzz_target && "
        "git clone --depth 1 --branch v1.1 https://github.com/google/bloaty.git "
    )

    ex(f"mkdir {work}  && cd {src} && chmod a+x ./build.sh && ./build.sh")
    ex(
        f"cd {out} && mv fuzz_target bloaty.${{FUZZER}} && "
        f"unzip -ou fuzz_target_seed_corpus.zip -d ./seeds/bloaty && rm fuzz_target_seed_corpus.zip"
    )


def build_curl():
    base = "/fuzzbench/benchmarks/curl_curl_fuzzer_http"
    src = f"{base}/curl"
    work = f"{base}/b"
    out = os.environ["MOUNT_PATH"]
    os.environ["SRC"] = src
    os.environ["SRCDIR"] = src
    os.environ["WORK"] = work
    os.environ["OUT"] = out

    print(f"Build {src} to {out}")
    ex(
        f"cd {base} &&  git clone https://github.com/curl/curl-fuzzer && "
        f"git -C ./curl-fuzzer checkout dd486c1e5910e722e43c451d4de928ac80f5967d && "
        f"git clone  https://github.com/curl/curl.git && "
        f"git -C ./curl checkout a20f74a16ae1e89be170eeaa6059b37e513392a4"
    )

    ex(
        f"mkdir {work} && mkdir /src && cd {base}/curl-fuzzer && chmod a+x ./ossfuzz.sh && "
        f"sed -i 's#install_curl.sh /src/curl#install_curl.sh {src}#' ./ossfuzz.sh && ./ossfuzz.sh "
    )
    ex(
        f"cd {out} && mv curl_fuzzer_http curl.${{FUZZER}} && mv http.dict ./dicts/curl.dict && "
        f"unzip -ou curl_fuzzer_http_seed_corpus.zip -d ./seeds/curl && "
        f"rm curl_fuzzer* fuzz_url*"
    )


def build_libpcap():
    base = "/fuzzbench/benchmarks/libpcap_fuzz_both"
    src = f"{base}"
    work = f"{src}/build"
    out = os.environ["MOUNT_PATH"]
    os.environ["SRC"] = src
    os.environ["SRCDIR"] = src
    os.environ["WORK"] = work
    os.environ["OUT"] = out

    print(f"Build {src} to {out}")
    ex(
        f"cd {base} &&  git clone https://github.com/the-tcpdump-group/libpcap.git libpcap && "
        f"git -C libpcap checkout 17ff63e88ea99112a905eefc6f862dac20de09e1 &&"
        f"git clone https://github.com/the-tcpdump-group/tcpdump.git tcpdump && "
        f"git -C tcpdump checkout 032e4923e5202ea4d5a6d1cead83ed1927135874"
    )
    ex(f"cd {base} && chmod a+x ./build.sh && /bin/bash ./build.sh ")

    ex(
        f"cd {out} && mv fuzz_both libpcap.${{FUZZER}} && "
        f"unzip -ou fuzz_pcap_seed_corpus.zip -d ./seeds/libpcap && "
        f"unzip -ou fuzz_filter_seed_corpus.zip -d ./seeds/libpcap && "
        f"mv ./seeds/libpcap/*/* ./seeds/libpcap/ && "
        f"rm *.options *.zip"
    )


# Does not build :/
def build_libxlst():
    base = "/fuzzbench/benchmarks/libxslt_xpath"
    src = f"{base}/libxslt"
    work = f"{src}/build"
    out = os.environ["MOUNT_PATH"]
    os.environ["SRC"] = src
    os.environ["SRCDIR"] = src
    os.environ["WORK"] = work
    os.environ["OUT"] = out

    print(f"Build {src} to {out}")
    ex(
        f"cd {base} &&  git clone https://gitlab.gnome.org/GNOME/libxml2.git && \
            git -C libxml2 checkout c7260a47f19e01f4f663b6a56fbdc2dafd8a6e7e && \
            git clone https://gitlab.gnome.org/GNOME/libxslt.git && \
            git -C libxslt checkout 180cdb804efedcba363016fcf6cd3dbd2adca607"
    )
    ex(f"cd {base}/libxml2 && mkdir b && cd b && cmake .. && make ")
    ex(f"cd {src} && chmod a+x ../build.sh && /bin/bash ../build.sh ")

    # ex(
    #    f"cd {out} && mv fuzz_both libpcap.${{FUZZER}} && "
    #    f"unzip -ou fuzz_pcap_seed_corpus.zip -d ./seeds/libpcap && "
    #    f"unzip -ou fuzz_filter_seed_corpus.zip -d ./seeds/libpcap && "
    #    f"mv ./seeds/libpcap/*/* ./seeds/libpcap/ && "
    #    f"rm *.options *.zip"
    # )


# Does not work with shared memory test case transfer :(
def build_mbed_tls():
    base = "/fuzzbench/benchmarks/mbedtls_fuzz_dtlsclient"
    src = f"{base}"
    work = f"{src}/build"
    out = os.environ["MOUNT_PATH"]
    os.environ["SRC"] = src
    os.environ["SRCDIR"] = src
    os.environ["WORK"] = work
    os.environ["OUT"] = out

    print(f"Build {src} to {out}")
    ex(
        f"cd {base} &&  \
            git clone --recursive -b development https://github.com/Mbed-TLS/mbedtls.git mbedtls \
            &&  git -C mbedtls checkout 169d9e6eb4096cb48aa25651f42b276089841087 && \
            git clone --depth 1 https://github.com/google/boringssl.git boringssl && \
            git clone --depth 1 https://github.com/openssl/openssl.git openssl "
    )
    ex(f"cd {base}/mbedtls && chmod a+x ../build.sh && /bin/bash ../build.sh ")
    ex(
        f"cd {out} && mv fuzz_dtlsclient mbedtls.${{FUZZER}} && "
        f"unzip -ou fuzz_dtlsclient_seed_corpus.zip -d ./seeds/mbedtls && "
        f"mv ./seeds/mbedtls/*/*/* ./seeds/mbedtls/ && "
        f"rm *.options *.zip"
    )


def build_openh264():
    base = "/fuzzbench/benchmarks/openh264_decoder_fuzzer"
    src = f"{base}"
    work = f"{src}/build"
    out = os.environ["MOUNT_PATH"]
    os.environ["SRC"] = src
    os.environ["SRCDIR"] = src
    os.environ["WORK"] = work
    os.environ["OUT"] = out

    print(f"Build {src} to {out}")
    ex(
        f"cd {base} &&  git clone https://github.com/cisco/openh264.git && \
            git -C openh264 checkout 045aeac1dd01df12dec7b1ef8191b3193cf4273c "
    )
    ex(f"cd {base}/openh264 && chmod a+x ../build.sh && /bin/bash ../build.sh ")
    ex(
        f"cd {out} && mv decoder_fuzzer openh264.${{FUZZER}} && "
        f"unzip -ou decoder_fuzzer_seed_corpus.zip -d ./seeds/openh264 && "
        # f"mv ./seeds/mbedtls/*/*/* ./seeds/mbedtls/ && "
        f"rm  *.zip"
    )

    seed_folder = pathlib.Path(out) / "seeds" / "openh264"
    flatten_and_trim_files_in_folder(seed_folder, seed_folder)


def build_stb():
    base = "/fuzzbench/benchmarks/stb_stbi_read_fuzzer"
    src = f"{base}"
    work = f"{src}/build"
    out = os.environ["MOUNT_PATH"]
    os.environ["SRC"] = src
    os.environ["SRCDIR"] = src
    os.environ["WORK"] = work
    os.environ["OUT"] = out

    print(f"Build {src} to {out}")
    ex(
        f"cd {base} &&  git clone https://github.com/nothings/stb && \
            git -C stb checkout 5736b15f7ea0ffb08dd38af21067c314d6a3aae9 "
    )
    ex(
        "mkdir $SRC/stbi && \
        wget --no-check-certificate -O \
        $SRC/stbi/gif.tar.gz https://storage.googleapis.com/google-code-archive-downloads/v2/code.google.com/imagetestsuite/imagetestsuite-gif-1.00.tar.gz && \
        wget --no-check-certificate -O \
        $SRC/stbi/jpg.tar.gz https://storage.googleapis.com/google-code-archive-downloads/v2/code.google.com/imagetestsuite/imagetestsuite-jpg-1.00.tar.gz && \
        wget --no-check-certificate -O \
        $SRC/stbi/bmp.zip http://entropymine.com/jason/bmpsuite/releases/bmpsuite-2.6.zip && \
        wget --no-check-certificate -O \
        $SRC/stbi/tga.zip https://github.com/richgel999/tga_test_files/archive/master.zip && \
        wget --no-check-certificate -O \
        $SRC/stbi/gif.dict https://raw.githubusercontent.com/mirrorer/afl/master/dictionaries/gif.dict && \
        cp \
        $SRC/stbi/gif.tar.gz \
        $SRC/stbi/jpg.tar.gz \
        $SRC/stbi/bmp.zip \
        $SRC/stbi/gif.dict \
        $SRC/stb"
    )
    ex(f"cd {base}/stbi && chmod a+x ../build.sh && /bin/bash ../build.sh ")
    ex(
        f"cd {out} && mv stbi_read_fuzzer stb.${{FUZZER}} && "
        f"unzip -ou stbi_read_fuzzer_seed_corpus.zip -d ./seeds/stb && "
        f"mv stbi_read_fuzzer.dict ./dicts/stb.dict && "
        f"rm  *.zip && "
        f"rm stb_png*"
    )

    seed_folder = pathlib.Path(out) / "seeds" / "stb"
    flatten_and_trim_files_in_folder(seed_folder, seed_folder)


def build_zlib():
    base = "/fuzzbench/benchmarks/zlib_zlib_uncompress_fuzzer"
    src = f"{base}"
    work = f"{src}/build"
    out = os.environ["MOUNT_PATH"]
    os.environ["SRC"] = src
    os.environ["SRCDIR"] = src
    os.environ["WORK"] = work
    os.environ["OUT"] = out

    print(f"Build {src} to {out}")
    ex(
        f"cd {base} &&  git clone https://github.com/madler/zlib.git && \
            git -C zlib checkout d71dc66fa8a153fb6e7c626847095d9697a6cf42 "
    )
    ex("")
    ex(f"cd {base}/zlib && chmod a+x ../build.sh && /bin/bash ../build.sh ")
    ex(
        f"cd {out} && mv zlib_uncompress_fuzzer zlib.${{FUZZER}} && "
        f"mkdir -p ./seeds/zlib/ && "
        f"mv seed_corpus.zip ./seeds/zlib/seed_corpus.zip "

    )

    seed_folder = pathlib.Path(out) / "seeds" / "zlib"
    flatten_and_trim_files_in_folder(seed_folder, seed_folder)


if __name__ == "__main__":
    main()
