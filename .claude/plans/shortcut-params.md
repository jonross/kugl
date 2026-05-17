# Plan: Positional Shortcut Parameters

## Context

Shortcuts are currently static command aliases. Adding positional parameters lets users write
one shortcut and invoke it with different values, like calling a shell function:

```
kugl pods-in-ns kube-system
```

The shortcut config declares param names; invocation supplies values positionally; `{{name}}`
templates in `args` are substituted before expansion.

---

## Config Change — `kugl/impl/config.py`

Add `params: list[str] = []` to `Shortcut` and a validator that checks every `{{name}}` token
in `args` is covered by a declared param name.

```python
class Shortcut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    args: list[str]
    comment: Optional[str] = None
    params: list[str] = []

    @model_validator(mode="after")
    @classmethod
    def _check_params(cls, shortcut: "Shortcut") -> "Shortcut":
        declared = set(shortcut.params)
        for arg in shortcut.args:
            for token in re.findall(r'\{\{(\w+)\}\}', arg):
                if token not in declared:
                    fail(f"Shortcut '{shortcut.name}': undeclared parameter '{{{{token}}}}'")
        return shortcut
```

User config example:

```yaml
shortcuts:
  - name: pods-in-ns
    args: ["select name, status from pods where namespace = '{{ns}}'"]
    params:
      - ns
```

---

## Parsing Change — `kugl/main.py`

### 1. Switch to `parse_known_args`

In `parse_args()`, change:
```python
args = ap.parse_args(argv)
```
to:
```python
args, extras = ap.parse_known_args(argv)
```

Return signature becomes `tuple[argparse.Namespace, CacheFlag, list[str]]`.

Update the one call site in `main2` accordingly:
```python
args, cache_flag, extras = parse_args(argv, ap, init.settings)
```

### 2. Shortcut expansion block

Replace the current 3-line shortcut block (lines 85-89) with:

```python
if " " not in args.sql:
    if not (shortcut := shortcuts.get(args.sql)):
        fail(f"No shortcut named '{args.sql}' is defined")
    # Reject flag-looking extras (unrecognized options, not param values)
    bad = [e for e in extras if e.startswith('-')]
    if bad:
        fail(f"Unrecognized options: {' '.join(bad)}")
    # Validate positional param count
    if len(extras) != len(shortcut.params):
        if shortcut.params:
            fail(f"Shortcut '{shortcut.name}' requires {len(shortcut.params)} argument(s): {', '.join(shortcut.params)}")
        else:
            fail(f"Shortcut '{shortcut.name}' takes no arguments")
    # Substitute and recurse
    bindings = dict(zip(shortcut.params, extras))
    expanded = [re.sub(r'\{\{(\w+)\}\}', lambda m: bindings[m.group(1)], a) for a in shortcut.args]
    base = [a for a in argv if a not in set(extras) and a != args.sql]
    return main2(base + expanded, init)
```

Add `import re` at the top of `main.py`.

**Known limitation**: If a flag's value happens to equal the shortcut name (e.g., `kugl -c my-sc my-sc`),
the value-based `argv` reconstruction could drop it. This is the same class of fragility as the current
`argv[:-1]` approach and is unlikely in practice.

---

## Tests — `tests/config/test_merge_init.py`

Add parametrized tests alongside the existing shortcut tests:

| Case | Expected |
|---|---|
| Shortcut with 1 param, correct invocation | Correct output |
| Shortcut with 2 params, correct invocation | Correct output |
| Too few args | `KuglError` with param names in message |
| Too many args | `KuglError` with "takes no arguments" |
| Undeclared `{{token}}` in config | `KuglError` at config parse time |
| Flags before shortcut name still work (e.g. `-H`) | Headers suppressed |

---

## Files to Modify

| File | Change |
|---|---|
| `kugl/impl/config.py` | Add `params` field + `_check_params` validator to `Shortcut` |
| `kugl/main.py` | `parse_known_args`, new shortcut expansion block, `import re` |
| `tests/config/test_merge_init.py` | New test cases for parameterized shortcuts |

---

## Verification

```bash
# Run the full test suite
uv run pytest tests/

# Manual smoke test
# In ~/.kugl/init.yaml:
#   shortcuts:
#     - name: test-sc
#       args: ["select '{{val}}'"]
#       params: [val]
kugl test-sc hello          # should print "hello"
kugl test-sc                # should fail with param count error
kugl test-sc a b            # should fail with param count error
kugl -H test-sc hello       # should suppress headers
```
