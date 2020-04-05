#!/usr/bin/env python3

import datetime
import decimal
import json
import os
import re
import sys

from ledger.util.colors import (
    colorise_if_possible,
    COLOR_PERIOD_NAME,
    COLOR_DATETIME,
    COLOR_EXPENSES,
    COLOR_REVENUES,
    COLOR_BALANCE,
    COLOR_SPENT_RATIO,
    COLOR_WARNING,
    COLOR_EXCHANGE_RATE,
)
import ledger.util.screen
import ledger.util.math
import ledger.book


OWN_ACCOUNT_T = 0
EXT_ACCOUNT_T = 1
def is_own_account(a):
    mx = lambda k: a.startswith('{}/'.format(k))
    return any(map(mx, ledger.book.ACCOUNT_T))

TX_TRANSFER_T = 'tx'
TX_EXPENSE_T = 'ex'
TX_REVENUE_T = 'rx'

KEYWORD_END = 'end'
KEYWORD_WITH = 'with'
KEYWORD_MATCH = 'match'
KEYWORD_OPEN = 'open'
KEYWORD_SET = 'set'
KEYWORD_BALANCE = 'balance'

ACCEPTED_CURRENCIES = {
    'CHF',
    'CZK',
    'EUR',
    'GBP',
    'JPY',
    'NOK',
    'PLN',
    'USD',
}


class Parser:
    @staticmethod
    def lex_line(text):
        mx = lambda s: text.startswith(s)

        if mx(KEYWORD_OPEN):
            return text.split()
        elif mx(TX_TRANSFER_T) or mx(TX_EXPENSE_T) or mx(TX_REVENUE_T):
            return text.split()
        elif mx('asset:') or (text == 'end') or mx('balance:'):
            return text.split()
        elif mx(KEYWORD_MATCH) or mx(KEYWORD_BALANCE):
            return text.split()
        elif mx(KEYWORD_SET):
            return text.split(maxsplit=2)
        else:
            return [ text ]

    @staticmethod
    def parse_timestamp(s):
        try:
            return datetime.datetime.strptime(s, ledger.book.TIMESTAMP_FORMAT)
        except ValueError:
            return datetime.datetime.strptime(s, ledger.book.DAYSTAMP_FORMAT)
        else:
            raise

    @staticmethod
    def parse(lines, convert = decimal.Decimal):
        book_contents = {
            'accounts': { 'asset': {}, 'liability': {}, 'equity': {}, 'adhoc': {}, },
            'transactions': [],
            'patterns': [],
        }
        patterns = []

        configuration = {}
        groups = []
        current = { 'head': None, 'body': [], 'with': [], }
        add_to = 'body'
        for each in lines:
            if each[0] == KEYWORD_SET:
                configuration[each[1]] = each[2]
                continue

            if each[0] == KEYWORD_END:
                groups.append(current)
                current = { 'head': None, 'body': [], 'with': [], }
                add_to = 'body'
                continue

            if each[0] in (TX_TRANSFER_T, TX_EXPENSE_T, TX_REVENUE_T, KEYWORD_OPEN, KEYWORD_MATCH,
                    KEYWORD_BALANCE):
                current['head'] = each
                continue

            if each[0] == KEYWORD_WITH:
                add_to = 'with'
                continue

            if current:
                current[add_to].append(each)
                continue

        # print('groups:', groups)

        for each in groups:
            head = each['head']
            body = each['body']
            extra = each['with']

            if head[0] == KEYWORD_OPEN:
                account_type = head[3]
                account_name = head[4]
                account_date = head[2]

                balance = list(filter(
                    lambda each: (each[0] == 'balance:'),
                    body,
                ))
                if not balance:
                    raise Exception('{} account {} does not have an opening balance'.format(
                        account_type,
                        account_name,
                    ))
                account_balance, account_currency = (convert(balance[0][1]), balance[0][2])

                if account_currency not in ACCEPTED_CURRENCIES:
                    raise Exception('invalid currency: {}'.format(
                        account_currency,
                    ))

                is_overview = False
                only_if_negative = False
                only_if_positive = False
                is_main = False
                for x in extra:
                    if x[0] == 'overview':
                        is_overview = True
                    elif x[0] == 'only_if_negative':
                        only_if_negative = True
                    elif x[0] == 'only_if_positive':
                        only_if_positive = True
                    elif x[0] == 'main':
                        is_main = True

                if account_name in book_contents['accounts'][account_type]:
                    raise Exception('{} account {}/{} already exists'.format(
                        account_date,
                        account_type,
                        account_name,
                    ))
                book_contents['accounts'][account_type][account_name] = {
                    'opened': Parser.parse_timestamp(account_date),
                    'balance': account_balance,
                    'currency': account_currency,
                    'overview': is_overview,
                    'only_if_negative': only_if_negative,
                    'only_if_positive': only_if_positive,
                    'main': is_main,
                }

            if head[0] == KEYWORD_MATCH:
                transaction_type = head[1]
                accounts = map(lambda a: a[0], body)
                extra = extra
                patterns.append({
                    'what': transaction_type,
                    'accounts': set(accounts),
                    'with': extra,
                })

            if head[0] == KEYWORD_BALANCE:
                # print('=>', head)
                accounts = [
                    ((OWN_ACCOUNT_T, a.rsplit(maxsplit = 2),)
                     if is_own_account(a)
                     else (EXT_ACCOUNT_T, a,))
                    for a
                    in map(lambda x: x[0], body)
                ]
                ts = Parser.parse_timestamp(head[1])
                # FIXME Maybe balances for external accounts are also needed?
                for a in map(lambda a: a[1], filter(lambda a: a[0] == OWN_ACCOUNT_T, accounts)):
                    book_contents['transactions'].append({
                        'type': 'balance',
                        'of': a[0],
                        'value': { 'currency': a[2], 'amount': decimal.Decimal(a[1]), },
                        'timestamp': ts,
                    })
                continue

            if head[0] in (TX_TRANSFER_T, TX_EXPENSE_T, TX_REVENUE_T,):
                # print('=>', head)
                accounts = [
                    ((OWN_ACCOUNT_T, a.rsplit(maxsplit = 2),)
                     if is_own_account(a)
                     else (EXT_ACCOUNT_T, a,))
                    for a
                    in map(lambda x: x[0], body)
                ]

                tx_kind = head[0]
                if tx_kind == TX_EXPENSE_T:
                    source_account = list(filter(
                        lambda a: (a[0] == OWN_ACCOUNT_T),
                        accounts,
                    ))
                    dest_account =  list(filter(
                        lambda a: (a[0] == EXT_ACCOUNT_T),
                        accounts,
                    ))

                    if not source_account:
                        raise Exception('{}: no source account found for expense'.format(
                            head[1],
                        ))
                    source_account = source_account[0][1]

                    if not dest_account:
                        raise Exception('{}: no destination account found for expense'.format(
                            head[1],
                        ))
                    dest_account = dest_account[0][1]


                    currency = source_account[2]
                    if currency not in ACCEPTED_CURRENCIES:
                        raise Exception('invalid currency: {}'.format(
                            currency,
                        ))

                    value = {
                        'currency': currency,
                        'amount': convert(source_account[1]),
                    }
                    source_account = source_account[0]

                    for pat in patterns:
                        if pat['what'] != tx_kind:
                            continue
                        if (source_account in pat['accounts']) or (dest_account in pat['accounts']):
                            extra.extend(pat['with'])

                    book_contents['transactions'].append({
                        'type': 'expense',
                        'source': source_account,
                        'destination': dest_account,
                        'value': value,
                        'tags': [],
                        'with': {},
                    })
                elif tx_kind == TX_REVENUE_T:
                    source_account = list(filter(
                        lambda a: (a[0] == EXT_ACCOUNT_T),
                        accounts,
                    ))
                    dest_account =  list(filter(
                        lambda a: (a[0] == OWN_ACCOUNT_T),
                        accounts,
                    ))

                    if not source_account:
                        raise Exception('{}: no source account found for revenue'.format(
                            head[1],
                        ))
                    source_account = source_account[0][1]

                    if not dest_account:
                        raise Exception('{}: no destination account found for revenue'.format(
                            head[1],
                        ))
                    dest_account = dest_account[0][1]

                    currency = dest_account[2]
                    if currency not in ACCEPTED_CURRENCIES:
                        raise Exception('invalid currency: {}'.format(
                            currency,
                        ))

                    value = {
                        'currency': currency,
                        'amount': convert(dest_account[1]),
                    }
                    dest_account = dest_account[0]

                    for pat in patterns:
                        if pat['what'] != tx_kind:
                            continue
                        if (source_account in pat['accounts']) or (dest_account in pat['accounts']):
                            extra.extend(pat['with'])

                    book_contents['transactions'].append({
                        'type': 'revenue',
                        'source': source_account,
                        'destination': dest_account,
                        'value': value,
                        'tags': [],
                    })
                elif tx_kind == TX_TRANSFER_T:
                    source_account = None
                    dest_account = None

                    if not accounts:
                        raise Exception('{}: no accounts'.format(
                            head[1],
                        ))
                    for x in accounts:
                        if x[0] != OWN_ACCOUNT_T:
                            raise Exception('{}: invalid account for transfer (not owned): {}'.format(
                                head[1],
                                x[1],
                            ))

                    if convert(accounts[0][1][1]) < 0:
                        source_account = accounts[0][1]
                        dest_account = accounts[1][1]
                    else:
                        source_account = accounts[1][1]
                        dest_account = accounts[0][1]

                    # FIXME Make a function for accessing currency to avoid
                    # this specify-none then check then assign code.
                    source_currency = None
                    dest_currency = None

                    try:
                        source_currency = source_account[2]
                    except IndexError:
                        raise Exception('{}: no currency on transfer from {}'.format(
                            head[1],
                            source_account[0],
                        ))
                    if source_currency not in ACCEPTED_CURRENCIES:
                        raise Exception('invalid currency: {}'.format(
                            source_currency,
                        ))

                    dest_currency = dest_account[2]
                    if dest_currency not in ACCEPTED_CURRENCIES:
                        raise Exception('invalid currency: {}'.format(
                            dest_currency,
                        ))

                    if source_currency == dest_currency and source_account[1] != ('-' + dest_account[1]):
                        raise Exception('amounts are not balanced: {} {} != {} {}'.format(
                            source_account[1], source_currency,
                            dest_account[1], dest_currency,
                        ))

                    value = {
                        'src': {
                            'currency': source_currency,
                            'amount': convert(source_account[1]),
                        },
                        'dst': {
                            'currency': dest_currency,
                            'amount': convert(dest_account[1]),
                        },
                    }
                    source_account = source_account[0]
                    dest_account = dest_account[0]

                    for pat in patterns:
                        if pat['what'] != tx_kind:
                            continue
                        if (source_account in pat['accounts']) or (dest_account in pat['accounts']):
                            extra.extend(pat['with'])

                    book_contents['transactions'].append({
                        'type': 'transfer',
                        'source': source_account,
                        'destination': dest_account,
                        'value': value,
                        'tags': [],
                    })
                    if source_currency != dest_currency:
                        rate = list(
                            map(lambda x: x[0],
                            filter(lambda x: x[0].startswith('rate:'),
                            extra
                        )))
                        rate = (rate[0].split() if rate else None)
                        if rate is None:
                            raise Exception('{}: no rate on transfer from {} to {}'.format(
                                head[1],
                                source_account,
                                dest_account,
                            ))
                        try:
                            rate = (tuple(rate[1].split('/')), decimal.Decimal(rate[2]),)
                        except IndexError:
                            raise Exception('{}: invalid rate on transfer from {} to {}'.format(
                                head[1],
                                source_account,
                                dest_account,
                            ))

                        multiplier = (100 if value['dst']['currency'] == 'JPY' else 1)
                        op = None
                        if value['src']['currency'] == ledger.book.DEFAULT_CURRENCY:
                            op = lambda a, b: a / b
                        else:
                            op = lambda a, b: a * b
                        src_value_converted = op(-1 * value['src']['amount'], (rate[1] / multiplier))
                        dst_value_converted = value['dst']['amount']
                        ok = ledger.util.math.diff_less_than(
                            src_value_converted,
                            dst_value_converted,
                            ledger.book.ALLOWED_CONVERSION_DIFFERENCE,
                        )
                        if not ok:
                            raise Exception(
                                    '{}: discrepancy in transfer from {} to {}: {} {} != {} {} (== {:.4f} {})'.format(
                                head[1],
                                source_account,
                                dest_account,
                                value['src']['amount'],
                                value['src']['currency'],
                                value['dst']['amount'],
                                value['dst']['currency'],
                                src_value_converted,
                                value['dst']['currency'],
                            ))

                        book_contents['transactions'][-1]['rate'] = rate

                    if source_account.startswith('adhoc/'):
                        kind, name = source_account.split('/')
                        book_contents['accounts'][kind][name] = {
                            'opened': Parser.parse_timestamp(head[1]),
                            'balance': decimal.Decimal('0.00'),
                            'currency': source_currency,
                            'overview': True,
                            'only_if_negative': False,
                            'only_if_positive': False,
                            'main': False,
                        }
                    if dest_account.startswith('adhoc/'):
                        kind, name = dest_account.split('/')
                        book_contents['accounts'][kind][name] = {
                            'opened': Parser.parse_timestamp(head[1]),
                            'balance': decimal.Decimal('0.00'),
                            'currency': dest_currency,
                            'overview': True,
                            'only_if_negative': False,
                            'only_if_positive': False,
                            'main': False,
                        }

                book_contents['transactions'][-1]['timestamp'] = Parser.parse_timestamp(head[1])

                for each in extra:
                    if each[0].startswith('tags:'):
                        tags = list(filter(bool, map(
                            lambda a: a.strip(),
                            each[0].split(':', 1)[1].split(',')
                        )))
                        book_contents['transactions'][-1]['tags'].extend(tags)
                    elif each[0].startswith('calculate_as:'):
                        value = each[0].split(':', 1)[1].strip()
                        amount, currency = value.split()
                        amount = decimal.Decimal(amount)
                        book_contents['transactions'][-1]['with']['calculate_as'] = {
                            'amount': amount,
                            'currency': currency,
                        }

        for k, v in configuration.items():
            if k == 'budget':
                limit, kind = v.split()
                book_contents['budgets'] = {
                    '_target': (kind, decimal.Decimal(limit),),
                }

        book_contents['transactions'] = sorted(book_contents['transactions'], key = lambda each: each['timestamp'],)

        return book_contents

__version__ = '0.0.1'

def main(args):
    book_path = args[0]
    if book_path == '--version':
        print("Maelkum's ledger {}".format(__version__))
        exit(0)

    book_text = []
    with open(book_path, 'r') as ifstream:
        book_text = ifstream.read().splitlines()

        tmp = []
        for each in book_text:
            if each.startswith('include'):
                _, path = each.split(maxsplit = 1)
                with open(os.path.join('.', path), 'r') as ifstream:
                    tmp.extend(ifstream.readlines())
                continue
            tmp.append(each)
        book_text = tmp

        book_text = list(filter(lambda x: bool(x), map(lambda x: x.strip(), book_text)))
        book_text = [ each for each in book_text if (not each.startswith('#')) ]
        book_text = [ Parser.lex_line(each) for each in book_text ]

    book_contents = Parser.parse(book_text)

    screen = ledger.util.screen.Screen(
        width = ledger.util.screen.Screen.get_tty_width(),
        columns = 2,
    )
    ledger.book.Book.report(
        screen = screen,
        book = book_contents,
    )


main(sys.argv[1:])
