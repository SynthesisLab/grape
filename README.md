# Grammar Pruning with Observational Equivalence (GPOE)

## Example

Let us assume you have the following ``dsl.py`` file:

```python
import random

MAXI = 1 << 32 - 1
random.seed(1)

# Given a type provides a function to sample one element
sample_dict = {"int": lambda: int(random.randint(-MAXI, MAXI))}

# Given a primitive provides a tuple (type, implementation)
dsl = {
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
target_type = "int"

# Set of errors which will not trigger but cause the program to return None
skip_exceptions = {OverFlowError}

# Given a type provides an implementation of ==
# Warning: this is not fully supported so better leave it empty
equal_dict = {}
```

Then you can run:

```sh
python -m gpoe dsl.py --size 7 --samples 300 -o grammar.txt
```
