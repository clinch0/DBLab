import os

FILE = "datasets.txt"

def select_all():
    rows = []
    if not os.path.exists(FILE):
        return rows
    with open(FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(";")
            rows.append((int(parts[0]), parts[1], parts[2], int(parts[3])))
    return rows


def insert(name, task, size):
    new_id = len(select_all()) + 1
    with open(FILE, "a", encoding="utf-8") as f:
        f.write(f"{new_id};{name};{task};{size}\n")


insert("Тест1", "classification", 1000)
insert("Тест2", "regression", 500)

for row in select_all():
    print(row)