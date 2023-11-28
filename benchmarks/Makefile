
.PHONY: targets
targets:
	docker build . -t mlfuzzbenchmark:1.0
	rm -rf binaries
	mkdir binaries

	docker run --rm -e MOUNT_PATH=/binaries -e FUZZER=afl -v $(shell pwd)/binaries:/binaries/ mlfuzzbenchmark:1.0 bash -c "/scripts/build_benchmark_targets.py && cp -r /targets/* /binaries && chmod -R a+rw /binaries"
	docker run --rm -e MOUNT_PATH=/binaries -e FUZZER=aflpp -v $(shell pwd)/binaries:/binaries/ mlfuzzbenchmark:1.0 bash -c "/scripts/build_benchmark_targets.py && cp -r /targets/* /binaries && chmod -R a+rw /binaries"
	docker run --rm -e MOUNT_PATH=/binaries -e FUZZER=afl -v $(shell pwd)/binaries:/binaries/ mlfuzzbenchmark:1.0 bash -c "/scripts/build_fuzzbench_targets.py "
	docker run --rm -e MOUNT_PATH=/binaries -e FUZZER=aflpp -v $(shell pwd)/binaries:/binaries/ mlfuzzbenchmark:1.0 bash -c "/scripts/build_fuzzbench_targets.py "
