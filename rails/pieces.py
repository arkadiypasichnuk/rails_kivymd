"""Виджеты поля: клетки, детали, маркеры, слоты лотка (бывший Boxes.py).

Размеры здесь — в «виртуальных» единицах: клетка = CELL. Под экран всё
масштабирует ScatterPlane (см. board.py), поэтому нет привязки к размеру окна.
Логика рельс живёт в core.py; виджеты только рисуют и ловят касания.
"""
from __future__ import annotations

from kivy.animation import Animation
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from .core import Outcome, PieceKind, PieceModel, Side
from .paths import asset

CELL = 100

TILE_EMPTY = (.2, .6, .9, .18)
LINE_EMPTY = (.2, .6, .9, 1)
TILE_BLOCK = (.20, .22, .27, 1)
FRAME_OPEN = (.25, .85, .35, .95)    # сторона соединена
FRAME_CLOSED = (.95, .30, .30, .55)  # сторона закрыта
FRAME_NEXT = (.30, .55, 1.0, 1)      # сторона, которая откроется при переключении
MARKER = {  # role -> (заливка поверх клетки, цвет стороны старта/финиша, цвет кольца)
    "start": ((1, .9, 0, .20), (1, .85, 0, 1), (0, 0, 0, 0)),
    "end": ((.2, .4, 1, .25), (.3, .6, 1, 1), (0, 0, 0, 0)),
    "point": ((1, 1, 1, .20), (0, 0, 0, 0), (1, 1, 1, .85)),
}


# ───────────────────────── клетки ─────────────────────────
class Cell(Widget):
    """Клетка поля. Деталь «стоит» в клетке, пока piece не None."""
    col = NumericProperty(0)
    row = NumericProperty(0)
    piece = ObjectProperty(None, allownone=True)
    tile_color = ListProperty(TILE_EMPTY)
    line_color = ListProperty(LINE_EMPTY)
    accepts_pieces = True
    side: Side | None = None  # у старта — откуда въезжает поезд; у финиша — куда выезжает

    def __init__(self, col: int, row: int, **kwargs):
        super().__init__(col=col, row=row, size_hint=(None, None), size=(CELL, CELL),
                         pos=(col * CELL, row * CELL), **kwargs)

    def can_take(self, piece) -> bool:
        return self.accepts_pieces and self.piece is None

    def train_on_enter(self, enter: Side) -> Side | Outcome:
        """Куда выедет поезд, въехавший с стороны enter (или BREAK)."""
        return self.piece.exits(enter) if self.piece is not None else Outcome.BREAK


class BlockCell(Cell):
    accepts_pieces = False

    def __init__(self, col: int, row: int, **kwargs):
        super().__init__(col, row, **kwargs)
        self.tile_color = TILE_BLOCK

    def train_on_enter(self, enter: Side) -> Side | Outcome:
        return Outcome.BREAK


class PointCell(Cell):
    """Станция: через неё поезд обязан проехать."""


class StartCell(Cell):
    pass


class EndCell(Cell):
    def train_on_enter(self, enter: Side) -> Side | Outcome:
        result = super().train_on_enter(enter)
        return Outcome.WIN if result == self.side else result


class Marker(Widget):
    """Пометка старта/финиша/станции. Рисуется ПОВЕРХ деталей, чтобы не пряталась под ними."""
    tint = ListProperty([0, 0, 0, 0])
    edge_color = ListProperty([0, 0, 0, 0])
    ring_color = ListProperty([0, 0, 0, 0])
    bar_points = ListProperty([0, 0, 0, 0])
    arrow_points = ListProperty([0] * 6)

    def __init__(self, cell: Cell, role: str, side: Side | None = None, **kwargs):
        super().__init__(size_hint=(None, None), size=cell.size, pos=cell.pos, **kwargs)
        self.tint, self.edge_color, self.ring_color = MARKER[role]
        if side is not None:
            self._build_arrow(side, inward=(role == "start"))

    def _build_arrow(self, side: Side, inward: bool) -> None:
        vx, vy = side.vector
        px, py = -vy, vx                                  # перпендикуляр к стороне
        bx = self.center_x + vx * (self.width / 2 - 3)    # середина полоски у края клетки
        by = self.center_y + vy * (self.height / 2 - 3)
        half = self.width / 2 - 8
        self.bar_points = [bx - px * half, by - py * half, bx + px * half, by + py * half]
        edge = (bx - vx * 4, by - vy * 4)                 # точка чуть внутри клетки у края
        inner = (edge[0] - vx * 16, edge[1] - vy * 16)
        base, tip = (edge, inner) if inward else (inner, edge)  # старт — внутрь, финиш — наружу
        self.arrow_points = [base[0] - px * 9, base[1] - py * 9, base[0] + px * 9, base[1] + py * 9, *tip]


# ───────────────────────── лоток ─────────────────────────
class TraySlot(Widget):
    """Подложка стопки одинаковых деталей в лотке."""

    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), size=(CELL, CELL), **kwargs)


class TrayBadge(Label):
    """Счётчик «×N» на стопке (виден, когда деталей две и больше)."""
    count = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), size=(46, 26), bold=True, font_size=17, opacity=0, **kwargs)

    def on_count(self, _, value):
        self.text = f"×{int(value)}"
        self.opacity = 1 if value >= 2 else 0


# ───────────────────────── деталь ─────────────────────────
_FRAME_ATTR = {Side.UP: "frame_up", Side.DOWN: "frame_down", Side.LEFT: "frame_left", Side.RIGHT: "frame_right"}


class Piece(Widget):
    """Деталь рельс. Перетаскивается пальцем, двойной тап — поворот на 90°.
    Переключаемая деталь (Rowation) во время поездки меняется одним тапом."""
    source = StringProperty("")
    visual_angle = NumericProperty(0)
    held = BooleanProperty(False)
    frame_up = ListProperty(FRAME_CLOSED)
    frame_down = ListProperty(FRAME_CLOSED)
    frame_left = ListProperty(FRAME_CLOSED)
    frame_right = ListProperty(FRAME_CLOSED)

    def __init__(self, board, kind: PieceKind, **kwargs):
        super().__init__(size_hint=(None, None), size=(CELL, CELL), **kwargs)
        self.board = board
        self.model = PieceModel(kind)
        self.cell: Cell | None = None         # клетка, в которой стоит деталь
        self.origin_cell: Cell | None = None  # откуда её подняли (для отката)
        self._grab_offset = (0.0, 0.0)
        self.sync(animate=False)

    @property
    def kind_name(self) -> str:
        return self.model.kind.name

    def exits(self, enter: Side) -> Side | Outcome:
        return self.model.exits(enter)

    def sync(self, animate: bool = True) -> None:
        """Обновить картинку, угол и цвета рамок по модели."""
        model = self.model
        self.source = asset(model.image)
        open_now, open_next = model.open_sides(), model.next_open_sides()
        for side, attr in _FRAME_ATTR.items():
            setattr(self, attr, FRAME_NEXT if side in open_next else FRAME_OPEN if side in open_now else FRAME_CLOSED)
        diff = (90 * model.total_turns - self.visual_angle + 180) % 360 - 180  # кратчайший поворот
        Animation.cancel_all(self, "visual_angle")
        if animate and diff:
            Animation(visual_angle=self.visual_angle + diff, d=.15, t="out_quad").start(self)
        else:
            self.visual_angle += diff

    # ----- касания -----
    def on_touch_down(self, touch):
        if getattr(touch, "is_mouse_scrolling", False) or not self.collide_point(*touch.pos):
            return False
        board = self.board
        if board.state == "running":
            if self.model.kind.switchable:        # стрелка-переключатель на ходу
                self.model.cycle()
                self.sync()
                return True
            return False
        if touch.is_double_tap:
            board.unfinish()
            self.model.rotate()
            self.sync()
            return True
        if not board.begin_drag(self):
            return False
        touch.grab(self)
        self._grab_offset = (touch.x - self.x, touch.y - self.y)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self.pos = (touch.x - self._grab_offset[0], touch.y - self._grab_offset[1])
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self.board.end_drag(self)
            return True
        return super().on_touch_up(touch)
