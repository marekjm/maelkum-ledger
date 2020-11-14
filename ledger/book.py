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
    COLOR_NEUTRAL,
    COLOR_SHARE_PRICE,
    COLOR_SHARE_PRICE_AVG,
    COLOR_SHARE_WORTH,
    COLOR_SHARE_COUNT,
)
import ledger.util.math
import ledger.constants


TIMESTAMP_FORMAT      = '%Y-%m-%dT%H:%M'
TIMESTAMP_ZERO_FORMAT = '%Y-%m-%dT00:00'
DAYSTAMP_FORMAT       = '%Y-%m-%d'
THIS_MONTH_FORMAT     = '%Y-%m-01T00:00'
THIS_YEAR_FORMAT      = '%Y-01-01T00:00'
LAST_YEAR_DAY_FORMAT  = '%Y-12-31T23:59'

DEFAULT_CURRENCY   = 'PLN'
ALLOWED_CONVERSION_DIFFERENCE = decimal.Decimal('0.005')

DISPLAY_IMBALANCES = False
DISPLAY_ALL_IMBALANCES = False

ACCOUNT_ASSET_T = ledger.constants.ACCOUNT_ASSET_T
ACCOUNT_LIABILITY_T = ledger.constants.ACCOUNT_LIABILITY_T
ACCOUNT_EQUITY_T = ledger.constants.ACCOUNT_EQUITY_T
ACCOUNT_ADHOC_T = ledger.constants.ACCOUNT_ADHOC_T
ACCOUNT_T = (
    ACCOUNT_ASSET_T,
    ACCOUNT_LIABILITY_T,
    ACCOUNT_EQUITY_T,
    ACCOUNT_ADHOC_T,
)
def is_own_account(a):
    mx = lambda k: a.startswith('{}/'.format(k))
    return any(map(mx, ACCOUNT_T))


def value_in_default_currency(transaction, book):
    IN_DEFAULT_CURRENCY_KEY = 'in_default_currency'
    if IN_DEFAULT_CURRENCY_KEY in transaction:
        return transaction[IN_DEFAULT_CURRENCY_KEY]
    return decimal.Decimal('0.0')


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
                value = each.get('with', {}).get('calculate_as', each['value'])
                if value['currency'] != DEFAULT_CURRENCY:
                    c = value['currency']
                    r = book['currency_basket'][(c, DEFAULT_CURRENCY)]['rates']['buy']['weighted']
                    in_default_currency = (value['amount'] * r)
                    value['in_default_currency'] = in_default_currency
                expenses.append({
                    'value': value,
                })
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
                value = each.get('with', {}).get('calculate_as', each['value'])
                if value['currency'] != DEFAULT_CURRENCY:
                    c = value['currency']
                    r = book['currency_basket'][(c, DEFAULT_CURRENCY)]['rates']['buy']['weighted']
                    in_default_currency = (value['amount'] * r)
                    value['in_default_currency'] = in_default_currency
                expenses.append({
                    'timestamp': each['timestamp'],
                    'value': value,
                })
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
    def report_prev_7_days(book, column):
        today = datetime.datetime.strptime(
            (datetime.datetime.now() - datetime.timedelta(days = 8)).strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        last_week = datetime.datetime.strptime(
            (datetime.datetime.now() - datetime.timedelta(days = 14)).strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        Book.report_period_impl(book, last_week, today, 'Previous 7 days', column)

    @staticmethod
    def report_last_14_days(book, column):
        today = datetime.datetime.strptime(
            (datetime.datetime.now() - datetime.timedelta(days = 0)).strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        last_week = datetime.datetime.strptime(
            (datetime.datetime.now() - datetime.timedelta(days = 14)).strftime(TIMESTAMP_ZERO_FORMAT),
            TIMESTAMP_FORMAT,
        )
        Book.report_period_impl(book, last_week, today, 'Last 14 days', column)

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
            fmt = '{:7.2f}'
            Book.screen.print(column = column, text = '  Daily expense cap to meet budget: {} {}'.format(
                colorise_if_possible(
                    COLOR_BALANCE(available_budgeted_funds_per_day),
                    fmt.format(available_budgeted_funds_per_day),
                ),
                DEFAULT_CURRENCY,
            ))
            Book.screen.print(
                column = column,
                text = '  Total expense cap to meet budget: {} {}'.format(
                colorise_if_possible(
                    COLOR_BALANCE(available_budgeted_funds),
                    fmt.format(available_budgeted_funds),
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
    def no_of_accounts(book, kind = None):
        a = book['accounts']
        count_all = (
              len(list(a.get('asset', {}).keys()))
            + len(list(a.get('liability', {}).keys()))
            + len(list(a.get('equity', {}).keys()))
        )
        if kind is None:
            return count_all
        else:
            return len(list(a.get(kind, {}).keys()))

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
        def flt_if_positive(each):
            if 'if_positive' not in each[1]:
                return True
            if each[1]['if_positive'] == False:
                return True
            return False
        flt = lambda seq: filter(flt_if_positive,
            filter(flt_if_negative,
            filter(flt_if_overview,
            seq)))

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
                weighted_buying_rate = None
                in_default_currency = None
                key = (v['currency'], DEFAULT_CURRENCY)

                balance = v['balance']
                current_rate = book['currency_rates'][key]

                if key in book['currency_basket']:
                    weighted_buying_rate = book['currency_basket'][key]['rates']['buy']['weighted']
                    in_default_currency = value_in_default_currency(
                        v, book
                    )
                else:
                    weighted_buying_rate = current_rate

                worth_current = (balance * current_rate)

                gain_percent = (((current_rate / weighted_buying_rate) - 1) * 100)

                if in_default_currency:
                    message += ' ~ {} {} at {} {} rate ({}% vs {} {})'.format(
                        colorise_if_possible(
                            COLOR_BALANCE(worth_current),
                            '{:8.2f}'.format(worth_current)),
                        DEFAULT_CURRENCY,
                        colorise_if_possible(
                            COLOR_EXCHANGE_RATE,
                            '{:6.4f}'.format(current_rate)),
                        '/'.join(key),
                        colorise_if_possible(
                            COLOR_BALANCE(gain_percent),
                            '{:7.4f}'.format(gain_percent)),
                        colorise_if_possible(
                            COLOR_EXCHANGE_RATE,
                            '{:6.4f}'.format(weighted_buying_rate)),
                        '/'.join(key),
                    )

            if kind == ledger.constants.ACCOUNT_EQUITY_T:
                gain = v['profit']
                nominal = gain['nominal']
                percent = gain['percent']
                gain_sign = ('+' if percent > 0 else '')
                message += ' ({} {}, {}%)'.format(
                    colorise_if_possible(
                        COLOR_BALANCE(nominal),
                        '{:.2f}'.format(nominal)),
                    v['currency'],
                    colorise_if_possible(
                        COLOR_BALANCE(percent),
                        '{}{:.4f}'.format(gain_sign, percent)),
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
            elif each['type'] == 'dividend':
                dst = each['destination']
                if not (dst.startswith('asset/') or dst.startswith('liability/')):
                    continue
                dst_account_kind, dst_account_id = dst.split('/')

                src_account, div_company = each['source']
                src_account_kind, src_account_id = src_account.split('/')

                src_account = book['accounts'][ACCOUNT_EQUITY_T][src_account_id]
                if div_company not in src_account['shares']:
                    raise Exception('{}: company {} does not exist in account: {}'.format(
                        each['timestamp'].strftime('%Y-%m-%dT%H:%M:%S'),
                        div_company,
                        (src_account_kind + '/' + src_account_id),
                    ))

                company_account = src_account['shares'][div_company]
                company_account['dividends'] += each['value']['amount']
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
                if 'shares' in value:
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
                    if src['currency'] != dst['currency']:
                        fmt = ('currencies do not match on equity transaction'
                               ' on {}: {} != {}')
                        raise Exception(fmt.format(
                            each['timestamp'],
                            src['currency'],
                            dst['currency'],
                        ))

                    book['accounts'][src_account_kind][src_account_id]['balance'] += src['amount']
                    book['accounts'][dst_account_kind][dst_account_id]['balance'] += dst['amount']

                    no_shares = value['shares']['shares']
                    if src_account_kind == ACCOUNT_EQUITY_T and no_shares == 0:
                        print(value)
                        fmt = '{}: amount of sold shares must not be 0'
                        raise Exception(fmt.format(
                            each['timestamp'],
                        ))

                    if no_shares > 0:
                        eq_account = book['accounts'][dst_account_kind][dst_account_id]
                        eq_account_shares = eq_account['shares']
                        use_amount = dst['amount']
                    elif no_shares < 0:
                        eq_account = book['accounts'][src_account_kind][src_account_id]
                        eq_account_shares = eq_account['shares']
                        use_amount = src['amount']
                    else:
                        raise Exception('{}: share transfer of 0'.format(
                            each['timestamp'],
                        ))

                    if value['shares']['company'] not in eq_account_shares:
                        # Initialise shares tracking for a company.
                        eq_account_shares[value['shares']['company']] = {
                            'txs': [],
                            'shares': decimal.Decimal(),
                            'fees': decimal.Decimal(),
                            'dividends': decimal.Decimal(),
                            'price_per_share': decimal.Decimal(),
                        }

                    sh_company = value['shares']['company']
                    sh_shares = value['shares']['shares']
                    sh_fee = value['shares']['fee']['amount']
                    sh_price_per_share = abs(use_amount / sh_shares)
                    company_shares = eq_account_shares[sh_company]

                    company_shares['txs'].append({
                        'value': each['value'],
                        'shares': no_shares,
                        'timestamp': each['timestamp'],
                    })
                    company_shares['shares'] += sh_shares
                    company_shares['fees'] += sh_fee
                    company_shares['price_per_share'] = sh_price_per_share
                elif 'amount' in value:
                    # Transfer between two fiat accounts in the same currency.
                    # For example between the main account and a credit card or
                    # rent liability account.
                    raise Exception('old-style transfer')
                elif 'src' in value:
                    # Transfer between two fiat accounts in the same or in
                    # different currencies. For example between the main account
                    # in PLN and a savings account in JPY.
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
                    a, company = account_id.split()
                    amount = each['value']['amount']
                    currency = each['value']['currency']
                    if currency != book['accounts']['equity'][a]['currency']:
                        fmt = 'mismatched currency: {}: {} != {}'
                        raise Exception(fmt.format(
                            each['timestamp'],
                            book['accounts']['equity'][a]['currency'],
                            currency,
                        ))
                    shares = book['accounts']['equity'][a]['shares'][company]
                    shares['price_per_share'] = decimal.Decimal(amount)
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
        is_from_default_currency = (lambda e:
                e['src']['currency'] == DEFAULT_CURRENCY)
        for each in filter(is_from_default_currency, currency_ops):
            src = each['src']
            dst = each['dst']
            key = (dst['currency'], src['currency'],)
            currency_basket[key]['rates'].append(each['rate'])
            currency_basket[key]['ops'].append(each)

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
            in_default_currency = account['balance'] * rate
            account['in_default_currency'] = in_default_currency

        for name, account in book['accounts']['liability'].items():
            if account['currency'] == DEFAULT_CURRENCY:
                continue
            account['in_default_currency'] = decimal.Decimal()

            key = (account['currency'], DEFAULT_CURRENCY)
            if key not in book['currency_basket']:
                continue
            rate = book['currency_basket'][key]['rates']['buy']['weighted']
            in_default_currency = account['balance'] * rate
            account['in_default_currency'] = in_default_currency

        for name, account in book['accounts']['equity'].items():
            account['balance'] = decimal.Decimal()
            account['paid'] = decimal.Decimal()
            account['value'] = decimal.Decimal()
            account['dividends'] = decimal.Decimal()
            account['worth'] = decimal.Decimal()

            for company, shares in account['shares'].items():
                shares_no = shares['shares']
                share_price = shares['price_per_share']
                fees = shares['fees']
                dividends = shares['dividends']

                # Here is the total money that you had to pay to obtain the
                # shares. It is the source price because what you paid not only
                # includes the shares' worth, but also the fees.
                #
                # Note that the amount may be negative (if you were only buying
                # shares or sold them with a loss) or positive (if you sold
                # shares with a profit).
                #
                # FIXME Calculations should be reset of the amount of shares
                # ever reaches 0 as that means we sold all our shares, and using
                # old prices after such a point does not make much sense.
                paid = sum(map(
                    lambda x: (
                        x['value']['src']['amount']
                        # A clever way of obtaining 1 if the operation was a buy
                        # and -1 if the operation was a sell.
                        #
                        # We need this to correctly calculate the total amount
                        # of money we have paid for the shares we have. If we
                        # were buying then we should add the amount to the total
                        # cost, but if we were selling then we should subtract.
                        # Multiplying the source amount by either 1 or -1 makes
                        # it possible to do it in a simple map/sum operation.
                        #
                        # Why do we sum source amounts? Because when buying we
                        # should consider the amount of money we had to give to
                        # the trading organisation to obtain the shares, and
                        # when selling we should consider the amount of money we
                        # got from the market.
                        * (x['shares'] / abs(x['shares']))
                    ),
                    shares['txs']))

                # What the shares are worth is simple: you take price of one
                # share and multiply it by the amount of shares you own.
                worth = (shares_no * share_price)

                # The value of shares for you is not exactly what they are worth
                # on the market. Remember that you paid some fees to acquite
                # them, and that they may have yielded you some dividends.
                value = (worth - fees + dividends)

                # Account's balance tells you the worth of your account and is
                # not concerned with any fees that you may have incurred while
                # acquiting the wealth.
                #
                # The balance should not be modified if there are no shares for
                # a company. This means that all shares were sold and including
                # their cost in the report would be hugely misleading.
                account['balance'] += (worth
                    if shares_no
                    else decimal.Decimal(0))
                account['paid'] += (paid
                    if shares_no
                    else decimal.Decimal(0))
                account['value'] += (value
                    if shares_no
                    else decimal.Decimal(0))
                account['dividends'] += dividends

                tr_nominal = (worth + paid + dividends)
                tr_percent = -((tr_nominal / paid) * 100)
                tr = {
                    'relevant': (dividends != 0),
                    'nominal': tr_nominal,
                    'percent': tr_percent,
                }

                shares['balance'] = worth
                shares['paid'] = paid
                shares['value'] = value
                shares['total_return'] = tr

            # Include dividends in profit calculations. If the shares went down,
            # but the dividends were healthy then you are still OK.
            nominal_value = (account['balance'] + account['dividends'])
            nominal_profit = (nominal_value + account['paid'])
            percent_profit = decimal.Decimal()
            if account['paid']:  # beware zero division!
                percent_profit = (((nominal_value / -account['paid'])) - 1) * 100
            account['profit'] = {
                'nominal': nominal_profit,
                'percent': percent_profit,
            }

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
                    foreign_currencies += value_in_default_currency(
                        each, book
                    )
                    estimated = True
                    continue
                total_balance += value

        return (total_balance, foreign_currencies, estimated)

    @staticmethod
    def calculate_cash_balance(book):
        total_balance = decimal.Decimal('0.0')
        foreign_currencies = decimal.Decimal('0.0')
        estimated = False

        accounts = book['accounts']

        main_account_kind, main_account_name = Book.get_main_account(book).split('/')
        main_currency = accounts[main_account_kind][main_account_name]['currency']

        for kind in ('asset', 'liability',):
            for each in accounts[kind].values():
                value = each['balance']
                if each['currency'] != main_currency:
                    # FIXME Apply conversion rates and notify that the balance
                    # is only estimated.
                    foreign_currencies += value_in_default_currency(
                        each, book
                    )
                    estimated = True
                    continue
                total_balance += value

        return (total_balance, foreign_currencies, estimated)

    @staticmethod
    def report_balances(book):
        if True:  # report cold, hard cash balance (ie, readily available reserves)
            total_balance, foreign_currencies, is_estimated = Book.calculate_cash_balance(book)
            m = '{} on all {} accounts: {} {}'.format(
                colorise_if_possible(COLOR_PERIOD_NAME, 'Reserve'),
                (Book.no_of_accounts(book, ACCOUNT_ASSET_T) +
                    Book.no_of_accounts(book, ACCOUNT_LIABILITY_T)),
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
                t = (total_balance + foreign_currencies)
                m += ' (~{t} {c}, ~{f} {c} in foreign currencies)'.format(
                    f = colorise_if_possible(
                        COLOR_BALANCE(foreign_currencies),
                        '{:.2f}'.format(foreign_currencies),
                    ),
                    t = colorise_if_possible(
                        COLOR_BALANCE(t),
                        '{:.2f}'.format(t),
                    ),
                    c = DEFAULT_CURRENCY,
                )
            print(m)
        if True:  # report total balance
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
                t = (total_balance + foreign_currencies)
                m += ' (~{t} {c}, ~{f} {c} in foreign currencies)'.format(
                    f = colorise_if_possible(
                        COLOR_BALANCE(foreign_currencies),
                        '{:.2f}'.format(foreign_currencies),
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
    def report_equities(book):
        no_of_accounts = Book.no_of_accounts(book, ACCOUNT_EQUITY_T)
        m = '{} of {} equity account{}'.format(
            colorise_if_possible(COLOR_PERIOD_NAME, 'State'),
            no_of_accounts,
            ('s' if no_of_accounts > 1 else ''),
        )
        print(m)

        account_name_length = max(map(len,
            book['accounts'][ACCOUNT_EQUITY_T].keys()))
        balance_length = max(map(lambda each: len(str(each['balance'])),
            book['accounts'][ACCOUNT_EQUITY_T].values()))
        for account_name in book['accounts'][ACCOUNT_EQUITY_T]:
            account = book['accounts'][ACCOUNT_EQUITY_T][account_name]

            gain = account['profit']
            nominal = gain['nominal']
            percent = gain['percent']
            gain_sign = ('+' if percent > 0 else '')
            companies_with_loss = len(list(
                filter(lambda x: (x < 0),
                map(lambda x: x['total_return']['nominal'],
                filter(lambda x: x['shares'],
                account['shares'].values(),
            )))))

            companies_held = len(list(
                filter(lambda k: (account['shares'][k]['shares'] != 0),
                account['shares'].keys(),
            )))

            oneline_report = '  {} => {} {}'.format(
                account_name,
                colorise_if_possible(
                    COLOR_BALANCE(account['balance']),
                    '{:.2f}'.format(account['balance']),
                ),
                account['currency'],
            )
            oneline_report += ' ({} {}, {}%) in {} compan{}{}'.format(
                colorise_if_possible(
                    COLOR_BALANCE(nominal),
                    '{:.2f}'.format(nominal)),
                account['currency'],
                colorise_if_possible(
                    COLOR_BALANCE(percent),
                    '{}{:.4f}'.format(gain_sign, percent)),
                colorise_if_possible(COLOR_SHARE_WORTH, companies_held),
                ('y' if companies_held == 1 else 'ies'),
                (
                    ', {} with loss'.format(colorise_if_possible(
                        COLOR_EXPENSES, companies_with_loss))
                    if companies_with_loss else
                    ''
                ),
            )
            print(oneline_report)

            if not account['shares']:
                # If there are no shares the code reporting them has no reason
                # to run so let's just return early.
                return

            company_name_length = max(map(len, account['shares'].keys()))
            shares_length = max(map(lambda each: len(str(each['shares'])),
                account['shares'].values()))
            share_price_length = max(map(
                lambda each: len(str(each['price_per_share']).split('.')[0]),
                account['shares'].values())) + 5
            shares_value_length = max(map(
                lambda each: len(str(each['balance']).split('.')[0]),
                account['shares'].values())) + 3
            for company_name in sorted(account['shares'].keys()):
                company = account['shares'][company_name]

                no_of_shares = company['shares']
                if no_of_shares == 0:
                    continue

                txs = company['txs']
                fees = company['fees']
                worth = company['balance']
                value = company['value']
                paid = company['paid']
                dividends = company['dividends']
                price_per_share = company['price_per_share']
                price_per_share_avg = abs(paid / no_of_shares)

                gain_nominal = (worth + paid)
                gain_percent = -((gain_nominal / paid) * 100)

                gain_nominal_per_share = (gain_nominal / no_of_shares)

                header = '    {}'.format(
                    colorise_if_possible(
                        COLOR_BALANCE(company['total_return']['nominal']),
                        company_name.ljust(company_name_length),
                    ),
                )
                market_worth = '{} * {} = {}'.format(
                    colorise_if_possible(
                        COLOR_SHARE_PRICE,
                        '{{:{}.4f}}'.format(share_price_length).format(price_per_share)),
                    colorise_if_possible(
                        COLOR_SHARE_COUNT,
                        str(no_of_shares).rjust(shares_length)),
                    colorise_if_possible(
                        COLOR_SHARE_WORTH,
                        '{{:{}.2f}}'.format(shares_value_length).format(worth)),
                )
                captial_gain = '{} {}, {}% @ {}{} {}'.format(
                    colorise_if_possible(
                        COLOR_BALANCE(gain_nominal),
                        '{:8.2f}'.format(gain_nominal)),
                    account['currency'],
                    colorise_if_possible(
                        COLOR_BALANCE(gain_percent),
                        '{:8.4f}'.format(gain_percent)),
                    colorise_if_possible(
                        COLOR_SHARE_PRICE_AVG,
                        '{:.2f}'.format(price_per_share_avg)),
                    colorise_if_possible(
                        COLOR_BALANCE(gain_nominal_per_share),
                        '{}{:.4f}'.format(
                            ('' if (gain_nominal_per_share < 0) else '+'),
                            gain_nominal_per_share,
                        )),
                    account['currency'],
                )
                total_return = ''
                if company['total_return']['relevant']:
                    tr_nominal = company['total_return']['nominal']
                    tr_percent = company['total_return']['percent']
                    total_return = ', return {} {}, {}%'.format(
                        colorise_if_possible(
                            COLOR_BALANCE(tr_nominal),
                            '{:.2f}'.format(tr_nominal)),
                        account['currency'],
                        colorise_if_possible(
                            COLOR_BALANCE(tr_percent),
                            '{:.2f}'.format(tr_percent)),
                    )

                company_report = '{} : {} ({}){}'.format(
                    header,
                    market_worth,
                    captial_gain,
                    total_return,
                )
                print(company_report)

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
            Book.report_prev_7_days(book, column = 1)
            Book.report_last_14_days(book, column = 2)
            print(screen.str())
            screen.reset()

            Book.report_this_month(book, column = 0)
            Book.report_last_month(book, column = 1)
            print(screen.str())
            screen.reset()

            Book.report_this_year(book, column = 0)
            Book.report_last_year(book, column = 1)
            Book.report_total(book, column = 2)
            print(screen.str())
            screen.reset()

            # Book.report_total(book, column = 1)
            # print(screen.str())
            # screen.reset()
        else:
            print('No transactions.')

        # FIXME Also, maybe add a report of destinations that
        # receive the most money from us? This could be useful.

        Book.report_balances(book)
        Book.report_equities(book)
