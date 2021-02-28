#!/usr/bin/env python3

import os
import sys

import ledger


def main(args):
    print("Maelkum's ledger {} ({})".format(
        ledger.__version__,
        ledger.__commit__,
    ))

    book_main = args[0]
    book_contents = ledger.loader.load(book_main)
    print('\n'.join(map(repr, book_contents)))

main(sys.argv[1:])
