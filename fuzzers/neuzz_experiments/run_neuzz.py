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
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Sequence

from neuzzpp.utils import kill_fuzzer, replay_corpus


def main(argv: Sequence[str] = tuple(sys.argv)) -> None:
    warmup_duration: int = 60 * 60  # 1 hour warmup with AFL
    max_seed_length: int = 10000  # Limit seed input size for effective learning
    neuzz_duration: Optional[int] = None
    hide_output: bool = False

    parser = argparse.ArgumentParser(
        description="Script running a single Neuzz experiment",
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

    if args.duration is not None:
        warmup_duration = min(args.duration, warmup_duration)
        neuzz_duration = max(0, args.duration - warmup_duration)  # Subtract warmup from total time

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
    threading.Timer(warmup_duration, kill_fuzzer, ["afl-fuzz", output_stream]).start()
    print("[run_afl_fuzz] Running target with afl-fuzz")
    command = [
        "/afl/afl-fuzz",
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
        command += ["-s", str(args.seed_prng)]

    command += [
        "--",
        args.target_binary,
    ]
    if args.pass_by_file:
        command += ["@@"]
    else:
        # Pass INT_MAX to afl to maximize the number of persistent loops it performs
        command += ["2147483647"]

    print("[run_afl_fuzz] Running command: " + " ".join(command))
    output_stream = subprocess.DEVNULL if hide_output else None
    subprocess.check_call(command, stdout=output_stream, stderr=output_stream)
    # After warming up, copy the 'queue' to use for neuzz input
    print("[run_neuzz] Warmed up!")

    if neuzz_duration is not None and neuzz_duration == 0:
        print("[run_neuzz] Exit early without running Neuzz due to time constraints")
        return

    afl_output_dir = os.path.join(args.output_folder, "queue")
    neuzz_input_dir = os.path.join(args.output_folder, "neuzz_in")
    # Treat afl's queue folder as the input for Neuzz.
    os.rename(afl_output_dir, neuzz_input_dir)

    # Trim the corpus according to max_seed_length
    print(f"[run_neuzz] Trim seed inputs to max {max_seed_length}")
    files = Path(neuzz_input_dir).glob("*")

    # Preserve longest seed length
    longest_seed_len = 0

    for file in files:
        if file.is_dir():  # delete folders
            shutil.rmtree(file)
        else:  # trim files
            with open(file, "rb+") as seed_file:
                seed_file.seek(0, os.SEEK_END)
                seed_len = seed_file.tell()
                if seed_len > max_seed_length:
                    seed_file.truncate(max_seed_length)
                    longest_seed_len = max_seed_length
                elif seed_len > longest_seed_len:
                    longest_seed_len = seed_len
    print(f"[run_neuzz] Longest seed length is: {longest_seed_len}")

    # Spinning up the neural network
    command = [
        "python",
        "/neuzz/nn.py",
        "--enable-asan",
        "--output-folder",
        afl_output_dir,
        args.target_binary,
    ]
    print("[run_neuzz] Running command: " + " ".join(command))
    subprocess.Popen(command, stdout=output_stream, stderr=output_stream)
    time.sleep(30)  # wait for ml part to settle
    target_rel_path = os.path.relpath(args.target_binary, os.getcwd())

    # Spinning up neuzz
    command = [
        "/neuzz/neuzz",
        "-m",
        "none",
        "-i",
        neuzz_input_dir,
        "-o",
        afl_output_dir,
        "-l",
        str(longest_seed_len),
        "-t",
        str(int(warmup_duration) * 1000),
    ]
    if args.seed_prng:
        command += ["-s", str(args.seed_prng)]
    command += [target_rel_path]

    print("[run_neuzz] Running command: " + " ".join(command))
    neuzz_proc = subprocess.Popen(command, stdout=output_stream, stderr=output_stream)
    if neuzz_duration is not None and neuzz_duration > 0:
        threading.Timer(int(neuzz_duration), kill_fuzzer, ["neuzz", output_stream]).start()
    neuzz_proc.wait()
    print("[run_neuzz] Neuzz is done. Replaying corpus.")

    # Replay corpus
    replay_corpus(Path(args.output_folder), Path(args.target_binary))
    print("[run_neuzz] All done. Exiting now.")


if __name__ == "__main__":
    main()
