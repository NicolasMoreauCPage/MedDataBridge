from app.routers.endpoints import uses_background_poller


def test_file_and_sftp_statuses_are_driven_by_the_background_poller():
    assert uses_background_poller("FILE")
    assert uses_background_poller("sftp")
    assert not uses_background_poller("FTP")
    assert not uses_background_poller("MLLP")
