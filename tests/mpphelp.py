"""
Build a small binary .mpp for tests, in memory.

WHY THIS FILE EXISTS:
======================
The binary importer can only be tested against real MPP14 bytes, and the
one safe way to get them in a repository is to write them here rather than
commit a file produced by Microsoft Project - which would arrive carrying
a real plan somebody else owns, under a licence nobody can state.

What is written is not a mock of the reader. It is a genuine OLE2 compound
document laid out the way MPP14 lays it out - a Props stream carrying the
field map, FixedMeta/FixedData records, VarMeta/Var2Data strings and the
TBkndCons relation block - built with the same pymppwriter helpers the
reader itself uses. A reader that parses this is parsing the real format;
a file whose field map moves the fields would exercise the reader's own
map rather than this builder's choices, which is the point of driving
everything through the map entries below.

Used by tests/test_mpp_importer_bdd.py.
"""

import struct
from datetime import datetime
from typing import Dict, List, Optional

import pymppwriter.blocks as blocks
from pymppwriter.cfb import Storage, write_cfb
from pymppwriter.writer import PRJ, REL_TYPES, CONSTRAINT_TYPES

#: Task record size written below - comfortably over the 100 bytes a real
#: reader treats as a stub row.
RECORD_SIZE = 128

#: Tenths of a minute in one eight-hour day, the count durations use.
TENTHS_PER_DAY = 4800

#: The field map the fixture's Props stream carries. Every fixed field the
#: builder writes is declared here at the offset it is written at, which is
#: how a real file behaves: the layout lives in the file, not the reader.
#: (native id, offset, category)
_FIXED_FIELDS = [
    (86, 0, 0x03),     # UNIQUE_ID u32
    (23, 4, 0x03),     # ID u32
    (160, 36, 0x03),   # PARENT_TASK_UNIQUE_ID u32
    (249, 40, 0x02),   # OUTLINE_LEVEL u16
    (29, 42, 0x03),    # DURATION u32 tenths-of-minute
    (181, 46, 0x02),   # ACTUAL_DURATION_UNITS u16
    (17, 56, 0x02),    # CONSTRAINT_TYPE u16
    (35, 64, 0x13),    # START timestamp
    (36, 68, 0x13),    # FINISH timestamp
    (18, 80, 0x13),    # CONSTRAINT_DATE timestamp
    (25, 88, 0x02),    # PRIORITY u16
    (32, 90, 0x02),    # PERCENT_COMPLETE u16
]

#: The same for the strings, which live in Var2Data - offset 0xFFFF says so.
_VAR_FIELDS = [
    (14, 0x08),        # NAME
    (15, 0x08),        # NOTES
    (16, 0x08),        # WBS
]


def _field_map() -> bytes:
    """The 28-byte field-map entries _FIXED_FIELDS and _VAR_FIELDS declare."""
    entries = []
    for native_id, offset, category in _FIXED_FIELDS:
        entries.append(struct.pack("<IHB5xI4xH6x", 0, offset, 0,
                                   native_id, category))
    for native_id, category in _VAR_FIELDS:
        entries.append(struct.pack("<IHB5xI4xH6x", 0, 0xFFFF, 0,
                                   native_id, category))
    return b"".join(entries)


def _task_record(task: Dict) -> bytes:
    """One FixedData record for the task dict build_mpp14 was given."""
    record = bytearray(RECORD_SIZE)
    struct.pack_into("<I", record, 0, task["uid"])
    struct.pack_into("<I", record, 4, task.get("id", task["uid"]))
    struct.pack_into("<I", record, 36, task.get("parent_uid", 0))
    struct.pack_into("<H", record, 40, task.get("outline_level", 1))
    duration = task.get("duration_days", 0.0)
    struct.pack_into("<I", record, 42,
                     int(round(duration * TENTHS_PER_DAY)))
    struct.pack_into("<H", record, 46, task.get("duration_units", 0))
    constraint = CONSTRAINT_TYPES.get(task.get("constraint"), 0)
    struct.pack_into("<H", record, 56, constraint)
    record[64:68] = blocks.encode_timestamp(task.get("start"))
    record[68:72] = blocks.encode_timestamp(task.get("finish"))
    record[80:84] = blocks.encode_timestamp(task.get("constraint_date"))
    struct.pack_into("<H", record, 88, task.get("priority", 500))
    struct.pack_into("<H", record, 90, task.get("percent_complete", 0))
    return bytes(record)


def _task_streams(tasks: List[Dict]):
    """The four TBkndTask streams for the task list build_mpp14 was given."""
    fixed_data = bytearray()
    meta_items = []
    var_values = []
    for task in tasks:
        meta_items.append(
            struct.pack("<II", 0, len(fixed_data)) + b"\0" * (47 - 8))
        fixed_data += _task_record(task)
        var_values.append((task["uid"], 14,
                           blocks.encode_unicode(task.get("name", ""))))
        if task.get("notes"):
            from pymppwriter.writer import encode_rtf_notes
            var_values.append((task["uid"], 15,
                               encode_rtf_notes(task["notes"])))

    fixed_meta = blocks.build_fixed_meta(
        struct.pack("<IIII", blocks.MAGIC, 0, 0, 0),
        meta_items, len(fixed_data))
    var_meta, var_data = blocks.build_var_blocks(
        struct.pack("<IIIIII", blocks.MAGIC, 0, 0, 0, 0, 0), var_values)
    return fixed_meta, bytes(fixed_data), var_meta, var_data


def _relation_streams(relations: List[Dict]):
    """The TBkndCons streams for the links build_mpp14 was given."""
    fixed_data = bytearray()
    meta_items = []
    for uid, relation in enumerate(relations, start=1):
        meta_items.append(
            struct.pack("<IIH", 0, len(fixed_data), 0))
        # M365 relation layout: type@12, lag@14, lag-units@18
        fixed_data += struct.pack(
            "<IIIHiH", uid,
            relation["pred"], relation["succ"],
            REL_TYPES.get(relation.get("type", "FS"), 1),
            int(round(relation.get("lag_days", 0.0) * TENTHS_PER_DAY)), 0)
    fixed_meta = blocks.build_fixed_meta(
        struct.pack("<IIII", blocks.MAGIC, 0, 0, 0),
        meta_items, len(fixed_data))
    return fixed_meta, bytes(fixed_data)


def build_mpp14(tasks: List[Dict], relations: Optional[List[Dict]] = None,
                title: str = "Fixture Plan",
                project_start: Optional[datetime] = None) -> bytes:
    """
    A complete MPP14 project as bytes, ready to write to a .mpp.

    Each task dict takes: uid, name, outline_level, parent_uid, start,
    finish, duration_days, percent_complete, priority, constraint,
    constraint_date, notes, duration_units. Each relation dict takes:
    pred, succ, type, lag_days.
    """
    props = blocks.build_props(
        struct.pack("<IIII", 0, 0, 0, 0),
        {
            blocks.PROPS_TASK_FIELD_MAP: _field_map(),
            blocks.PROPS_TITLE: blocks.encode_unicode(title),
            blocks.PROPS_PROJECT_START_DATE:
                blocks.encode_timestamp(project_start),
        },
        [blocks.PROPS_TASK_FIELD_MAP, blocks.PROPS_TITLE,
         blocks.PROPS_PROJECT_START_DATE])

    fixed_meta, fixed_data, var_meta, var_data = _task_streams(tasks)

    root = Storage()
    root.set_path(f"{PRJ}/Props", props)
    root.set_path(f"{PRJ}/TBkndTask/FixedMeta", fixed_meta)
    root.set_path(f"{PRJ}/TBkndTask/FixedData", fixed_data)
    root.set_path(f"{PRJ}/TBkndTask/VarMeta", var_meta)
    root.set_path(f"{PRJ}/TBkndTask/Var2Data", var_data)

    if relations:
        cons_meta, cons_data = _relation_streams(relations)
        root.set_path(f"{PRJ}/TBkndCons/FixedMeta", cons_meta)
        root.set_path(f"{PRJ}/TBkndCons/FixedData", cons_data)

    return write_cfb(root)


def write_mpp14(path: str, tasks: List[Dict],
                relations: Optional[List[Dict]] = None,
                title: str = "Fixture Plan",
                project_start: Optional[datetime] = None) -> str:
    """Build the bytes and put them at a path, for the import call's sake."""
    with open(path, "wb") as handle:
        handle.write(build_mpp14(tasks, relations, title, project_start))
    return path
