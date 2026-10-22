
default:
    just --list --justfile {{ justfile() }}

[group("Lost Wizards")]
new-wizards-solution name:
    touch solutions/lost-wizards-of-artermia/lost-wizards-{{ name }}.py

[group("Lost Wizards")]
run-wizards-solution-for name:
    #!/bin/bash

    workdir=$(mktemp -d --tmpdir=/tmp lost-wizards-of-artemia.XXX)
    echo "Running solution from temporary directory: $workdir"

    cp lost-wizards-of-artemia/* $workdir

    cp solutions/lost-wizards-of-artemia/lost-wizards-{{ name }}.py $workdir/run.py
    cd $workdir && python run.py

[group("Titan Protocol")]
new-titan-protocol-solution name:
    touch solutions/titan-protocol/titan-protocol-{{ name }}.c

[group("Titan Protocol")]
run-titan-protocol-for name:
    #!/bin/bash
    set -euo pipefail

    workdir=$(mktemp -d --tmpdir=/tmp titan-protocol.XXX)
    echo "Running solution from temporary directory: $workdir"

    cp titan-protocol/titan-protocol/* $workdir

    solution=solutions/titan-protocol/titan-protocol-{{ name }}

    if [ -d "$solution" ]; then
        # Multi-file submission: copy the directory and use its build script.
        cp -r "$solution"/* $workdir
        cd $workdir
        make
    else
        # Single-file submission: one translation unit built with g++.
        cp $solution.* $workdir/run.cpp
        cd $workdir
        g++ run.cpp -o titan-protocol
    fi

    chmod 775 titan-protocol
    ./titan-protocol titan-protocol-capture.txt
