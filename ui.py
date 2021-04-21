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

ACCOUNT_ASSET_T = 'asset'
ACCOUNT_LIABILITY_T = 'liability'
ACCOUNT_EQUITY_T = 'equity'
ACCOUNT_TYPES = (
    ACCOUNT_ASSET_T,
    ACCOUNT_LIABILITY_T,
    ACCOUNT_EQUITY_T,
)

def report_total_impl(period, account_types, accounts, book, default_currency):
    reserves_default = decimal.Decimal()
    reserves_foreign = decimal.Decimal()
    for t in account_types:
        for name, acc in accounts[t].items():
            if acc['currency'] == default_currency:
                reserves_default += acc['balance']
            else:
                _, currency_basket = book

                pair = (acc['currency'], default_currency,)
                rev = False
                try:
                    rate = currency_basket['rates'][pair]
                except KeyError:
                    try:
                        pair = (default_currency, acc['currency'],)
                        rate = currency_basket['rates'][pair]
                        rev = True
                    except KeyError:
                        fmt = 'no currency pair {}/{} for {} account named {}'
                        sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                            ledger.util.colors.colorise(
                                'white',
                                acc['~'].text[0].location,
                            ),
                            ledger.util.colors.colorise(
                                'red',
                                'error',
                            ),
                            ledger.util.colors.colorise(
                                'white',
                                acc['currency'],
                            ),
                            ledger.util.colors.colorise(
                                'white',
                                default_currency,
                            ),
                            t,
                            ledger.util.colors.colorise(
                                'white',
                                name,
                            ),
                        ))
                        exit(1)

                rate = rate.rate
                if rev:
                    reserves_foreign += (acc['balance'] / rate)
                else:
                    reserves_foreign += (acc['balance'] * rate)

    reserves_total = (reserves_default + reserves_foreign)

    no_of_accounts = 0
    for t in account_types:
        no_of_accounts += len(accounts[t].keys())

    fmt = '{} on all {} account(s): '
    if reserves_foreign:
        fmt += '≈{} {} ({} {} + ≈{} {} in foreign currencies)'
    else:
        fmt += '{} {}'

    to_stdout(fmt.format(
        ledger.util.colors.colorise(
            ledger.util.colors.COLOR_PERIOD_NAME,
            period,
        ),
        no_of_accounts,
        ledger.util.colors.colorise_balance(
            reserves_total if reserves_foreign else reserves_default),
        default_currency,
        ledger.util.colors.colorise_balance(
            reserves_default if reserves_foreign else reserves_total),
        default_currency,
        ledger.util.colors.colorise_balance(reserves_foreign),
        default_currency,
    ))

def report_total_reserves(accounts, book, default_currency):
    report_total_impl(
        'Reserve',
        (ACCOUNT_ASSET_T, ACCOUNT_LIABILITY_T,),
        accounts,
        book,
        default_currency,
    )

def report_total_balances(accounts, book, default_currency):
    report_total_impl(
        'Balance',
        ACCOUNT_TYPES,
        accounts,
        book,
        default_currency,
    )

    longest_account_name = 0
    for t in ACCOUNT_TYPES:
        for a in accounts[t].keys():
            longest_account_name = max(longest_account_name, len(a))

    def sort_main_on_top(accounts):
        keys = sorted(accounts.keys())
        keys = sorted(
            keys,
            key = lambda k: ('main' in accounts[k]['tags']),
            reverse = True,
        )
        return keys
    for t in ACCOUNT_TYPES:
        for name in sort_main_on_top(accounts[t]):
            acc = accounts[t][name]

            m = ''

            balance_raw = acc['balance']
            fmt = '  {}: {} {}'
            m += fmt.format(
                name.ljust(longest_account_name),
                ledger.util.colors.colorise_balance(balance_raw, '{:8.2f}'),
                acc['currency'],
            )

            balance_in_default = None
            rate = None
            if acc['currency'] != default_currency and acc['balance']:
                _, currency_basket = book

                pair = (acc['currency'], default_currency,)
                rev = False
                try:
                    rate = currency_basket['rates'][pair]
                except KeyError:
                    try:
                        pair = (default_currency, acc['currency'],)
                        rate = currency_basket['rates'][pair]
                        rev = True
                    except KeyError:
                        fmt = 'no currency pair {}/{} for {} account named {}'
                        sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                            ledger.util.colors.colorise(
                                'white',
                                acc['~'].text[0].location,
                            ),
                            ledger.util.colors.colorise(
                                'red',
                                'error',
                            ),
                            ledger.util.colors.colorise(
                                'white',
                                acc['currency'],
                            ),
                            ledger.util.colors.colorise(
                                'white',
                                default_currency,
                            ),
                            t,
                            ledger.util.colors.colorise(
                                'white',
                                name,
                            ),
                        ))
                        exit(1)

                rate = rate.rate
                if rev:
                    balance_in_default = (balance_raw / rate)
                else:
                    balance_in_default = (balance_raw * rate)

                # FIXME display % gain/loss depending on exchange rate
                fmt = ' ≅ {} {} at {} {}/{} rate'
                m += fmt.format(
                    ledger.util.colors.colorise_balance(
                        (balance_in_default or 0),
                        '{:7.2f}',
                    ),
                    default_currency,
                    ledger.util.colors.colorise(
                        ledger.util.colors.COLOR_EXCHANGE_RATE,
                        rate,
                    ),
                    acc['currency'],
                    default_currency,
                )

            to_stdout(m)

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
    for each in book_ir:
        if type(each) is ledger.ir.Account_record:
            kind = each.kind
            name = each.name

            if name in accounts[kind]:
                sys.stderr.write('{}: error: {} account `{}` already exists\n'.format(
                    each.text[0].location,
                    kind,
                    name,
                ))
                sys.stderr.write('note: {} account `{}` is defined at {}\n'.format(
                    kind,
                    name,
                    accounts[kind][name]['~'].text[0].location,
                ))
                exit(1)

            accounts[kind][name] = {
                'balance': each.balance[0],
                'currency': each.balance[1],
                'created': each.timestamp,
                'tags': each.tags,
                '~': each,
            }

    # Then, process transactions (ie, revenues, expenses, dividends, transfers)
    # to get an accurate picture of balances.
    currency_basket = { 'rates': {}, 'txs': [], }
    def ensure_currency_match(accounts, a):
        kind, name = a.account
        account_currency = accounts[kind][name]['currency']
        tx_currency = a.value[1]
        if account_currency != tx_currency:
            fmt = 'mismatched currency: account {} is in {}, but value is in {}'
            sys.stdout.write(('{}: {}: ' + fmt + '\n').format(
                ledger.util.colors.colorise(
                    'white',
                    a.text.location,
                ),
                ledger.util.colors.colorise(
                    'red',
                    'error',
                ),
                ledger.util.colors.colorise(
                    'white',
                    '{}/{}'.format(kind, name),
                ),
                ledger.util.colors.colorise(
                    'light_green',
                    account_currency,
                ),
                ledger.util.colors.colorise(
                    'red_1',
                    tx_currency,
                ),
            ))
            exit(1)
    this_moment_in_time = datetime.datetime.now()
    for each in book_ir:
        if type(each) is ledger.ir.Configuration_line:
            continue
        if type(each) is ledger.ir.Account_record:
            continue

        if each.effective_date() > this_moment_in_time:
            continue

        if type(each) is ledger.ir.Balance_record:
            for b in each.accounts:
                ensure_currency_match(accounts, a)
                kind, name = b.account
                # FIXME report mismatched currencies
                accounts[kind][name]['balance'] = b.value[0]
        if type(each) is ledger.ir.Revenue_tx:
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
        elif type(each) is ledger.ir.Expense_tx:
            for a in each.ins:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
        elif type(each) is ledger.ir.Transfer_tx:
            for a in each.ins:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
        elif type(each) is ledger.ir.Exchange_rates_record:
            for r in each.rates:
                currency_basket['rates'][(str(r.src), str(r.dst),)] = r
        # FIXME dividends

    book = (book_ir, currency_basket,)

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
    to_stdout(screen.str())
    screen.reset()

    report_total_reserves(accounts, book, default_currency)
    report_total_balances(accounts, book, default_currency)

main(sys.argv[1:])
