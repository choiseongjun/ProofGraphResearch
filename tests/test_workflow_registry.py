from app.workflow_registry import RESEARCH_WORKFLOW, list_workflows


def test_research_workflow_has_contractual_steps():
    workflow = RESEARCH_WORKFLOW.as_dict()
    assert workflow["id"] == "evidence-first-research"
    assert [step["id"] for step in workflow["steps"]] == ["plan", "collect", "retrieve", "compress", "map", "write", "review", "learn"]
    assert workflow["quality_gate"]


def test_workflow_catalog_exposes_research_workflow():
    assert list_workflows()[0]["id"] == RESEARCH_WORKFLOW.id
