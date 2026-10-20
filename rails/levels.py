"""Загрузка и проверка уровней из TOML — без Kivy.

Формат уровня (всё, кроме id, можно опустить):

    [[levels]]
    id = 5
    cols = 5                        # по умолчанию 3
    rows = 5                        # по умолчанию 3
    lab_text = "Подсказка"

    [levels.stations]               # клетки-блоки
    "(1, 1)" = "Block"

    [[levels.trains]]               # если не указать — поезд (0,1)->(2,1)
    start  = { pos = [0, 4], side = "Left" }        # side по умолчанию Left
    end    = { pos = [4, 0], side_options = ["Down", "Up"] }
    points = [[1, 2], [2, 1]]       # станции, через которые надо проехать

    [[levels.pazls]]
    type = "Rotation"               # "" / Straight / Rotation / Crossroads / Rowation
    count = 4

Конец поезда можно задать так: pos | pos_options, side | side_options.
Если вариантов несколько — один выбирается случайно при каждом запуске уровня.
pos_options + side_options работают парами (одинаковой длины).
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .core import LEFT, RIGHT, Pos, Side, resolve_kind

DEFAULT_COLS = DEFAULT_ROWS = 3
DEFAULT_START: tuple[Pos, Side] = ((0, 1), LEFT)
DEFAULT_END: tuple[Pos, Side] = ((2, 1), RIGHT)
MAX_SIZE = 12

_POS_RE = re.compile(r"^\s*\(?\s*(-?\d+)\s*[,;]\s*(-?\d+)\s*\)?\s*$")


class LevelError(ValueError):
    """Ошибка в файле уровней (текст — для человека)."""


@dataclass(frozen=True)
class TrainSpec:
    start: Pos
    start_side: Side
    ends: tuple[tuple[Pos, Side], ...]  # варианты финиша; выбирается один
    points: tuple[Pos, ...] = ()


@dataclass(frozen=True)
class LevelData:
    id: int
    cols: int
    rows: int
    hint: str = ""
    blocks: frozenset[Pos] = frozenset()
    pieces: tuple[tuple[str, int], ...] = ()  # (имя детали, сколько штук)
    trains: tuple[TrainSpec, ...] = ()


@dataclass
class LevelPack:
    name: str
    levels: list[LevelData]
    errors: list[str]
    path: Path | None = None


# ───────────────────────── разбор значений ─────────────────────────
def _int(value, what: str, where: str, low: int = 0, high: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LevelError(f"{where}: «{what}» должно быть целым числом, а не {value!r}")
    if value < low or (high is not None and value > high):
        raise LevelError(f"{where}: «{what}» вне диапазона ({value})")
    return value


def _pos(value, what: str, where: str) -> Pos:
    """[2, 1] или "(2, 1)" -> (2, 1). Никакого eval."""
    if isinstance(value, str):
        m = _POS_RE.match(value)
        if m:
            return int(m.group(1)), int(m.group(2))
    elif isinstance(value, (list, tuple)) and len(value) == 2 and all(
            isinstance(v, int) and not isinstance(v, bool) for v in value):
        return value[0], value[1]
    raise LevelError(f"{where}: «{what}» — ожидаются координаты [col, row], получено {value!r}")


def _side(value, what: str, where: str) -> Side:
    try:
        return Side.parse(value)
    except ValueError as e:
        raise LevelError(f"{where}: «{what}» — {e}") from None


def _table(value, what: str, where: str) -> dict:
    if not isinstance(value, dict):
        raise LevelError(f"{where}: «{what}» должно быть таблицей")
    return value


def _parse_ends(end: dict, where: str) -> tuple[tuple[Pos, Side], ...]:
    if "pos" in end and "pos_options" in end:
        raise LevelError(f"{where}: в end нельзя одновременно pos и pos_options")
    if "side" in end and "side_options" in end:
        raise LevelError(f"{where}: в end нельзя одновременно side и side_options")

    if "pos_options" in end:
        raw = end["pos_options"]
        if not isinstance(raw, list) or not raw:
            raise LevelError(f"{where}: end.pos_options должен быть непустым списком")
        positions = [_pos(p, "end.pos_options", where) for p in raw]
    else:
        positions = [_pos(end["pos"], "end.pos", where) if "pos" in end else DEFAULT_END[0]]

    if "side_options" in end:
        raw = end["side_options"]
        if not isinstance(raw, list) or not raw:
            raise LevelError(f"{where}: end.side_options должен быть непустым списком")
        sides = [_side(s, "end.side_options", where) for s in raw]
        if "pos_options" in end:
            if len(sides) != len(positions):
                raise LevelError(f"{where}: pos_options и side_options должны быть одной длины")
            return tuple(zip(positions, sides))
        return tuple((positions[0], s) for s in sides)

    side = _side(end["side"], "end.side", where) if "side" in end else DEFAULT_END[1]
    return tuple((p, side) for p in positions)


def _parse_train(raw: dict, where: str) -> TrainSpec:
    start = _table(raw.get("start", {}), "start", where)
    pos = _pos(start["pos"], "start.pos", where) if "pos" in start else DEFAULT_START[0]
    side = _side(start["side"], "start.side", where) if "side" in start else DEFAULT_START[1]
    ends = _parse_ends(_table(raw.get("end", {}), "end", where), where)
    points = tuple(_pos(p, "points", where) for p in raw.get("points", ()))
    return TrainSpec(pos, side, ends, points)


# ───────────────────────── уровень и пакет ─────────────────────────
def parse_level(raw: dict, index: int) -> LevelData:
    where = f"уровень #{index + 1}"
    lid = _int(raw.get("id", index + 1), "id", where, low=0)
    where = f"уровень {lid}"
    cols = _int(raw.get("cols", DEFAULT_COLS), "cols", where, low=1, high=MAX_SIZE)
    rows = _int(raw.get("rows", DEFAULT_ROWS), "rows", where, low=1, high=MAX_SIZE)

    hint_raw = raw.get("lab_text", "")
    if not isinstance(hint_raw, str):
        raise LevelError(f"{where}: lab_text должен быть строкой")
    hint = "\n".join(line.strip() for line in hint_raw.strip().splitlines()).strip()

    blocks: set[Pos] = set()
    for key, kind in _table(raw.get("stations", {}), "stations", where).items():
        pos = _pos(key, "stations", where)
        if kind == "Block":
            blocks.add(pos)
        elif kind not in ("", "StationBox", "Empty"):
            raise LevelError(f"{where}: неизвестный тип клетки {kind!r} в stations (доступно: Block)")

    pieces = []
    for item in raw.get("pazls", ()):
        item = _table(item, "pazls", where)
        try:
            name = resolve_kind(item.get("type", "")).name
        except KeyError as e:
            raise LevelError(f"{where}: {e.args[0]}") from None
        pieces.append((name, _int(item.get("count", 1), "count", where, low=0, high=99)))

    trains_raw = raw.get("trains")
    trains = tuple(_parse_train(_table(t, "trains", where), where) for t in trains_raw) if trains_raw \
        else (TrainSpec(DEFAULT_START[0], DEFAULT_START[1], (DEFAULT_END,)),)

    level = LevelData(lid, cols, rows, hint, frozenset(blocks), tuple(pieces), trains)
    _validate(level, where)
    return level


def _validate(level: LevelData, where: str) -> None:
    def check(pos: Pos, what: str) -> None:
        if not (0 <= pos[0] < level.cols and 0 <= pos[1] < level.rows):
            raise LevelError(f"{where}: {what} {pos} за пределами поля {level.cols}×{level.rows}")

    special: dict[Pos, str] = {}

    def claim(pos: Pos, what: str) -> None:
        check(pos, what)
        if pos in special:
            raise LevelError(f"{where}: клетка {pos} занята дважды ({special[pos]} и {what})")
        special[pos] = what

    for pos in level.blocks:
        claim(pos, "блок")
    for t in level.trains:
        claim(t.start, "старт")
        for p in t.points:
            claim(p, "станция")
        for end_pos, _ in t.ends:
            check(end_pos, "финиш")
            if end_pos in special and special[end_pos] != "финиш":
                raise LevelError(f"{where}: клетка {end_pos} занята дважды ({special[end_pos]} и финиш)")
        # финиши одного поезда — это варианты, поэтому они могут совпадать между собой
        for end_pos in {e[0] for e in t.ends}:
            special[end_pos] = "финиш"


def parse_pack(data: dict, name: str = "", path: Path | None = None) -> LevelPack:
    levels: list[LevelData] = []
    errors: list[str] = []
    raw_levels = data.get("levels")
    if not isinstance(raw_levels, list) or not raw_levels:
        errors.append("в файле нет ни одного блока [[levels]]")
        raw_levels = []
    seen: set[int] = set()
    for i, raw in enumerate(raw_levels):
        try:
            level = parse_level(_table(raw, "levels", f"уровень #{i + 1}"), i)
            if level.id in seen:
                raise LevelError(f"уровень {level.id}: такой id уже есть")
            seen.add(level.id)
            levels.append(level)
        except LevelError as e:
            errors.append(str(e))
    return LevelPack(str(data.get("name", name)), levels, errors, path)


def load_pack(path: str | Path) -> LevelPack:
    path = Path(path)
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise LevelError(f"файл уровней не найден: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise LevelError(f"{path.name}: ошибка в TOML — {e}") from None
    return parse_pack(data, name=path.stem, path=path)
