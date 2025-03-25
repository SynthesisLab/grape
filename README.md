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
