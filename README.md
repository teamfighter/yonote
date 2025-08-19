# yonote-tools — CLI для Yonote

[![CI](https://github.com/teamfighter/yonote/actions/workflows/ci.yml/badge.svg)](https://github.com/teamfighter/yonote/actions/workflows/ci.yml)
[![Release](https://github.com/teamfighter/yonote/actions/workflows/release.yml/badge.svg)](https://github.com/teamfighter/yonote/actions/workflows/release.yml)

Инструмент командной строки для экспорта и импорта документов из платформы [Yonote](https://yonote.ru). CLI умеет интерактивно просматривать коллекции и документы, обновлять кэш выборочно и работать с вложенными папками.

## Запуск в Docker

Образ публикуется в [GitHub Container Registry](https://github.com/orgs/teamfighter/packages). Для работы с CLI достаточно
загрузить образ и подключить shell‑обёртку:

```bash
export YONOTE_VERSION=<latest tag>
docker pull ghcr.io/teamfighter/yonote:$YONOTE_VERSION
curl -O https://raw.githubusercontent.com/teamfighter/yonote/main/yonote.sh
chmod +x yonote.sh
source yonote.sh
yonote --help
```

Обёртка монтирует файлы `~/.yonote.json` и `~/.yonote-cache.json`, а также текущую директорию в `/app/work`, что позволяет
использовать относительные пути. Далее во всех примерах предполагается, что функция `yonote` уже доступна.

## Запуск через Python venv

Альтернативно CLI можно установить в локальное виртуальное окружение Python:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e yonote_cli
yonote --help
```

## Настройка доступа

Получите JWT‑токен в интерфейсе Yonote и сохраните параметры подключения:

```bash
yonote auth set --base-url https://example.yonote.ru --token <JWT>
```

Конфигурация хранится в `~/.yonote.json`, а кэш структуры документов — в `~/.yonote-cache.json`.

## Экспорт

```bash
yonote export --out-dir ./dump --workers 20 --format md
```

Команда откроет встроенный браузер для выбора коллекций и документов. Выбранные элементы выгружаются в указанную директорию с сохранением иерархии. Полезные флаги:

- `--refresh-cache` — принудительно обновить кэш метаданных;
- `--format md|json` — формат выгрузки файлов;
- `--use-ids` — использовать идентификаторы в именах файлов.

## Импорт

```bash
yonote import --src-dir ./dump
```

CLI предложит выбрать коллекцию и родительский документ, затем воспроизведёт локальную структуру каталогов в Yonote и опубликует созданные документы. Опции:

- `--refresh-cache` — обновить кэш перед выбором;
- `--workers N` — максимальное число потоков при создании документов (по умолчанию 20).

## Встроенный браузер

Интерактивные диалоги экспорта и импорта используют встроенный браузер. Библиотека [InquirerPy](https://github.com/kazhala/InquirerPy), на которой он основан, включена в образ последних версий. Если при запуске появляется сообщение `Interactive mode requires InquirerPy`, обновите `YONOTE_VERSION` до актуального тега. Доступные клавиши:

- `↑`/`↓` — перемещение по списку;
- `PgUp`/`PgDn` — пролистывание по 10 элементов;
- `Enter` — открыть раздел или подтвердить действие;
- `Space` — отметить/снять документ в режиме экспорта;
- `Ctrl+S` — поиск; повторное `Ctrl+S` выходит из режима поиска, `Enter` переходит к следующему совпадению;
- `Ctrl+R` — обновить текущий список с сервера (точечный сброс кэша);
- `..` — перейти на уровень выше.

## Работа с кэшем

Метаданные коллекций и документов сохраняются в `~/.yonote-cache.json`. Управлять кэшем можно командами:

```bash
yonote cache info   # показать информацию о кэше
yonote cache clear  # очистить кэш
```

Флаг `--refresh-cache` или сочетание `Ctrl+R` позволяют обновлять только нужные ветки дерева, сокращая время запросов.

## Примеры

### Экспорт коллекции в Markdown

```bash
yonote export --out-dir ./dump --format md --workers 20
```

### Импорт подготовленных файлов

```bash
yonote import --src-dir ./dump
```

Команда для загрузки образа с конкретной версией публикуется в релизных заметках.

## Локальная разработка

Следуйте инструкции из раздела [«Запуск через Python venv»](#запуск-через-python-venv), затем запустите тесты и при необходимости соберите образ.

### Запуск тестов

```bash
pytest
```

### Сборка Docker-образа

```bash
docker build -f docker/Dockerfile -t yonote:dev .
```
