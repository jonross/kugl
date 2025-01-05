from kugl.util import fail

_BY_TYPE: dict[str, "Resource"] = {}
_BY_SCHEMA: dict[str, "Resource"] = {}


class Resource:

    @staticmethod
    def add_type(cls: type, name: str, schema_defaults: list[str]):
        """
        Register a resource type.  This is called by the @resource decorator.

        :param cls: The class to register
        :param name: e.g. "file", "kubernetes", "aws"
        :param schema_defaults: The schema names for which this is the default resource type.
            For type "file" this is an empty list because any schema can use a file resource,
                it's never the default.
            For type "kubernetes" this any schema that will use 'kubectl get' so e.g.
                ["kubernetes", "argo", "kueue", "karpenter"] et cetera
            It's TBD whether we will have a single common resource type for AWS resources, or
                if there will be one per AWS service.
        """
        existing = _BY_TYPE.get(name)
        if existing:
            fail(f"Resource type {name} already registered as {existing.__name__}")
        for schema_name in schema_defaults:
            existing = _BY_SCHEMA.get(schema_name)
            if existing:
                fail(f"Resource type {name} already registered as the default for schema {schema_name}")
        _BY_TYPE[name] = cls
        for schema_name in schema_defaults:
            _BY_SCHEMA[schema_name] = cls