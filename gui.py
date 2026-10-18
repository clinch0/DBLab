import io
import tkinter as tk
from contextlib import redirect_stdout
from tkinter import ttk, messagebox, simpledialog, filedialog

import minidb

SIGNS = ["=", "!=", ">", "<", ">=", "<="]
SHOW_LIMIT = 1000


def run(function, *args, **kwargs):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = function(*args, **kwargs)
    return result, buffer.getvalue().strip()


def to_value(text, type_name):
    try:
        return minidb.convert(text.strip(), type_name)
    except ValueError:
        return text.strip()


class App:
    def __init__(self, root):
        self.root = root
        root.title("MiniDB")
        root.geometry("1050x600")
        self.table = tk.StringVar()
        self.current_filter = None
        self.build_top()
        self.build_filter()
        self.status = tk.Label(root, anchor="w")
        self.status.pack(fill="x", side="bottom", padx=8, pady=2)
        self.build_buttons()
        self.build_tree()
        self.refresh_tables()

    def build_top(self):
        frame = tk.Frame(self.root)
        frame.pack(fill="x", padx=8, pady=6)
        tk.Label(frame, text="Таблица:").pack(side="left")
        self.combo = ttk.Combobox(frame, textvariable=self.table, state="readonly", width=18)
        self.combo.pack(side="left", padx=6)
        self.combo.bind("<<ComboboxSelected>>", lambda event: self.on_table_change())
        tk.Button(frame, text="Тестовые данные", command=self.fill_test_data).pack(side="left", padx=4)
        tk.Button(frame, text="Новая таблица", command=self.new_table).pack(side="left", padx=4)
        tk.Button(frame, text="JOIN экспериментов", command=self.show_join).pack(side="left", padx=4)
        tk.Button(frame, text="Backup", command=self.backup).pack(side="left", padx=4)
        tk.Button(frame, text="Restore", command=self.restore).pack(side="left", padx=4)

    def build_filter(self):
        frame = tk.Frame(self.root)
        frame.pack(fill="x", padx=8, pady=2)
        tk.Label(frame, text="Фильтр:").pack(side="left")
        self.field_boxes = []
        self.filters = []
        self.logic = tk.StringVar(value="AND")
        for index in range(2):
            field = tk.StringVar()
            op = tk.StringVar(value="=")
            value = tk.StringVar()
            box = ttk.Combobox(frame, textvariable=field, state="readonly", width=14)
            box.pack(side="left", padx=2)
            ttk.Combobox(frame, textvariable=op, values=SIGNS, state="readonly", width=4).pack(side="left", padx=2)
            tk.Entry(frame, textvariable=value, width=14).pack(side="left", padx=2)
            self.field_boxes.append(box)
            self.filters.append((field, op, value))
            if index == 0:
                ttk.Combobox(frame, textvariable=self.logic, values=["AND", "OR"],
                             state="readonly", width=5).pack(side="left", padx=6)
        tk.Button(frame, text="Найти", command=self.apply_filter).pack(side="left", padx=6)
        tk.Button(frame, text="Сбросить", command=self.reset_filter).pack(side="left")

    def build_buttons(self):
        frame = tk.Frame(self.root)
        frame.pack(fill="x", side="bottom", padx=8, pady=6)
        tk.Button(frame, text="Добавить", width=14, command=self.add_row).pack(side="left", padx=4)
        tk.Button(frame, text="Изменить поле", width=14, command=self.edit_row).pack(side="left", padx=4)
        tk.Button(frame, text="Удалить", width=14, command=self.delete_row).pack(side="left", padx=4)
        tk.Button(frame, text="Найти по id (индекс)", width=20, command=self.find_by_id).pack(side="left", padx=4)

    def build_tree(self):
        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree = ttk.Treeview(frame, show="headings", selectmode="browse")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def current_table(self):
        table = self.table.get()
        if table == "":
            messagebox.showinfo("MiniDB", "Таблиц пока нет. Нажмите «Тестовые данные» или «Новая таблица».")
            return None
        return table

    def refresh_tables(self, select=None):
        names = list(minidb.SCHEMAS)
        self.combo["values"] = names
        if select in names:
            self.table.set(select)
        elif self.table.get() not in names:
            self.table.set(names[0] if names else "")
        self.on_table_change()

    def on_table_change(self):
        for field, op, value in self.filters:
            field.set("")
            op.set("=")
            value.set("")
        self.logic.set("AND")
        self.current_filter = None
        table = self.table.get()
        names = [name for name, _ in minidb.SCHEMAS[table]] if table in minidb.SCHEMAS else []
        for box in self.field_boxes:
            box["values"] = names
        self.reload()

    def reload(self):
        table = self.table.get()
        self.tree.delete(*self.tree.get_children())
        if table not in minidb.SCHEMAS:
            self.tree.configure(columns=())
            self.status.config(text="Нет таблиц")
            return
        names = [name for name, _ in minidb.SCHEMAS[table]]
        if self.current_filter:
            conditions, logic = self.current_filter
            rows = minidb.select(table, None, conditions, logic)
        else:
            rows = minidb.read_all(table)
        self.tree.configure(columns=names)
        for name in names:
            self.tree.heading(name, text=name)
            self.tree.column(name, width=130, anchor="w")
        for row in rows[:SHOW_LIMIT]:
            self.tree.insert("", "end", values=tuple(row[name] for name in names))
        shown = min(len(rows), SHOW_LIMIT)
        self.status.config(text=f"Таблица {table}: показано {shown} из {len(rows)} строк")

    def apply_filter(self):
        table = self.current_table()
        if table is None:
            return
        types = dict(minidb.SCHEMAS[table])
        conditions = []
        for field, op, value in self.filters:
            column = field.get()
            text = value.get().strip()
            if column == "" and text == "":
                continue
            if column == "" or text == "":
                messagebox.showerror("Ошибка", "В условии нужно заполнить и поле, и значение")
                return
            typed = to_value(text, types[column])
            if minidb.check_type(typed, types[column]) is None:
                messagebox.showerror("Ошибка", f"Значение для поля {column} должно быть типа {types[column]}")
                return
            conditions.append((column, op.get(), typed))
        self.current_filter = (conditions, self.logic.get()) if conditions else None
        self.reload()

    def reset_filter(self):
        for field, op, value in self.filters:
            field.set("")
            op.set("=")
            value.set("")
        self.logic.set("AND")
        self.current_filter = None
        self.reload()

    def selected_id(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("MiniDB", "Сначала выберите строку в таблице")
            return None
        return int(self.tree.item(selection[0])["values"][0])

    def ask_form(self, title, labels):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.transient(self.root)
        window.grab_set()
        entries = {}
        for index, label in enumerate(labels):
            tk.Label(window, text=label, anchor="w").grid(row=index, column=0, sticky="w", padx=8, pady=4)
            entry = tk.Entry(window, width=40)
            entry.grid(row=index, column=1, padx=8, pady=4)
            entries[label] = entry
        result = {}

        def confirm():
            for label, entry in entries.items():
                result[label] = entry.get()
            window.destroy()

        buttons = tk.Frame(window)
        buttons.grid(row=len(labels), column=0, columnspan=2, pady=8)
        tk.Button(buttons, text="OK", width=10, command=confirm).pack(side="left", padx=4)
        tk.Button(buttons, text="Отмена", width=10, command=window.destroy).pack(side="left", padx=4)
        window.wait_window()
        return result or None

    def add_row(self):
        table = self.current_table()
        if table is None:
            return
        schema = [(name, type_name) for name, type_name in minidb.SCHEMAS[table] if name != "id"]
        labels = [f"{name} ({type_name})" for name, type_name in schema]
        answer = self.ask_form(f"Добавить в {table}", labels)
        if answer is None:
            return
        values = {}
        for (name, type_name), label in zip(schema, labels):
            values[name] = to_value(answer[label], type_name)
        new_id, message = run(minidb.insert, table, **values)
        if new_id is None:
            messagebox.showerror("Ошибка", message or "Не удалось добавить строку")
        else:
            self.reload()

    def edit_row(self):
        table = self.current_table()
        if table is None:
            return
        row_id = self.selected_id()
        if row_id is None:
            return
        types = dict(minidb.SCHEMAS[table])
        names = [name for name in types if name != "id"]
        column = simpledialog.askstring("Изменить поле", "Какое поле изменить?\n" + ", ".join(names))
        if column is None:
            return
        column = column.strip()
        if column not in names:
            messagebox.showerror("Ошибка", f"В таблице нет поля {column}, которое можно менять")
            return
        current = minidb.find_by_id_index(table, row_id)
        text = simpledialog.askstring("Изменить поле", f"Новое значение для {column}:",
                                      initialvalue=str(current[column]))
        if text is None:
            return
        ok, message = run(minidb.update, table, row_id, column, to_value(text, types[column]))
        if ok:
            self.reload()
        else:
            messagebox.showerror("Ошибка", message or "Не удалось изменить строку")

    def delete_row(self):
        table = self.current_table()
        if table is None:
            return
        row_id = self.selected_id()
        if row_id is None:
            return
        if not messagebox.askyesno("Удаление", f"Удалить строку с id={row_id} из таблицы {table}?"):
            return
        ok, message = run(minidb.delete, table, row_id)
        if ok:
            self.reload()
        else:
            messagebox.showerror("Ошибка", message or "Не удалось удалить строку")

    def find_by_id(self):
        table = self.current_table()
        if table is None:
            return
        row_id = simpledialog.askinteger("Поиск по id", f"id в таблице {table}:")
        if row_id is None:
            return
        row = minidb.find_by_id_index(table, row_id)
        if row is None:
            messagebox.showinfo("Поиск по id", "Строки с таким id нет")
        else:
            messagebox.showinfo("Поиск по id", "\n".join(f"{key}: {value}" for key, value in row.items()))

    def fill_test_data(self):
        ok, message = run(minidb.fill_test_data)
        messagebox.showinfo("Тестовые данные", message)
        self.refresh_tables()

    def new_table(self):
        labels = ["Имя таблицы", "Поля (имя:тип через запятую)", "Внешние ключи (поле>таблица, можно пусто)"]
        answer = self.ask_form("Новая таблица", labels)
        if answer is None:
            return
        fields = []
        for part in answer[labels[1]].split(","):
            pieces = part.strip().split(":")
            if len(pieces) != 2:
                messagebox.showerror("Ошибка", "Поле нужно писать как имя:тип, например title:str")
                return
            fields.append((pieces[0].strip(), pieces[1].strip()))
        foreign_keys = {}
        if answer[labels[2]].strip() != "":
            for part in answer[labels[2]].split(","):
                pieces = part.strip().split(">")
                if len(pieces) != 2:
                    messagebox.showerror("Ошибка", "Внешний ключ нужно писать как поле>таблица")
                    return
                foreign_keys[pieces[0].strip()] = pieces[1].strip()
        name = answer[labels[0]].strip()
        ok, message = run(minidb.create_table, name, fields, foreign_keys)
        if ok:
            self.refresh_tables(select=name)
        else:
            messagebox.showerror("Ошибка", message or "Не удалось создать таблицу")

    def show_join(self):
        for table in ("experiments", "datasets", "models"):
            if table not in minidb.SCHEMAS:
                messagebox.showerror("Ошибка", "Сначала создайте тестовые данные")
                return
        step1 = minidb.inner_join(minidb.prefixed("experiments"), "experiments.dataset_id",
                                  "datasets", "datasets.id")
        step2 = minidb.inner_join(step1, "experiments.model_id", "models", "models.id")
        window = tk.Toplevel(self.root)
        window.title("INNER JOIN: experiments + datasets + models")
        window.geometry("760x420")
        columns = ["experiments.id", "datasets.name", "models.name", "experiments.accuracy", "experiments.status"]
        tree = ttk.Treeview(window, columns=columns, show="headings")
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=140, anchor="w")
        tree.pack(fill="both", expand=True)
        for row in step2[:SHOW_LIMIT]:
            tree.insert("", "end", values=tuple(row[column] for column in columns))

    def backup(self):
        path, message = run(minidb.backup)
        if path is None:
            messagebox.showerror("Ошибка", message or "Не удалось создать копию")
        else:
            messagebox.showinfo("Backup", f"Резервная копия создана:\n{path}")

    def restore(self):
        path = filedialog.askopenfilename(title="Выберите резервную копию", initialdir="backups",
                                          filetypes=[("Резервные копии", "*.zip")])
        if not path:
            return
        if not messagebox.askyesno("Restore", "Текущие данные будут заменены. Продолжить?"):
            return
        ok, message = run(minidb.restore, path)
        if ok:
            messagebox.showinfo("Restore", message)
        else:
            messagebox.showerror("Ошибка", message or "Не удалось восстановить данные")
        self.refresh_tables()


def main():
    minidb.load_schema()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()