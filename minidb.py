import os
import operator

SCHEMAS = {
    "datasets": [("id", "int"), ("name", "str"), ("task", "str"), ("size", "int")],
    "models": [("id", "int"), ("name", "str"), ("version", "str"), ("description", "str")],
    "experiments": [("id", "int"), ("dataset_id", "int"), ("model_id", "int"),
                    ("accuracy", "float"), ("status", "str")],
}

FOREIGN_KEYS = {
    "experiments": {"dataset_id": "datasets", "model_id": "models"},
}

OPS = {
    "=": operator.eq, "!=": operator.ne,
    ">": operator.gt, "<": operator.lt,
    ">=": operator.ge, "<=": operator.le,
}


def convert(text, type_name):
    if type_name == "int":
        return int(text)
    if type_name == "float":
        return float(text)
    return text


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


def select_where(table, column, op, value):
    result = []
    for row in read_all(table):
        if OPS[op](row[column], value):
            result.append(row)
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
    print(f"{table}")
    for row in read_all(table):
        print(row)

if len(read_all("datasets")) == 0:
    insert("datasets", name="Тест1", task="classification", size=1000)
    insert("datasets", name="Тест2", task="regression", size=500)
    insert("models", name="МодельA", version="1.0", description="Описание модели A")
    insert("models", name="МодельB", version="2.1", description="Описание модели B")
    insert("experiments", dataset_id=1, model_id=1, accuracy=0.91, status="completed")
    insert("experiments", dataset_id=1, model_id=2, accuracy=0.88, status="completed")
    insert("experiments", dataset_id=2, model_id=1, accuracy=0.76, status="running")

show("datasets")
show("models")
show("experiments")

print("Проверки ошибок:")
insert("experiments", dataset_id=99, model_id=1, accuracy=0.5, status="running")
insert("datasets", name="Тест3", task="clustering", size="много")
delete("datasets", 1)