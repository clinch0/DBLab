import os
import random
import time
import zipfile
import hashlib

SCHEMA_FILE = "schema.txt"
BACKUP_DIR = "backups"
SCHEMAS = {}
FOREIGN_KEYS = {}
INDEXES = {}
TYPES = ("int", "float", "str")
COMPARE_SIGNS = ("=", "!=", ">", "<", ">=", "<=")


def load_schema():
    SCHEMAS.clear()
    FOREIGN_KEYS.clear()
    if not os.path.exists(SCHEMA_FILE):
        return
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line == "":
                continue
            table, fields_text, fks_text = line.split(";")
            fields = []
            for part in fields_text.split(","):
                field_name, type_name = part.split(":")
                fields.append((field_name, type_name))
            SCHEMAS[table] = fields
            if fks_text != "":
                fks = {}
                for part in fks_text.split(","):
                    column, parent = part.split(">")
                    fks[column] = parent
                FOREIGN_KEYS[table] = fks


def save_schema():
    with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
        for table, fields in SCHEMAS.items():
            fields_text = ",".join(name + ":" + type_name for name, type_name in fields)
            fks = FOREIGN_KEYS.get(table, {})
            fks_text = ",".join(column + ">" + parent for column, parent in fks.items())
            f.write(table + ";" + fields_text + ";" + fks_text + "\n")


def valid_name(name):
    return name != "" and name.replace("_", "").isalnum()


def create_table(name, fields, foreign_keys=None):
    if foreign_keys is None:
        foreign_keys = {}
    if not valid_name(name):
        print("Ошибка: имя таблицы может содержать буквы, цифры и _")
        return False
    if name in SCHEMAS:
        print(f"Ошибка: таблица {name} уже есть")
        return False
    if len(fields) == 0:
        print("Ошибка: нужно хотя бы одно поле кроме id")
        return False
    names = ["id"]
    for field_name, type_name in fields:
        if not valid_name(field_name):
            print(f"Ошибка: неверное имя поля {field_name}")
            return False
        if type_name not in TYPES:
            print(f"Ошибка: тип {type_name} не поддерживается (int, float, str)")
            return False
        if field_name in names:
            print(f"Ошибка: поле {field_name} повторяется")
            return False
        names.append(field_name)
    types = dict(fields)
    for column, parent in foreign_keys.items():
        if column not in types or types[column] != "int":
            print(f"Ошибка: внешний ключ {column} должен быть полем типа int")
            return False
        if parent not in SCHEMAS:
            print(f"Ошибка: таблицы {parent} нет")
            return False
    SCHEMAS[name] = [("id", "int")] + list(fields)
    if foreign_keys:
        FOREIGN_KEYS[name] = dict(foreign_keys)
    save_schema()
    open(name + ".txt", "a", encoding="utf-8").close()
    return True


def create_default_tables():
    if "datasets" not in SCHEMAS:
        create_table("datasets", [("name", "str"), ("task", "str"), ("size", "int")])
    if "models" not in SCHEMAS:
        create_table("models", [("name", "str"), ("version", "str"), ("description", "str")])
    if "experiments" not in SCHEMAS:
        create_table("experiments",
                     [("dataset_id", "int"), ("model_id", "int"), ("accuracy", "float"), ("status", "str")],
                     {"dataset_id": "datasets", "model_id": "models"})


def convert(text, type_name):
    if type_name == "int":
        return int(text)
    if type_name == "float":
        return float(text)
    return text


def compare(x, op, value):
    if op == "=":
        return x == value
    if op == "!=":
        return x != value
    if op == ">":
        return x > value
    if op == "<":
        return x < value
    if op == ">=":
        return x >= value
    if op == "<=":
        return x <= value
    return False


def parse_line(table, line):
    parts = line.strip().split(";")
    row = {}
    for i, (name, type_name) in enumerate(SCHEMAS[table]):
        row[name] = convert(parts[i], type_name)
    return row


def read_all(table):
    rows = []
    path = table + ".txt"
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip() == "":
                continue
            rows.append(parse_line(table, line))
    return rows


def build_index(table):
    path = table + ".txt"
    index = {}
    if os.path.exists(path):
        offset = 0
        with open(path, "rb") as f:
            for line in f:
                if line.strip() != b"":
                    row_id = int(line.split(b";", 1)[0])
                    index[row_id] = offset
                offset += len(line)
    with open(table + ".idx", "w", encoding="utf-8") as f:
        for row_id, offset in index.items():
            f.write(f"{row_id};{offset}\n")
    INDEXES[table] = index
    return index


def load_index_file(table):
    index = {}
    with open(table + ".idx", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip() == "":
                continue
            row_id, offset = line.strip().split(";")
            index[int(row_id)] = int(offset)
    return index


def get_index(table):
    if table in INDEXES:
        return INDEXES[table]
    table_path = table + ".txt"
    index_path = table + ".idx"
    fresh = (os.path.exists(index_path) and os.path.exists(table_path)
             and os.path.getmtime(index_path) >= os.path.getmtime(table_path))
    if fresh:
        INDEXES[table] = load_index_file(table)
    else:
        build_index(table)
    return INDEXES[table]


def find_by_id_scan(table, row_id):
    path = table + ".txt"
    if not os.path.exists(path):
        return None
    key = str(row_id).encode("utf-8")
    with open(path, "rb") as f:
        for line in f:
            if line.split(b";", 1)[0] == key:
                return parse_line(table, line.decode("utf-8"))
    return None


def find_by_id_index(table, row_id):
    index = get_index(table)
    offset = index.get(row_id)
    if offset is None:
        return None
    with open(table + ".txt", "rb") as f:
        f.seek(offset)
        line = f.readline()
    return parse_line(table, line.decode("utf-8"))


def save_all(table, rows):
    with open(table + ".txt", "w", encoding="utf-8") as f:
        for row in rows:
            values = [str(row[name]) for name, _ in SCHEMAS[table]]
            f.write(";".join(values) + "\n")
    build_index(table)


def check_type(value, type_name):
    if type_name == "int" and isinstance(value, int) and not isinstance(value, bool):
        return value
    if type_name == "float" and isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if type_name == "str" and isinstance(value, str) and ";" not in value:
        return value
    return None


def row_exists(table, row_id):
    return find_by_id_index(table, row_id) is not None


def check_foreign_keys(table, column, value):
    parent = FOREIGN_KEYS.get(table, {}).get(column)
    if parent is not None and not row_exists(parent, value):
        print(f"Ошибка: в таблице {parent} нет строки с id={value}")
        return False
    return True


def insert(table, **values):
    schema = SCHEMAS[table]
    needed = [name for name, _ in schema if name != "id"]
    if set(values.keys()) != set(needed):
        print(f"Ошибка: для таблицы {table} нужны поля {needed}")
        return None

    row = {}
    for name, type_name in schema:
        if name == "id":
            continue
        fixed = check_type(values[name], type_name)
        if fixed is None:
            print(f"Ошибка: поле {name} должно быть типа {type_name} (и без символа ;)")
            return None
        if not check_foreign_keys(table, name, fixed):
            return None
        row[name] = fixed

    rows = read_all(table)
    row["id"] = max([r["id"] for r in rows], default=0) + 1
    rows.append(row)
    save_all(table, rows)
    return row["id"]


def matches(row, conditions, logic):
    results = []
    for column, op, value in conditions:
        results.append(compare(row[column], op, value))
    if logic == "AND":
        return all(results)
    return any(results)


def select(table, columns=None, conditions=None, logic="AND"):
    result = []
    for row in read_all(table):
        if conditions and not matches(row, conditions, logic):
            continue
        if columns is None:
            result.append(row)
        else:
            short_row = {}
            for column in columns:
                short_row[column] = row[column]
            result.append(short_row)
    return result


def prefixed(table):
    result = []
    for row in read_all(table):
        new_row = {}
        for key, value in row.items():
            new_row[table + "." + key] = value
        result.append(new_row)
    return result


def inner_join(left_rows, left_column, right_table, right_column):
    right_rows = prefixed(right_table)
    result = []
    for left in left_rows:
        for right in right_rows:
            if left[left_column] == right[right_column]:
                joined = dict(left)
                joined.update(right)
                result.append(joined)
    return result


def update(table, row_id, column, new_value):
    type_name = dict(SCHEMAS[table]).get(column)
    if type_name is None or column == "id":
        print("Ошибка: такое поле нельзя менять")
        return False
    fixed = check_type(new_value, type_name)
    if fixed is None:
        print(f"Ошибка: поле {column} должно быть типа {type_name}")
        return False
    if not check_foreign_keys(table, column, fixed):
        return False

    rows = read_all(table)
    for row in rows:
        if row["id"] == row_id:
            row[column] = fixed
            save_all(table, rows)
            return True
    print("Ошибка: строки с таким id нет")
    return False


def delete(table, row_id):
    for child_table, fks in FOREIGN_KEYS.items():
        for column, parent in fks.items():
            if parent == table:
                for child_row in read_all(child_table):
                    if child_row[column] == row_id:
                        print(f"Ошибка: на эту строку ссылается {child_table} (id={child_row['id']})")
                        return False

    rows = read_all(table)
    new_rows = [row for row in rows if row["id"] != row_id]
    if len(new_rows) == len(rows):
        print("Ошибка: строки с таким id нет")
        return False
    save_all(table, new_rows)
    return True


def show(table):
    for row in read_all(table):
        print(row)


def show_join():
    step1 = inner_join(prefixed("experiments"), "experiments.dataset_id", "datasets", "datasets.id")
    step2 = inner_join(step1, "experiments.model_id", "models", "models.id")
    for row in step2:
        print(row["experiments.id"], row["datasets.name"], row["models.name"],
              row["experiments.accuracy"], row["experiments.status"])


def fill_test_data():
    create_default_tables()
    if len(read_all("datasets")) > 0:
        print("Данные уже есть, ничего не добавляю")
        return

    datasets = [
        ("MNIST", "classification", 70000),
        ("CIFAR-10", "classification", 60000),
        ("Boston", "regression", 506),
        ("Iris", "classification", 150),
        ("Wine", "clustering", 178),
    ]
    models = [
        ("LogReg", "1.0", "Логистическая регрессия"),
        ("Tree", "1.2", "Решающее дерево"),
        ("Forest", "2.0", "Случайный лес"),
        ("SVM", "1.5", "Метод опорных векторов"),
        ("KNN", "1.1", "Метод ближайших соседей"),
    ]
    for name, task, size in datasets:
        insert("datasets", name=name, task=task, size=size)
    for name, version, description in models:
        insert("models", name=name, version=version, description=description)

    for i in range(20):
        dataset_id = i % 5 + 1
        model_id = (i * 2) % 5 + 1
        accuracy = round(0.60 + (i * 7 % 35) / 100, 2)
        status = "running" if i % 4 == 3 else "completed"
        insert("experiments", dataset_id=dataset_id, model_id=model_id, accuracy=accuracy, status=status)
    print("Добавлено: 5 datasets, 5 models, 20 experiments")


def generate_big_data(count):
    create_default_tables()
    dataset_ids = [row["id"] for row in read_all("datasets")]
    model_ids = [row["id"] for row in read_all("models")]
    if len(dataset_ids) == 0 or len(model_ids) == 0:
        print("Ошибка: сначала создайте тестовые данные (пункт 7)")
        return
    if "big_experiments" not in SCHEMAS:
        create_table("big_experiments",
                     [("dataset_id", "int"), ("model_id", "int"), ("accuracy", "float"), ("status", "str")],
                     {"dataset_id": "datasets", "model_id": "models"})
    random.seed(1)
    rows = []
    for i in range(count):
        rows.append({
            "id": i + 1,
            "dataset_id": random.choice(dataset_ids),
            "model_id": random.choice(model_ids),
            "accuracy": round(random.uniform(0.5, 0.99), 2),
            "status": random.choice(["completed", "running", "failed"]),
        })
    save_all("big_experiments", rows)
    print(f"В таблице big_experiments теперь {count} строк")


def benchmark(table, count):
    index = get_index(table)
    if len(index) == 0:
        print("Ошибка: таблица пустая")
        return
    ids = list(index.keys())
    random.seed(2)
    queries = [random.choice(ids) for _ in range(count)]

    start = time.perf_counter()
    for row_id in queries:
        find_by_id_scan(table, row_id)
    scan_time = time.perf_counter() - start

    start = time.perf_counter()
    for row_id in queries:
        find_by_id_index(table, row_id)
    index_time = time.perf_counter() - start

    start = time.perf_counter()
    build_index(table)
    build_time = time.perf_counter() - start

    scan_ms = scan_time / count * 1000
    index_ms = index_time / count * 1000
    lines = [
        f"Таблица: {table}, строк: {len(ids)}, запросов: {count}",
        f"Поиск перебором файла: {scan_ms:.4f} мс на запрос",
        f"Поиск по индексу id->offset: {index_ms:.4f} мс на запрос",
        f"Ускорение: в {scan_ms / index_ms:.1f} раз",
        f"Построение индекса: {build_time * 1000:.1f} мс",
    ]
    for line in lines:
        print(line)
    with open("benchmark.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("Результат сохранён в benchmark.txt")


def file_hash(data):
    return hashlib.sha256(data).hexdigest()


def backup():
    if len(SCHEMAS) == 0:
        print("Ошибка: нет таблиц, копировать нечего")
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, "backup_" + time.strftime("%Y%m%d_%H%M%S") + ".zip")
    file_names = [SCHEMA_FILE] + [table + ".txt" for table in SCHEMAS]
    manifest = []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_name in file_names:
            if not os.path.exists(file_name):
                continue
            with open(file_name, "rb") as f:
                data = f.read()
            archive.writestr(file_name, data)
            manifest.append(file_name + ";" + file_hash(data))
        archive.writestr("manifest.txt", "\n".join(manifest) + "\n")
    print(f"Резервная копия создана: {path} (файлов: {len(manifest)})")
    return path


def list_backups():
    if not os.path.exists(BACKUP_DIR):
        return []
    names = [name for name in os.listdir(BACKUP_DIR) if name.endswith(".zip")]
    names.sort()
    return [os.path.join(BACKUP_DIR, name) for name in names]


def restore(path):
    if not os.path.exists(path):
        print("Ошибка: такого файла нет")
        return False
    contents = {}
    try:
        with zipfile.ZipFile(path) as archive:
            manifest_text = archive.read("manifest.txt").decode("utf-8")
            for line in manifest_text.splitlines():
                if line.strip() == "":
                    continue
                file_name, expected = line.split(";")
                if os.path.basename(file_name) != file_name or not file_name.endswith(".txt"):
                    print(f"Ошибка: недопустимое имя файла в архиве: {file_name}")
                    return False
                data = archive.read(file_name)
                if file_hash(data) != expected:
                    print(f"Ошибка: контрольная сумма файла {file_name} не совпадает, архив повреждён")
                    return False
                contents[file_name] = data
    except (zipfile.BadZipFile, KeyError, ValueError):
        print("Ошибка: архив повреждён или это не резервная копия")
        return False
    if SCHEMA_FILE not in contents:
        print("Ошибка: в архиве нет файла схемы")
        return False

    for table in list(SCHEMAS):
        for extension in (".txt", ".idx"):
            if os.path.exists(table + extension):
                os.remove(table + extension)
    for file_name, data in contents.items():
        with open(file_name, "wb") as f:
            f.write(data)
    INDEXES.clear()
    load_schema()
    print(f"Восстановлено из {path}: таблиц {len(SCHEMAS)}")
    return True


def choose_table():
    name = input(f"Таблица ({' / '.join(SCHEMAS)}): ").strip()
    if name not in SCHEMAS:
        print("Ошибка: нет такой таблицы")
        return None
    return name


def ask_value(column, type_name):
    text = input(f"{column} ({type_name}): ").strip()
    try:
        return convert(text, type_name)
    except ValueError:
        return text


def ask_id():
    text = input("id строки: ").strip()
    if not text.isdigit():
        print("Ошибка: id должен быть числом")
        return None
    return int(text)


def ask_columns(table):
    text = input("Столбцы через запятую (пусто = все): ").strip()
    if text == "":
        return True, None
    columns = [name.strip() for name in text.split(",")]
    names = [name for name, _ in SCHEMAS[table]]
    for column in columns:
        if column not in names:
            print(f"Ошибка: в таблице нет поля {column}")
            return False, None
    return True, columns


def ask_conditions(table):
    count_text = input("Сколько условий (0, 1, 2...): ").strip()
    if not count_text.isdigit():
        print("Ошибка: нужно число")
        return False, None, None
    conditions = []
    for i in range(int(count_text)):
        column = input("Поле: ").strip()
        op = input("Знак (=, !=, >, <, >=, <=): ").strip()
        type_name = dict(SCHEMAS[table]).get(column)
        if type_name is None or op not in COMPARE_SIGNS:
            print("Ошибка: неверное поле или знак")
            return False, None, None
        value = ask_value("значение", type_name)
        if check_type(value, type_name) is None:
            print(f"Ошибка: значение должно быть типа {type_name}")
            return False, None, None
        conditions.append((column, op, value))
    logic = "AND"
    if len(conditions) > 1:
        logic = input("AND или OR: ").strip().upper()
        if logic not in ("AND", "OR"):
            print("Ошибка: нужно AND или OR")
            return False, None, None
    return True, conditions, logic


def ask_create_table():
    name = input("Имя новой таблицы: ").strip()
    text = input("Поля в виде имя:тип через запятую (id добавится сам), например title:str,score:float: ").strip()
    fields = []
    for part in text.split(","):
        pieces = part.strip().split(":")
        if len(pieces) != 2:
            print("Ошибка: поле нужно писать как имя:тип")
            return
        fields.append((pieces[0].strip(), pieces[1].strip()))
    fks_text = input("Внешние ключи в виде поле>таблица через запятую (пусто = нет): ").strip()
    foreign_keys = {}
    if fks_text != "":
        for part in fks_text.split(","):
            pieces = part.strip().split(">")
            if len(pieces) != 2:
                print("Ошибка: внешний ключ нужно писать как поле>таблица")
                return
            foreign_keys[pieces[0].strip()] = pieces[1].strip()
    if create_table(name, fields, foreign_keys):
        print(f"Таблица {name} создана")


def ask_restore():
    backups = list_backups()
    if len(backups) == 0:
        print("Резервных копий нет")
        return
    for i, path in enumerate(backups, start=1):
        print(i, path)
    text = input("Номер копии: ").strip()
    if not text.isdigit() or not 1 <= int(text) <= len(backups):
        print("Ошибка: нет такого номера")
        return
    answer = input("Текущие данные будут заменены. Продолжить? (да/нет): ").strip().lower()
    if answer != "да":
        print("Отменено")
        return
    restore(backups[int(text) - 1])


def menu():
    while True:
        print()
        print("1 - показать таблицу")
        print("2 - добавить строку")
        print("3 - поиск (столбцы, условия AND/OR)")
        print("4 - изменить поле")
        print("5 - удалить строку")
        print("6 - эксперименты с названиями датасета и модели (INNER JOIN)")
        print("7 - создать таблицы задания и тестовые данные")
        print("8 - создать новую таблицу (CREATE TABLE)")
        print("9 - сгенерировать большую таблицу для теста скорости")
        print("10 - найти строку по id (через индекс)")
        print("11 - замер скорости: перебор и индекс")
        print("12 - сделать резервную копию (backup)")
        print("13 - восстановить из резервной копии (restore)")
        print("0 - выход")
        choice = input("Команда: ").strip()

        if choice == "0":
            break

        elif choice == "6":
            show_join()

        elif choice == "7":
            fill_test_data()

        elif choice == "8":
            ask_create_table()

        elif choice == "9":
            count_text = input("Сколько строк (например 10000): ").strip()
            if not count_text.isdigit() or int(count_text) == 0:
                print("Ошибка: нужно число больше нуля")
                continue
            generate_big_data(int(count_text))

        elif choice == "10":
            table = choose_table()
            if table is None:
                continue
            row_id = ask_id()
            if row_id is None:
                continue
            row = find_by_id_index(table, row_id)
            if row is None:
                print("Строки с таким id нет")
            else:
                print(row)

        elif choice == "11":
            table = choose_table()
            if table is None:
                continue
            count_text = input("Сколько запросов (например 1000): ").strip()
            if not count_text.isdigit() or int(count_text) == 0:
                print("Ошибка: нужно число больше нуля")
                continue
            benchmark(table, int(count_text))

        elif choice == "12":
            backup()

        elif choice == "13":
            ask_restore()

        elif choice in ("1", "2", "3", "4", "5"):
            table = choose_table()
            if table is None:
                continue

            if choice == "1":
                show(table)

            elif choice == "2":
                values = {}
                for name, type_name in SCHEMAS[table]:
                    if name != "id":
                        values[name] = ask_value(name, type_name)
                new_id = insert(table, **values)
                if new_id is not None:
                    print("Добавлено, id =", new_id)

            elif choice == "3":
                ok, columns = ask_columns(table)
                if not ok:
                    continue
                ok, conditions, logic = ask_conditions(table)
                if not ok:
                    continue
                for row in select(table, columns, conditions, logic):
                    print(row)

            elif choice == "4":
                row_id = ask_id()
                if row_id is None:
                    continue
                column = input("Какое поле менять: ").strip()
                type_name = dict(SCHEMAS[table]).get(column, "str")
                new_value = ask_value("новое значение", type_name)
                if update(table, row_id, column, new_value):
                    print("Изменено")

            elif choice == "5":
                row_id = ask_id()
                if row_id is None:
                    continue
                if delete(table, row_id):
                    print("Удалено")

        else:
            print("Неизвестная команда")


load_schema()
menu()