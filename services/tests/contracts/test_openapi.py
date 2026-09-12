"""What a change to an OpenAPI document does to the caller."""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence

from services.contracts.openapi import Change, breaking, changes, surface_of


REQUEST = {"sample_id": "string", "temperature": "number"}
RESPONSE = {"label": "string"}


def schema(properties: Mapping[str, str], required: Sequence[str]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {name: {"type": kind} for name, kind in properties.items()},
        "required": list(required),
    }


def document(
    *,
    request: Mapping[str, str] | None = None,
    request_required: Sequence[str] | None = None,
    response: Mapping[str, str] | None = None,
    response_required: Sequence[str] | None = None,
    statuses: Sequence[str] = ("200",),
    path: str = "/predict",
) -> dict[str, object]:
    """One document with a single operation, varied one promise at a time."""
    request = REQUEST if request is None else request
    response = RESPONSE if response is None else response
    body = schema(request, list(request) if request_required is None else request_required)
    answered = schema(response, list(response) if response_required is None else response_required)
    return {
        "openapi": "3.1.0",
        "paths": {
            path: {
                "post": {
                    "requestBody": {"content": {"application/json": {"schema": body}}},
                    "responses": {
                        status: {"content": {"application/json": {"schema": answered}}}
                        for status in statuses
                    },
                }
            }
        },
    }


def messages(found: Sequence[Change]) -> tuple[str, ...]:
    return tuple(change.describe() for change in found)


class SurfaceTest(unittest.TestCase):
    def test_an_operation_is_named_by_its_method_and_path(self) -> None:
        surface = surface_of(document())

        self.assertEqual(list(surface), ["POST /predict"])

    def test_a_nested_value_is_named_by_the_path_a_caller_writes(self) -> None:
        nested = {
            "openapi": "3.1.0",
            "paths": {
                "/predict": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["measurements"],
                                        "properties": {
                                            "measurements": {
                                                "type": "array",
                                                "items": schema(REQUEST, list(REQUEST)),
                                            }
                                        },
                                    }
                                }
                            }
                        },
                        "responses": {},
                    }
                }
            },
        }

        fields = surface_of(nested)["POST /predict"].request

        self.assertEqual(
            [field.name for field in fields],
            ["measurements", "measurements[].sample_id", "measurements[].temperature"],
        )

    def test_a_component_is_followed_to_what_it_describes(self) -> None:
        referring = {
            "openapi": "3.1.0",
            "paths": {
                "/ready": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Ready"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {"schemas": {"Ready": schema(RESPONSE, list(RESPONSE))}},
        }

        fields = surface_of(referring)["GET /ready"].answers[0].fields

        self.assertEqual([field.name for field in fields], ["label"])

    def test_a_schema_that_refers_to_itself_is_read_once(self) -> None:
        """A tree-shaped payload must not be followed forever."""
        recursive = {
            "openapi": "3.1.0",
            "paths": {
                "/tree": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Node"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "Node": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "child": {"$ref": "#/components/schemas/Node"},
                        },
                    }
                }
            },
        }

        fields = surface_of(recursive)["GET /tree"].answers[0].fields

        self.assertEqual([field.name for field in fields], ["name", "child"])

    def test_an_optional_value_keeps_the_null_in_its_type(self) -> None:
        """`number | null` and `number` are not the same promise to a reader."""
        optional = document(response={"confidence": "unused"})
        properties = optional["paths"]["/predict"]["post"]["responses"]["200"]  # type: ignore[index]
        properties["content"]["application/json"]["schema"]["properties"]["confidence"] = {
            "anyOf": [{"type": "number"}, {"type": "null"}]
        }

        field = surface_of(optional)["POST /predict"].answers[0].fields[0]

        self.assertEqual(field.type, "null|number")


class UnchangedTest(unittest.TestCase):
    def test_the_same_document_has_moved_in_no_way(self) -> None:
        self.assertEqual(changes(document(), document()), ())

    def test_a_description_is_not_part_of_the_promise(self) -> None:
        described = document()
        described["paths"]["/predict"]["post"]["summary"] = "Judge products"  # type: ignore[index]

        self.assertEqual(changes(document(), described), ())


class OperationTest(unittest.TestCase):
    def test_removing_an_operation_breaks_its_callers(self) -> None:
        found = changes(document(), document(path="/judge"))

        self.assertEqual(
            messages(breaking(found)),
            ("POST /predict: この操作が無くなった",),
        )

    def test_adding_an_operation_breaks_nobody(self) -> None:
        found = changes(document(), document(path="/judge"))

        self.assertEqual(
            messages(tuple(change for change in found if not change.breaking)),
            ("POST /judge: この操作が増えた",),
        )


class RequestTest(unittest.TestCase):
    def test_a_new_required_value_breaks_every_existing_caller(self) -> None:
        found = breaking(changes(document(), document(request={**REQUEST, "lot_id": "string"})))

        self.assertEqual(messages(found), ("POST /predict: 要求に必須の lot_id が増えた",))

    def test_a_new_optional_value_breaks_nobody(self) -> None:
        found = changes(
            document(),
            document(request={**REQUEST, "lot_id": "string"}, request_required=list(REQUEST)),
        )

        self.assertEqual(breaking(found), ())

    def test_no_longer_accepting_a_value_breaks_the_caller_that_sends_it(self) -> None:
        found = breaking(changes(document(), document(request={"sample_id": "string"})))

        self.assertEqual(
            messages(found),
            ("POST /predict: 要求の temperature を受け取らなくなった",),
        )

    def test_requiring_a_value_that_was_optional_breaks_the_caller_that_omits_it(self) -> None:
        found = breaking(
            changes(
                document(request_required=["sample_id"]),
                document(request_required=list(REQUEST)),
            )
        )

        self.assertEqual(messages(found), ("POST /predict: 要求の temperature が必須になった",))

    def test_no_longer_requiring_a_value_breaks_nobody(self) -> None:
        found = changes(
            document(request_required=list(REQUEST)), document(request_required=["sample_id"])
        )

        self.assertEqual(breaking(found), ())

    def test_changing_the_type_of_a_value_breaks_the_caller_that_sends_it(self) -> None:
        found = breaking(
            changes(document(), document(request={**REQUEST, "temperature": "string"}))
        )

        self.assertEqual(
            messages(found),
            ("POST /predict: 要求の temperature の型が number から string になった",),
        )


class ResponseTest(unittest.TestCase):
    def test_removing_a_status_breaks_the_caller_that_handles_it(self) -> None:
        found = breaking(changes(document(statuses=("200", "503")), document()))

        self.assertEqual(messages(found), ("POST /predict: 応答 503 が無くなった",))

    def test_adding_a_status_breaks_nobody(self) -> None:
        found = changes(document(), document(statuses=("200", "503")))

        self.assertEqual(breaking(found), ())

    def test_removing_an_answered_value_breaks_its_reader(self) -> None:
        found = breaking(
            changes(document(response={**RESPONSE, "confidence": "number"}), document())
        )

        self.assertEqual(messages(found), ("POST /predict: 応答 200の confidence が無くなった",))

    def test_no_longer_guaranteeing_a_value_breaks_its_reader(self) -> None:
        """The reverse of the request rule: what a reader gets may not weaken."""
        found = breaking(changes(document(), document(response_required=[])))

        self.assertEqual(messages(found), ("POST /predict: 応答 200の label が任意になった",))

    def test_guaranteeing_a_value_that_was_optional_breaks_nobody(self) -> None:
        found = changes(document(response_required=[]), document())

        self.assertEqual(breaking(found), ())

    def test_changing_the_type_of_an_answered_value_breaks_its_reader(self) -> None:
        found = breaking(changes(document(), document(response={"label": "integer"})))

        self.assertEqual(
            messages(found),
            ("POST /predict: 応答 200の label の型が string から integer になった",),
        )


if __name__ == "__main__":
    unittest.main()
