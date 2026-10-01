from fixtures import mock_record

from app.pipeline.units import UnitStage, UnitState, checkpoint_for, plan_units
from app.contracts.models import PageSnapshot, StructuralNode, TableSnapshot


def test_plan_units_is_bounded_complete_and_deterministic():
    record = mock_record()
    record.pages.extend(
        [
            PageSnapshot(page_revision_id="page_2_rev_1", page_number=2, text="page 2"),
            PageSnapshot(page_revision_id="page_3_rev_1", page_number=3, text="page 3"),
            PageSnapshot(page_revision_id="page_4_rev_1", page_number=4, text="page 4"),
        ]
    )
    record.nodes.extend(
        [
            StructuralNode(node_id="field_2", type="FIELD", raw_label="p2", order=10, page_range=[2]),
            StructuralNode(node_id="field_3", type="FIELD", raw_label="p3", order=11, page_range=[3]),
        ]
    )

    units = plan_units(record, pages_per_unit=2)
    assert [unit.page_numbers for unit in units] == [(1, 2), (3, 4)]
    assert {page for unit in units for page in unit.page_numbers} == {1, 2, 3, 4}
    assert units[0].node_ids[-1] == "field_2"
    assert units == plan_units(record, pages_per_unit=2)
    assert all(unit.stage == UnitStage.EXTRACT for unit in units)


def test_plan_units_keeps_tables_attached_by_node_when_revision_missing():
    record = mock_record()
    record.tables[0].page_revision_id = None
    units = plan_units(record, pages_per_unit=1)
    assert units[0].table_ids == ("table_1",)


def test_checkpoint_is_resume_friendly():
    unit = plan_units(mock_record())[0]
    checkpoint = checkpoint_for(unit, generation=3)
    assert checkpoint.unit_id == unit.unit_id
    assert checkpoint.generation == 3
    assert checkpoint.state == UnitState.PENDING
    assert checkpoint.attempt == 0

