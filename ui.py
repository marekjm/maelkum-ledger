#!/usr/bin/env python3

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


def report_total_reserves(accounts, book, default_currency):
    reserves_default = decimal.Decimal()
    reserves_foreign = decimal.Decimal()
    for _, each in accounts['asset'].items():
        if each['currency'] == default_currency:
            reserves_default += each['balance']
        else:
            pass # FIXME calculate value in default currency

    reserves_total = (reserves_default + reserves_foreign)

    no_of_asset_accounts = len(accounts['asset'].keys())

    fmt = '{} on all {} account(s): {} {}'
    if reserves_foreign:
        fmt += ' (~{:.2f} {}, ~{:.2f} {} in foreign currencies)'

    print(fmt.format(
        ledger.util.colors.colorise(
            ledger.util.colors.COLOR_PERIOD_NAME,
            'Reserve',
        ),
        no_of_asset_accounts,
        ledger.util.colors.colorise_balance(reserves_total),
        default_currency,
    ))

def report_total_balances(accounts, book, default_currency):
    reserves_default = decimal.Decimal()
    reserves_foreign = decimal.Decimal()
    for _, acc in accounts['asset'].items():
        if acc['currency'] == default_currency:
            reserves_default += acc['balance']
        else:
            _, currency_basket = book

            pair = (acc['currency'], default_currency,)
            try:
                rate = currency_basket['rates'][pair]
            except KeyError:
                print(currency_basket)
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
            reserves_foreign += (acc['balance'] * rate)

    reserves_total = (reserves_default + reserves_foreign)

    no_of_accounts = (len(accounts['asset'].keys()) +
        len(accounts['liability'].keys()) +
        len(accounts['equity'].keys()))

    fmt = '{} on all {} account(s): '
    if reserves_foreign:
        fmt += '≈{} {} ({} {} + ≈{} {} in foreign currencies)'
    else:
        fmt += '{} {}'

    print(fmt.format(
        ledger.util.colors.colorise(
            ledger.util.colors.COLOR_PERIOD_NAME,
            'Balance',
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

    ACCOUNT_ASSET_T = 'asset'
    ACCOUNT_LIABILITY_T = 'liability'
    ACCOUNT_EQUITY_T = 'equity'
    ACCOUNT_TYPES = (
        ACCOUNT_ASSET_T,
        ACCOUNT_LIABILITY_T,
        ACCOUNT_EQUITY_T,
    )

    longest_account_name = 0
    for t in ACCOUNT_TYPES:
        for a in accounts[t].keys():
            longest_account_name = max(longest_account_name, len(a))

    for t in ACCOUNT_TYPES:
        for name in sorted(accounts[t].keys()):
            acc = accounts[t][name]

            m = ''

            balance_raw = acc['balance']
            fmt = '  {}: {} {}'
            m += fmt.format(
                name.ljust(longest_account_name),
                ledger.util.colors.colorise_balance(balance_raw, '{:7.2f}'),
                acc['currency'],
            )

            balance_in_default = None
            rate = None
            if acc['currency'] != default_currency and acc['balance']:
                _, currency_basket = book

                pair = (acc['currency'], default_currency,)
                try:
                    rate = currency_basket['rates'][pair]
                except KeyError:
                    print(currency_basket)
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

            print(m)

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

    # First, process configuration to see if there is anything the ledger should
    # be aware of - default currency, budger levels, etc.
    for each in book_ir:
        if type(each) is ledger.ir.Configuration_line:
            pass

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
    for each in book_ir:
        if type(each) is ledger.ir.Balance_record:
            for b in each.accounts:
                kind, name = b.account
                # FIXME report mismatched currencies
                accounts[kind][name]['balance'] = b.value[0]
        if type(each) is ledger.ir.Revenue_tx:
            pass
        elif type(each) is ledger.ir.Expense_tx:
            pass
        elif type(each) is ledger.ir.Transfer_tx:
            pass
        elif type(each) is ledger.ir.Exchange_rates_record:
            for r in each.rates:
                currency_basket['rates'][(str(r.src), str(r.dst),)] = r
        # FIXME dividends

    book = (book_ir, currency_basket,)

    # Then, prepare and display a report.
    report_total_reserves(accounts, book, default_currency)
    report_total_balances(accounts, book, default_currency)

main(sys.argv[1:])
