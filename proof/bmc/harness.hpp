// Shared parts of the bounded-model-checking harnesses. CBMC and ESBMC both treat a body-less
// nondet_* function as "any value", and __VERIFIER_assume as "only inputs where this is true".
#pragma once
#include "src/format.hpp"

#include <assert.h>

extern "C" {
long long nondet_longlong();
unsigned long nondet_ulong();
unsigned char nondet_uchar();
void __VERIFIER_assume(int);
}
