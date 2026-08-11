from uuid import UUID

from backend.app.search.execution_domain import (
    IdentificationContribution,
    IdentificationSourceClassification,
    group_identification_records,
)


def _ids(start: int, count: int) -> frozenset[UUID]:
    return frozenset(UUID(int=value) for value in range(start, start + count))


def test_prisma_identification_groups_preserve_prededup_execution_counts() -> None:
    pubmed = _ids(1, 100)
    embase = _ids(101, 200)
    update = _ids(301, 25)
    groups = group_identification_records(
        [
            IdentificationContribution(
                UUID(int=1001),
                IdentificationSourceClassification.BIBLIOGRAPHIC_DATABASE,
                pubmed,
            ),
            IdentificationContribution(
                UUID(int=1002),
                IdentificationSourceClassification.BIBLIOGRAPHIC_DATABASE,
                embase,
            ),
            IdentificationContribution(
                UUID(int=1003),
                IdentificationSourceClassification.BIBLIOGRAPHIC_DATABASE,
                update,
            ),
        ]
    )
    assert len(groups.databases_and_registers) == 325
    assert not groups.other_methods
    assert not groups.conflicting_records


def test_same_import_linked_repeatedly_counts_once_and_cross_group_is_conflict() -> None:
    record_id = UUID(int=1)
    groups = group_identification_records(
        [
            IdentificationContribution(
                UUID(int=2),
                IdentificationSourceClassification.TRIAL_REGISTER,
                frozenset({record_id}),
            ),
            IdentificationContribution(
                UUID(int=3),
                IdentificationSourceClassification.OTHER_REGISTER,
                frozenset({record_id}),
            ),
        ]
    )
    assert groups.databases_and_registers == {record_id}

    conflict = group_identification_records(
        [
            IdentificationContribution(
                UUID(int=2),
                IdentificationSourceClassification.TRIAL_REGISTER,
                frozenset({record_id}),
            ),
            IdentificationContribution(
                UUID(int=4),
                IdentificationSourceClassification.REFERENCE_LIST,
                frozenset({record_id}),
            ),
        ]
    )
    assert conflict.conflicting_records == {record_id}
    assert not conflict.databases_and_registers
    assert not conflict.other_methods


def test_every_source_classification_has_an_explicit_prisma_group() -> None:
    database_classes = {
        "BIBLIOGRAPHIC_DATABASE",
        "TRIAL_REGISTER",
        "OTHER_REGISTER",
    }
    grouped = {item.value: item.prisma_group for item in IdentificationSourceClassification}
    assert {key for key, value in grouped.items() if value == "DATABASES_AND_REGISTERS"} == (
        database_classes
    )
    assert all(value in {"DATABASES_AND_REGISTERS", "OTHER_METHODS"} for value in grouped.values())
