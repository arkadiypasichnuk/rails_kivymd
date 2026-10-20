"""Тесты логики рельс и движения поезда."""
import sys

import pytest

from rails.core import (DOWN, KINDS, LEFT, RIGHT, UP, Outcome, PieceModel, Run, Side, StepKind, advance,
                        resolve_kind, rotate_connections)


def test_pure_modules_do_not_import_kivy():
    assert "kivy" not in sys.modules


def test_side_rotation_is_counterclockwise():
    assert [s.rotated() for s in (UP, LEFT, DOWN, RIGHT)] == [LEFT, DOWN, RIGHT, UP]
    assert UP.opposite == DOWN and LEFT.opposite == RIGHT
    assert UP.rotated(4) == UP and UP.rotated(-1) == RIGHT


def test_side_parse():
    assert Side.parse("up") == UP and Side.parse(" Down ") == DOWN and Side.parse("R") == RIGHT
    with pytest.raises(ValueError):
        Side.parse("sideways")


def test_heading_angles_match_old_train_py():
    # Train.GetPosSide: заезд снизу -> 0°, справа -> 90°, сверху -> 180°, слева -> 270°
    assert (UP.heading_angle, LEFT.heading_angle, DOWN.heading_angle, RIGHT.heading_angle) == (0, 90, 180, 270)


def test_curve_rotation_matches_old_boxes_py():
    curve = KINDS["Rotation"].states[0].connections
    assert dict(curve) == {LEFT: DOWN, DOWN: LEFT}
    assert rotate_connections(curve, 1) == {DOWN: RIGHT, RIGHT: DOWN}
    assert rotate_connections(curve, 2) == {RIGHT: UP, UP: RIGHT}
    assert rotate_connections(curve, 3) == {UP: LEFT, LEFT: UP}
    assert rotate_connections(curve, 4) == dict(curve)


def test_piece_exits_and_break():
    straight = PieceModel(resolve_kind(""))
    assert straight.exits(LEFT) == RIGHT and straight.exits(UP) is Outcome.BREAK
    straight.rotate()
    assert straight.exits(UP) == DOWN and straight.exits(LEFT) is Outcome.BREAK


def test_rowation_cycles_through_three_states():
    piece = PieceModel(resolve_kind("Rowation"))
    assert piece.connections == {LEFT: RIGHT, RIGHT: LEFT}
    assert piece.next_open_sides() == {UP}            # синяя полоска сверху, как в старой игре
    piece.cycle()
    assert piece.connections == {RIGHT: UP, UP: RIGHT} and piece.image == "rotation_real.png"
    assert piece.next_open_sides() == {LEFT}
    piece.cycle()
    assert piece.connections == {LEFT: UP, UP: LEFT}
    piece.cycle()
    assert piece.connections == {LEFT: RIGHT, RIGHT: LEFT}


def test_rowation_keeps_player_rotation_and_resets_state():
    piece = PieceModel(resolve_kind("Rowation"))
    piece.rotate()
    piece.cycle()
    assert piece.total_turns == 3
    piece.reset_state()
    assert piece.state == 0 and piece.turns == 1


def test_resolve_kind_aliases_and_errors():
    assert resolve_kind("").name == "Straight" == resolve_kind("MovableBox").name
    assert resolve_kind("rotation").name == "Rotation"
    with pytest.raises(KeyError):
        resolve_kind("Teleport")


# ───────────── движение поезда ─────────────
def make_world(pieces, end, end_side, size=(5, 3)):
    """pieces: {(col,row): PieceModel}; end — клетка финиша."""
    def exit_for(pos, enter):
        if pos not in pieces:
            return Outcome.BREAK
        result = pieces[pos].exits(enter)
        return Outcome.WIN if pos == end and result == end_side else result

    return exit_for, lambda pos: 0 <= pos[0] < size[0] and 0 <= pos[1] < size[1]


def straights(cols, row):
    return {(c, row): PieceModel(resolve_kind("")) for c in cols}


def drive(run, exit_for, in_bounds, limit=50):
    steps = []
    for _ in range(limit):
        step = advance(run, exit_for, in_bounds)
        steps.append(step)
        if step.kind is not StepKind.MOVE:
            return steps
    raise AssertionError("поезд ездит по кругу")


def test_train_wins_on_straight_line():
    exit_for, in_bounds = make_world(straights(range(5), 1), (4, 1), RIGHT)
    steps = drive(Run((0, 1), LEFT), exit_for, in_bounds)
    assert [s.kind for s in steps] == [StepKind.MOVE] * 4 + [StepKind.WIN]
    assert steps[-1].won


def test_win_requires_all_points():
    exit_for, in_bounds = make_world(straights(range(5), 1), (4, 1), RIGHT)
    steps = drive(Run((0, 1), LEFT, {(2, 2)}), exit_for, in_bounds)
    assert steps[-1].kind is StepKind.WIN and not steps[-1].won
    steps = drive(Run((0, 1), LEFT, {(2, 1)}), exit_for, in_bounds)   # станция на пути
    assert steps[-1].won


def test_train_crashes_without_rails():
    exit_for, in_bounds = make_world(straights([0, 1], 1), (4, 1), RIGHT)
    steps = drive(Run((0, 1), LEFT), exit_for, in_bounds)
    assert steps[-1].kind is StepKind.CRASH and steps[-1].pos == (2, 1)


def test_train_leaving_the_board_is_reported():
    # раньше в этом случае поезд телепортировался в (0, 0), а игра зависала
    pieces = {(0, 1): PieceModel(resolve_kind("")), (1, 1): PieceModel(resolve_kind(""))}
    pieces[(1, 1)].rotate()  # вертикальная прямая: LEFT не соединён -> крушение
    exit_for, in_bounds = make_world(pieces, (4, 1), RIGHT)
    assert drive(Run((0, 1), LEFT), exit_for, in_bounds)[-1].kind is StepKind.CRASH

    edge = {(0, 0): PieceModel(resolve_kind(""))}
    edge[(0, 0)].rotate()                              # вертикальная: UP <-> DOWN
    exit_for, in_bounds = make_world(edge, (4, 1), RIGHT)
    last = drive(Run((0, 0), UP), exit_for, in_bounds)[-1]
    assert last.kind is StepKind.LEAVE and last.exit == DOWN


def test_crossroads_can_be_passed_twice():
    cross = PieceModel(resolve_kind("Crossroads"))
    exit_for, in_bounds = make_world({(1, 1): cross}, (4, 1), RIGHT)
    for enter, out in ((LEFT, RIGHT), (UP, DOWN), (RIGHT, LEFT), (DOWN, UP)):
        assert exit_for((1, 1), enter) == out
