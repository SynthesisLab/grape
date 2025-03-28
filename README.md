# Grammar Pruning with Observational Equivalence (GPOE)

Given a domain specific language (DSL), the goal of this tool is to automatically find the semantically redundant programs.

Take for example: ``x, -x, - (-x)``, ``- (-x)`` is redundant since it evaluates to ``x`` whatever the ``x`` value.

This tool offers automatically finding these redundancies by evaluating the programs.
It works by enumerating program by increasing size until a maximum target size, each enumerated program is evaluated on sampled inputs.
The evaluation of a program on the set of inputs is its characteristic sequence, two programs that have the same characteristic sequences are redundant, therefore only the smallest program is kept.

Currently, this redundant information is compiled by the tool to produce:

- a deterministic bottom-up tree automaton, which can trivially be converted into a context-free grammar for example;
- a set of program rewrites

**Table of contents**:
<!-- TOC START -->
- [Installation](#installation)
- [Example](#example)
- [How it works](#how-it-works)
- [Type System](#type-system)
- [Additional Notes](#additional-notes)
- [Output Format](#output-format)

<!-- TOC END -->

## Installation

```sh
pip install git+https://github.com/SynthesisLab/gpoe.git
```

## Example

Let us assume you have the following ``dsl.py`` file:

```python
import random

MAXI = 1 << 32 - 1
random.seed(1)

# Given a type provides a function to sample one element
sample_dict: dict[str, callable] = {"int": lambda: int(random.randint(-MAXI, MAXI))}

# Given a primitive provides a tuple (type, implementation)
# supported types are:
#   - primitive: just give it a name and you are good to go!
#   - sum types: a | b can either be a or b
#   - polymorphics: 'a [ t1 | t2 ] -> 'a
#       syntax: must start with a "'"
#               the list of supported types must be given at 1st usage inside the []
#       semantic: the above example means either: t1 -> t1 or t2 -> t2 
#                 but t1 -> t2 and t2 -> t1 are impossibles 
#                 because all instanciations of 'a must have the same value
#                 at any given time
dsl: dict[str, tuple[str, callable]] = {
    "+": ("int -> int -> int", lambda x, y: x + y),
    "*": ("int -> int -> int", lambda x, y: x * y),
    "-": ("int -> int -> int", lambda x, y: x - y),
    "^": ("int -> int -> int", lambda x, y: x ^ y),
    "&": ("int -> int -> int", lambda x, y: x & y),
    "|": ("int -> int -> int", lambda x, y: x | y),
    "~": ("int -> int", lambda x: ~x),
    "1": ("int", 1)
}

# (Optional) Every element underneath is OPTIONAL
# In other words you can omit them without error

# Type of object you want to produce, if not specified all types can be generated
target_type: str = "int"

# Set of errors which will not trigger but cause the program to return None
skip_exceptions: set = {OverflowError}
```

Then you can run:

```sh
python -m gpoe dsl.py --size 5 --samples 300 -o grammar.txt
```

The output I have on my machine is the following:

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

Some explanations:

```text
at size: 5
    no pruning: 1.04e+04
    commutativity pruned: 5.49e+03 (52.92%)
```

This indicates the size gained by early checking for commutativity, the number of programs that will be enumerated is ``5.49e+03``, it is a good indication of time that the algorithm will take even though it is highly DSL dependent.

```text
obs. equivalence: 6.620e+02 pruned: 8.070e+02 (121.90%)
```

These numbers indicate mostly how much an over-approximation of the truly semantically equivalent programs we built, here it is ``121.90%`` so it contains ``21.90%`` more programs given the same conditions.
It is mostly indicative and do not indicate full enumeration numbers.

```text
at size: 5
    method: ratio no pruning | ratio comm. pruned | ratio pruned
    no pruning: 100.00% | 188.98% | 260.22%
    commutativity pruned: 52.92% | 100.00% | 137.70%
    pruned: 38.43% | 72.62% | 100.00%
```

This table compares the number of programs in the three different languages for programs of size up to 5.
These are the relative number of programs.
Therefore the automaton contains up to size 5 ``38.43%`` of all the programs in the naive language, and ``72.62%`` of all the programs in the language with commutativity pruned.

## How it works

### Step 1

First, we load your DSL as a python file and look for the following variables:

```text
sample_dict
dsl
target_type (optional)
skip_exceptions (optional)
```

#### Sample Dict

The sampling dictionary maps each type to a function taking no argument to sample elements of this type.
By default, the tool aims to sample different inputs, but will stop if it fails after a number of tries.
The more types that can be sampled the more properties can be checked.

Be aware, that if your sampling depends on a pseudo random number generator, then you probably want to seed it as to get reproducible results.

#### DSL

This objects describes for each primitive a tuple containing its type and its semantic.
Constants can be directly given, so there is no way currently to have functions with no arguments (that actually trigger a call).

#### Target Type

Instead of generating everything and anything that can be generated given your DSL, you target a specific type.
Be aware that it must be a base type (no sum type, no function, no polymorphic).
It reduces the space of research so it can speed up the process and gives you better results.

#### Skip Exceptions

It may occur that your code triggers some exceptions during executions, they will stop the execution of the process.
Instead, the tool will catch exceptions given in this set, the program will return ``None`` as output instead when such an exception is triggered but the tool will continue.

### Step 2

The tool samples inputs for all the types sampler provided.

### Step 3

The tool checks for commutativity.
This check must be done manually since the automaton model used cannot order trees, it cannot forbid a+b if b+a was generated, this would imply that you can order a and b.
Therefore we check for it manually, and approximate it under something a bit less powerful but still captures a part of commutativity.
Let us take ``+`` which is commutative, instead we order programs based on the last primitive used (the root of the trees), only ``+ t_a t_b`` where ``t_a`` <= ``t_b`` are allowed and ``t_a``, ``t_b`` are programs/trees with functions ``a``, ``b`` as their root.

### Step 4

The tool generate a pruned grammar based on commutativity constraints since they are fast to find and prune away a lot of programs.
This is helpful to speed-up this part where we enumerate programs of increasing size.
Evaluating a program on all the sampled inputs produce a set of outputs, this is what we call its characteristic sequence.
For each program enumerated, it is evaluated, if its characteristic sequence is the same as another previously enumerated program then it is discarded because those two programs are semantically equivalent.
Since our enumeration is done in a bottom-up manner, all expansions of redundant programs are not even considered.

### Step 5

We build an automaton from the enumerated programs that were kept.
We found that building from programs kept is way faster than using automata product and forbidding programs.
Note that the language described by the automaton is an over approximation.
Since the automaton needs to be valid for any number of variables number and types, then all variables of the same types are merged, and thus some programs like ``x - x`` which were pruned must be present in the language described in the automaton, as ``x1 - x0`` may be an interesting program.
This automaton describes a language from programs up to a fixed size.

### Step 6

This step is done only if the flag ``--no-loop`` is not given.
We now extend the automaton to make it work for any size of programs.
There are numerous ways to do this, however we considered a non-optimal but faster one due to the sheer combinatorial explosion of the size of the automata considered.
The idea is to take ending states of programs of maximal size and make them loop over the maximum size.
The idea is that a program of size ``n+1`` can be seen as two windows of programs of size ``n`` by moving slightly our window.
There are multiple such windows, by default the tool chooses the first one which is way faster.
The flag ``--optimize`` chooses the most constrained window, that is the most restrictive one, at the cost of slower extension.
The resulting automaton is reduced then minimized.

### Step 7

Now we check that the automaton obtained is consistent:

- any program that was kept during enumeration is kept in the language of the automaton
- any primitive of the DSL is present and used by the automaton
- all type variants of every primitives of the DSL are present and used by the automaton

If any of these conditions is not respected then a warning is printed ot the user as this may be intentional.

## Type System

The type system is rudimentary and is not intended for complex DSL but a good contribution would be augmenting its capabilities.
Functions are not first class citizens.
The type system works as a simple way to produce syntactically correct programs and nothing else, there are no specific keywords.

```python
# Defines a type a
a 
# Defines a function with two arguments the first of type a, the second of type b and returns a c
a -> b -> c
# Defines a function that can be one of the following option:
#   t1 -> t1
#   t1 -> t2
#   t2 -> t1
#   t2 -> t2
t1 | t2  -> t1 | t2
# Defines a polymorphic type 'a, the "'" is treated as a special character for detecting this.
# All instantiations of 'a must be the same therefore producing the following options:
#   t1 -> t1
#   t2 -> t2
'a [ t1 | t2 ] -> 'a
```

## Additional Notes

For the ``size`` parameter:

- if it is too small you won't get all your primitives in the automaton because the max size was too small, basically for a primitive of arity ``k`` to be in the automaton, the minimal size must be ``k+1``.
- gains decrease with increased size, and time taken increases exponentially.
- there are some effects with ``size`` such that you can get gains that are not monotone due to the fact that very few redundant programs have been added, in that case try going to one size larger, usually you get back your improvements.

For the ``--optimize`` flag:

- on our hardware, recent i7, it was 10 times as slow.
- on the provided example case, it provided no improvement, even if it did we expect the improvements to be minimal.

For the ``--no-loop`` flag:

- if you compare the number of programs up to the max size with and without the flag, you will observe that without ``no-loop`` there are slightly more programs because of the loops. It is not a bug, it is due that some programs are not of the maximum size and needs to loop, therefore producing new redundant programs because of the loops within the size bound.

## Output Format

The output format for the deterministic tree automaton is the following:

```text
finals:S0,S1
terminals:+,1,var0
nonterminals:S0,S1
S0,+,S0,S0
S0,+,S1,S0
S0,+,S1,S1
S1,1
S0,var0
```

The first line has the prefix ``finals:`` and contains comma separated the list of final states of the automaton.
The second line has the prefix ``terminals:`` and contains comma separated the list of DSL primitives used, that is the alphabet of the automaton.
The third line has the prefix ``nonterminals:`` and contains comma separated the list of states of the automaton.
Then on each line is defined a transition of the automaton.
First, let us look at:

```text
S0,+,S1,S0
# Which is the following transition:
S0 <- + S1 S0
```

and for variables and constants we have:

```text
S1,1
# Which is the following transition:
S1 <- 1
```

If you want to extend the automaton for more variables, it is quite straightforward, for every rule ``dst,var0`` add a rule ``dst,vari``.
Note that if you have variables of different types, you should od this with the variable of the respecting type.
