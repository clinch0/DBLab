import os
import zipfile

import pytest

import minidb


def reset_state():
    minidb.SCHEMAS.clear()
    minidb.FOREIGN_KEYS.clear()
    minidb.INDEXES.clear()


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reset_state()
    yield
    reset_state()


def test_default_tables_created():
    minidb.create_default_tables()
    assert set(minidb.SCHEMAS) == {"datasets", "models", "experiments"}
    assert minidb.FOREIGN_KEYS["experiments"] == {"dataset_id": "datasets", "model_id": "models"}
    assert os.path.exists("schema.txt")


def test_fill_test_data_counts():
    minidb.fill_test_data()
    assert len(minidb.read_all("datasets")) == 5
    assert len(minidb.read_all("models")) == 5
    assert len(minidb.read_all("experiments")) == 20


def test_insert_gives_increasing_ids():
    minidb.create_default_tables()
    first = minidb.insert("datasets", name="A", task="classification", size=10)
    second = minidb.insert("datasets", name="B", task="regression", size=20)
    assert (first, second) == (1, 2)


def test_insert_wrong_type_rejected():
    minidb.create_default_tables()
    assert minidb.insert("datasets", name="A", task="t", size="много") is None
    assert minidb.read_all("datasets") == []


def test_insert_semicolon_rejected():
    minidb.create_default_tables()
    assert minidb.insert("datasets", name="A;B", task="t", size=1) is None
    assert minidb.read_all("datasets") == []


def test_insert_missing_field_rejected():
    minidb.create_default_tables()
    assert minidb.insert("datasets", name="A") is None
    assert minidb.read_all("datasets") == []


def test_float_field_accepts_int():
    minidb.fill_test_data()
    new_id = minidb.insert("experiments", dataset_id=1, model_id=1, accuracy=1, status="completed")
    assert minidb.find_by_id_index("experiments", new_id)["accuracy"] == 1.0


def test_insert_with_missing_dataset_rejected():
    minidb.fill_test_data()
    assert minidb.insert("experiments", dataset_id=99, model_id=1, accuracy=0.5, status="running") is None
    assert len(minidb.read_all("experiments")) == 20


def test_insert_with_missing_model_rejected():
    minidb.fill_test_data()
    assert minidb.insert("experiments", dataset_id=1, model_id=99, accuracy=0.5, status="running") is None
    assert len(minidb.read_all("experiments")) == 20


def test_update_to_missing_foreign_key_rejected():
    minidb.fill_test_data()
    assert minidb.update("experiments", 1, "dataset_id", 99) is False
    assert minidb.find_by_id_index("experiments", 1)["dataset_id"] == 1


def test_delete_parent_with_children_blocked():
    minidb.fill_test_data()
    assert minidb.delete("datasets", 1) is False
    assert minidb.find_by_id_index("datasets", 1) is not None


def test_delete_parent_after_children_removed():
    minidb.fill_test_data()
    for row in minidb.select("experiments", conditions=[("dataset_id", "=", 1)]):
        assert minidb.delete("experiments", row["id"]) is True
    assert minidb.delete("datasets", 1) is True
    assert minidb.find_by_id_index("datasets", 1) is None


def test_update_changes_value():
    minidb.fill_test_data()
    assert minidb.update("datasets", 3, "size", 999) is True
    assert minidb.find_by_id_index("datasets", 3)["size"] == 999


def test_update_rejects_bad_requests():
    minidb.fill_test_data()
    assert minidb.update("datasets", 3, "id", 50) is False
    assert minidb.update("datasets", 99, "size", 1) is False
    assert minidb.update("datasets", 3, "size", "много") is False
    assert minidb.update("datasets", 3, "nope", 1) is False
    assert minidb.find_by_id_index("datasets", 3)["size"] == 506


def test_delete_removes_row():
    minidb.fill_test_data()
    assert minidb.delete("experiments", 5) is True
    assert minidb.find_by_id_index("experiments", 5) is None
    assert len(minidb.read_all("experiments")) == 19


def test_delete_unknown_id_returns_false():
    minidb.fill_test_data()
    assert minidb.delete("experiments", 999) is False
    assert len(minidb.read_all("experiments")) == 20


def test_new_id_continues_after_max():
    minidb.fill_test_data()
    minidb.delete("experiments", 10)
    new_id = minidb.insert("experiments", dataset_id=1, model_id=1, accuracy=0.5, status="running")
    assert new_id == 21


def test_select_columns():
    minidb.fill_test_data()
    rows = minidb.select("datasets", columns=["name", "size"])
    assert len(rows) == 5
    assert all(set(row) == {"name", "size"} for row in rows)


@pytest.mark.parametrize("op, expected", [("=", 1), ("!=", 4), (">", 2), ("<", 2), (">=", 3), ("<=", 3)])
def test_select_operators(op, expected):
    minidb.fill_test_data()
    rows = minidb.select("datasets", conditions=[("size", op, 506)])
    assert len(rows) == expected


def test_select_and():
    minidb.fill_test_data()
    rows = minidb.select("datasets",
                         conditions=[("task", "=", "classification"), ("size", "<", 1000)],
                         logic="AND")
    assert [row["name"] for row in rows] == ["Iris"]


def test_select_or():
    minidb.fill_test_data()
    rows = minidb.select("datasets",
                         conditions=[("task", "=", "clustering"), ("size", "=", 506)],
                         logic="OR")
    assert {row["name"] for row in rows} == {"Wine", "Boston"}


def test_inner_join():
    minidb.fill_test_data()
    step1 = minidb.inner_join(minidb.prefixed("experiments"), "experiments.dataset_id",
                              "datasets", "datasets.id")
    step2 = minidb.inner_join(step1, "experiments.model_id", "models", "models.id")
    assert len(step2) == 20
    first = step2[0]
    assert first["experiments.id"] == 1
    assert first["datasets.name"] == "MNIST"
    assert first["models.name"] == "LogReg"


def test_data_and_schema_survive_restart():
    minidb.fill_test_data()
    minidb.create_table("notes", [("text", "str")])
    minidb.insert("notes", text="hello")
    reset_state()
    minidb.load_schema()
    assert set(minidb.SCHEMAS) == {"datasets", "models", "experiments", "notes"}
    assert len(minidb.read_all("datasets")) == 5
    assert minidb.read_all("notes")[0]["text"] == "hello"
    assert minidb.FOREIGN_KEYS["experiments"]["dataset_id"] == "datasets"


def test_create_table_rejects_bad_definitions():
    minidb.create_default_tables()
    assert minidb.create_table("datasets", [("x", "int")]) is False
    assert minidb.create_table("bad name", [("x", "int")]) is False
    assert minidb.create_table("t1", [("x", "date")]) is False
    assert minidb.create_table("t2", []) is False
    assert minidb.create_table("t3", [("x", "int"), ("x", "str")]) is False
    assert minidb.create_table("t4", [("id", "int")]) is False
    assert minidb.create_table("t5", [("x", "int")], {"x": "missing"}) is False
    assert minidb.create_table("t6", [("x", "str")], {"x": "datasets"}) is False
    assert set(minidb.SCHEMAS) == {"datasets", "models", "experiments"}


def test_new_table_foreign_key_works():
    minidb.fill_test_data()
    assert minidb.create_table("runs", [("experiment_id", "int"), ("note", "str")],
                               {"experiment_id": "experiments"}) is True
    assert minidb.insert("runs", experiment_id=999, note="x") is None
    assert minidb.insert("runs", experiment_id=1, note="x") == 1
    assert minidb.delete("experiments", 1) is False


def test_index_lookup_matches_scan():
    minidb.fill_test_data()
    minidb.generate_big_data(300)
    for row_id in (1, 2, 150, 299, 300):
        by_index = minidb.find_by_id_index("big_experiments", row_id)
        assert by_index["id"] == row_id
        assert by_index == minidb.find_by_id_scan("big_experiments", row_id)
    assert minidb.find_by_id_index("big_experiments", 301) is None
    assert minidb.find_by_id_scan("big_experiments", 301) is None


def test_index_is_rebuilt_when_file_missing():
    minidb.fill_test_data()
    assert os.path.exists("datasets.idx")
    os.remove("datasets.idx")
    minidb.INDEXES.clear()
    assert minidb.find_by_id_index("datasets", 3)["name"] == "Boston"
    assert os.path.exists("datasets.idx")


def test_index_updated_after_delete():
    minidb.create_table("notes", [("text", "str")])
    for text in ("a", "b", "c"):
        minidb.insert("notes", text=text)
    minidb.delete("notes", 2)
    assert minidb.find_by_id_index("notes", 2) is None
    assert minidb.find_by_id_index("notes", 3)["text"] == "c"


def test_backup_and_restore():
    minidb.fill_test_data()
    path = minidb.backup()
    assert os.path.exists(path)
    minidb.insert("datasets", name="Extra", task="regression", size=1)
    assert len(minidb.read_all("datasets")) == 6
    assert minidb.restore(path) is True
    assert len(minidb.read_all("datasets")) == 5
    assert minidb.find_by_id_index("datasets", 6) is None


def test_restore_rejects_tampered_archive():
    minidb.fill_test_data()
    path = minidb.backup()
    tampered = os.path.join("backups", "tampered.zip")
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(tampered, "w") as target:
        for name in source.namelist():
            data = source.read(name)
            if name == "datasets.txt":
                data = data + b"99;Fake;classification;1\n"
            target.writestr(name, data)
    before = minidb.read_all("datasets")
    assert minidb.restore(tampered) is False
    assert minidb.read_all("datasets") == before


def test_restore_rejects_missing_and_broken_files():
    minidb.fill_test_data()
    assert minidb.restore("nope.zip") is False
    with open("broken.zip", "w", encoding="utf-8") as f:
        f.write("это не архив")
    assert minidb.restore("broken.zip") is False
    assert len(minidb.read_all("datasets")) == 5


def test_restore_rejects_unsafe_file_names():
    minidb.fill_test_data()
    with zipfile.ZipFile("evil.zip", "w") as archive:
        archive.writestr("manifest.txt", "../evil.txt;abc\n")
        archive.writestr("evil.txt", "x")
    assert minidb.restore("evil.zip") is False
    assert len(minidb.read_all("datasets")) == 5