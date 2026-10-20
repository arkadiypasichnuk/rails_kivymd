"""Игровое поле: сетка, лоток деталей, запуск поезда.

Сюда переехали куски, которые раньше были размазаны по Screens.py (сборка уровня),
Boxes.py (перетаскивание и защёлкивание в клетки) и Train.py (проход по рельсам).

Поле — ScatterPlane (как и раньше MainPlane): его можно двигать и масштабировать
жестами. Дополнительно оно само подгоняется под размер окна (fit), так что на
телефоне и на ПК всё помещается без ручного зума.
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics.transformation import Matrix
from kivy.properties import NumericProperty, OptionProperty, StringProperty
from kivy.uix.scatter import ScatterPlane
from kivy.uix.stencilview import StencilView
from kivy.uix.widget import Widget

from .core import KINDS, Pos, Run, Side, StepKind, advance, resolve_kind
from .levels import LevelData, TrainSpec
from .paths import asset
from .pieces import (CELL, BlockCell, Cell, EndCell, Marker, Piece, PointCell, StartCell,
                     TrayBadge, TraySlot)
from .train import TRAIN_LEN, TRAIN_W, Train

_CELL_TYPES = {"empty": Cell, "block": BlockCell, "point": PointCell, "start": StartCell, "end": EndCell}
_BACKDROP = asset("fon_game.jpg")


def anchor_center(cell: Cell, side: Side) -> tuple[float, float]:
    """Центр поезда, стоящего СНАРУЖИ клетки у стороны side, передом к клетке."""
    vx, vy = side.vector
    dist = CELL / 2 + TRAIN_LEN / 2
    return cell.center_x + vx * dist, cell.center_y + vy * dist


@dataclass(frozen=True)
class Result:
    won: bool
    reason: str  # "ok" | "crash" | "off_board" | "points"


@dataclass
class TrainRun:
    train: Train
    spec: TrainSpec
    end_pos: Pos
    end_side: Side
    core: Run | None = None
    done: bool = False
    won: bool = False
    reason: str = ""


class Playfield(StencilView):
    """Окно просмотра: обрезает всё, что поле рисует за своими границами
    (раньше огромный фон ScatterPlane заходил на соседние виджеты)."""
    backdrop = StringProperty(_BACKDROP if os.path.exists(_BACKDROP) else "")


class Board(ScatterPlane):
    state = OptionProperty("idle", options=("idle", "running", "finished"))
    step_duration = NumericProperty(0.8)  # секунд на одну клетку

    __events__ = ("on_finish",)

    PAD = 12               # отступ сцены от краёв окна просмотра, px экрана
    MAX_FIT_SCALE = 1.6    # на огромных мониторах не раздуваем поле сильнее
    TRAY_GAP = 70          # расстояние от поля до лотка (виртуальные единицы)
    SLOT_GAP = 24
    EXIT_PEEK = 40         # сколько финишной «выездной» зоны резервируем в кадре

    def __init__(self, **kwargs):
        kwargs.setdefault("do_rotation", False)  # в KV было do_rotate — такого свойства нет
        kwargs.setdefault("scale_min", 0.25)
        kwargs.setdefault("scale_max", 4.0)
        super().__init__(**kwargs)
        self.level: LevelData | None = None
        self.rng = random.Random()
        self.cells: dict[Pos, Cell] = {}
        self.pieces: list[Piece] = []
        self.runs: list[TrainRun] = []
        self.slot_order: list[str] = []
        self.slots: dict[str, TraySlot] = {}
        self.badges: dict[str, TrayBadge] = {}
        self._held: Piece | None = None
        self._token = 0  # меняется при сбросе — устаревшие колбэки анимации сами отваливаются
        self._viewport = (0.0, 0.0, 800.0, 600.0)
        # порядок слоёв снизу вверх; поезд до старта лежит под деталями, на ходу — над ними
        self.layers = {name: Widget(size_hint=(None, None), size=(0, 0))
                       for name in ("slots", "cells", "trains_back", "pieces", "overlay", "trains_front")}
        for layer in self.layers.values():
            self.add_widget(layer)

    # ───────────────────────── сборка уровня ─────────────────────────
    def clear(self) -> None:
        self._token += 1
        for run in self.runs:
            Animation.cancel_all(run.train)
        for piece in self.pieces:
            Animation.cancel_all(piece)
        for layer in self.layers.values():
            layer.clear_widgets()
        self.cells, self.pieces, self.runs = {}, [], []
        self.slot_order, self.slots, self.badges = [], {}, {}
        self._held = None
        self.state = "idle"

    def load(self, level: LevelData, rng: random.Random | None = None) -> None:
        self.clear()
        self.level = level
        if rng is not None:
            self.rng = rng

        roles: dict[Pos, tuple[str, Side | None]] = {}
        setups = []
        for spec in level.trains:
            end_pos, end_side = self.rng.choice(spec.ends)  # финиш бывает случайным
            setups.append((spec, end_pos, end_side))
            roles[spec.start] = ("start", spec.start_side)
            roles[end_pos] = ("end", end_side)
            for pos in spec.points:
                roles[pos] = ("point", None)
        for pos in level.blocks:
            roles[pos] = ("block", None)

        for row in range(level.rows):
            for col in range(level.cols):
                role, side = roles.get((col, row), ("empty", None))
                cell = _CELL_TYPES[role](col, row)
                cell.side = side
                self.cells[(col, row)] = cell
                self.layers["cells"].add_widget(cell)
                if role in ("start", "end", "point"):
                    self.layers["overlay"].add_widget(Marker(cell, role, side))

        for spec, end_pos, end_side in setups:
            train = Train()
            self.layers["trains_back"].add_widget(train)
            self.runs.append(TrainRun(train, spec, end_pos, end_side))

        counts: dict[str, int] = {}
        for kind_name, n in level.pieces:
            name = resolve_kind(kind_name).name
            counts[name] = counts.get(name, 0) + n
        self.slot_order = [name for name, n in counts.items() if n > 0]
        for name in self.slot_order:
            self.slots[name] = TraySlot()
            self.layers["slots"].add_widget(self.slots[name])
            self.badges[name] = TrayBadge()
            self.layers["overlay"].add_widget(self.badges[name])
            for _ in range(counts[name]):
                piece = Piece(self, KINDS[name])
                self.pieces.append(piece)
                self.layers["pieces"].add_widget(piece)

        self.reset_trains()
        self._apply_layout()
        self._refresh_counts()

    # ───────────────────────── раскладка и масштаб ─────────────────────────
    def fit(self, x: float, y: float, w: float, h: float) -> None:
        """Вписать сцену в прямоугольник (x, y, w, h) — координаты родителя."""
        self._viewport = (x, y, max(w, 1.0), max(h, 1.0))
        self._apply_layout()

    def _train_rects(self) -> list[tuple[float, float, float, float]]:
        """Где поезд стоит на старте (виден целиком) и где выезжает на финише
        (достаточно, чтобы выглядывал нос — остальное уезжает за край кадра)."""
        rects = []
        for run in self.runs:
            spots = [(run.spec.start, run.spec.start_side, None)] + \
                    [(pos, side, self.EXIT_PEEK) for pos, side in run.spec.ends]
            for (col, row), side, peek in spots:
                vx, vy = side.vector
                cx = (col + .5) * CELL + vx * (CELL / 2 + TRAIN_LEN / 2)
                cy = (row + .5) * CELL + vy * (CELL / 2 + TRAIN_LEN / 2)
                horizontal = side in (Side.LEFT, Side.RIGHT)
                hw, hh = (TRAIN_LEN / 2, TRAIN_W / 2) if horizontal else (TRAIN_W / 2, TRAIN_LEN / 2)
                x0, y0, x1, y1 = cx - hw, cy - hh, cx + hw, cy + hh
                if peek is not None:  # обрезать прямоугольник: за краем клетки только peek единиц
                    edge_x, edge_y = (col + .5 + vx * .5) * CELL, (row + .5 + vy * .5) * CELL
                    if vx > 0:
                        x1 = min(x1, edge_x + peek)
                    elif vx < 0:
                        x0 = max(x0, edge_x - peek)
                    if vy > 0:
                        y1 = min(y1, edge_y + peek)
                    elif vy < 0:
                        y0 = max(y0, edge_y - peek)
                rects.append((x0, y0, x1, y1))
        return rects

    def _main_rect(self) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = 0.0, 0.0, self.level.cols * CELL, self.level.rows * CELL
        for rx0, ry0, rx1, ry1 in self._train_rects():
            x0, y0, x1, y1 = min(x0, rx0), min(y0, ry0), max(x1, rx1), max(y1, ry1)
        return x0, y0, x1, y1

    def _tray_layout(self, mode: str, cols: int, main):
        """Позиции слотов лотка и его прямоугольник: справа от поля или под ним."""
        n = len(self.slot_order)
        if n == 0 or mode == "none":
            return [], None
        cols = min(cols, n)
        rows = -(-n // cols)
        width = cols * CELL + (cols - 1) * self.SLOT_GAP
        height = rows * CELL + (rows - 1) * self.SLOT_GAP
        if mode == "right":
            left, top = main[2] + self.TRAY_GAP, self.level.rows * CELL
        else:
            left, top = self.level.cols * CELL / 2 - width / 2, main[1] - self.TRAY_GAP
        positions = [(left + (i % cols) * (CELL + self.SLOT_GAP), top - CELL - (i // cols) * (CELL + self.SLOT_GAP))
                     for i in range(n)]
        return positions, (left, top - height, left + width, top)

    def _plan(self, vw: float, vh: float):
        """Перебрать варианты раскладки лотка и взять тот, где поле получается крупнее."""
        main = self._main_rect()
        n = len(self.slot_order)
        # при равном масштабе выигрывает вариант раньше в списке: узкий столбец справа
        # или, под полем, одна широкая строка
        modes = [("none", 1)] if n == 0 else \
            [("right", c) for c in (1, 2, 3)] + [("below", c) for c in range(min(n, 6), 0, -1)]
        best = None
        for mode, cols in modes:
            positions, rect = self._tray_layout(mode, cols, main)
            box = main if rect is None else (min(main[0], rect[0]), min(main[1], rect[1]),
                                             max(main[2], rect[2]), max(main[3], rect[3]))
            scale = min((vw - 2 * self.PAD) / (box[2] - box[0]), (vh - 2 * self.PAD) / (box[3] - box[1]))
            if best is None or scale > best[0] * 1.001:
                best = (scale, positions, box)
        return best

    def _apply_layout(self) -> None:
        if self.level is None:
            return
        x, y, w, h = self._viewport
        scale, positions, box = self._plan(w, h)
        for name, pos in zip(self.slot_order, positions):
            self.slots[name].pos = pos
            self.badges[name].pos = (pos[0] + CELL - 40, pos[1] + CELL - 20)
        for piece in self.pieces:  # детали в лотке переезжают вместе со слотами
            if piece.cell is None and piece is not self._held:
                Animation.cancel_all(piece, "pos")
                piece.pos = self.slots[piece.kind_name].pos
        scale = max(self.scale_min, min(scale, self.MAX_FIT_SCALE))
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        self.transform = Matrix().scale(scale, scale, 1).translate(x + w / 2 - cx * scale, y + h / 2 - cy * scale, 0)

    # ───────────────────────── перетаскивание деталей ─────────────────────────
    def cell_at(self, point) -> Cell | None:
        return self.cells.get((int(point[0] // CELL), int(point[1] // CELL)))

    def begin_drag(self, piece: Piece) -> bool:
        if self.state == "running" or self._held is not None:
            return False
        self.unfinish()
        self._held = piece
        Animation.cancel_all(piece, "pos")
        piece.origin_cell = piece.cell
        if piece.cell is not None:  # освободить клетку
            piece.cell.piece = None
            piece.cell = None
        layer = self.layers["pieces"]  # поднять деталь над остальными
        layer.remove_widget(piece)
        layer.add_widget(piece)
        piece.held = True
        self._refresh_counts()
        return True

    def end_drag(self, piece: Piece) -> None:
        self._held = None
        piece.held = False
        origin, piece.origin_cell = piece.origin_cell, None
        target = self.cell_at(piece.center)
        if target is None:                              # бросили вне поля — деталь уходит в лоток
            self._to_tray(piece)
        elif target.can_take(piece):
            self._place(piece, target)
        elif origin is not None and origin.can_take(piece):  # клетка занята/блок — откат
            self._place(piece, origin)
        else:
            self._to_tray(piece)
        self._refresh_counts()

    def _move_piece(self, piece: Piece, pos, animate: bool = True) -> None:
        Animation.cancel_all(piece, "pos")
        if animate:
            Animation(pos=pos, d=.12, t="out_quad").start(piece)
        else:
            piece.pos = pos

    def _place(self, piece: Piece, cell: Cell, animate: bool = True) -> None:
        cell.piece, piece.cell = piece, cell
        self._move_piece(piece, cell.pos, animate)

    def _to_tray(self, piece: Piece) -> None:
        piece.cell = None
        piece.model.reset()
        piece.sync()
        self._move_piece(piece, self.slots[piece.kind_name].pos)

    def place_from_tray(self, kind_name: str, pos: Pos, turns: int = 0) -> Piece | None:
        """Поставить свободную деталь нужного вида в клетку pos (для тестов и подсказок)."""
        cell = self.cells.get(pos)
        piece = next((p for p in reversed(self.pieces) if p.kind_name == kind_name and p.cell is None
                      and p is not self._held), None)
        if piece is None or cell is None or not cell.can_take(piece):
            return None
        self.unfinish()
        piece.model.reset()
        piece.model.rotate(turns)
        piece.sync(animate=False)
        self._place(piece, cell, animate=False)
        self._refresh_counts()
        return piece

    def _refresh_counts(self) -> None:
        for name in self.slot_order:
            self.badges[name].count = sum(1 for p in self.pieces if p.kind_name == name
                                          and p.cell is None and p is not self._held)

    # ───────────────────────── запуск поезда ─────────────────────────
    def unfinish(self) -> None:
        """После результата первое же действие игрока возвращает поезд на старт."""
        if self.state == "finished":
            self.reset_trains()
            self.state = "idle"

    def reset_trains(self) -> None:
        """Поезда — на старт, переключатели Rowation — в исходное положение."""
        self._token += 1
        for run in self.runs:
            spec = run.spec
            run.core = Run(spec.start, spec.start_side, set(spec.points))
            run.done, run.won, run.reason = False, False, ""
            run.train.place(anchor_center(self.cells[spec.start], spec.start_side),
                            spec.start_side.opposite.heading_angle)
            self._reparent(run.train, "trains_back")
        for piece in self.pieces:
            if piece.model.state:
                piece.model.reset_state()
                piece.sync(animate=False)

    def _reparent(self, widget: Widget, layer_name: str) -> None:
        layer = self.layers[layer_name]
        if widget.parent is not layer:
            if widget.parent is not None:
                widget.parent.remove_widget(widget)
            layer.add_widget(widget)

    def start(self) -> bool:
        if self.level is None or self.state == "running" or self._held is not None:
            return False
        self.reset_trains()
        token = self._token
        self.state = "running"
        for run in self.runs:
            self._reparent(run.train, "trains_front")
            self._advance(run, token)
        return True

    def stop(self) -> None:
        """Остановить поездку (или убрать результат): поезда возвращаются на старт."""
        if self.level is None:
            return
        self.reset_trains()
        self.state = "idle"

    def _exit_for(self, pos: Pos, enter: Side):
        return self.cells[pos].train_on_enter(enter)

    def _advance(self, run: TrainRun, token: int) -> None:
        if token != self._token or run.done:
            return
        step = advance(run.core, self._exit_for, self.cells.__contains__)
        if step.kind is StepKind.MOVE:
            target = self.cells[step.next_pos]
            run.train.go(anchor_center(target, step.exit.opposite), step.exit.heading_angle,
                         self.step_duration, lambda: self._advance(run, token))
            return

        cell = self.cells[step.pos]
        won = step.kind is StepKind.WIN and step.won
        if step.kind is StepKind.LEAVE:
            out = step.exit                  # ехал за край поля — едет дальше и «падает»
        elif isinstance(cell, EndCell):
            out = cell.side                  # финиш: выезд в нужную сторону
        else:
            out = step.enter.opposite        # тупик: пролетает клетку насквозь
        angle = out.heading_angle + (0 if won else self.rng.randint(-90, 90))
        reason = "ok" if won else {StepKind.CRASH: "crash", StepKind.LEAVE: "off_board"}.get(step.kind, "points")
        run.train.go(anchor_center(cell, out), angle, self.step_duration,
                     lambda: self._finish_run(run, token, won, reason))

    def _finish_run(self, run: TrainRun, token: int, won: bool, reason: str) -> None:
        if token != self._token:
            return
        run.done, run.won, run.reason = True, won, reason
        if all(r.done for r in self.runs):
            self.state = "finished"
            failed = next((r for r in self.runs if not r.won), None)
            result = Result(failed is None, "ok" if failed is None else failed.reason)
            Clock.schedule_once(lambda dt: self._emit(token, result), .35)

    def _emit(self, token: int, result: Result) -> None:
        if token == self._token and self.state == "finished":
            self.dispatch("on_finish", result)

    def on_finish(self, result: Result) -> None:
        """Событие: поездка закончилась (победа или поражение)."""
