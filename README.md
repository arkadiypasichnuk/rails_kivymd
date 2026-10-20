# Рейки — Kivy + KivyMD 2.0

## Запуск
```
pip install -r requirements.txt     # Python 3.11+, kivy 2.3.1, kivymd 2.0.0
python main.py
RAILS_LEVELS=suns/test.toml python main.py   # другой файл уровней
python -m pytest                              # тесты логики (Kivy не нужен)
```
Папка `assets/` — ваша, проект её не меняет. Нужны: `train.png`, `forward_real.png`,
`rotation_real.png`, `crossroads_real.png`; необязательны: `fon_game.jpg`, `Music/fon_game.mp3`.
Язык интерфейса — константа `LANG` в `rails/strings.py` (uk / ru / en).

## Что где лежит
| Было | Стало |
|---|---|
| `Main.py` | `main.py` (вход) + `rails/app.py` (`RailsApp(MDApp)`: тема, навигация, музыка) |
| `Main.py` (разбор TOML) | `rails/levels.py` — загрузка и проверка уровней |
| `Screens.py`, `lvls.py` | `rails/screens.py` — `MenuScreen`, `LevelsScreen`, `GameScreen` (`MDScreen`) |
| `Boxes.py` | `rails/pieces.py` (виджеты) + `rails/core.py` (логика рельс без Kivy) |
| `Train.py` | `rails/train.py` (спрайт) + `rails/board.py` (проход по рельсам) |
| куски `Screens.py`/`Boxes.py` | `rails/board.py` — `Board`: сетка, лоток, перетаскивание, запуск |
| `widgets.kv` | `rails/kv/screens.kv` (KivyMD-экраны) + `rails/kv/board.kv` (клетки, детали) |
| `sound` в каждом экране | `rails/audio.py` — один плеер на приложение |

Слои: `core.py` и `levels.py` не знают про Kivy и покрыты тестами; виджеты (`pieces`, `train`, `board`)
не знают про экраны; экраны общаются с полем через `Board.load/start/stop/fit` и событие `on_finish`.

## Формат уровня
См. docstring в `rails/levels.py` и пример `suns/build-in/Main.toml` (ваш файл, формат прежний).
Новое: у `end` можно задать `pos_options` (+ `side_options` парами) — финиш выбирается случайно.

## Управление
- Деталь из лотка перетаскивается в клетку; брошенная вне поля или на занятую клетку/блок — возвращается.
- Двойной тап — повернуть деталь. На ходу тап по Rowation переключает её.
- Поле двигается и масштабируется жестами (как раньше); кнопка «⛶» возвращает вид «показать всё».
- Esc / «назад» на Android: игра → уровни → меню.
# rails_kivymd
