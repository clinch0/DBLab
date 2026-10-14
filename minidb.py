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


def insert(name, task, size):
    new_id = len(select_all()) + 1
    with open(FILE, "a", encoding="utf-8") as f:
        f.write(f"{new_id};{name};{task};{size}\n")


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


if len(select_all()) == 0:
    insert("Тест1", "classification", 1000)
    insert("Тест2", "regression", 500)
    insert("Тест3", "classification", 2500)
    insert("Тест4", "clustering", 300)

print("Все строки:")
for row in select_all():
    print(row)

print("size > 600:")
for row in select_where("size", ">", 600):
    print(row)

print("task = classification:")
for row in select_where("task", "=", "classification"):
    print(row)

print("size <= 500:")
for row in select_where("size", "<=", 500):
    print(row)