from app.services.message_diff import semantic_diff


def test_hl7_diff_points_to_the_changed_field():
    changes = semantic_diff("MSH|^~\\&|A|B\rPID|||OLD", "MSH|^~\\&|A|B\rPID|||NEW", "hl7")
    assert {item["path"] for item in changes} == {"PID[1]-3"}
    assert changes[0]["before"] == "OLD"
    assert changes[0]["after"] == "NEW"


def test_json_and_xml_diffs_are_structured():
    assert semantic_diff('{"id":"old"}', '{"id":"new"}', "fhir")[0]["path"] == "id"
    assert semantic_diff("<root><id>old</id></root>", "<root><id>new</id></root>", "xml")[0]["path"] == "root/id[1]"
