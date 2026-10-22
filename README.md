# What is this

There are two branches here:
* `git checkout handmade` -- everything was written by hand.
* `git checkout autotests` -- I have used tooling to build wide range of tests.

# Assumptions

The original challenge is internally inconsistent: `README.md` , the `titan-encoder/*.py` files and the `titan-protocol/titan-protocol-capture.txt` disagree as to the details of the protocol.

Moreover, the output format is undefined. 

The challenge verbal instructions call for a "production ready" code, however, there are many unknowns that would normally get resolved by discussing the requirement set with the client.
in particular, the following is unclear:
* Whether this is for a new product, maintenance of existing product, or archival data exploration
* Whether the code is to run on a HPC cluster or on a low-end microcontroller
* Whether there could be a maliciously crafted data, or is the data source trusted
* What kind of damage could occur to the data in transport
* Whether to accept valid packets only, or to attempt recover any leftover data from damaged packets. 

Hence, the following assumptions have been added:

* Lenient interpretation of the protocol mostly based on the `titan-protocol-capture.txt` and it is assumed that all of it is correct
* Strict-like mode: accept valid packets only, discard entire packet on a first smell of trouble
* Heap-less code (no memory allocations)


# Known problems

* For an overall invalid packet where the header is good, but the payload data (e.g. housekeeping data) is damaged, the program will output partial output.
  * Workaround: None
  * To Do: there are at least 3 solutions to this; preferably, upgrade the writer object to support transactional mode, where output contents are buffered and then in the end can be commited or discarded at any time.
* Performance: this version has been written for simplicity. There are known ways this could be much faster:
  * Workaround: None 
  * To Do: buffered reads. Then, re-profile.

# Demonstration

The following is required:
* C++20 compiler
* POSIX OS, e.g. ubuntu linux
* cmake >3.16
* bash

3 scripts are provided in the repo root:
* `build.sh` : uses cmake to build the source code
* `run.sh` : assuming that build.sh succeeded, runs the code to process `data/titan-protocol-capture.txt` into `results/result.yaml`; also outputs `yaml` to `stdout`
* `clean.sh` : deletes the `build` folder and results/result.yaml

# Test suite

Tests have been built with tooling, hence, they are held in separate branch, `git checkout autotests`
