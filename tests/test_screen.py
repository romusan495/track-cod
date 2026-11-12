from trackcod.capture.screen import is_game_title


def test_title_with_zero_width_chars():
    title = "​".join("Call of Duty®") + "​" * 30
    assert is_game_title(title)


def test_other_titles():
    assert not is_game_title("Bloc-notes")
    assert not is_game_title("")
