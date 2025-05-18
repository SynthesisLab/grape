# Grammar for Program Synthesis (GRAPE)

This tool aims to simplify the manipulation of grammars for program synthesis.

It offers the following features:

- `grape-compile`: Generates a grammar from a basic Domain Specific Language (DSL) with size and/or depth constraints.
- `grape-convert`: Converts a grammar into another format.
- `grape-count`: Counts the number of programs in a grammar up to a specified size.
- `grape-enum`: Enumerates all programs in a grammar up to a specified size.
- `grape-info`: Provides basic information about a given grammar.
- `grape-intersection`: Produces the intersection of two grammars based on the same input symbols.
- `grape-union`: Produces the union of two grammars based on the same input symbols.
- `grape-prune`: Generates a pruned grammar by removing semantically redundant programs.
- `grape-specialize`: Specializes a generic grammar to a specific type request.
- `grape-despecialize`: Despecializes a generic grammar from a specific type request.

**Supported Grammar Formats:**

- `.grape`: Our custom format. Its advantage lies in having only one special character (`,`), making it straightforward to parse.
- `.ebnf`: Extended Backus-Naur Form (EBNF), supporting a subset for bottom-up tree automata (where each rule must start with a terminal).
- `.lark`: Lark format, also supporting a subset for bottom-up tree automata (where each rule must start with a terminal).

We strongly recommend using the `.grape` format whenever possible, as it offers seamless functionality. The other formats are partially supported primarily for export purposes, reflecting the project's focus.

**Table of Contents:**
- [Installation](#installation)
- [Example](#example)
- [Pruning](#pruning)
  - [How it works](#how-it-works)
  - [Additional Notes](#additional-notes)
- [Type System](#type-system)
- [GRAPE Format](#grape-format)

## Installation

```sh
pip install git+[https://github.com/SynthesisLab/grape.git](https://github.com/SynthesisLab/grape.git)
````

## Example

Let's consider the following `dsl.py` file:

```python
from typing import Callable
import random

MAXI = (1 << 32) - 1
random.seed(1)

# Given a type, provides a function to sample one element
sample_dict: dict[str, Callable] = {"int": lambda: random.randint(-MAXI, MAXI)}

# Given a primitive, provides a tuple (type, implementation)
# Supported types are:
#   - primitive: simply provide its name.
#   - sum types: 'a | b' can be either 'a' or 'b'.
#   - polymorphics: "'a [ t1 | t2 ] -> 'a'"
#     syntax: must start with a "'"
#             the list of supported types must be given at the first usage within '[]'
#     semantic: the example above means either: 't1 -> t1' or 't2 -> t2'
#               't1 -> t2' and 't2 -> t1' are not possible
#               because all instantiations of 'a' must have the same value
#               at any given time.
# Also supports functions with basic type hints: the type is inferred from the annotations.
# Similarly, the type of constants is inferred.
def add(x: int, y: int) -> int:
    return x + y

dsl: dict[str, tuple[str, Callable]] = {
    "+": add,
    "*": ("int -> int -> int", lambda x, y: x * y),
    "-": ("int -> int -> int", lambda x, y: x - y),
    "^": ("int -> int -> int", lambda x, y: x ^ y),
    "&": ("int -> int -> int", lambda x, y: x & y),
    "|": ("int -> int -> int", lambda x, y: x | y),
    "~": ("int -> int", lambda x: ~x),
    "1": ("int", 1)
}

# (Optional) All elements below are OPTIONAL.
# In other words, you can omit them without causing an error.

# Type of object you want to produce. If not specified, all types can be generated.
target_type: str = "int"

# Set of exceptions that will not terminate the process but cause the program to return None.
skip_exceptions: set = {OverflowError}
```

You can then execute various commands using this DSL.

## Pruning

Given a Domain Specific Language (DSL), this tool aims to automatically identify semantically redundant programs.

For instance, consider: `$x, -x, -(-x)$`. Here, $-(-x)$ is redundant because it evaluates to $x$ regardless of the value of $x$.

This tool automatically detects such redundancies by evaluating programs on a set of sampled inputs. The evaluation of a program across these inputs yields its characteristic sequence. Two programs with identical characteristic sequences are considered semantically equivalent, and consequently, only the smallest program is retained.

Currently, this redundancy information is compiled by the tool to produce:

  - A deterministic bottom-up tree automaton, which can be easily converted into a context-free grammar.
  - A set of program rewrites.

<!-- end list -->

```sh
grape-prune dsl.py --size 5 --samples 50
```

The output observed on a machine might be similar to the following:

```text
sampling: 100%|█████████████████████████████████████████████| 100/100 [00:00<00:00, 183718.97it/s, int]
commutatives: &, *, +, ^, |
at size: 5
    no pruning: 1.04e+04
    commutativity pruned: 5.49e+03 (52.92%)
obs. equiv.: 100%|███████████████████████████████████████████████████████| 5/5 [00:00<00:00, 28.07it/s]
building automaton: 100%|██████████████████████████████████████████████| 5/5 [00:00<00:00, 2280.26it/s]
extending automaton: 100%|████████████████████████████████████████| 138/138 [00:00<00:00, 56779.87it/s]
checking: 100%|████████████████████████████████████████████████████████| 5/5 [00:00<00:00, 2089.63it/s]
obs. equivalence: 6.620e+02 pruned: 8.070e+02 (121.90%)
at size: 5
    method: ratio no pruning | ratio comm. pruned | ratio pruned
    no pruning: 100.00% | 188.98% | 260.22%
    commutativity pruned: 52.92% | 100.00% | 137.70%
    pruned: 38.43% | 72.62% | 100.00%
```

**Explanation of the Output:**

```text
at size: 5
    no pruning: 1.04e+04
    commutativity pruned: 5.49e+03 (52.92%)
```

This section indicates the reduction in the number of programs achieved by initially checking for commutativity. The number of programs to be enumerated is reduced to approximately $5.49 \\times 10^3$. While highly DSL-dependent, this provides a good estimate of the algorithm's runtime.

```text
obs. equivalence: 6.620e+02 pruned: 8.070e+02 (121.90%)
```

These figures primarily show the extent of over-approximation in identifying truly semantically equivalent programs. Here, the over-approximation is $121.90%$, suggesting that the identified set contains $21.90%$ more programs than the actual number of unique semantic programs under the given conditions. These numbers are mostly indicative and do not represent the full enumeration counts.

```text
at size: 5
    method: ratio no pruning | ratio comm. pruned | ratio pruned
    no pruning: 100.00% | 188.98% | 260.22%
    commutativity pruned: 52.92% | 100.00% | 137.70%
    pruned: 38.43% | 72.62% | 100.00%
```

This table compares the number of programs in three different scenarios (no pruning, commutativity pruning, and full pruning) for programs up to size 5. The values represent the relative number of programs. Therefore, the automaton for programs up to size 5 contains $38.43%$ of all programs in the naive language and $72.62%$ of all programs in the language with commutativity pruning.

### How it works

#### Step 1

First, your DSL is loaded as a Python file, and the following variables are searched for:

```text
sample_dict
dsl
target_type (optional)
skip_exceptions (optional)
```

##### Sample Dict

The sampling dictionary maps each type to a function that takes no arguments and returns a sample element of that type. By default, the tool aims to generate diverse inputs but will stop after a certain number of failed attempts. A wider range of samplable types allows for checking more properties.

Note that if your sampling relies on a pseudo-random number generator, seeding it is advisable for reproducible results.

##### DSL

This object defines each primitive as a tuple containing its type and its semantic implementation. Constants can be provided directly; currently, functions without arguments that trigger a call are not supported.

##### Target Type

Instead of generating all possible programs from your DSL, you can specify a target type. This must be a base type (not a sum type, function, or polymorphic type). Specifying a target type can significantly reduce the search space and speed up the process, often yielding better results.

##### Skip Exceptions

During program execution, certain exceptions might occur, potentially halting the process. By providing a set of exceptions in `skip_exceptions`, the tool will catch these exceptions, and the program's output will be `None` instead, allowing the tool to continue its operation.

#### Step 2

The tool samples input values for all the types for which samplers are provided.

#### Step 3

The tool checks for commutativity. This check needs to be performed explicitly because the automaton model used cannot inherently order trees, thus it cannot automatically forbid $a+b$ if $b+a$ was generated (this would require the ability to order $a$ and $b$). Therefore, a manual, approximate check for commutativity is performed. For a commutative operation like $+$, programs are ordered based on the last primitive used (the root of the trees). Only $t\_a + t\_b$ where $t\_a \\le t\_b$ is allowed, and $t\_a$, $t\_b$ are programs with functions $a$ and $b$ as their respective roots.

#### Step 4

The tool generates a pruned grammar based on commutativity constraints, as these are quick to identify and can eliminate a significant number of programs, speeding up the subsequent enumeration process. For each enumerated program (up to a maximum target size), it is evaluated on all the sampled inputs. The resulting set of outputs is its characteristic sequence. If a program's characteristic sequence is identical to that of a previously enumerated program, it is discarded because the two programs are semantically equivalent. Since the enumeration is done in a bottom-up manner, the expansions of redundant programs are never even considered.

#### Step 5

An automaton is built from the enumerated and retained programs. It has been observed that building the automaton from the kept programs is significantly faster than using automata product and then forbidding programs. Note that the language described by the automaton is an over-approximation. Because the automaton must be valid for any number of variables and types, all variables of the same type are merged. Consequently, some programs like $x - x$, which were pruned, might still be present in the automaton's language, as $x_1 - x_0$ could represent a valid and interesting program. This automaton describes the language of programs up to a fixed size.

#### Step 6

This step is performed only if the `--no-loop` flag is not provided. The automaton is extended to handle programs of any size. While various methods exist for this, a faster, albeit non-optimal, approach is used due to the combinatorial explosion in the size of the automata being considered. The idea is to take the ending states of programs of the maximum size and make them loop over the maximum size. The rationale is that a program of size $n+1$ can be viewed as two overlapping "windows" of programs of size $n$. Multiple such windows exist, and the tool selects the most restrictive one. The resulting automaton is then reduced and minimized.

#### Step 7

The consistency of the obtained automaton is checked:

  - Any program retained during enumeration should be accepted by the automaton.
  - Every primitive of the DSL should be present and used by the automaton.
  - All type variations of every primitive in the DSL should be present and used by the automaton.

If any of these conditions are not met, a warning is printed to the user, as this might indicate an unintended outcome.

### Additional Notes

Regarding the `size` parameter:

  - If the `size` is too small, not all your primitives might be included in the automaton. For a primitive with arity $k$ to be in the automaton, the minimum `size` should be $k+1$.
  - The benefits of increasing the `size` diminish, while the computation time increases exponentially.
  - Non-monotonic gains with increasing `size` can occur if very few redundant programs are added at a particular size. In such cases, trying a slightly larger `size` often resolves this and yields further improvements.

Regarding the `--no-loop` flag:

  - Comparing the number of programs up to the maximum `size` with and without the `--no-loop` flag will show slightly more programs when the flag is absent due to the introduced loops. This is not a bug; it arises because some programs are smaller than the maximum size and require looping, potentially generating new redundant programs within the size limit.

## Type System

The type system is basic and not intended for complex DSLs, although contributions to enhance its capabilities would be welcome. Functions are not treated as first-class citizens. The type system primarily serves to ensure the generation of syntactically correct programs without enforcing deeper semantic constraints. There are no specific keywords.

```python
# Defines a type 'a'
a
# Defines a function with two arguments: the first of type 'a', the second of type 'b', and returns a 'c'
a -> b -> c
# Defines a function that can have one of the following type signatures:
#   t1 -> t1
#   t1 -> t2
#   t2 -> t1
#   t2 -> t2
t1 | t2 -> t1 | t2
# Defines a polymorphic type 'a'. The "'" character is a special marker for detecting this.
# All instantiations of 'a' must be the same, resulting in the following options:
#   t1 -> t1
#   t2 -> t2
'a [ t1 | t2 ] -> 'a
```

## GRAPE Format

The GRAPE format for the deterministic tree automaton is as follows:

```text
finals:S0,S1
letters:+,1,var_int
states:S0,S1
S0,+,S0,S0
S0,+,S1,S0
S0,+,S1,S1
S1,1
S0,var_int
```

The first line starts with `finals:` and lists the comma-separated final states of the automaton.
The second line starts with `letters:` and lists the comma-separated DSL primitives used, which constitute the alphabet of the automaton.
The third line starts with `states:` and lists the comma-separated states of the automaton.
Each subsequent line defines a transition of the automaton. For example:

```text
S0,+,S1,S0
# Represents the following transition:
S0 <- + S1 S0
```

For variables and constants, we have:

```text
S1,1
# Represents the following transition:
S1 <- 1
```

To extend the automaton for more variables, for every rule `dst,var_X` where `X` is the type of your variable, add a rule `dst,var_i`. Note that if you have variables of different types, you should do this for the variable corresponding to the respective type.
