#!/usr/bin/env python3

import datetime
import decimal
import os
import sys

import ledger

# USEFUL CHARACTERS
#
# ≅ U+2245 APPROXIMATELY EQUAL TO
# ≈ U+2248 ALMOST EQUAL TO
# ∾
# ∝
# ⊕
# ⊖
# ⊗
# ⊘
# ⊙
# ⊜
# ∫
# ∗
# ∘
# ∙

def to_impl(stream, fmt, *args, **kwargs):
    stream.write((fmt + '\n').format(*args, **kwargs))

to_stdout = lambda fmt, *args, **kwargs: to_impl(sys.stdout, fmt, *args, **kwargs)
to_stderr = lambda fmt, *args, **kwargs: to_impl(sys.stderr, fmt, *args, **kwargs)

def main(args):
    to_stdout("Maelkum's ledger {} ({})".format(
        ledger.__version__,
        ledger.__commit__,
    ))

    book_main = args[0]
    book_lines = ledger.loader.load(book_main)
    # to_stdout('\n'.join(map(repr, book_lines)))

    book_ir = ledger.parser.parse(book_lines)
    # to_stdout('{} item(s):'.format(len(book_ir)))
    # to_stdout('\n'.join(map(repr, book_ir)))

    def sorting_key(item):
        if isinstance(item, ledger.ir.Transaction_record):
            return item.effective_date()
        return item.timestamp
    book_ir = sorted(book_ir, key = sorting_key)
    # to_stdout('chronologically sorted item(s):'.format(len(book_ir)))
    # to_stdout('\n'.join(map(lambda x: '{} {}'.format(x.timestamp, repr(x)), book_ir)))

    ####

    default_currency = 'EUR'
    accounts = { 'asset': {}, 'liability': {}, 'equity': {}, }
    txs = []

    # First, process configuration to see if there is anything the ledger should
    # be aware of - default currency, budger levels, etc.
    for each in book_ir:
        if type(each) is ledger.ir.Configuration_line:
            if each.key == 'default-currency':
                default_currency = str(each.value)
            elif each.key == 'budget': # FIXME TODO
                pass
            else:
                raise

    # Then, set up accounts to be able to track balances and verify that
    # transactions refer to recognised accounts.
    ledger.book.setup_accounts(accounts, book_ir)

    # Then, process transactions (ie, revenues, expenses, dividends, transfers)
    # to get an accurate picture of balances.
    currency_basket = { 'rates': {}, 'txs': [], }

    book = (book_ir, currency_basket,)

    ledger.book.calculate_balances(accounts, book, default_currency)
    ledger.book.calculate_equity_values(accounts, book, default_currency)

    Screen = ledger.util.screen.Screen
    screen = Screen(Screen.get_tty_width(), 2)

    # Then, prepare and display a report.

    ledger.reporter.report_today((screen, 0), book, default_currency)
    ledger.reporter.report_yesterday((screen, 1), book, default_currency)
    to_stdout(screen.str())
    screen.reset()

    ledger.reporter.report_this_month((screen, 0), book, default_currency)
    ledger.reporter.report_last_month((screen, 1), book, default_currency)
    to_stdout(screen.str())
    screen.reset()

    ledger.reporter.report_this_year((screen, 0), book, default_currency)
    ledger.reporter.report_last_year((screen, 1), book, default_currency)
    to_stdout(screen.str())
    screen.reset()

    ledger.reporter.report_all_time((screen, 1), book, default_currency)
    ledger.reporter.report_total_reserves((screen, 0), accounts, book, default_currency)
    ledger.reporter.report_total_balances((screen, 0), accounts, book, default_currency)
    screen.print(0, '')
    ledger.reporter.report_total_equity((screen, 0), accounts, book, default_currency)
    to_stdout(screen.str())
    screen.reset()

main(sys.argv[1:])
