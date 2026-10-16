import os

SCHEMAS = {
    "datasets": [("id", "int"), ("name", "str"), ("task", "str"), ("size", "int")],
    "models": [("id", "int"), ("name", "str"), ("version", "str"), ("description", "str")],
    "experiments": [("id", "int"), ("dataset_id", "int"), ("model_id", "int"),
                    ("accuracy", "float"), ("status", "str")],
}

FOREIGN_KEYS = {
    "experiments": {"dataset_id": "datasets", "model_id": "models"},
}

COMPARE_SIGNS = ("=", "!=", ">", "<", ">=", "<=")


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


def read_all(table):
    rows = []
    path = table + ".txt"
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip() == "":
                continue
            parts = line.strip().split(";")
            row = {}
            for i, (name, type_name) in enumerate(SCHEMAS[table]):
                row[name] = convert(parts[i], type_name)
            rows.append(row)
    return rows


def save_all(table, rows):
    with open(table + ".txt", "w", encoding="utf-8") as f:
        for row in rows:
            values = [str(row[name]) for name, _ in SCHEMAS[table]]
            f.write(";".join(values) + "\n")


def check_type(value, type_name):
    if type_name == "int" and isinstance(value, int) and not isinstance(value, bool):
        return value
    if type_name == "float" and isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if type_name == "str" and isinstance(value, str) and ";" not in value:
        return value
    return None


def row_exists(table, row_id):
    for row in read_all(table):
        if row["id"] == row_id:
            return True
    return False


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
    if len(read_all("datasets")) > 0:
        print("Данные уже есть, ничего не добавляю")
        return
    insert("datasets", name="Тест1", task="classification", size=1000)
    insert("datasets", name="Тест2", task="regression", size=500)
    insert("models", name="МодельA", version="1.0", description="Описание модели A")
    insert("models", name="МодельB", version="2.1", description="Описание модели B")
    insert("experiments", dataset_id=1, model_id=1, accuracy=0.91, status="completed")
    insert("experiments", dataset_id=1, model_id=2, accuracy=0.88, status="completed")
    insert("experiments", dataset_id=2, model_id=1, accuracy=0.76, status="running")
    print("Тестовые данные добавлены")


def choose_table():
    name = input("Таблица (datasets / models / experiments): ").strip()
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


def menu():
    while True:
        print()
        print("1 - показать таблицу")
        print("2 - добавить строку")
        print("3 - поиск (столбцы, условия AND/OR)")
        print("4 - изменить поле")
        print("5 - удалить строку")
        print("6 - эксперименты с названиями датасета и модели (INNER JOIN)")
        print("7 - заполнить тестовыми данными")
        print("0 - выход")
        choice = input("Команда: ").strip()

        if choice == "0":
            break

        elif choice == "6":
            show_join()

        elif choice == "7":
            fill_test_data()

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


menu()