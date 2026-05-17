# Implementation Plan: Named Scopes + `from:` Unification

Two related improvements to the YAML extension mechanism. They can be implemented
sequentially on one branch or separately; Phase 1 is a prerequisite for Phase 2's
scope-aware path resolution.

Scope references use a consistent `in <name>` suffix, mirroring the `as <name>` suffix
in `row_source` declarations: `as` binds a name, `in` references it.

---

## Phase 1: Named Scopes in `row_source`

**Status: implemented with `<scope>.` prefix syntax — needs revision to `in <scope>` suffix.**

### Goal

Replace the `^` parent-hop syntax with named scope references.

**Single row_source** (the common case — default `["items"]` or one explicit entry):
path expressions resolve against the one implicit object; no scope qualifier required.

**Multiple row_source entries**: every entry must carry `as <name>`, and every path /
label expression must end with an explicit `in <name>` qualifier.  There is no implicit
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
        path: metadata.uid in node
      - name: taint_key
        path: key in taint
```

### Changes

**`kugl/impl/tables.py` — `Itemizer`**

- Parse `as <name>` suffix from row_source entries.  `"items as node"` yields
  `Itemizer(expr="items", name="node", finder=..., unpack=False)`.
- Store `name: Optional[str]` on the dataclass.

**`kugl/impl/tables.py` — `RowContext`**

- Add `_scopes: dict[int, dict[str, object]]`.  Key is `id(child)`; value is the
  map of scope names visible at that child's level.
- `set_scope(child, name, parent)` records the child's scope map, inheriting all
  ancestor scopes from parent and adding `name → child`.
- Add `get_scope(obj, name) -> Optional[object]` that looks up the named object.

**`kugl/impl/tables.py` — `TableFromConfig._itemize`**

- After calling `context.set_parent(child, item)`, also call
  `context.set_scope(child, source.name, item)` when `source.name` is not None,
  carrying forward all ancestor scopes so deeper levels can still reference `node`.

**`kugl/impl/extract.py` — `FieldRef` / `PathExtractor` / `LabelExtractor`**

- `FieldRef.parse`: remove `^` handling; detect a trailing ` in <word>` suffix as a
  scope name.  Store as `scope_name: Optional[str]` and strip it from the target
  before JMESPath compilation.
- In `PathExtractor.extract` and `LabelExtractor.extract`, when `self._ref.scope_name`
  is set, resolve the object via `context.get_scope(obj, scope_name)`.
- Validation at table-build time (`TableFromConfig.__init__`): if `len(row_source) > 1`,
  every `row_source` entry must have a name and every column path/label must carry an
  `in <name>` qualifier; raise a clear `ConfigError` if either constraint is violated.

### Builtin Update

`kugl/builtins/schemas/kubernetes.yaml` — convert `node_taints` to use named scopes
as a self-contained example:

```yaml
    row_source:
      - items as node
      - spec.taints as taint
    columns:
      - name: node_uid
        path: metadata.uid in node
      - name: taint_key
        path: key in taint
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
auto-detects extraction type.  Named scope qualifiers compose naturally via the same
`in <name>` suffix.

Single row_source (no scope qualifier needed):

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
        from: metadata.name in pod            # JMESPath on pod scope
      - name: pod_pool
        from: karpenter.sh/nodepool in pod    # label on pod scope — unambiguous
      - name: container_name
        from: name in container               # JMESPath on container scope
```

### Auto-Detection Rule

Strip any trailing ` in <word>` suffix first, then apply to the remainder:

- Matches `[a-zA-Z0-9.-]+/[a-zA-Z0-9._/-]+` (K8s label format: DNS domain + `/` +
  key) → `LabelExtractor`
- Otherwise → `PathExtractor`

A value like `metadata.labels.foo/bar` is a JMESPath, not a label — the `/` appears
inside a path segment, not as the label-domain separator.  The regex handles this
correctly because `metadata.labels.foo` is not a valid DNS domain segment.

Parsing ` in <word>` is safe because neither JMESPath expressions nor label keys
contain spaces, so the delimiter is unambiguous.

### Changes

**`kugl/impl/config.py` — `UserColumn`**

- Add `from_: Optional[str] = Field(None, alias="from")` (Pydantic alias needed
  because `from` is a Python keyword).
- In `gen_extractor`, handle `from_` alongside `path` and `label`.
  - If `from_` is set alongside `path` or `label`, raise `ValueError`.
  - Strip any ` in <word>` suffix from `from_` to extract the scope name.
  - Apply the label-vs-path regex to the remainder.
  - Construct the appropriate extractor, passing the scope name through.
- Keep `path:` and `label:` fully supported so existing configs are not broken.

**`kugl/impl/extract.py` — `FieldRef`**

- Centralise the ` in <scope>` parsing in `FieldRef.parse_scoped(s)`; both
  `gen_extractor` (for `from:`) and `FieldRef.parse` (for `path:`/`label:`) delegate
  to it.
- Known scopes are not available at Pydantic parse time.  Use lazy validation: accept
  any ` in <word>` suffix as a potential scope; fail at table-build time in
  `TableFromConfig.__init__` if the referenced scope name is not declared in
  `row_source`.

### Tests

- `from: karpenter.sh/nodepool` produces the same result as `label: karpenter.sh/nodepool`.
- `from: spec.providerID` produces the same result as `path: spec.providerID`.
- `from: metadata.name in pod` with a named `pod` scope resolves correctly.
- `from: karpenter.sh/nodepool in pod` with a named `pod` scope resolves as a label
  on the pod object.
- Error: `from:` and `path:` both specified → validation error.
- Error: `from: foo in unknownscope` where `unknownscope` is not in `row_source` → clear
  error message at table-build time.

---

## Files Touched

| File | Change |
|---|---|
| `kugl/impl/extract.py` | `FieldRef.parse`: detect ` in <scope>` suffix; extractors: resolve via scope |
| `kugl/impl/tables.py` | `Itemizer`: parse `as <name>`; `RowContext`: track named scopes |
| `kugl/impl/config.py` | `UserColumn`: add `from_` field and dispatch in `gen_extractor` |
| `kugl/builtins/schemas/kubernetes.yaml` | Convert `node_taints` to named scope syntax |
| `tests/` | Update node_taints test; add multi-level and `from:` tests |

---

## Out of Scope

- The broader resource-coverage gaps from `discuss.md` (deployments, containers table,
  etc.) are separate work and should not be bundled here.
