"""Versioned canonical BOQ items and project-scoped estimator mapping decisions."""
from __future__ import annotations

import datetime as dt
import base64
import hashlib
import hmac
import json
import os
import secrets
import shutil
import tempfile
import uuid

from .. import service, store
from ..filelock import locked
from .compare import TYPE_KEYWORDS, norm_code, norm_description, norm_unit

SCHEMA_VERSION = 1
CANONICAL_SCHEMA_VERSION = 1
PREVIEW_TTL_SECONDS = 300
_STATUSES = {"approved", "rejected", "unresolved"}


def _stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value):
    return hashlib.sha256(_stable(value).encode("utf-8")).hexdigest()


def _source_row_identity(row):
    return {k: row.get(k) for k in ("source_row", "row", "source_sheet", "source_item_no", "item_no",
                                     "source_description", "description", "source_unit", "unit",
                                     "source_quantity", "quantity", "section", "element", "floor")}


def source_key(source_file, sheet, row):
    identity = "\0".join((str(source_file or "").strip().casefold(), str(sheet or ""), str(row or "")))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _mapping_path(pid):
    return store.pdir(pid, "boq", "mappings.json")


def _canonical_path():
    return os.path.join(store.CONFIG, "canonical_boq_items.json")


def _preview_secret():
    path = os.path.join(store.DATA, "boq_mapping_preview.key")
    with locked(path + ".lock"):
        try:
            with open(path, "rb") as fh:
                secret = fh.read()
        except FileNotFoundError:
            secret = secrets.token_bytes(32)
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(secret)
                fh.flush()
                os.fsync(fh.fileno())
        if len(secret) != 32:
            raise ValueError(f"Invalid BOQ preview-signing key at {path}; refusing to reset it")
        return secret


def _read_mapping_unlocked(pid):
    path = _mapping_path(pid)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"BOQ mapping store is damaged; preserved file at {path}. Use explicit recovery.") from exc
    if (not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION
            or not isinstance(data.get("mappings"), dict)):
        raise ValueError(f"Unsupported or invalid BOQ mapping store schema at {path}")
    for key, rec in data["mappings"].items():
        if (not isinstance(key, str) or not isinstance(rec, dict) or rec.get("mapping_id") != key
                or rec.get("status") not in _STATUSES or not isinstance(rec.get("version"), int)
                or rec["version"] < 1 or not isinstance(rec.get("history"), list)):
            raise ValueError(f"Invalid BOQ mapping record '{key}' in {path}; use explicit recovery.")
    return data["mappings"]


def load(pid):
    with locked(_mapping_path(pid) + ".lock"):
        return _read_mapping_unlocked(pid)


def _atomic_write(path, data, backup_current=True):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    encoded = (_stable(data) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=".qto-", suffix=".tmp", dir=directory)
    backup_tmp = path + ".bak.tmp"
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
            fh.flush()
            os.fsync(fh.fileno())
        if backup_current and os.path.exists(path):
            shutil.copyfile(path, backup_tmp)
            with open(backup_tmp, "r+b") as backup:
                os.fsync(backup.fileno())
            os.replace(backup_tmp, path + ".bak")
        os.replace(tmp, path)
        if hasattr(os, "O_DIRECTORY"):
            dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
        if os.path.exists(backup_tmp):
            os.unlink(backup_tmp)


def _write_mappings_unlocked(pid, mappings):
    _atomic_write(_mapping_path(pid), {"schema_version": SCHEMA_VERSION, "mappings": mappings})


def recover(pid, use_backup=True):
    """Explicit recovery only: preserve damaged data, validate backup, then restore it."""
    path = _mapping_path(pid)
    with locked(path + ".lock"):
        candidate = path + ".bak" if use_backup else path
        try:
            with open(candidate, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Recovery source is unavailable or damaged: {candidate}") from exc
        if (not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION
                or not isinstance(data.get("mappings"), dict)):
            raise ValueError(f"Recovery source has an unsupported schema: {candidate}")
        for key, rec in data["mappings"].items():
            if (not isinstance(rec, dict) or rec.get("mapping_id") != key or rec.get("status") not in _STATUSES
                    or not isinstance(rec.get("version"), int) or not isinstance(rec.get("history"), list)):
                raise ValueError(f"Recovery source contains invalid mapping record: {key}")
        if use_backup and os.path.exists(path):
            stamp = dt.datetime.now().strftime("%Y%m%d%H%M%S%f")
            shutil.copy2(path, f"{path}.corrupt.{stamp}")
        _atomic_write(path, data, backup_current=not use_backup)
    return data["mappings"]


def _canonical_read_unlocked():
    path = _canonical_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {"schema_version": CANONICAL_SCHEMA_VERSION, "version": 0, "items": {}, "history": []}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Canonical BOQ library is damaged at {path}; use explicit recovery.") from exc
    if (not isinstance(data, dict) or data.get("schema_version") != CANONICAL_SCHEMA_VERSION
            or not isinstance(data.get("version"), int) or not isinstance(data.get("items"), dict)
            or not isinstance(data.get("history"), list)):
        raise ValueError(f"Unsupported or invalid canonical BOQ library at {path}")
    for item_id, item in data["items"].items():
        if (not isinstance(item, dict) or item.get("canonical_id") != item_id
                or not isinstance(item.get("version"), int) or item.get("status") not in ("active", "inactive")
                or not item.get("code") or not norm_unit(item.get("unit")) or not item.get("category")):
            raise ValueError(f"Invalid canonical BOQ item '{item_id}'")
    return data


def canonical_library():
    path = _canonical_path()
    with locked(path + ".lock"):
        data = _canonical_read_unlocked()
    return data


def recover_canonical_library(use_backup=True):
    path = _canonical_path()
    with locked(path + ".lock"):
        candidate = path + ".bak" if use_backup else path
        try:
            with open(candidate, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Canonical library recovery source is unavailable or damaged: {candidate}") from exc
        if (not isinstance(data, dict) or data.get("schema_version") != CANONICAL_SCHEMA_VERSION
                or not isinstance(data.get("version"), int) or not isinstance(data.get("items"), dict)
                or not isinstance(data.get("history"), list)):
            raise ValueError(f"Canonical library recovery source has an unsupported schema: {candidate}")
        for item_id, item in data["items"].items():
            if (not isinstance(item, dict) or item.get("canonical_id") != item_id
                    or item.get("status") not in ("active", "inactive") or not item.get("code")
                    or not item.get("description") or not item.get("category") or not norm_unit(item.get("unit"))):
                raise ValueError(f"Canonical library recovery source contains invalid item: {item_id}")
        if use_backup and os.path.exists(path):
            stamp = dt.datetime.now().strftime("%Y%m%d%H%M%S%f")
            shutil.copy2(path, f"{path}.corrupt.{stamp}")
        _atomic_write(path, data, backup_current=not use_backup)
    return data


def canonical_target(target_id):
    if not isinstance(target_id, str) or not target_id.startswith("canonical:"):
        raise ValueError("Invalid canonical target identity")
    item_id = target_id.split(":", 1)[1]
    data = canonical_library()
    item = data["items"].get(item_id)
    if not item:
        raise ValueError("Canonical BOQ target does not exist")
    if item["status"] != "active":
        raise ValueError("Canonical BOQ target is inactive")
    return data, item


def save_canonical_item(body, expected_version=None):
    """Create or version an item; callers must enforce their deployment's access policy."""
    if expected_version is None:
        expected_version = body.get("expected_version")
    action = body.get("action")
    if action not in ("create", "edit", "activate", "deactivate"):
        raise ValueError("action must be create, edit, activate or deactivate")
    item_id = body.get("canonical_id")
    path = _canonical_path()
    with locked(path + ".lock"):
        data = _canonical_read_unlocked()
        current = data["items"].get(item_id) if item_id else None
        if action == "create":
            if item_id:
                raise ValueError("canonical_id is not accepted when creating an item")
            item_id = uuid.uuid4().hex
            current = None
            if expected_version is None:
                expected_version = 0
        elif not current:
            raise ValueError("Canonical BOQ item does not exist")
        current_version = current["version"] if current else 0
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version != current_version:
            raise ValueError(f"Canonical BOQ version changed (expected {expected_version}, current {current_version})")
        if action in ("activate", "deactivate"):
            if action == "activate" and current.get("status") == "active":
                raise ValueError("Canonical BOQ item is already active")
            if action == "deactivate" and current.get("status") == "inactive":
                raise ValueError("Canonical BOQ item is already inactive")
            proposed = {k: current.get(k) for k in ("code", "description", "category", "unit")}
            status = "active" if action == "activate" else "inactive"
        else:
            proposed = {}
            for field in ("code", "description", "category", "unit"):
                value = body.get(field, current.get(field, "") if current else "")
                if not isinstance(value, str):
                    raise ValueError(f"Canonical item {field} must be text")
                proposed[field] = value.strip()
            status = body.get("status", current.get("status", "active") if current else "active")
        if not proposed["code"] or not proposed["description"] or not proposed["category"] or not norm_unit(proposed["unit"]):
            raise ValueError("Canonical item requires code, description, category and unit")
        if status not in ("active", "inactive"):
            raise ValueError("Canonical item status must be active or inactive")
        normalized = norm_code(proposed["code"])
        if any(other_id != item_id and norm_code(it["code"]) == normalized and it["status"] == "active"
               for other_id, it in data["items"].items()):
            raise ValueError("An active canonical item already uses this normalized code")
        now = store.now()
        reviewer = store.user()
        if reviewer == "unknown":
            reviewer = None
        version = current_version + 1
        item = {"canonical_id": item_id, **proposed, "status": status, "version": version,
                "updated_at": now, "updated_by": reviewer}
        data["items"][item_id] = item
        data["version"] += 1
        data["history"].append({"library_version": data["version"], "canonical_id": item_id,
                                "item_version": version, "action": action, "reviewer": reviewer,
                                "timestamp": now, "before": current, "after": item})
        _atomic_write(path, data)
    store.audit("global", "canonical_boq_" + action, canonical_id=item_id, version=version,
                library_version=data["version"], reviewer=reviewer)
    return item


def _line_target(pid, target_key):
    rid = store.latest_run_id(pid)
    if not rid:
        raise ValueError("Project has no calculated run")
    result_path = store.run_path(pid, rid, "results.json")
    result = store.read_json(result_path)
    if not isinstance(result, dict):
        raise ValueError("Latest calculation result is unavailable")
    line = next((line for line in result.get("boq", []) if line.get("match_key") == target_key), None)
    return rid, result, line


def _active_import(pid, source_row):
    boq = store.active_boq(pid)
    if not boq:
        raise ValueError("No active imported BOQ")
    row = next((r for r in boq.get("rows", [])
                if r.get("source_row", r.get("row")) == source_row), None)
    if row is None:
        raise ValueError(f"Source BOQ row {source_row} is not in the active import")
    source_file = boq.get("source_file") or boq.get("name") or ""
    sheet = row.get("source_sheet") or "CSV"
    return boq, row, source_key(source_file, sheet, row.get("source_row", row.get("row")))


def _validate_compatibility(row, target):
    source_unit, target_unit = norm_unit(row.get("unit")), norm_unit(target.get("unit"))
    if not source_unit or not target_unit or source_unit != target_unit:
        raise ValueError(f"Incompatible or missing units: BOQ '{row.get('unit')}' vs target '{target.get('unit')}'")

    def category_kinds(value):
        # A real description routinely names more than one element type at once (e.g. "blinding
        # under footings and raft") - taking only the first TYPE_KEYWORDS hit made the match
        # depend on dict ordering and rejected genuinely compatible pairs like that one against a
        # target categorised just "Blinding concrete". Collect every keyword that appears instead,
        # and treat the two sides as compatible as soon as they share any one of them.
        text = norm_description(value)
        return {kind for kind, words in TYPE_KEYWORDS.items()
                if any(norm_description(word).strip() in text for word in words)}

    source_label = row.get("section") or row.get("description", "")
    target_label = target.get("category", "")
    source_kinds, target_kinds = category_kinds(source_label), category_kinds(target_label)
    if (source_kinds or target_kinds) and not (source_kinds & target_kinds):
        raise ValueError(f"Selected target category '{target_label}' is incompatible with BOQ category '{source_label}'")
    if source_label and target_label:
        a, b = norm_description(source_label), norm_description(target_label)
        if not source_kinds and not target_kinds and a != b:
            raise ValueError(f"Cannot validate category compatibility between '{source_label}' and '{target_label}'")


def _target_for(pid, row, target_type, target_id, validate_compatibility=True, allow_inactive=False):
    if target_type == "calculated":
        run_id, result, target = _line_target(pid, target_id)
        if not target:
            raise ValueError("Selected calculated BOQ target does not exist in the current run")
        if validate_compatibility:
            _validate_compatibility(row, target)
        return {"type": "calculated", "id": target_id, "run_id": run_id, "target": target,
                "library_version": None, "result_digest": _digest(result)}
    if target_type == "canonical":
        if allow_inactive:
            library = canonical_library()
            target = library["items"].get(target_id.split(":", 1)[1]) if target_id.startswith("canonical:") else None
            if not target:
                raise ValueError("Canonical BOQ target does not exist")
        else:
            library, target = canonical_target(target_id)
        if validate_compatibility:
            _validate_compatibility(row, target)
        return {"type": "canonical", "id": f"canonical:{target['canonical_id']}", "run_id": None,
                "target": target, "library_version": library["version"], "result_digest": None}
    raise ValueError("target_type must be calculated or canonical")


def _preview_state(pid, source_row, action, target_type, target_id, expected_version, mappings=None):
    boq, row, key = _active_import(pid, source_row)
    mappings = load(pid) if mappings is None else mappings
    current = mappings.get(key)
    version = current.get("version", 0) if current else 0
    if expected_version is not None and expected_version != version:
        raise ValueError(f"Mapping version changed (expected {expected_version}, current {version})")
    if action not in ("approve", "reject", "unresolved"):
        raise ValueError("action must be approve, reject or unresolved")
    target_info = None
    if action == "approve":
        if not target_id:
            raise ValueError("An explicit target is required for approval")
        if not target_type:
            target_type = "calculated"
        target_info = _target_for(pid, row, target_type, target_id)
    elif action == "reject" and bool(target_type) != bool(target_id):
        raise ValueError("Both target_type and target_id are required to reject a specific candidate")
    elif action == "reject" and target_id:
        if not target_type:
            target_type = "calculated"
        target_info = _target_for(pid, row, target_type, target_id,
                                  validate_compatibility=False, allow_inactive=True)
    elif target_type or target_id:
        raise ValueError(f"Target is only allowed for approval or candidate rejection, not {action}")
    run_id = store.latest_run_id(pid)
    row_fingerprint = _digest(_source_row_identity(row))
    import_identity = {"import_id": boq.get("import_id"), "source_file": boq.get("source_file") or boq.get("name"),
                       "source_fingerprint": boq.get("source_fingerprint")}
    token_payload = {"project": pid, "import": import_identity, "source_key": key, "source_row": source_row,
                     "source_row_fingerprint": row_fingerprint, "action": action, "target_type": target_type,
                     "target_id": target_id, "target_version": target_info["target"].get("version") if target_info and target_type == "canonical" else None,
                     "library_version": target_info.get("library_version") if target_info else None,
                     "mapping_version": version, "run_id": run_id,
                     "calculation_digest": target_info.get("result_digest") if target_info else None,
                     "mapping_store_digest": _digest(mappings), "nonce": secrets.token_hex(16),
                     "issued_at": dt.datetime.now(dt.timezone.utc).timestamp()}
    claims = base64.urlsafe_b64encode(_stable(token_payload).encode()).decode().rstrip("=")
    signature = hmac.new(_preview_secret(), claims.encode(), hashlib.sha256).hexdigest()
    token = f"{claims}.{signature}"
    before = {"decision": current.get("status", "unresolved") if current else "unresolved",
              "target_id": current.get("target_id") if current else None,
              "target_type": current.get("target_type") if current else None,
              "target_key": current.get("target_key") if current else None}
    after = {"decision": "approved" if action == "approve" else action,
             "target_id": target_info["id"] if target_info else None,
             "target_type": target_info["type"] if target_info else None,
             "target_key": target_info["id"] if target_info else None}
    return {"token": token, "token_payload": token_payload, "boq": boq, "row": row, "key": key,
            "current": current, "target_info": target_info, "before": before, "after": after,
            "changed": before != after}


def _valid_preview(state, preview_token):
    try:
        claims, signature = preview_token.split(".", 1)
        expected = hmac.new(_preview_secret(), claims.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Mapping preview was modified or is stale; preview the decision again")
        payload = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
    except (AttributeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Mapping preview was modified or is stale; preview the decision again") from exc
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    if now - payload["issued_at"] > PREVIEW_TTL_SECONDS or payload["issued_at"] > now + 30:
        raise ValueError("Mapping preview expired; create a new preview")
    current_payload = state["token_payload"]
    for key in current_payload.keys() - {"nonce", "issued_at"}:
        if payload.get(key) != current_payload[key]:
            raise ValueError("Mapping preview is stale; preview the decision again")


def preview(pid, source_row, action, target_id=None, expected_version=0, target_type=None):
    from .compare import compare
    state = _preview_state(pid, source_row, action, target_type, target_id, expected_version)
    rid = store.latest_run_id(pid)
    result = store.read_json(store.run_path(pid, rid, "results.json")) if rid else {}
    result = result or {}
    lines = result.get("boq", [])
    elements = {e["uid"]: e for e in result.get("elements", [])}
    rows = [dict(row) for row in state["boq"].get("rows", [])]
    applied, issues = applicable(pid, state["boq"], rows, lines)
    current_cmp = compare(rows, lines, elements, store.settings(pid), applied, issues)
    existing = next((r for r in current_cmp["rows"] if r.get("boq_source_row") == source_row), {})
    target = state["target_info"]["target"] if state["target_info"] else None
    after_qty = target.get("quantity") if action == "approve" and target and state["target_info"]["type"] == "calculated" else None
    source_qty = state["row"].get("quantity")
    after_variance = after_qty - source_qty if after_qty is not None and source_qty is not None else None
    return {"preview_token": state["token"], "mapping_id": state["key"], "source_row": source_row,
            "source_description": state["row"].get("description"), "source_unit": state["row"].get("unit"),
            "suggested_targets": existing.get("candidate_items", []),
            "candidate_scores": existing.get("candidate_scores", []),
            "before": {**state["before"], "drawing_quantity": existing.get("drawing_quantity"),
                       "variance": existing.get("variance"), "variance_pct": existing.get("variance_pct")},
            "after": {**state["after"], "target_description": target.get("description") if target else None,
                      "drawing_quantity": after_qty, "variance": after_variance,
                      "variance_pct": (after_variance / source_qty * 100 if after_variance is not None and source_qty else None)},
            "run_id": rid, "import_id": state["boq"].get("import_id"), "changed": state["changed"],
            "expires_in_seconds": PREVIEW_TTL_SECONDS}


def decide(pid, source_row, action, target_id=None, expected_version=0, preview_token=None, comment="", target_type=None):
    if isinstance(comment, str):
        comment = comment.strip()
    else:
        raise ValueError("Mapping comment must be text")
    if len(comment) > 2000:
        raise ValueError("Mapping comment must be 2000 characters or fewer")
    path = _mapping_path(pid)
    with locked(path + ".lock"):
        mappings = _read_mapping_unlocked(pid)
        state = _preview_state(pid, source_row, action, target_type, target_id, expected_version, mappings)
        _valid_preview(state, preview_token)
        key, row, boq = state["key"], state["row"], state["boq"]
        status = {"approve": "approved", "reject": "rejected", "unresolved": "unresolved"}[action]
        target_info = state["target_info"]
        target = target_info["target"] if target_info else None
        target_key = target_info["id"] if target_info else None
        if status == "approved" and target_info["type"] == "calculated":
            for other_key, other in mappings.items():
                other_type = other.get("target_type") or ("calculated" if other.get("target_key") else None)
                other_id = other.get("target_id") or other.get("target_key")
                if (other_key != key and other.get("status") == "approved"
                        and other_type == "calculated" and other_id == target_key):
                    raise ValueError("This calculated BOQ line is already approved for another source row")
        now = store.now()
        reviewer = store.user()
        if reviewer == "unknown":
            reviewer = None
        version = expected_version + 1
        previous = mappings.get(key)
        target_type_saved = target_info["type"] if target_info else None
        change = {"version": version, "action": action, "status": status, "reviewer": reviewer,
                  "timestamp": now, "comment": comment, "previous_target_type": previous.get("target_type") if previous else None,
                  "previous_target_id": previous.get("target_id") if previous else None,
                  "target_type": target_type_saved, "target_id": target_key,
                  "target_key": target_key,
                  "source_import_id": boq.get("import_id"), "comparison_run_id": store.latest_run_id(pid)}
        history = (previous.get("history", []) if previous else []) + [change]
        updated = {"mapping_id": key, "project_id": pid,
                   "source_identity": {"import_id": boq.get("import_id"),
                    "source_file": boq.get("source_file") or boq.get("name"), "source_sheet": row.get("source_sheet"),
                    "source_row": source_row, "source_fingerprint": boq.get("source_fingerprint"),
                    "source_row_fingerprint": _digest(_source_row_identity(row))},
                   "normalized_item_code": norm_code(row.get("item_no")),
                   "normalized_description": norm_description(row.get("description")),
                   "source_unit": row.get("unit"), "source_category": row.get("section", ""),
                   "target_type": target_type_saved, "target_id": target_key,
                   "target_key": target_key, "target_version": target.get("version") if target_info and target_info["type"] == "canonical" else None,
                   "target_code": target.get("code", target.get("item_no")) if target else None,
                   "target_description": target.get("description") if target else None,
                   "target_unit": target.get("unit") if target else None,
                   "target_category": target.get("category") if target else None,
                   "canonical_library_version": target_info.get("library_version") if target_info else None,
                   "status": status, "reviewer": reviewer, "timestamp": now, "comment": comment,
                   "version": version, "history": history}
        mappings[key] = updated
        _write_mappings_unlocked(pid, mappings)
    store.audit(pid, "boq_mapping_" + action, mapping_id=key, source_row=source_row,
                import_id=boq.get("import_id"), target_type=target_type_saved, target_id=target_key,
                version=updated["version"], reviewer=reviewer, comment=comment,
                previous_target_id=change["previous_target_id"], comparison_run_id=change["comparison_run_id"])
    service.invalidate()
    return updated


def list_for_project(pid):
    mappings = load(pid)
    active = store.active_boq(pid)
    import_id = active.get("import_id") if active else None
    library = canonical_library()
    return {"schema_version": SCHEMA_VERSION, "mappings": list(mappings.values()),
            "active_import_id": import_id,
            "canonical_library_version": library["version"],
            "canonical_items": list(library["items"].values())}


def applicable(pid, boq, rows, lines):
    """Return valid calculated mappings, stale mappings, and canonical annotations."""
    mappings = load(pid)
    by_key = {line.get("match_key"): i for i, line in enumerate(lines)}
    approved_by_target = {}
    for key, record in mappings.items():
        record_type = record.get("target_type") or ("calculated" if record.get("target_key") else None)
        if record.get("status") == "approved" and record_type == "calculated":
            approved_by_target.setdefault(record.get("target_id") or record.get("target_key"), []).append(key)
    applied, issues = {}, {}
    for row in rows:
        source_file = boq.get("source_file") or boq.get("name") or ""
        key = source_key(source_file, row.get("source_sheet") or "CSV",
                         row.get("source_row", row.get("row")))
        row["mapping_key"] = key
        record = mappings.get(key)
        if not record:
            continue
        if record.get("project_id") not in (None, pid):
            issues[key] = ["Mapping belongs to a different project"]
            continue
        identity = record.get("source_identity", {})
        row["mapping_record"] = {k: record.get(k) for k in ("status", "version", "target_key", "target_id",
                                 "target_type", "target_code", "target_description", "reviewer", "timestamp",
                                 "target_category", "target_unit", "comment", "history", "canonical_library_version",
                                 "source_identity")}
        if identity.get("import_id") != boq.get("import_id"):
            issues[key] = ["Mapping was created for a different BOQ import"]
            continue
        if record.get("status") != "approved":
            continue
        reasons = []
        if record.get("normalized_item_code") != norm_code(row.get("item_no")):
            reasons.append("BOQ item code changed since mapping approval")
        if record.get("normalized_description") != norm_description(row.get("description")):
            reasons.append("BOQ description changed since mapping approval")
        if record.get("source_unit") != row.get("unit"):
            reasons.append("BOQ source unit changed since mapping approval")
        if norm_description(record.get("source_category")) != norm_description(row.get("section", "")):
            reasons.append("BOQ section changed since mapping approval")
        if identity.get("source_fingerprint") != boq.get("source_fingerprint"):
            reasons.append("Source BOQ file changed since mapping approval")
        if identity.get("source_row_fingerprint") != _digest(_source_row_identity(row)):
            reasons.append("BOQ source row changed since mapping approval")
        if record.get("target_type") == "canonical":
            try:
                _, canonical = canonical_target(record.get("target_id"))
                _validate_compatibility(row, canonical)
                if canonical.get("version") != record.get("target_version"):
                    reasons.append("Canonical BOQ item changed since mapping approval")
            except ValueError as exc:
                reasons.append(str(exc))
        elif record.get("target_type") == "calculated":
            idx = by_key.get(record.get("target_id"))
            if idx is None:
                reasons.append("Approved target is no longer present in the current calculated run")
            else:
                target = lines[idx]
                try:
                    _validate_compatibility(row, target)
                except ValueError as exc:
                    reasons.append(str(exc))
                if norm_unit(record.get("target_unit")) != norm_unit(target.get("unit")):
                    reasons.append("Approved target unit changed")
            if len(approved_by_target.get(record.get("target_id"), [])) > 1:
                reasons.append("Multiple approved BOQ rows target the same calculated line")
        else:
            reasons.append("Approved mapping has an invalid target type")
        if reasons:
            issues[key] = reasons
        elif record["target_type"] == "calculated":
            applied[key] = {**record, "target_index": idx}
    return applied, issues
