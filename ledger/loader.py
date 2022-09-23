import datetime
import os
import re


class Location:
    def __init__(self, path, line):
        self.path = path
        self.line = line

    def __str__(self):
        return "{}:{}".format(self.path, self.line + 1)

    def __repr__(self):
        return str(self)


class Line:
    def __init__(self, text, location, by):
        # Text of the line, its literal content.
        self.text = text

        # Location of the chunk of text - path and line number.
        self.location = location  # Location

        # Include path of the line; ie, the chain of include directives that led
        # to the chunk of text being included in the final output.
        self.by = by

    def __str__(self):
        return self.text

    def __repr__(self):
        return "{} by {} = {}".format(
            self.location,
            self.by,
            self.text,
        )


def ingest_impl(out, raw, source_path, by):
    for i, each in enumerate(raw):
        if re.compile(r"^include ").match(each):
            _, included_path = each.split()

            rawer = None
            with open(included_path, "r") as ifstream:
                rawer = ifstream.read().splitlines()

            ingest_impl(out, rawer, included_path, by + (Location(source_path, i),))

            continue

        out.append(
            Line(
                each,
                Location(source_path, i),
                by,
            )
        )


def ingest(source_path, by):
    raw = None
    with open(source_path, "r") as ifstream:
        raw = ifstream.read().splitlines()

    source = []
    ingest_impl(source, raw, source_path, by)

    return source


def load(book_path):
    source_lines = ingest(book_path, by=())
    return list(
        filter(
            lambda each: str(each).strip() and not str(each).strip().startswith("#"),
            source_lines,
        )
    )
