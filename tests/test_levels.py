"""Тесты загрузки уровней из TOML. Kivy не нужен."""
from pathlib import Path

import pytest

from rails.core import DOWN, LEFT, RIGHT, UP
from rails.levels import LevelError, load_pack, parse_level, parse_pack

MAIN_TOML = Path(__file__).resolve().parent.parent / "suns" / "build-in" / "Main.toml"


@pytest.fixture(scope="module")
def pack():
    return load_pack(MAIN_TOML)


def test_real_levels_file_loads_without_errors(pack):
    assert pack.errors == []
    assert [level.id for level in pack.levels] == list(range(1, 9))


def test_level_1_defaults(pack):
    level = pack.levels[0]
    assert (level.cols, level.rows) == (3, 3)
    train = level.trains[0]
    assert (train.start, train.start_side, train.ends) == ((0, 1), LEFT, (((2, 1), RIGHT),))
    assert level.pieces == (("Straight", 3),)
    assert level.hint.splitlines()[0].startswith("Перетягніть")


def test_blocks_points_and_start_side(pack):
    level5, level6 = pack.levels[4], pack.levels[5]
    assert level5.blocks == {(1, 1), (1, 3), (3, 1), (3, 3)}
    assert level5.trains[0].points == ((1, 2), (2, 1), (2, 3), (3, 2))
    assert level6.trains[0].start == (2, 2) and level6.trains[0].start_side == UP
    assert ("Rowation", 1) in level6.pieces


def test_level_5_end_side_is_a_random_choice(pack):
    assert pack.levels[4].trains[0].ends == (((4, 0), DOWN), ((4, 0), UP))


def test_pos_options_and_side_options_are_paired():
    level = parse_level({"id": 1, "cols": 5, "rows": 5, "trains": [
        {"end": {"pos_options": [[4, 0], [0, 4]], "side_options": ["Down", "Left"]}}]}, 0)
    assert level.trains[0].ends == (((4, 0), DOWN), ((0, 4), LEFT))


@pytest.mark.parametrize("raw, text", [
    ({"id": 1, "cols": 2, "rows": 2, "trains": [{"end": {"pos": [5, 5]}}]}, "за пределами"),
    ({"id": 1, "pazls": [{"type": "Teleport", "count": 1}]}, "Teleport"),
    ({"id": 1, "stations": {"(0, 0)": "Lava"}}, "Lava"),
    ({"id": 1, "stations": {"oops": "Block"}}, "координаты"),
    ({"id": 1, "trains": [{"start": {"side": "Sideways"}}]}, "сторона"),
    ({"id": 1, "stations": {"(0, 1)": "Block"}}, "дважды"),                  # блок на старте
    ({"id": 1, "trains": [{"end": {"pos_options": [[1, 1]], "side_options": ["Up", "Down"]}}]}, "одной длины"),
    ({"id": 1, "trains": [{"end": {"pos": [2, 1], "pos_options": [[1, 1]]}}]}, "нельзя"),
    ({"id": 1, "cols": 0}, "вне диапазона"),
    ({"id": "x"}, "целым"),
])
def test_invalid_levels_have_readable_errors(raw, text):
    with pytest.raises(LevelError, match=text):
        parse_level(raw, 0)


def test_one_bad_level_does_not_break_the_pack():
    pack = parse_pack({"levels": [{"id": 1}, {"id": 2, "cols": 99}, {"id": 1}, {"id": 3}]})
    assert [level.id for level in pack.levels] == [1, 3]
    assert len(pack.errors) == 2 and "id" in pack.errors[1]


def test_pack_without_levels_reports_it():
    pack = parse_pack({})
    assert pack.levels == [] and pack.errors


def test_file_errors_are_level_errors(tmp_path):
    with pytest.raises(LevelError, match="не найден"):
        load_pack(tmp_path / "nope.toml")
    broken = tmp_path / "broken.toml"
    broken.write_text("[[levels\n", encoding="utf-8")
    with pytest.raises(LevelError, match="TOML"):
        load_pack(broken)
