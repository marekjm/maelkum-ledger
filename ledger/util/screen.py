import os
import re


class Screen:
    ANSI_CODE = re.compile("\x1b\[(0|\d+;\d+;\d+)m")

    @staticmethod
    def get_tty_width():
        width = int(os.popen("stty size", "r").read().split()[1])
        if (width % 2) == 1:
            width -= 1
        return width

    @staticmethod
    def strip_ansi(s):
        return Screen.ANSI_CODE.sub("", s)

    def __init__(self, width, columns):
        self._width = width
        self._columns = columns
        self.reset()

    def clear_buffer(self):
        self._buffer = []
        self._column_line = {}
        for i in range(self._columns):
            self._column_line[i] = 0

    def new_line(self):
        self._buffer.append([])
        for _ in range(self._columns):
            self._buffer[-1].append("")

    def reset(self):
        self.clear_buffer()
        self.new_line()

    def max_line(self):
        return max(self._column_line.values())

    def print(self, column, text, line=None):
        if column >= self._columns:
            raise Exception(
                "column {} out of range ({})".format(
                    column,
                    self._columns,
                )
            )

        if line is not None:
            raise Exception("FIXME")
        else:
            line = self._column_line[column]
        self._buffer[line].pop(column)
        self._buffer[line].insert(column, text)
        self._column_line[column] += 1
        if len(self._buffer) <= self.max_line():
            self.new_line()

    def fill(self):
        n = self.max_line()
        for each in self._column_line:
            self._column_line[each] = n

    def empty_line(self):
        self.fill()
        self.new_line()
        n = self.max_line() + 1
        for each in self._column_line:
            self._column_line[each] = n

    def str(self):
        output = []
        column_width = self._width // self._columns
        for buf_line in self._buffer:
            line = ""
            for buf_column in buf_line[:-1]:
                padding = (column_width - len(Screen.strip_ansi(buf_column))) * " "
                line += (buf_column) + padding
            line += buf_line[-1]
            output.append(line)
        return "\n".join(output)
