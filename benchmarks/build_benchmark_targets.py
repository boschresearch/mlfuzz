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
execute `make`.
"""
import os
import pathlib

MAX_SEED_LEN: int = 1024 * 1024  # 1MB


def ex(cmd: str) -> None:
    exitcode = os.system(cmd)
    if exitcode != 0:
        # TODO: later exit?
        breakpoint()


def flatten_and_trim_files_in_folder(
    source: pathlib.Path, destination: pathlib.Path, max_len: int = MAX_SEED_LEN
):
    """
    Recursively moves all files in the given folder to the upper most level and trims
    the files to the given length

    Args:
        source : The source folder
        destination : The destination folder (can be the same than source)
        max_len : The maximum length of a file.
    """

    for file_or_dir in source.iterdir():
        if file_or_dir.is_file():
            try:
                # TODO use dd
                newpath = file_or_dir.rename(destination.joinpath(file_or_dir.name))
                if os.path.getsize(newpath) > MAX_SEED_LEN:
                    ex(f"truncate -s {MAX_SEED_LEN} {newpath} ")
            except FileExistsError:
                print(f"File {file_or_dir.name} already exists!")
                file_or_dir.unlink()  # Remove it :)
        elif file_or_dir.is_dir():
            flatten_and_trim_files_in_folder(file_or_dir, destination, max_len)
            file_or_dir.rmdir()  # Directory should be empty now


targets = [
    # Some targets require 'autoconf-archive#, even though it is already installed?
    "boringssl-2016-02-12",
    "c-ares-CVE-2016-5180",
    "freetype2-2017",
    "guetzli-2017-3-30",
    "harfbuzz-1.3.2",
    "json-2017-02-12",
    "lcms-2017-03-21",
    "libarchive-2017-01-04",
    "libjpeg-turbo-07-2017",
    "libpng-1.2.56",
    "libssh-2017-1272",
    "libxml2-v2.9.2",
    # "llvm-libcxxabi-2017-01-27", (unable to checkout -> other repo required)
    "openssl-1.0.2d",
    # "openssl-1.1.0c" (Folder not found),
    # "openthread-2018-02-27", # (compiler error),
    "pcre2-10.00",
    "proj4-2017-08-14",
    "re2-2014-12-09",
    "sqlite-2016-11-14",
    "vorbis-2017-12-11",
    "woff2-2016-05-06",
    # 'wpantund-2018-02-27'#( deprecated autoreconf dependency ),
]


def main():
    if os.path.exists("fuzzer-test-suite"):
        i = input(
            "fuzzer-test-suite exists already. Remove old build files and create new build? [y/n]: "
        )
        if i != "y":
            print("exiting")
            exit(0)
        os.system("rm -rf ./fuzzer-test-suite")
        os.system("rm -r ./targets")

    os.mkdir("targets")
    os.mkdir("targets/seeds")

    ex("git clone https://github.com/google/fuzzer-test-suite.git")
    ex("cd fuzzer-test-suite && git checkout 6955fc97efedfda7dcc0979658b169d7eeb5ccd6")

    ex("patch fuzzer-test-suite/freetype2-2017/build.sh < /scripts/freetype_build.sh.patch")
    ex("patch fuzzer-test-suite/libssh-2017-1272/build.sh < /scripts/libssh_build.sh.patch")
    ex("patch fuzzer-test-suite/pcre2-10.00/build.sh < /scripts/pcre2_build.sh.patch")

    # Use -O2 for original afl, too
    ex("patch fuzzer-test-suite/custom-build.sh < /scripts/custom-build.sh.patch")

    print("Check for compiler")
    if os.environ.get("FUZZER") == "afl":
        os.environ["CC"] = "/afl/afl-clang-fast"
        os.environ["CXX"] = "/afl/afl-clang-fast++"
        print(f'Using {os.environ.get("CC")}')
    elif os.environ.get("FUZZER") == "aflpp":
        os.environ["CC"] = "/aflpp/afl-clang-fast"
        os.environ["CXX"] = "/aflpp/afl-clang-fast++"
        print(f'Using {os.environ.get("CXX")}')

    # Don't ask about the binary name :)
    for target in targets:
        if os.environ.get("FUZZER") == "afl":
            ex(
                f"cd fuzzer-test-suite/{target} && mkdir b && cd b && "
                f"../build.sh hooks /afl/afl_driver.cpp && "
                f'cp ./..-hooks ../../../targets/{target + ".afl"}'
            )
        elif os.environ.get("FUZZER") == "aflpp":
            ex(
                f"cd fuzzer-test-suite/{target} && mkdir b && cd b && "
                f'../build.sh && cp ./..-fsanitize_fuzzer ../../../targets/{target + ".aflpp"}'
            )

    for target in targets:
        seed_destination_dir = pathlib.Path("targets/seeds") / target
        seed_destination_dir.mkdir(parents=True, exist_ok=True)

        # Go through possible seed file locations
        seeds_dir = pathlib.Path("fuzzer-test-suite") / target / "b" / "seeds"
        if seeds_dir.is_dir():
            flatten_and_trim_files_in_folder(seeds_dir, seed_destination_dir, MAX_SEED_LEN)
            continue

        seeds_dir = pathlib.Path("fuzzer-test-suite") / target / "seeds"
        if seeds_dir.is_dir():
            flatten_and_trim_files_in_folder(seeds_dir, seed_destination_dir, MAX_SEED_LEN)


if __name__ == "__main__":
    main()
