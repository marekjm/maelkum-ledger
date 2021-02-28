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
    book_lines = ledger.loader.load(book_main)
    print('\n'.join(map(repr, book_lines)))

    book_ir = ledger.parser.parse(book_lines)
    print('{} item(s):'.format(len(book_ir)))
    print('\n'.join(map(repr, book_ir)))

    book_ir = sorted(book_ir, key = lambda each: each.timestamp)
    print('chronologically sorted item(s):'.format(len(book_ir)))
    print('\n'.join(map(repr, book_ir)))

    ####

    default_currency = 'EUR'
    accounts = { 'asset': {}, 'liability': {}, 'equity': {}, }
    txs = []

    for each in book_ir:
        if type(each) is ledger.ir.Account_record:
            kind = each.kind
            name = each.name
            accounts[kind][name] = {
                'balance': each.balance[0],
                'currency': each.balance[1],
                'created': each.timestamp,
                'tags': each.tags,
            }

    print('Balance on {} asset account(s):'.format(len(accounts['asset'].keys())))
    for name in sorted(accounts['asset'].keys()):
        acc = accounts['asset'][name]
        print('    {}  {:.2f} {}'.format(
            name,
            acc['balance'],
            acc['currency'],
        ))


main(sys.argv[1:])
