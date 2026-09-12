from app.services.adt_parser import parse_adt_message


def test_pid_18_is_parsed_as_dossier_identifier_before_pv1_19_venue():
    pid = ["PID"] + [""] * 18
    pid[3], pid[18] = "IPP^^^TEST^PI", "NDA-42^^^DOSSIER^AN"
    pv1 = ["PV1"] + [""] * 19
    pv1[2], pv1[3], pv1[19] = "I", "UF", "VEN-7^^^VENUE^VN"
    message = "\r".join([
        "MSH|^~\\&|S|F|R|F|20260912090000||ADT^A01|1|P|2.5",
        "|".join(pid),
        "|".join(pv1),
    ])

    parsed = parse_adt_message(message)

    assert parsed["pid"]["account_number"] == "NDA-42"
    assert parsed["pv1"]["visit_number"] == "VEN-7"
