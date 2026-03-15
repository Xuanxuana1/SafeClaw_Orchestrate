from ontoplan_mvp.executor.artifact_store import ArtifactStore


def test_artifact_store_formats_only_present_artifacts():
    store = ArtifactStore()
    store.put("extracted_data", "rows=10")

    block = store.to_context_block(["missing_artifact", "extracted_data"])

    assert "[extracted_data]\nrows=10" in block
    assert "missing_artifact" not in block


def test_artifact_store_returns_all_keys():
    store = ArtifactStore()
    store.put("a", "1")
    store.put("b", "2")

    assert set(store.all_keys()) == {"a", "b"}
