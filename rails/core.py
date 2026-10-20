"""Чистая логика рельсов и движения поезда — без Kivy.

Всё здесь проверяется обычными тестами:  python -m pytest
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Callable, Mapping

Pos = tuple[int, int]  # (колонка, ряд); ряд 0 — нижний


class Side(StrEnum):
    UP = "Up"
    LEFT = "Left"
    DOWN = "Down"
    RIGHT = "Right"

    @classmethod
    def parse(cls, value) -> "Side":
        """'Up' / 'up' / 'U' -> Side.UP. На мусоре бросает ValueError."""
        if isinstance(value, cls):
            return value
        key = str(value).strip().lower()
        for side in cls:
            if key in (side.value.lower(), side.value[0].lower()):
                return side
        raise ValueError(f"неизвестная сторона {value!r} (нужно Up, Down, Left или Right)")

    def rotated(self, steps: int = 1) -> "Side":
        """Повернуть сторону на steps четвертей ПРОТИВ часовой стрелки."""
        return _CCW[(_CCW.index(self) + steps) % 4]

    @property
    def opposite(self) -> "Side":
        return self.rotated(2)

    @property
    def vector(self) -> tuple[int, int]:
        return _VECTORS[self]

    @property
    def heading_angle(self) -> int:
        """Угол спрайта (против часовой), когда поезд едет В эту сторону.
        Спрайт поезда по умолчанию смотрит вверх."""
        return 90 * _CCW.index(self)


_CCW = (Side.UP, Side.LEFT, Side.DOWN, Side.RIGHT)
_VECTORS = {Side.UP: (0, 1), Side.DOWN: (0, -1), Side.LEFT: (-1, 0), Side.RIGHT: (1, 0)}
UP, LEFT, DOWN, RIGHT = Side.UP, Side.LEFT, Side.DOWN, Side.RIGHT


class Outcome(Enum):
    BREAK = "break"  # поезд сошёл с рельс
    WIN = "win"      # поезд выехал через финишную сторону


Connections = Mapping[Side, Side]  # въезд с этой стороны -> выезд на эту сторону


def rotate_connections(connections: Connections, steps: int) -> dict[Side, Side]:
    steps %= 4
    return {a.rotated(steps): b.rotated(steps) for a, b in connections.items()}


def open_sides(connections: Connections) -> frozenset[Side]:
    return frozenset(connections) | frozenset(connections.values())


# ───────────────────────── виды деталей ─────────────────────────
@dataclass(frozen=True)
class PieceState:
    image: str               # файл в assets/
    connections: Connections  # как нарисовано на картинке (угол 0)
    turns: int = 0           # доп. поворот картинки и рельс (четверти, против часовой)


@dataclass(frozen=True)
class PieceKind:
    name: str
    states: tuple[PieceState, ...]

    @property
    def switchable(self) -> bool:
        """Можно ли переключать деталь одним тапом во время поездки."""
        return len(self.states) > 1


_STRAIGHT = {LEFT: RIGHT, RIGHT: LEFT}
_CURVE = {LEFT: DOWN, DOWN: LEFT}  # так нарисован rotation_real.png
_CROSS = {LEFT: RIGHT, RIGHT: LEFT, DOWN: UP, UP: DOWN}
_FORWARD = PieceState("forward_real.png", _STRAIGHT)

KINDS: dict[str, PieceKind] = {
    "Straight": PieceKind("Straight", (_FORWARD,)),
    "Rotation": PieceKind("Rotation", (PieceState("rotation_real.png", _CURVE),)),
    "Crossroads": PieceKind("Crossroads", (PieceState("crossroads_real.png", _CROSS),)),
    # Rowation: прямая -> поворот R-U -> поворот L-U. Картинка поворота та же,
    # но повёрнута вместе с рельсами (раньше менялись только рельсы, а картинка — нет).
    "Rowation": PieceKind("Rowation", (
        _FORWARD,
        PieceState("rotation_real.png", _CURVE, turns=2),
        PieceState("rotation_real.png", _CURVE, turns=3),
    )),
}
_BY_LOWER = {name.lower(): kind for name, kind in KINDS.items()}
_BY_LOWER[""] = KINDS["Straight"]            # type = "" в TOML — обычная прямая
_BY_LOWER["movablebox"] = KINDS["Straight"]  # старое имя класса


def resolve_kind(name: str) -> PieceKind:
    """Имя из TOML -> PieceKind. KeyError, если такой детали нет."""
    try:
        return _BY_LOWER[(name or "").strip().lower()]
    except KeyError:
        raise KeyError(f"неизвестная деталь {name!r} (есть: {', '.join(KINDS)})") from None


class PieceModel:
    """Состояние одной детали: какие стороны соединены сейчас."""

    def __init__(self, kind: PieceKind):
        self.kind = kind
        self.state = 0  # индекс состояния (для переключаемых деталей)
        self.turns = 0  # повороты игрока двойным тапом (четверти, против часовой)

    @property
    def current(self) -> PieceState:
        return self.kind.states[self.state]

    @property
    def image(self) -> str:
        return self.current.image

    @property
    def total_turns(self) -> int:
        return self.current.turns + self.turns

    @property
    def connections(self) -> dict[Side, Side]:
        return rotate_connections(self.current.connections, self.total_turns)

    def exits(self, enter: Side) -> Side | Outcome:
        """Куда выедет поезд, въехавший с стороны enter."""
        return self.connections.get(enter, Outcome.BREAK)

    def open_sides(self) -> frozenset[Side]:
        return open_sides(self.connections)

    def next_open_sides(self) -> frozenset[Side]:
        """Стороны, которые откроются после следующего переключения."""
        if not self.kind.switchable:
            return frozenset()
        nxt = self.kind.states[(self.state + 1) % len(self.kind.states)]
        return open_sides(rotate_connections(nxt.connections, nxt.turns + self.turns)) - self.open_sides()

    def rotate(self, steps: int = 1) -> None:
        self.turns = (self.turns + steps) % 4

    def cycle(self) -> None:
        self.state = (self.state + 1) % len(self.kind.states)

    def reset_state(self) -> None:
        """Вернуть переключатель в исходное положение (поворот игрока сохраняется)."""
        self.state = 0

    def reset(self) -> None:
        self.state = 0
        self.turns = 0


# ───────────────────────── движение поезда ─────────────────────────
class StepKind(Enum):
    MOVE = "move"    # едем в следующую клетку
    WIN = "win"      # въехали в финиш и выезжаем куда нужно
    CRASH = "crash"  # нет рельс / тупик
    LEAVE = "leave"  # выехали за край поля


@dataclass
class Run:
    """Где сейчас поезд и какие станции ещё надо проехать."""
    pos: Pos
    side: Side  # с какой стороны въезжаем в клетку pos
    points_left: set[Pos] = field(default_factory=set)


@dataclass(frozen=True)
class Step:
    kind: StepKind
    pos: Pos                      # какую клетку оценивали
    enter: Side
    exit: Side | None = None
    next_pos: Pos | None = None
    won: bool = False             # для WIN: пройдены ли все станции


def advance(run: Run, exit_for: Callable[[Pos, Side], Side | Outcome],
            in_bounds: Callable[[Pos], bool]) -> Step:
    """Один шаг: оценить клетку run.pos и (если можно) сдвинуть run дальше."""
    pos, enter = run.pos, run.side
    result = exit_for(pos, enter)
    if result is Outcome.BREAK:
        return Step(StepKind.CRASH, pos, enter)
    if result is Outcome.WIN:
        return Step(StepKind.WIN, pos, enter, won=not run.points_left)
    run.points_left.discard(pos)
    dx, dy = result.vector
    nxt = (pos[0] + dx, pos[1] + dy)
    if not in_bounds(nxt):
        return Step(StepKind.LEAVE, pos, enter, exit=result)
    run.pos, run.side = nxt, result.opposite
    return Step(StepKind.MOVE, pos, enter, exit=result, next_pos=nxt)
