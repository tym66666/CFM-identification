"""Offline provenance tests; no model, provider, or Identification Core."""
from copy import deepcopy
import hashlib
import unittest

from cfm_id.source_locations import build_catalog, resolve_sources


class SourceLocationTests(unittest.TestCase):
    def test_original_characters_line_endings_and_python_unicode_offsets(self):
        first = "  不是固定两处；🙂原话。\r\n"
        second = "第二段保留 e\u0301 与 é。\n"
        final = "最后一段没有换行。"
        documents = {"研究.txt": first + "\r\n" + second + final}
        before = deepcopy(documents)
        records = list(build_catalog(documents).values())
        self.assertEqual([r["text"] for r in records], [first, second, final])
        self.assertEqual(
            [(r["start"], r["end"]) for r in records],
            [(0, len(first)),
             (len(first) + 2, len(first) + 2 + len(second)),
             (len(first) + 2 + len(second), len(documents["研究.txt"]))],
        )
        # An emoji occupies one Python code point, two UTF-16 code units,
        # and four UTF-8 bytes. Consumers must not confuse these offsets.
        self.assertNotEqual(len(first), len(first.encode("utf-16-le")) // 2)
        self.assertNotEqual(len(first), len(first.encode("utf-8")))
        for record in records:
            self.assertEqual(
                record["text"],
                documents[record["doc_id"]][record["start"]:record["end"]],
            )
            self.assertEqual(
                record["sha256"],
                hashlib.sha256(record["text"].encode("utf-8")).hexdigest(),
            )
            self.assertEqual(
                record["document_sha256"],
                hashlib.sha256(documents["研究.txt"].encode("utf-8")).hexdigest(),
            )
            self.assertRegex(record["source_id"], r"^src_[0-9a-f]{64}$")
        self.assertEqual(documents, before)

    def test_duplicate_lines_and_documents_have_distinct_locators(self):
        text = "没有说明各人的抽签是否独立。\n"
        documents = {"a.txt": text + text, "b.txt": text}
        catalog = build_catalog(documents)
        records = list(catalog.values())
        self.assertEqual(len(catalog), 3)
        self.assertEqual(len({r["source_id"] for r in records}), 3)
        self.assertEqual({r["text"] for r in records}, {text})
        self.assertEqual(records[0]["start"], 0)
        self.assertEqual(records[1]["start"], len(text))
        self.assertEqual(records[2]["doc_id"], "b.txt")
        self.assertEqual(catalog, build_catalog(dict(reversed(list(documents.items())))))

    def test_resolution_preserves_requested_order_and_returns_original_text(self):
        documents = {"a.txt": "原试点最多两处。\n具体概率未知。\r\n"}
        catalog = build_catalog(documents)
        ids = list(reversed(catalog))
        records = resolve_sources(documents, ids)
        self.assertEqual([r["source_id"] for r in records], ids)
        self.assertEqual(records, [catalog[source_id] for source_id in ids])

    def test_any_document_change_invalidates_even_unchanged_line_ids(self):
        documents = {"a.txt": "第一段保持原样。\n第二段不固定人数。\n"}
        old_ids = list(build_catalog(documents))
        changes = [
            "第一段保持原样。\n第二段固定人数。\n",
            "第一段保持原样。\r\n第二段不固定人数。\r\n",
            documents["a.txt"] + "\n",
            " " + documents["a.txt"],
            documents["a.txt"].replace("第二段", "修改后的第二段"),
        ]
        for changed in changes:
            with self.subTest(changed=changed):
                current = {"a.txt": changed}
                self.assertTrue(set(old_ids).isdisjoint(build_catalog(current)))
                for source_id in old_ids:
                    with self.assertRaisesRegex(ValueError, "UNKNOWN_OR_STALE"):
                        resolve_sources(current, [source_id])

    def test_unicode_normalization_is_not_applied(self):
        composed = {"a.txt": "é"}
        decomposed = {"a.txt": "e\u0301"}
        first = list(build_catalog(composed).values())[0]
        second = list(build_catalog(decomposed).values())[0]
        self.assertEqual(first["text"], "é")
        self.assertEqual(second["text"], "e\u0301")
        self.assertEqual(first["end"], 1)
        self.assertEqual(second["end"], 2)
        self.assertNotEqual(first["source_id"], second["source_id"])
        with self.assertRaisesRegex(ValueError, "UNKNOWN_OR_STALE"):
            resolve_sources(decomposed, [first["source_id"]])

    def test_renamed_document_cannot_reuse_old_locator(self):
        documents = {"old.txt": "原文不变。\n"}
        source_id = next(iter(build_catalog(documents)))
        for changed in ({"new.txt": documents["old.txt"]}, {"other.txt": ""}):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError, "UNKNOWN_OR_STALE"):
                    resolve_sources(changed, [source_id])

    def test_changes_to_another_document_do_not_invalidate_this_document(self):
        documents = {"a.txt": "第一份原文。", "b.txt": "第二份原文。"}
        a_id = next(k for k, r in build_catalog(documents).items() if r["doc_id"] == "a.txt")
        changed = {**documents, "b.txt": "第二份修改。"}
        self.assertEqual(resolve_sources(changed, [a_id])[0]["text"], "第一份原文。")

    def test_blank_lines_are_not_records_but_count_in_locations(self):
        documents = {"empty.txt": "", "blank.txt": " \t\r\n\n", "a.txt": "\n  \r\n否定条件不能删。\r"}
        records = list(build_catalog(documents).values())
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["start"], len("\n  \r\n"))
        self.assertEqual(records[0]["text"], "否定条件不能删。\r")
        self.assertEqual(build_catalog({"blank.txt": " \n\t\r\n"}), {})

    def test_unknown_empty_duplicate_and_invalid_id_inputs_are_rejected(self):
        documents = {"a.txt": "原文。\n"}
        source_id = next(iter(build_catalog(documents)))
        for ids in (None, source_id, (), [], [""], [" "], [None], [1],
                    [source_id, source_id], ["src_" + "0" * 64],
                    [source_id, "missing"], [" " + source_id]):
            with self.subTest(ids=ids):
                with self.assertRaises(ValueError):
                    resolve_sources(documents, ids)

    def test_document_types_are_validated_by_both_public_functions(self):
        invalid = (None, [], "text", {}, {1: "text"}, {"": "text"},
                   {" ": "text"}, {"a.txt": None}, {"a.txt": 1},
                   {"a.txt": []}, {"a.txt": {"text": "nested"}})
        for documents in invalid:
            with self.subTest(documents=documents):
                with self.assertRaises(ValueError):
                    build_catalog(documents)
                with self.assertRaises(ValueError):
                    resolve_sources(documents, ["a"])
        for documents in ({"a.txt": "\ud800"}, {"\ud800": "text"}):
            with self.subTest(kind="invalid_utf8"):
                with self.assertRaisesRegex(ValueError, "VALID_UTF8"):
                    build_catalog(documents)

    def test_resolve_rebuilds_catalog_instead_of_trusting_modified_records(self):
        documents = {"a.txt": "没有给定概率。\n"}
        catalog = build_catalog(documents)
        source_id = next(iter(catalog))
        catalog[source_id].update(text="已给定概率。", start=99, sha256="fake")
        resolved = resolve_sources(documents, [source_id])
        self.assertEqual(resolved[0]["text"], documents["a.txt"])
        self.assertEqual(resolved[0]["start"], 0)
        resolved[0]["text"] = "调用者修改返回值"
        self.assertEqual(resolve_sources(documents, [source_id])[0]["text"], documents["a.txt"])


if __name__ == "__main__":
    unittest.main()

