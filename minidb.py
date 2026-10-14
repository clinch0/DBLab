import os

FILE = "datasets.txt"

def select_all():
    rows = []
    if not os.path.exists(FILE):
        return rows
    with open(FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(";")
            rows.append({
                "id": int(parts[0]),
                "name": parts[1],
                "task": parts[2],
                "size": int(parts[3]),
            })
    return rows


def save_all(rows):
    with open(FILE, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(f"{row['id']};{row['name']};{row['task']};{row['size']}\n")


def insert(name, task, size):
    rows = select_all()
    if len(rows) == 0:
        new_id = 1
    else:
        new_id = max(row["id"] for row in rows) + 1
    with open(FILE, "a", encoding="utf-8") as f:
        f.write(f"{new_id};{name};{task};{size}\n")
    return new_id


def select_where(column, op, value):
    result = []
    for row in select_all():
        x = row[column]
        if op == "=" and x == value:
            result.append(row)
        elif op == "!=" and x != value:
            result.append(row)
        elif op == ">" and x > value:
            result.append(row)
        elif op == "<" and x < value:
            result.append(row)
        elif op == ">=" and x >= value:
            result.append(row)
        elif op == "<=" and x <= value:
            result.append(row)
    return result


def update(row_id, column, new_value):
    rows = select_all()
    found = False
    for row in rows:
        if row["id"] == row_id:
            row[column] = new_value
            found = True
    if found:
        save_all(rows)
    else:
        print("Ошибка: строки с таким id нет")
    return found


def delete(row_id):
    rows = select_all()
    new_rows = [row for row in rows if row["id"] != row_id]
    if len(new_rows) == len(rows):
        print("Ошибка: строки с таким id нет")
        return False
    save_all(new_rows)
    return True


if len(select_all()) == 0:
    insert("Тест1", "classification", 1000)
    insert("Тест2", "regression", 500)
    insert("Тест3", "classification", 2500)
    insert("Тест4", "clustering", 300)

print("Было:")
for row in select_all():
    print(row)

update(2, "size", 999)
delete(4)

print("Стало:")
for row in select_all():
    print(row)

insert("Тест5", "regression", 100)

print("Стало 2:")
for row in select_all():
    print(row)

delete(3)
insert("Тест6", "classification", 2000)

print("Стало 3:")
for row in select_all():
    print(row)