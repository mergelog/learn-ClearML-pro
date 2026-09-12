"""Read an OpenAPI document as the promise it makes to a caller.

A snapshot of the document tells us *that* something changed. It cannot tell
us whether the change breaks the callers, and that is the only question worth
waking somebody for. Adding an endpoint and deleting one look the same in a
diff.

So the document is first reduced to the part a caller depends on — which
operations exist, what each one accepts, and what each one answers — and two
of those are compared. Everything else in the document (descriptions,
summaries, the order of keys, the names of the generated components) can move
freely, because no caller breaks when it does.

**The comparison is not the detection.** Whoever holds the snapshot compares
the whole document for equality and fails on any difference at all; this
module only decides how loudly to report the difference it is given. That
division matters: a promise this module does not know how to read yet — a
tightened bound, a narrowed enum — still fails the build as an unexplained
change. It is never silently green.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


JSON_MEDIA_TYPE = "application/json"

BODY = "body"
RESPONSE = "response"

ANY_TYPE = "any"

# ref を辿る深さの上限。再帰的なスキーマ（木構造など）で止まらなくなることを
# 防ぐためだけのもので、この深さまで読めれば契約としては十分である。
MAXIMUM_DEPTH = 12


@dataclass(frozen=True)
class Field:
    """One value a caller sends or reads, named by where it sits."""

    location: str
    name: str
    type: str
    required: bool

    @property
    def key(self) -> tuple[str, str]:
        return (self.location, self.name)


@dataclass(frozen=True)
class Answer:
    """One status an operation can answer, and the body that comes with it."""

    status: str
    fields: tuple[Field, ...]


@dataclass(frozen=True)
class Operation:
    """One thing a caller can do, reduced to what it can depend on."""

    method: str
    path: str
    request: tuple[Field, ...]
    answers: tuple[Answer, ...]

    @property
    def name(self) -> str:
        return f"{self.method} {self.path}"


@dataclass(frozen=True)
class Change:
    """One difference between two documents, and whether it breaks a caller."""

    breaking: bool
    where: str
    message: str

    def describe(self) -> str:
        return f"{self.where}: {self.message}"


def surface_of(document: Mapping[str, Any]) -> dict[str, Operation]:
    """Reduce a document to the operations it publishes, keyed by name."""
    operations: dict[str, Operation] = {}
    paths = _mapping(document.get("paths"))
    for path, entry in paths.items():
        for method, operation in _mapping(entry).items():
            if not isinstance(operation, Mapping):
                continue
            reduced = _operation(method.upper(), path, operation, document)
            operations[reduced.name] = reduced
    return operations


def changes(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> tuple[Change, ...]:
    """List how the promise moved between two documents."""
    before, after = surface_of(previous), surface_of(current)
    found: list[Change] = []

    for name in sorted(set(before) | set(after)):
        if name not in after:
            found.append(Change(True, name, "この操作が無くなった"))
        elif name not in before:
            found.append(Change(False, name, "この操作が増えた"))
        else:
            found.extend(_operation_changes(before[name], after[name]))

    return tuple(found)


def breaking(found: Sequence[Change]) -> tuple[Change, ...]:
    return tuple(change for change in found if change.breaking)


def _operation_changes(before: Operation, after: Operation) -> tuple[Change, ...]:
    found: list[Change] = list(_request_changes(before, after))
    found.extend(_answer_changes(before, after))
    return tuple(found)


def _request_changes(before: Operation, after: Operation) -> tuple[Change, ...]:
    """Compare what the operation accepts.

    Every rule here is read from the sender's side. A field the sender has to
    start providing, and a field it may no longer provide, both stop a caller
    that was working yesterday.
    """
    sent, accepts = _by_key(before.request), _by_key(after.request)
    found: list[Change] = []

    for key in sorted(set(sent) | set(accepts)):
        was, now = sent.get(key), accepts.get(key)
        where = before.name
        if now is None and was is not None:
            found.append(Change(True, where, f"要求の {_named(was)} を受け取らなくなった"))
        elif was is None and now is not None:
            found.append(
                Change(
                    now.required,
                    where,
                    f"要求に{'必須の' if now.required else '任意の'} {_named(now)} が増えた",
                )
            )
        elif was is not None and now is not None:
            found.extend(_field_changes(where, "要求", was, now, required_is_breaking=True))

    return tuple(found)


def _answer_changes(before: Operation, after: Operation) -> tuple[Change, ...]:
    """Compare what the operation answers.

    The reader's side reverses two of the rules. A field that becomes
    guaranteed is safe to read; a field that stops being guaranteed is not.
    """
    answered = {answer.status: answer for answer in before.answers}
    answers = {answer.status: answer for answer in after.answers}
    found: list[Change] = []

    for status in sorted(set(answered) | set(answers)):
        where = before.name
        if status not in answers:
            found.append(Change(True, where, f"応答 {status} が無くなった"))
            continue
        if status not in answered:
            found.append(Change(False, where, f"応答 {status} が増えた"))
            continue
        found.extend(
            _body_changes(where, f"応答 {status}", answered[status], answers[status])
        )

    return tuple(found)


def _body_changes(where: str, subject: str, before: Answer, after: Answer) -> tuple[Change, ...]:
    read, returns = _by_key(before.fields), _by_key(after.fields)
    found: list[Change] = []

    for key in sorted(set(read) | set(returns)):
        was, now = read.get(key), returns.get(key)
        if now is None and was is not None:
            found.append(Change(True, where, f"{subject}の {_named(was)} が無くなった"))
        elif was is None and now is not None:
            found.append(Change(False, where, f"{subject}に {_named(now)} が増えた"))
        elif was is not None and now is not None:
            found.extend(_field_changes(where, subject, was, now, required_is_breaking=False))

    return tuple(found)


def _field_changes(
    where: str,
    subject: str,
    was: Field,
    now: Field,
    *,
    required_is_breaking: bool,
) -> tuple[Change, ...]:
    found: list[Change] = []

    if was.type != now.type:
        found.append(
            Change(
                True,
                where,
                f"{subject}の {_named(was)} の型が {was.type} から {now.type} になった",
            )
        )

    if was.required != now.required:
        # 送る側と読む側で向きが逆になる。送る値が必須になれば送り手が壊れ、
        # 読む値が任意になれば読み手が壊れる。どちらを見ているかは呼び元が決める。
        became_required = now.required
        found.append(
            Change(
                required_is_breaking if became_required else not required_is_breaking,
                where,
                f"{subject}の {_named(was)} が{'必須' if became_required else '任意'}になった",
            )
        )

    return tuple(found)


def _named(field: Field) -> str:
    return field.name if field.location in (BODY, RESPONSE) else f"{field.location} の {field.name}"


def _by_key(fields: Sequence[Field]) -> dict[tuple[str, str], Field]:
    return {field.key: field for field in fields}


def _operation(
    method: str,
    path: str,
    operation: Mapping[str, Any],
    document: Mapping[str, Any],
) -> Operation:
    request = list(_parameters(operation, document))
    request.extend(_body(operation.get("requestBody"), document))
    return Operation(
        method=method,
        path=path,
        request=tuple(request),
        answers=_answers(operation.get("responses"), document),
    )


def _parameters(operation: Mapping[str, Any], document: Mapping[str, Any]) -> tuple[Field, ...]:
    given = operation.get("parameters")
    if not isinstance(given, Sequence):
        return ()
    return tuple(
        Field(
            location=str(parameter.get("in", "query")),
            name=str(parameter.get("name", "")),
            type=_type_of(parameter.get("schema"), document),
            required=bool(parameter.get("required", False)),
        )
        for parameter in given
        if isinstance(parameter, Mapping)
    )


def _body(request_body: Any, document: Mapping[str, Any]) -> tuple[Field, ...]:
    schema = _json_schema(request_body)
    if schema is None:
        return ()
    return _fields(schema, document, BODY, prefix="", seen=())


def _answers(responses: Any, document: Mapping[str, Any]) -> tuple[Answer, ...]:
    return tuple(
        Answer(
            status=str(status),
            fields=_response_fields(response, document),
        )
        for status, response in sorted(_mapping(responses).items())
    )


def _response_fields(response: Any, document: Mapping[str, Any]) -> tuple[Field, ...]:
    schema = _json_schema(response)
    if schema is None:
        return ()
    return _fields(schema, document, RESPONSE, prefix="", seen=())


def _json_schema(carrier: Any) -> Mapping[str, Any] | None:
    """Take the JSON schema out of a request body or a response.

    Only JSON is read. A service that starts answering in another media type
    has changed its contract in a way this comparison would rather not guess
    about, and the snapshot still fails on it.
    """
    content = _mapping(_mapping(carrier).get("content"))
    schema = _mapping(content.get(JSON_MEDIA_TYPE)).get("schema")
    return schema if isinstance(schema, Mapping) else None


def _fields(
    schema: Mapping[str, Any],
    document: Mapping[str, Any],
    location: str,
    *,
    prefix: str,
    seen: tuple[str, ...],
) -> tuple[Field, ...]:
    """List every value inside a schema, named by the path a caller writes.

    Nested objects are flattened (``model.model_version``) and arrays keep the
    brackets (``measurements[].sample_id``), so a rename deep inside a payload
    is as visible as a rename at the top.
    """
    resolved = _resolve(schema, document, seen)
    if resolved is None:
        return ()
    body, seen = resolved

    if _type_of(body, document) == "array":
        items = body.get("items")
        if not isinstance(items, Mapping):
            return ()
        return _fields(items, document, location, prefix=f"{prefix}[]", seen=seen)

    properties = _mapping(body.get("properties"))
    required = {str(name) for name in _sequence(body.get("required"))}
    found: list[Field] = []
    for name, child in properties.items():
        if not isinstance(child, Mapping):
            continue
        path = f"{prefix}.{name}" if prefix else str(name)
        found.append(
            Field(
                location=location,
                name=path,
                type=_type_of(child, document),
                required=name in required,
            )
        )
        found.extend(_fields(child, document, location, prefix=path, seen=seen))
    return tuple(found)


def _resolve(
    schema: Mapping[str, Any],
    document: Mapping[str, Any],
    seen: tuple[str, ...],
) -> tuple[Mapping[str, Any], tuple[str, ...]] | None:
    """Follow ``$ref`` until a schema with content is reached.

    A reference already followed on this path is not followed again: a schema
    that refers to itself would otherwise be read forever.
    """
    reference = schema.get("$ref")
    if not isinstance(reference, str):
        return (schema, seen)
    if reference in seen or len(seen) >= MAXIMUM_DEPTH:
        return None

    target: Any = document
    for step in reference.removeprefix("#/").split("/"):
        target = _mapping(target).get(step)
    if not isinstance(target, Mapping):
        return None
    return _resolve(target, document, (*seen, reference))


def _type_of(schema: Any, document: Mapping[str, Any]) -> str:
    """Name the type a caller has to handle.

    An optional value is written by FastAPI as ``anyOf`` with ``null`` in it,
    so the union is kept rather than collapsed: dropping ``null`` would hide
    exactly the change that makes a reader crash.
    """
    if not isinstance(schema, Mapping):
        return ANY_TYPE

    resolved = _resolve(schema, document, ())
    if resolved is None:
        return ANY_TYPE
    body, _ = resolved

    named = body.get("type")
    if isinstance(named, str):
        return named

    alternatives = _sequence(body.get("anyOf")) or _sequence(body.get("oneOf"))
    if alternatives:
        return "|".join(sorted({_type_of(alternative, document) for alternative in alternatives}))

    return ANY_TYPE


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        return ()
    return tuple(value)


__all__ = [
    "Answer",
    "Change",
    "Field",
    "Operation",
    "breaking",
    "changes",
    "surface_of",
]
