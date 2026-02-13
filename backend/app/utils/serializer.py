"""Serialization utilities for export/import with intentional deserialization vulnerabilities.

Provides three deserialization functions with escalating bypass difficulty:
  - jsonpickle_decode: trivial RCE via py/reduce (CWE-502)
  - safe_yaml_load: FullLoader bypass via !!python/object/new (CWE-502)
  - safe_pickle_loads: RestrictedUnpickler with too-broad module check (CWE-502)

All three are intentionally vulnerable and used by routes/export_import.py.
"""

import base64
import io
import json
import pickle
from typing import Any

import jsonpickle
import yaml


# ---------------------------------------------------------------------------
# Pickle — RestrictedUnpickler with bypassable module allowlist (VULN 3)
# ---------------------------------------------------------------------------


# VULN: Insecure Deserialization (Pickle) - RestrictedUnpickler uses
# module.startswith("app.models") which is too broad: a crafted pickle
# referencing module "app.models_evil" would pass. Additionally, allowed
# classes can be chained via __reduce__ to escalate to RCE.
# Ref: https://hackerone.com/reports/2334460
class RestrictedUnpickler(pickle.Unpickler):
    """Pickle unpickler with an intentionally bypassable module allowlist.

    The restriction uses ``module.startswith("app.models")`` instead of
    an exact match, so any module whose name begins with "app.models"
    (e.g. ``app.models_evil``) passes the check.

    Attributes:
        ALLOWED_MODULE_PREFIX: The too-broad prefix used for filtering.
    """

    ALLOWED_MODULE_PREFIX = "app.models"

    def find_class(self, module: str, name: str) -> type:
        """Resolve a class reference during unpickling.

        Args:
            module: Fully qualified module name from the pickle stream.
            name: Class/function name within the module.

        Returns:
            The resolved class object.

        Raises:
            pickle.UnpicklingError: If the module does not start with
                the allowed prefix.
        """
        # VULN: startswith is too broad — "app.models_anything" passes
        if not module.startswith(self.ALLOWED_MODULE_PREFIX):
            raise pickle.UnpicklingError(
                f"Module '{module}' is not allowed (must start with "
                f"'{self.ALLOWED_MODULE_PREFIX}')"
            )
        return super().find_class(module, name)


EXPORT_PREFIX = "VSEXPORT_V2:"


def safe_pickle_loads(data: str) -> Any:
    """Deserialize pickle data with a bypassable RestrictedUnpickler.

    Expects the VSEXPORT_V2 prefix format followed by base64-encoded
    pickle bytes. The RestrictedUnpickler is intentionally weak: its
    ``startswith`` check can be bypassed with crafted module names.

    Args:
        data: String in format ``VSEXPORT_V2:<base64-pickle>``.

    Returns:
        The deserialized Python object.

    Raises:
        ValueError: If the VSEXPORT_V2 prefix is missing.
        pickle.UnpicklingError: If a non-allowed module is referenced
            (but the check is bypassable).
    """
    if not data.startswith(EXPORT_PREFIX):
        raise ValueError(
            f"Invalid export format: data must start with '{EXPORT_PREFIX}'"
        )

    encoded = data[len(EXPORT_PREFIX):]
    raw_bytes = base64.b64decode(encoded)

    # VULN: RestrictedUnpickler's module check is bypassable
    return RestrictedUnpickler(io.BytesIO(raw_bytes)).load()


# ---------------------------------------------------------------------------
# YAML — FullLoader instead of SafeLoader (VULN 2)
# ---------------------------------------------------------------------------


def safe_yaml_load(data: str) -> Any:
    """Deserialize YAML using FullLoader instead of SafeLoader.

    FullLoader blocks ``!!python/object/apply`` but allows
    ``!!python/object/new:type`` with ``extend=exec`` in listitems,
    enabling arbitrary code execution.

    If the data has the VSEXPORT_V2 prefix, it is stripped and
    base64-decoded first (for round-trip with the export endpoint).

    Args:
        data: Raw YAML string, or VSEXPORT_V2-prefixed base64 YAML.

    Returns:
        The deserialized Python object.
    """
    # Support round-trip: exported data has the VSEXPORT_V2 prefix
    if data.startswith(EXPORT_PREFIX):
        encoded = data[len(EXPORT_PREFIX):]
        data = base64.b64decode(encoded).decode("utf-8")

    # VULN: Insecure Deserialization (YAML) - FullLoader allows
    # !!python/object/new:type bypass — SafeLoader would prevent this.
    # Attack: !!python/object/new:type { args: [""], extend: exec,
    #   listitems: "import os; os.system('id')" }
    # Ref: https://hackerone.com/reports/1415436
    return yaml.load(data, Loader=yaml.FullLoader)


# ---------------------------------------------------------------------------
# jsonpickle — Unrestricted decode (VULN 1)
# ---------------------------------------------------------------------------


def jsonpickle_decode(data: str) -> Any:
    """Deserialize JSON using jsonpickle.decode — trivial RCE.

    jsonpickle interprets ``py/reduce``, ``py/object``, and ``py/exec``
    directives embedded in JSON, allowing arbitrary code execution.
    The JSON syntax validation via ``json.loads()`` does not prevent
    exploitation because the malicious directives are valid JSON.

    Args:
        data: JSON string potentially containing jsonpickle directives.

    Returns:
        The deserialized Python object.

    Raises:
        ValueError: If the input is not valid JSON syntax.
    """
    # Validate JSON syntax — does NOT prevent RCE payloads
    try:
        json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    # VULN: Insecure Deserialization (jsonpickle) - jsonpickle.decode()
    # executes py/reduce, py/object, and py/exec directives embedded
    # in otherwise valid JSON. Trivial RCE with:
    # {"py/reduce": [{"py/function": "os.system"}, {"py/tuple": ["id"]}]}
    # Ref: https://hackerone.com/reports/350401
    return jsonpickle.decode(data)
