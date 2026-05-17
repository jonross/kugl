# Implementation Plan: Named Scopes + `from:` Unification

Two related improvements to the YAML extension mechanism. They can be implemented
sequentially on one branch or separately; Phase 1 is a prerequisite for Phase 2's
scope-aware path resolution.

---

## Phase 1: Named Scopes in `row_source`

### Goal

Replace the `^` parent-hop syntax with named scope references.

**Single row_source** (the common case — default `["items"]` or one explicit entry):
path expressions resolve against the one implicit object; no scope prefix required.

**Multiple row_source entries**: every entry must carry `as <name>`, and every path /
label expression must begin with an explicit scope name.  There is no implicit
"current object" when more than one level exists.

```yaml
create:
  - table: node_taints
    resource: nodes
    row_source:
      - items as node
      - spec.taints as taint
    columns:
      - name: node_uid
        path: node.metadata.uid
      - name: taint_key
        path: taint.key
```

### Changes

**`kugl/impl/tables.py` — `Itemizer`**

- Parse `as <name>` suffix from row_source entries.  `"items as node"` yields
  `Itemizer(expr="items", name="node", finder=..., unpack=False)`.
- Store `name: Optional[str]` on the dataclass.

**`kugl/impl/tables.py` — `RowContext`**

- Add `_scopes: dict[int, dict[str, object]]`.  Key is `id(child)`; value is the
  map of scope names visible at that child's level.
- Update `set_parent` to also record named scopes: when a child is created from a
  level that had a name, include that name → parent-object in the child's scope map,
  merging with any scopes already inherited.
- Add `get_scope(child, name) -> Optional[object]` that walks up the scope chain
  to find the named object.

**`kugl/impl/tables.py` — `TableFromConfig._itemize`**

- After calling `context.set_parent(child, item)`, also call a new
  `context.set_scope(child, source.name, item)` when `source.name` is not None,
  carrying forward all ancestor scopes so deeper levels can still reference `node`.

**`kugl/impl/extract.py` — `FieldRef` / `PathExtractor` / `LabelExtractor`**

- `FieldRef.parse`: remove `^` handling; detect a leading `<word>.` prefix as a
  scope name.  Store as `scope_name: Optional[str]` and strip it from the target
  before JMESPath compilation.
- In `PathExtractor.extract` and `LabelExtractor.extract`, when `self._ref.scope_name`
  is set, resolve the object via `context.get_scope(obj, scope_name)`.
- Validation at table-build time (`TableFromConfig.__init__`): if `len(row_source) > 1`,
  every `row_source` entry must have a name and every column path/label must carry a
  scope prefix; raise a clear `ConfigError` if either constraint is violated.

### Builtin Update

`kugl/builtins/schemas/kubernetes.yaml` — convert `node_taints` to use named scopes
as a self-contained example:

```yaml
    row_source:
      - items as node
      - spec.taints as taint
    columns:
      - name: node_uid
        path: node.metadata.uid
      - name: taint_key
        path: taint.key
```

### Tests

- Update the existing `node_taints` test (wherever it lives) to verify the new
  syntax produces the same output.
- Add a new test with three levels of nesting (e.g. `pod → container → env`) using
  two named scopes, verifying that both ancestor levels are reachable by name.
- Add a test that `^` in a path raises a clear parse error.
- Add a test that a multi-step `row_source` with a missing `as` name raises a `ConfigError`.
- Add a test that a multi-step `row_source` with a bare (un-scoped) column path raises a `ConfigError`.

---

## Phase 2: `from:` Key Unification

### Goal

Replace the two-key `path:` / `label:` vocabulary with a single `from:` key that
auto-detects extraction type.  Named scope prefixes compose naturally.

Single row_source (bare paths, no scope prefix needed):

```yaml
    columns:
      - name: node_pool
        from: karpenter.sh/nodepool   # auto-detected: label
      - name: provider_id
        from: spec.providerID         # auto-detected: JMESPath
```

Multi-step row_source (all entries named, all columns scoped):

```yaml
    row_source:
      - items as pod
      - spec.containers as container
    columns:
      - name: pod_name
        from: pod.metadata.name           # named scope + JMESPath
      - name: pod_pool
        from: pod.karpenter.sh/nodepool   # named scope + label
      - name: container_name
        from: container.name              # named scope + JMESPath
```

### Auto-Detection Rule

After stripping any `<scope>.` prefix:

- Matches `[a-zA-Z0-9.-]+/[a-zA-Z0-9._/-]+` (K8s label format: DNS domain + `/` +
  key) → `LabelExtractor`
- Otherwise → `PathExtractor`

A value like `metadata.labels.foo/bar` is a JMESPath, not a label — the `/` appears
inside a path segment, not as the label-domain separator.  The regex above handles
this correctly because `metadata.labels.foo` is not a valid DNS domain segment.

### Changes

**`kugl/impl/config.py` — `UserColumn`**

- Add `from_: Optional[str] = Field(None, alias="from")` (Pydantic alias needed
  because `from` is a Python keyword).
- In `gen_extractor`, handle `from_` alongside `path` and `label`.
  - If `from_` is set alongside `path` or `label`, raise `ValueError`.
  - Parse any scope prefix from `from_`.
  - Apply the label-vs-path regex to the remainder.
  - Construct the appropriate extractor, passing the scope name through.
- Keep `path:` and `label:` fully supported so existing configs are not broken.

**`kugl/impl/extract.py` — `FieldRef`**

- Move the scope-prefix parsing here; `gen_extractor`
  delegates to `FieldRef.parse_from(s, known_scopes=None)`.
- Known scopes are not available at Pydantic parse time (they live in `CreateTable`
  which is a sibling, not a parent).  Two options:
  - **Lazy validation**: accept any `<word>.` prefix as a potential scope; fail at
    table-build time in `TableFromConfig.__init__` if a referenced scope name is not
    declared in `row_source`.
  - **Two-pass**: `CreateTable` validates column scope references after parsing.
  Lazy validation is simpler and consistent with how `path:` expressions are
  currently validated (JMESPath compilation errors surface at parse time, but
  missing-path errors surface at query time).

### Tests

- `from: karpenter.sh/nodepool` produces the same result as `label: karpenter.sh/nodepool`.
- `from: spec.providerID` produces the same result as `path: spec.providerID`.
- `from: node.metadata.name` with a named `node` scope resolves correctly.
- `from: node.karpenter.sh/nodepool` with a named `node` scope resolves as a label
  on the node object.
- Error: `from:` and `path:` both specified → validation error.
- Error: `from: unknownscope.foo` where `unknownscope` is not in `row_source` → clear
  error message at table-build time.

---

## Files Touched

| File | Change |
|---|---|
| `kugl/impl/extract.py` | `FieldRef.parse`: detect scope prefix; extractors: resolve via scope |
| `kugl/impl/tables.py` | `Itemizer`: parse `as <name>`; `RowContext`: track named scopes |
| `kugl/impl/config.py` | `UserColumn`: add `from_` field and dispatch in `gen_extractor` |
| `kugl/builtins/schemas/kubernetes.yaml` | Convert `node_taints` to named scope syntax |
| `tests/` | Update node_taints test; add multi-level and `from:` tests |

---

## Out of Scope

- The broader resource-coverage gaps from `discuss.md` (deployments, containers table,
  etc.) are separate work and should not be bundled here.
