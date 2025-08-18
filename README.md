# yonote-tools — CLI для Yonote

[![CI](https://github.com/teamfighter/yonote/actions/workflows/ci.yml/badge.svg)](https://github.com/teamfighter/yonote/actions/workflows/ci.yml)
[![Release](https://github.com/teamfighter/yonote/actions/workflows/release.yml/badge.svg)](https://github.com/teamfighter/yonote/actions/workflows/release.yml)

Инструмент командной строки для экспорта и импорта документов из платформы [Yonote](https://yonote.ru). CLI умеет интерактивно просматривать коллекции и документы, обновлять кэш выборочно и работать с вложенными папками.

## Запуск в Docker

Образ публикуется в [GitHub Container Registry](https://github.com/orgs/teamfighter/packages).

```bash
docker pull ghcr.io/teamfighter/yonote:<tag>
```

Для сохранения конфигурации и кэша смонтируйте файлы в домашний каталог контейнера и прокиньте рабочую директорию:

```bash
docker run --rm -it \
  -v "$HOME/.yonote.json:/root/.yonote.json" \
  -v "$HOME/.yonote-cache.json:/root/.yonote-cache.json" \
  -v "$(pwd):/data" \
  ghcr.io/teamfighter/yonote:<tag> --help
```

В примерах далее `ghcr.io/teamfighter/yonote:<tag>` следует запускать аналогичным образом.

## Настройка доступа

Получите JWT‑токен в интерфейсе Yonote и сохраните параметры подключения:

```bash
docker run --rm -it \
  -v "$HOME/.yonote.json:/root/.yonote.json" \
  -v "$HOME/.yonote-cache.json:/root/.yonote-cache.json" \
  ghcr.io/teamfighter/yonote:<tag> auth set --base-url https://example.yonote.ru --token <JWT>
```

Конфигурация хранится в `~/.yonote.json`, а кэш структуры документов — в `~/.yonote-cache.json`.

## Экспорт

```bash
docker run --rm -it \
  -v "$HOME/.yonote.json:/root/.yonote.json" \
  -v "$HOME/.yonote-cache.json:/root/.yonote-cache.json" \
  -v "$(pwd)/dump:/data" \
  ghcr.io/teamfighter/yonote:<tag> export --out-dir /data --workers 4 --format md
```

Команда откроет встроенный браузер для выбора коллекций и документов. Выбранные элементы выгружаются в указанную директорию с сохранением иерархии. Полезные флаги:

- `--refresh-cache` — принудительно обновить кэш метаданных;
- `--format md|json` — формат выгрузки файлов;
- `--use-ids` — использовать идентификаторы в именах файлов.

## Импорт

```bash
docker run --rm -it \
  -v "$HOME/.yonote.json:/root/.yonote.json" \
  -v "$HOME/.yonote-cache.json:/root/.yonote-cache.json" \
  -v "$(pwd)/dump:/data" \
  ghcr.io/teamfighter/yonote:<tag> import --src-dir /data
```

CLI предложит выбрать коллекцию и родительский документ, затем воспроизведёт локальную структуру каталогов в Yonote и опубликует созданные документы. Опции:

- `--refresh-cache` — обновить кэш перед выбором;
- `--workers N` — максимальное число потоков при создании документов.

## Встроенный браузер

Интерактивные диалоги экспорта и импорта используют встроенный браузер. Библиотека [InquirerPy](https://github.com/kazhala/InquirerPy), на которой он основан, уже включена в Docker‑образ, поэтому дополнительная установка не требуется. Доступные клавиши:

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
docker run --rm -it \
  -v "$HOME/.yonote.json:/root/.yonote.json" \
  -v "$HOME/.yonote-cache.json:/root/.yonote-cache.json" \
  ghcr.io/teamfighter/yonote:<tag> cache info   # показать информацию о кэше
docker run --rm -it \
  -v "$HOME/.yonote.json:/root/.yonote.json" \
  -v "$HOME/.yonote-cache.json:/root/.yonote-cache.json" \
  ghcr.io/teamfighter/yonote:<tag> cache clear  # очистить кэш
```

Флаг `--refresh-cache` или сочетание `Ctrl+R` позволяют обновлять только нужные ветки дерева, сокращая время запросов.

## Примеры

### Экспорт коллекции в Markdown

```bash
docker run --rm -it \
  -v "$HOME/.yonote.json:/root/.yonote.json" \
  -v "$HOME/.yonote-cache.json:/root/.yonote-cache.json" \
  -v "$(pwd)/dump:/data" \
  ghcr.io/teamfighter/yonote:<tag> export --out-dir /data --format md --workers 4
```

### Импорт подготовленных файлов

```bash
docker run --rm -it \
  -v "$HOME/.yonote.json:/root/.yonote.json" \
  -v "$HOME/.yonote-cache.json:/root/.yonote-cache.json" \
  -v "$(pwd)/dump:/data" \
  ghcr.io/teamfighter/yonote:<tag> import --src-dir /data
```

Команда для загрузки образа с конкретной версией публикуется в релизных заметках.

## Локальная разработка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e yonote_cli
```

### Запуск тестов

```bash
pytest
```

### Сборка Docker-образа

```bash
docker build -f docker/Dockerfile -t yonote:dev .
```

