#!/usr/bin/env python
# Copyright 2023 Robert Bosch GmbH
# Copyright 2020 Google LLC
#
# Parts of the script below are adapted from [FuzzBench](https://github.com/google/fuzzbench)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Sequence

from neuzzpp.utils import kill_fuzzer, replay_corpus


def main(argv: Sequence[str] = tuple(sys.argv)) -> None:
    hide_output: bool = False

    parser = argparse.ArgumentParser(
        description="Script running a single Darwin experiment",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input_folder", help="path to input corpus", type=str)
    parser.add_argument("output_folder", help="path to output folder", type=str)
    parser.add_argument("target_binary", help="target to fuzz", type=str)
    parser.add_argument(
        "-d", "--duration", help="experiment duration in seconds", type=int, default=None
    )
    parser.add_argument(
        "-s", "--seed_prng", help="seed for AFL random number generator", type=int, default=None
    )
    parser.add_argument(
        "--pass_by_file",
        help="pass fuzz data to target by file",
        default=False,
        action="store_true",
    )
    args = parser.parse_args(argv[1:])

    os.environ["AFL_NO_UI"] = "1"
    # Skip AFL's CPU frequency check (fails on Docker).
    os.environ["AFL_SKIP_CPUFREQ"] = "1"
    # No need to bind affinity to one core, Docker enforces 1 core usage.
    os.environ["AFL_NO_AFFINITY"] = "1"
    # AFL will abort on startup if the core pattern sends notifications to
    # external programs. We don't care about this.
    os.environ["AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES"] = "1"
    # Don't exit when crashes are found. This can happen when corpus from
    # OSS-Fuzz is used.
    os.environ["AFL_SKIP_CRASHES"] = "1"
    # Shuffle the queue
    os.environ["AFL_SHUFFLE_QUEUE"] = "1"

    # Spawn the afl fuzzing process for warmup
    output_stream = subprocess.DEVNULL if hide_output else None
    threading.Timer(args.duration, kill_fuzzer, ["afl-fuzz", output_stream]).start()
    print("[run_darwin] Running target with afl-fuzz")
    command = [
        "/darwin/afl-fuzz",
        "-d",
        "-i",
        args.input_folder,
        "-o",
        args.output_folder,
        # Use no memory limit as ASAN doesn't play nicely with one.
        "-m",
        "none",
        "-t",
        "1000+",  # Use same default 1 sec timeout, but add '+' to skip hangs.
    ]
    if args.seed_prng is not None:
        command += ["-z", str(args.seed_prng)]

    command += [
        "--",
        args.target_binary,
    ]
    if args.pass_by_file:
        command += ["@@"]

    print("[run_darwin] Running command: " + " ".join(command))
    output_stream = subprocess.DEVNULL if hide_output else None
    subprocess.check_call(command, stdout=output_stream, stderr=output_stream)
    print("[run_darwin] Darwin is done. Replaying corpus.")

    # Replay corpus
    replay_corpus(Path(args.output_folder), Path(args.target_binary))
    print("[run_darwin] All done. Exiting now.")


if __name__ == "__main__":
    main()
