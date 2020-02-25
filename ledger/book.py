import datetime
import decimal
import json


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
import ledger.util.math


TIMESTAMP_FORMAT      = '%Y-%m-%dT%H:%M'
TIMESTAMP_ZERO_FORMAT = '%Y-%m-%dT00:00'
DAYSTAMP_FORMAT       = '%Y-%m-%d'
THIS_MONTH_FORMAT     = '%Y-%m-01T00:00'
THIS_YEAR_FORMAT      = '%Y-01-01T00:00'
LAST_YEAR_DAY_FORMAT  = '%Y-12-31T23:59'

DEFAULT_CURRENCY   = 'PLN'
SPREAD             = decimal.Decimal('0.88742')
ALLOWED_CONVERSION_DIFFERENCE = decimal.Decimal('0.005')

DISPLAY_IMBALANCES = True
DISPLAY_ALL_IMBALANCES = False

ACCOUNT_ASSET_T = 'asset'
ACCOUNT_LIABILITY_T = 'liability'
ACCOUNT_EQUITY_T = 'equity'
ACCOUNT_ADHOC_T = 'adhoc'
ACCOUNT_T = (
    ACCOUNT_ASSET_T,
    ACCOUNT_LIABILITY_T,
    ACCOUNT_EQUITY_T,
    ACCOUNT_ADHOC_T,
)
def is_own_account(a):
    mx = lambda k: a.startswith('{}/'.format(k))
    return any(map(mx, ACCOUNT_T))


class Book:
    @staticmethod
    def output_table(expenses, revenues, column, include_percentage = False):
        p = lambda t: Book.screen.print(column = column, text = t)

        if (not expenses) and (not revenues):
            p('  No transactions.')
            return

        total_expenses = abs(sum(map(lambda each:
            (each['value'].get('in_default_currency') or each['value']['amount']),
            expenses
        )))
        total_revenues = sum(map(lambda each: each['value']['amount'], revenues))
        total_balance = (total_revenues - total_expenses)
        padding = ('' if total_balance >= 0 else ' ')

        field_length = max(
            len('{:.2f}'.format(total_expenses)),
            len('{:.2f}'.format(total_revenues)),
        )

        if len(expenses) > 1:
            min_expense = min(map(lambda each: abs(each['value']['amount']), expenses))
            max_expense = max(map(lambda each: abs(each['value']['amount']), expenses))
            mean_expense = ledger.util.math.mean(list(map(
                lambda each: abs(each['value']['amount']), expenses)))
            median_expense = ledger.util.math.median(list(map(
                lambda each: abs(each['value']['amount']), expenses)))
            p('  Expenses range: {:.2f} - {:.2f} {}'.format(min_expense, max_expense, DEFAULT_CURRENCY))
            if mean_expense != median_expense:
                p('  Mean expense:   {:.2f} {}'.format(mean_expense, DEFAULT_CURRENCY))
            p('  Median expense: {:.2f} {}'.format(median_expense, DEFAULT_CURRENCY))
            p('    ----')

        if expenses:
            p('  Expenses:   {}{} {}'.format(
                padding,
                colorise_if_possible(
                    COLOR_EXPENSES,
                    '{{:{}.2f}}'.format(field_length).format(total_expenses)
                ),
                DEFAULT_CURRENCY,
            ))
        if revenues:
            p('  Revenues:   {}{} {}'.format(
                padding,
                colorise_if_possible(
                    COLOR_REVENUES,
                    '{{:{}.2f}}'.format(field_length).format(total_revenues)
                ),
                DEFAULT_CURRENCY,
            ))
        if revenues and expenses:
            name_net_income = 'Net income:'
            name_net_loss   = 'Net loss:  '
            p('  {name} {value} {currency}'.format(
                name = (name_net_income if (total_balance >= 0.0) else name_net_loss),
                value = colorise_if_possible(
                    COLOR_BALANCE(total_balance),
                    '{{:{}.2f}}'.format(field_length + len(padding)).format(total_balance)
                ),
                currency = DEFAULT_CURRENCY,
            ))
        if include_percentage:
            p('    ----')
            percentage_spent = decimal.Decimal('100.0')
            if total_revenues != 0:
                percentage_spent = (total_expenses / total_revenues) * 100
            p('  Expenses are {}% of revenues.'.format(
                colorise_if_possible(
                    COLOR_SPENT_RATIO(percentage_spent),
                    '{:.2f}'.format(percentage_spent),
                )
            ))

            DEFICIT_THRESHOLD = 100
            if percentage_spent > DEFICIT_THRESHOLD:
                p('  Deficit is {:.4f}% of revenues, or {:.2f} {}.'.format(
                    (percentage_spent - DEFICIT_THRESHOLD),
                    (total_expenses - total_revenues),
                    DEFAULT_CURRENCY,
                ))
                p('  Revenues covered about {:.4f}% of expenses.'.format(
                    (total_revenues / total_expenses) * 100,
                ))

    @staticmethod
    def report_single_day_impl(book, single_day, single_day_name, column):
        expenses = []
        revenues = []
        for each in book['transactions']:
            if single_day.date() != each['timestamp'].date():
                continue

            if each['type'] == 'expense':
                if each['value']['currency'] != DEFAULT_CURRENCY:
                    c = each['value']['currency']
                    r = book['currency_basket'][(c, DEFAULT_CURRENCY)]['rates']['buy']['weighted']
                    in_default_currency = (each['value']['amount'] * r)
                    each['value']['in_default_currency'] = in_default_currency
                expenses.append(each)
            elif each['type'] == 'revenue':
                revenues.append(each)

        Book.screen.print(column = column, text = '{} ({})'.format(
            colorise_if_possible(COLOR_PERIOD_NAME, single_day_name),
            colorise_if_possible(COLOR_DATETIME, single_day.strftime(DAYSTAMP_FORMAT)),
        ))
        Book.output_table(expenses, revenues, column)

    @staticmethod
    def report_today(book, column):
        today = datetime.datetime.strptime(
            datetime.datetime.now().strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        Book.report_single_day_impl(book, today, 'Today', column)

    @staticmethod
    def report_yesterday(book, column):
        yesterday = datetime.datetime.strptime(
            (datetime.datetime.now() - datetime.timedelta(days = 1)).strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        Book.report_single_day_impl(book, yesterday, 'Yesterday', column)

    @staticmethod
    def report_period_impl(book, period_begin, period_end, period_name, column, table_opts = {}):
        expenses = []
        revenues = []
        for each in book['transactions']:
            too_early = (each['timestamp'].date() < period_begin.date())
            too_late = (each['timestamp'].date() > period_end.date())
            if too_early or too_late:
                continue

            if each['type'] == 'expense':
                if each['value']['currency'] != DEFAULT_CURRENCY:
                    c = each['value']['currency']
                    r = book['currency_basket'][(c, DEFAULT_CURRENCY)]['rates']['buy']['weighted']
                    in_default_currency = (each['value']['amount'] * r)
                    each['value']['in_default_currency'] = in_default_currency
                expenses.append(each)
            elif each['type'] == 'revenue':
                revenues.append(each)

        Book.screen.print(column = column, text = '{} ({} to {})'.format(
            colorise_if_possible(COLOR_PERIOD_NAME, period_name),
            colorise_if_possible(COLOR_DATETIME, period_begin.strftime(DAYSTAMP_FORMAT)),
            colorise_if_possible(COLOR_DATETIME, period_end.strftime(DAYSTAMP_FORMAT)),
        ))
        Book.output_table(expenses, revenues, column, **table_opts)

        return (expenses, revenues)

    @staticmethod
    def report_last_7_days(book, column):
        today = datetime.datetime.strptime(
            datetime.datetime.now().strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        last_week = datetime.datetime.strptime(
            (datetime.datetime.now() - datetime.timedelta(days = 7)).strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        Book.report_period_impl(book, last_week, today, 'Last 7 days', column)

    @staticmethod
    def report_a_month_impl(book, first_day, last_day, name, column):
        expenses, revenues = Book.report_period_impl(book, first_day, last_day, name, column, {
            'include_percentage': True,
        })

        if not expenses:
            return expenses, revenues

        diff = (last_day - first_day)
        total_expenses = abs(sum(
            map(lambda each: each['value']['amount'],
            filter(lambda each: each['value']['currency'] == DEFAULT_CURRENCY,
            expenses
        ))))
        daily_average = (total_expenses / (diff.days or 1))
        Book.screen.print(column = column, text = '  Average daily expense is {:.2f} {}.'.format(
            daily_average,
            DEFAULT_CURRENCY,
        ))

        daily_median = {}
        x = first_day
        while x <= last_day:
            daily_median[x.strftime(DAYSTAMP_FORMAT)] = decimal.Decimal()
            x += datetime.timedelta(days = 1)
        for each in expenses:
            # FIXME Account for expenses in non-default currency.
            if each['value']['currency'] != DEFAULT_CURRENCY:
                continue
            daily_median[each['timestamp'].strftime(DAYSTAMP_FORMAT)] += each['value']['amount']
        daily_median = ledger.util.math.median(sorted(map(abs, daily_median.values())))
        Book.screen.print(column = column, text = '  Median daily expense is {:.2f} {}.'.format(
            daily_median,
            DEFAULT_CURRENCY,
        ))
        return expenses, revenues

    @staticmethod
    def report_this_month(book, column):
        today = datetime.datetime.strptime(
            datetime.datetime.now().strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        this_month = datetime.datetime.strptime(
            datetime.datetime.now().strftime(THIS_MONTH_FORMAT),
            TIMESTAMP_FORMAT,
        )
        expenses, revenues = Book.report_a_month_impl(book, this_month, today, 'This month', column)
        total_expenses = sum(
            map(lambda each: each['value']['amount'],
            filter(lambda each: each['value']['currency'] == DEFAULT_CURRENCY,
            expenses
        )))
        total_revenues = sum(
            map(lambda each: each['value']['amount'],
            filter(lambda each: each['value']['currency'] == DEFAULT_CURRENCY,
            revenues
        )))

        spending_target = book.get('budgets', {}).get('_target')
        if spending_target is not None:
            last_day_of_this_month = None
            if today.month == 12:
                last_day_of_this_month = datetime.datetime(
                    year = today.year + 1,
                    month = 1,
                    day = 1,
                )
            else:
                last_day_of_this_month = datetime.datetime(
                    year = today.year,
                    month = today.month + 1,
                    day = 1,
                )
            last_day_of_this_month = last_day_of_this_month - datetime.timedelta(days = 1)
            days_left_in_this_month = (last_day_of_this_month - today).days + 1
            available_budgeted_funds = decimal.Decimal()
            if spending_target[0] == '%':
                target_percentage = (spending_target[1] / 100)
                available_budgeted_funds = (total_revenues * target_percentage) - abs(total_expenses)
            elif spending_target[0] == '$':
                available_budgeted_funds = spending_target[1] - total_expenses
            available_budgeted_funds_per_day = (available_budgeted_funds / days_left_in_this_month)
            Book.screen.print(column = column, text = '  Daily expense cap to meet budget: {} {}'.format(
                colorise_if_possible(
                    COLOR_BALANCE(available_budgeted_funds_per_day),
                    '{:.2f}'.format(available_budgeted_funds_per_day),
                ),
                DEFAULT_CURRENCY,
            ))

    @staticmethod
    def report_last_month(book, column):
        last_day = datetime.datetime.strptime(
            datetime.datetime.now().strftime(THIS_MONTH_FORMAT),
            THIS_MONTH_FORMAT,
        ) - datetime.timedelta(days = 1)
        first_day = datetime.datetime.strptime(
            last_day.strftime(THIS_MONTH_FORMAT),
            THIS_MONTH_FORMAT,
        )
        Book.report_a_month_impl(book, first_day, last_day, 'Last month', column)

    @staticmethod
    def report_this_year(book, column):
        today = datetime.datetime.strptime(
            datetime.datetime.now().strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        this_year = datetime.datetime.strptime(
            datetime.datetime.now().strftime(THIS_YEAR_FORMAT),
            TIMESTAMP_FORMAT,
        )
        Book.report_period_impl(book, this_year, today, 'This year', column, {
            'include_percentage': True,
        })

    @staticmethod
    def report_last_year(book, column):
        this_year = datetime.datetime.now().year
        first_day = datetime.datetime.strptime(
            datetime.datetime(
                year = this_year - 1,
                month = 1,
                day = 1,
            ).strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        last_day = datetime.datetime.strptime(
            datetime.datetime(
                year = this_year - 1,
                month = 12,
                day = 31,
            ).strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        Book.report_period_impl(book, first_day, last_day, 'Last year', column, {
            'include_percentage': True,
        })

    @staticmethod
    def report_total(book, column):
        today = datetime.datetime.strptime(
            datetime.datetime.now().strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        first = today
        if book['transactions']:
            first = Book.first_recorded_transaction(book)['timestamp']
        Book.report_period_impl(book, first, today, 'All time', column, {
            'include_percentage': True,
        })

    @staticmethod
    def first_recorded_transaction(book):
        return sorted(
            book['transactions'],
            key = lambda each: each['timestamp']
        )[0]

    @staticmethod
    def last_recorded_transaction(book):
        return sorted(
            book['transactions'],
            key = lambda each: each['timestamp'],
            reverse = True,
        )[0]

    @staticmethod
    def no_of_accounts(book):
        a = book['accounts']
        return (
              len(list(a.get('asset', {}).keys()))
            + len(list(a.get('liability', {}).keys()))
            + len(list(a.get('equity', {}).keys()))
        )

    @staticmethod
    def get_main_account(book):
        a = book['accounts']

        for kind in ('asset', 'liability', 'equity',):
            for k, v in a[kind].items():
                if v.get('main', False):
                    return '{}/{}'.format(kind, k)
        return 'asset/{}'.format(sorted(
            a['asset'].items(), key = lambda each: each[1]['opened'])[0][0])

    @staticmethod
    def account_names(book, overview = True):
        a = book['accounts']

        flt_if_overview = lambda each: ((overview and each[1].get('overview', False)) or (not overview))
        def flt_if_negative(each):
            if 'if_negative' not in each[1]:
                return True
            if each[1]['if_negative'] == False:
                return True
            return False
        flt = lambda seq: filter(flt_if_negative, filter(flt_if_overview, seq))

        key = lambda each: each[0]
        return (
              list(map(key, flt(a.get('asset', {}).items())))
            + list(map(key, flt(a.get('liability', {}).items())))
            + list(map(key, flt(a.get('equity', {}).items())))
        )

    @staticmethod
    def account_values(book):
        a = book['accounts']
        return (
              list(map(lambda each: each['balance'], a.get('asset', {}).values()))
            + list(map(lambda each: each['balance'], a.get('liability', {}).values()))
            + list(map(lambda each: each['balance'], a.get('equity', {}).values()))
        )

    @staticmethod
    def report_balance_impl(book, kind):
        asset_overview = dict(filter(lambda each: each[1].get('overview', False),
            book['accounts'][kind].items()))
        if not asset_overview:
            return

        key_length = max(map(len, Book.account_names(book)))
        value_length = max(list(map(lambda each: len('{:.2f}'.format(each)),
            Book.account_values(book))))

        for k, v in book['accounts'][kind].items():
            if not v.get('overview', False):
                continue

            only_if_negative = v.get('only_if_negative', False)
            only_if_positive = v.get('only_if_positive', False)
            balance = v['balance']
            if only_if_negative and balance >= 0:
                continue
            if only_if_positive and balance <= 0:
                continue
            if kind == ACCOUNT_ADHOC_T and balance == 0:
                continue

            message = '  {{:{}}}: {{}} {{}}'.format(key_length, value_length).format(
                k,
                colorise_if_possible(
                    COLOR_BALANCE(v['balance']),
                    '{{:{}.2f}}'.format(value_length).format(v['balance']),
                ),
                v['currency'],
            )
            if v['currency'] != DEFAULT_CURRENCY:
                rate = decimal.Decimal()
                in_default_currency = decimal.Decimal()
                key = (v['currency'], DEFAULT_CURRENCY)

                if key in book['currency_basket']:
                    rate = book['currency_basket'][key]['rates']['buy']['weighted']
                    in_default_currency = v['in_default_currency']
                if in_default_currency:
                    r = (in_default_currency * SPREAD)
                    message += ' ~ {} {} at {} {}/{} buying rate'.format(
                        colorise_if_possible(
                            COLOR_BALANCE(r),
                            '{:7.2f}'.format(r),
                        ),
                        DEFAULT_CURRENCY,
                        colorise_if_possible(
                            COLOR_EXCHANGE_RATE,
                            '{:.4f}'.format(rate),
                        ),
                        v['currency'],
                        DEFAULT_CURRENCY,
                    )
            print(message)

    @staticmethod
    def report_asset_balance(book):
        Book.report_balance_impl(book, ACCOUNT_ASSET_T)

    @staticmethod
    def report_liability_balance(book):
        Book.report_balance_impl(book, ACCOUNT_LIABILITY_T)

    @staticmethod
    def report_equity_balance(book):
        Book.report_balance_impl(book, ACCOUNT_EQUITY_T)

    @staticmethod
    def report_adhoc_balance(book):
        Book.report_balance_impl(book, ACCOUNT_ADHOC_T)

    @staticmethod
    def calculate_balances(book):
        this_point_in_time = datetime.datetime.now()

        currency_ops = []
        currency_basket = {}

        for each in book['transactions']:
            # We don't want future transactions to count against the current
            # state of finances. Let them trigger when their time comes.
            if each['timestamp'] > this_point_in_time:
                continue

            if each['type'] == 'expense':
                source = each['source']
                if not (source.startswith('asset/') or source.startswith('liability/')):
                    continue
                account_kind, account_id = source.split('/')

                book['accounts'][account_kind][account_id]['balance'] += each['value']['amount']
            elif each['type'] == 'revenue':
                dst = each['destination']
                if not (dst.startswith('asset/') or dst.startswith('liability/')):
                    continue
                account_kind, account_id = dst.split('/')

                book['accounts'][account_kind][account_id]['balance'] += each['value']['amount']
            elif each['type'] == 'transfer':
                source = each['source']
                if not is_own_account(source):
                    continue
                src_account_kind, src_account_id = source.split('/')

                destination = each['destination']
                if not is_own_account(destination):
                    continue
                dst_account_kind, dst_account_id = destination.split('/')

                value = each['value']
                if 'amount' in value:
                    # Transfer between two fiat accounts in the same currency.
                    # For example between the main account and a credit card or
                    # rent liability account.
                    raise Exception('old-style transfer')
                    book['accounts'][src_account_kind][src_account_id]['balance'] += value['amount']
                    book['accounts'][dst_account_kind][dst_account_id]['balance'] += value['amount']
                elif 'src' in value:
                    # Transfer between two fiat accounts in the different
                    # currencies. For example between the main account in PLN
                    # and a savings account in JPY.
                    src = value['src']
                    dst = value['dst']
                    if book['accounts'][src_account_kind][src_account_id]['currency'] != src['currency']:
                        raise Exception('{}: mismatched currency: {} != {}'.format(
                            each['timestamp'],
                            book['accounts'][src_account_kind][src_account_id]['currency'],
                            src['currency'],
                        ))
                    if book['accounts'][dst_account_kind][dst_account_id]['currency'] != dst['currency']:
                        raise Exception('{}: mismatched currency: {} != {}'.format(
                            each['timestamp'],
                            book['accounts'][dst_account_kind][dst_account_id]['currency'],
                            dst['currency'],
                        ))
                    book['accounts'][src_account_kind][src_account_id]['balance'] += src['amount']
                    book['accounts'][dst_account_kind][dst_account_id]['balance'] += dst['amount']
                    if src['currency'] != dst['currency']:
                        currency_ops.append({
                            'src': src,
                            'dst': dst,
                            'rate': each['rate'],
                        })
                else:
                    # Transfer between a fiat account and an equity account
                    # where balance is represented in shares.
                    # FIXME Transfers between two share-based accounts are not
                    # supported currently.
                    raise Exception('equity transfers not supported')
                    fiat_amount = value['fiat']['amount']
                    fiat_currency = value['fiat']['currency']
                    shares_amount = value['shares']
                    book['accounts'][src_account_kind][src_account_id]['value'] -= fiat_amount
                    book['accounts'][dst_account_kind][dst_account_id]['balance']['u'] += shares_amount
                    book['accounts'][dst_account_kind][dst_account_id]['balance'][fiat_currency] += fiat_amount

                dst_account = book['accounts'][dst_account_kind][dst_account_id]

                if dst_account['balance'] == 0 and dst_account.get('ad_hoc', False):
                    del book['accounts'][dst_account_kind][dst_account_id]
            elif each['type'] == 'balance':
                of = each['of']
                if not (of.startswith('asset/') or of.startswith('liability/')
                        or of.startswith('equity/')):
                    continue
                account_kind, account_id = of.split('/')

                if account_kind in (ACCOUNT_ASSET_T, ACCOUNT_LIABILITY_T,):
                    recorded = book['accounts'][account_kind][account_id]['balance']
                    expected = each['value']['amount']
                    this_month = datetime.datetime.strptime(
                        this_point_in_time.strftime(THIS_MONTH_FORMAT)
                        , THIS_MONTH_FORMAT
                    )
                    if (recorded != expected) and (each['timestamp'] >= this_month or DISPLAY_ALL_IMBALANCES):
                        if DISPLAY_IMBALANCES:
                            print('  {}: {:.2f} {} not accounted for on {} as of {}'.format(
                                colorise_if_possible(COLOR_WARNING, 'notice'),
                                (recorded - expected),
                                book['accounts'][account_kind][account_id]['currency'],
                                of,
                                each['timestamp'],
                            ))
                    book['accounts'][account_kind][account_id]['balance'] = expected
                else:
                    recorded = book['accounts'][account_kind][account_id]['value']
                    expected = each['value']
                    for k, v in expected.items():
                        book['accounts'][account_kind][account_id][k] = v
            elif each['type'] == 'ad-hoc':
                tmp_name = each['name']
                book['accounts']['liability'][tmp_name] = {
                    'currency': each['value']['currency'],
                    'value': -each['value']['amount'],
                    'opened': each['timestamp'],
                    'overview': True,
                    'ad_hoc': True,
                }


        for each in currency_ops:
            src = each['src']
            dst = each['dst']
            if src['currency'] != DEFAULT_CURRENCY:
                continue
            key = (dst['currency'], src['currency'],)
            currency_basket.setdefault(key, {
                'rates': [],
                'ops': [],
            })
        for each in currency_ops:
            src = each['src']
            dst = each['dst']
            key = (dst['currency'], src['currency'],)
            if key[1] == DEFAULT_CURRENCY:
                currency_basket[key]['rates'].append(each['rate'])
                currency_basket[key]['ops'].append(each)
            else:
                key = (key[1], key[0],)
                if key not in currency_basket:
                    currency_basket.setdefault(key, {
                        'rates': [],
                        'ops': [],
                    })
                currency_basket[key]['rates'].append(each['rate'])
                currency_basket[key]['ops'].append({
                    'src': each['dst'],
                    'dst': {
                        'currency': each['src']['currency'],
                        'amount': -each['src']['amount'],
                    },
                    'rate': each['rate'],
                })

        book['currency_basket'] = currency_basket
        for key, item in currency_basket.items():
            raw_mean = ledger.util.math.mean(list(map(
                lambda each: each[1],
                item['rates'],
            )))

            weighted_ops = []
            accumulator = decimal.Decimal()
            for op in item['ops']:
                accumulator += op['dst']['amount']
                if accumulator == 0:
                    weighted_ops.clear()
                    continue
                weighted_ops.append(op)
            weighted_mean = ledger.util.math.mean_weighted(list(map(
                lambda each: (each['src']['amount'], each['rate'][1]),
                weighted_ops,
            )))

            book['currency_basket'][key]['rates'] = {
                'buy': {
                    'mean': raw_mean,
                    'weighted': weighted_mean,
                },
            }

        for name, account in book['accounts']['asset'].items():
            if account['currency'] == DEFAULT_CURRENCY:
                continue
            account['in_default_currency'] = decimal.Decimal()

            key = (account['currency'], DEFAULT_CURRENCY)
            if key not in book['currency_basket']:
                continue
            rate = book['currency_basket'][key]['rates']['buy']['weighted']
            per_amount = (100 if account['currency'] == 'JPY' else 1)
            in_default_currency = account['balance'] * (rate / per_amount)
            account['in_default_currency'] = in_default_currency

        for name, account in book['accounts']['liability'].items():
            if account['currency'] == DEFAULT_CURRENCY:
                continue
            account['in_default_currency'] = decimal.Decimal()

            key = (account['currency'], DEFAULT_CURRENCY)
            if key not in book['currency_basket']:
                continue
            rate = book['currency_basket'][key]['rates']['buy']['weighted']
            per_amount = (100 if account['currency'] == 'JPY' else 1)
            in_default_currency = account['balance'] * (rate / per_amount)
            account['in_default_currency'] = in_default_currency

        return book

    @staticmethod
    def calculate_total_balance(book):
        total_balance = decimal.Decimal('0.0')
        foreign_currencies = decimal.Decimal('0.0')
        estimated = False

        accounts = book['accounts']

        main_account_kind, main_account_name = Book.get_main_account(book).split('/')
        main_currency = accounts[main_account_kind][main_account_name]['currency']

        for kind in accounts:
            for each in accounts[kind].values():
                value = each['balance']
                if each['currency'] != main_currency:
                    # FIXME Apply conversion rates and notify that the balance
                    # is only estimated.
                    foreign_currencies += each['in_default_currency']
                    estimated = True
                    continue
                total_balance += value

        return (total_balance, foreign_currencies, estimated)

    @staticmethod
    def report_balances(book):
        total_balance, foreign_currencies, is_estimated = Book.calculate_total_balance(book)
        m = '{} on all {} accounts: {} {}'.format(
            colorise_if_possible(COLOR_PERIOD_NAME, 'Balance'),
            Book.no_of_accounts(book),
            colorise_if_possible(
                COLOR_BALANCE(total_balance),
                '{:.2f}'.format(total_balance),
            ),
            DEFAULT_CURRENCY,
        )
        if foreign_currencies:
            # Mean spread accross all currencies in the basket. Calculated to
            # match the value presented by real bank account. Spreads on
            # individual currencies are not matched as there is no automated way
            # to fetch them.
            f = (foreign_currencies * SPREAD)
            t = (total_balance + f)
            m += ' (~{t} {c}, ~{f} {c} in foreign currencies)'.format(
                f = colorise_if_possible(
                    COLOR_BALANCE(f),
                    '{:.2f}'.format(f),
                ),
                t = colorise_if_possible(
                    COLOR_BALANCE(t),
                    '{:.2f}'.format(t),
                ),
                c = DEFAULT_CURRENCY,
            )
        print(m)
        Book.report_asset_balance(book)
        Book.report_liability_balance(book)
        Book.report_equity_balance(book)
        Book.report_adhoc_balance(book)

    @staticmethod
    def report(screen, book):
        Book.screen = screen

        if not Book.account_names(book):
            print('No accounts.')
            return

        book = Book.calculate_balances(book)

        if book['transactions']:
            Book.report_today(book, column = 0)
            Book.report_yesterday(book, column = 1)
            print(screen.str())
            screen.reset()

            Book.report_last_7_days(book, column = 0)
            print(screen.str())
            screen.reset()

            Book.report_this_month(book, column = 0)
            Book.report_last_month(book, column = 1)
            print(screen.str())
            screen.reset()

            Book.report_this_year(book, column = 0)
            Book.report_total(book, column = 1)
            print(screen.str())
            screen.reset()

            Book.report_last_year(book, column = 1)
            print(screen.str())
            screen.reset()
        else:
            print('No transactions.')

        # FIXME Also, maybe add a report of destinations that
        # receive the most money from us? This could be useful.

        Book.report_balances(book)
