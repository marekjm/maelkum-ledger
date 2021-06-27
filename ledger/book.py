import datetime
import decimal
import sys

from ledger import constants, ir, util


def setup_accounts(accounts, book_ir):
    for each in book_ir:
        if type(each) is ir.Account_record:
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

            account_data = {
                'active': True,
                'balance': each.balance[0],
                'currency': each.balance[1],
                'created': each.timestamp,
                'tags': each.tags,
                '~': each,
            }

            # If the account represents an equity account, we need to track a
            # bit more information than for a regular asset account. Equity is
            # somewhat dynamic - shares change valuations, divindend are paid
            # out, and transactions usually have fees. This all needs to be
            # accounted for.
            if kind == constants.ACCOUNT_EQUITY_T:
                # First, let's track shares. This is the basic feature of an
                # equity account and will be the basis of the fluctuating value
                # of the account.
                account_data['shares'] = {}

                # We also need to track the list of companies that are held in
                # shares. This is useful where the amount of shares reaches zero
                # and profit-loss calculations must be reset.
                account_data['companies'] = set()

                # We also need to track profits (or, hopefully not, losses).
                # Profits are tracked as "nominal" ie, measured in monetary
                # units (eg, USD, EUR) and "percent" ie, measured in a
                # percentage increase (or decrease) in value of shares held.
                account_data['gain'] = {
                    'nominal': decimal.Decimal(),
                    'percent': decimal.Decimal(),
                }

            accounts[kind][name] = account_data
        if type(each) is ir.Account_close:
            kind = each.kind
            name = each.name

            if name not in accounts[kind]:
                sys.stderr.write('{}: error: {} account `{}` does not exists\n'.format(
                    each.text[0].location,
                    kind,
                    name,
                ))
                exit(1)

            accounts[kind][name]['active'] = False

def calculate_balances(accounts, book, default_currency):
    book_ir, currency_basket = book

    def ensure_currency_match(accounts, a):
        kind, name = a.account
        if kind is None:
            fmt = 'no currency for non-owned account {}'
            sys.stdout.write(('{}: {}: ' + fmt + '\n').format(
                util.colors.colorise(
                    'white',
                    a.text.location,
                ),
                util.colors.colorise(
                    'red',
                    'error',
                ),
                util.colors.colorise(
                    'white',
                    '{}/{}'.format(kind, name),
                ),
            ))
            exit(1)
        if name not in accounts[kind]:
            fmt = 'account {} does not exist'
            sys.stdout.write(('{}: {}: ' + fmt + '\n').format(
                util.colors.colorise(
                    'white',
                    a.to_location(),
                ),
                util.colors.colorise(
                    'red',
                    'error',
                ),
                util.colors.colorise(
                    'white',
                    '{}/{}'.format(kind, name),
                ),
            ))
            exit(1)
        account_currency = accounts[kind][name]['currency']
        tx_currency = a.value[1]
        if account_currency != tx_currency:
            fmt = 'mismatched currency: account {} is in {}, but value is in {}'
            sys.stdout.write(('{}: {}: ' + fmt + '\n').format(
                util.colors.colorise(
                    'white',
                    a.text.location,
                ),
                util.colors.colorise(
                    'red',
                    'error',
                ),
                util.colors.colorise(
                    'white',
                    '{}/{}'.format(kind, name),
                ),
                util.colors.colorise(
                    'light_green',
                    account_currency,
                ),
                util.colors.colorise(
                    'red_1',
                    tx_currency,
                ),
            ))
            exit(1)

    this_moment_in_time = datetime.datetime.now()

    # Calculate balances.
    for each in book_ir:
        if type(each) is ir.Configuration_line:
            continue
        if type(each) is ir.Account_record:
            continue

        if type(each) is ir.Exchange_rates_record:
            for r in each.rates:
                currency_basket['rates'][(str(r.src), str(r.dst),)] = r
            continue

        if each.effective_date() > this_moment_in_time:
            continue

        if type(each) is ir.Balance_record:
            for b in each.accounts:
                kind, name = b.account
                if kind == constants.ACCOUNT_EQUITY_T:
                    company, share_price, _ = b.value
                    shares = accounts[kind][name]['shares']
                    shares[company]['price_per_share'] = share_price
                else:
                    ensure_currency_match(accounts, b)
                    accounts[kind][name]['balance'] = b.value[0]
        if type(each) is ir.Revenue_tx:
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
        elif type(each) is ir.Expense_tx:
            for a in each.ins:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
        elif type(each) is ir.Transfer_tx:
            for a in each.ins:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
        elif type(each) is ir.Equity_tx:
            inflow = decimal.Decimal()
            outflow = decimal.Decimal()

            # There is only one destination account since we can only deposit
            # shares in one account using a single transfer.
            dst_account = None
            src_account = None
            for a in each.ins:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
                inflow += a.value[0]
                src_account = a.account
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                outflow += a.value[0]
                accounts[kind][name]['balance'] += a.value[0]
                dst_account = a.account

            fee_value = decimal.Decimal()
            fee_currency = default_currency
            for t in each.tags:
                s = str(t).strip()
                if s.startswith('fee:'):
                    fee = s.split()[1:]
                    fee_currency = fee[1]
                    fee_value = decimal.Decimal(fee[0])

            # FIXME check currency
            if fee_value:
                kind, name = src_account
                accounts[kind][name]['balance'] += fee_value

            this_shares = None
            for t in each.tags:
                s = str(t).strip()
                if s.startswith('shares:'):
                    shares = s.split()[1:]

                    company = shares[0]
                    this_shares = {
                        'company': company,
                        'no': decimal.Decimal(shares[1]),
                        'fee': {
                            'currency': fee_currency,
                            'amount': fee_value,
                        },
                    }

            pps = abs(-inflow / this_shares['no'])

            this_tx = {
                'base': each,
                'value': -inflow,
                'shares': this_shares,
            }

            if -outflow != (inflow - fee_value):
                fmt = 'inflow {} from {} does not equal outflow {} to {} plus fees {}'
                sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                    util.colors.colorise(
                        'white',
                        each.to_location(),
                    ),
                    util.colors.colorise(
                        'red',
                        'error',
                    ),
                    util.colors.colorise(
                        'white',
                        inflow,
                    ),
                    util.colors.colorise(
                        'white',
                        '/'.join(src_account),
                    ),
                    util.colors.colorise(
                        'white',
                        '/'.join(dst_account),
                    ),
                    util.colors.colorise(
                        'white',
                        outflow,
                    ),
                    util.colors.colorise(
                        'white',
                        fee_value,
                    ),
                ))
                exit(1)

            both_equity = (
                    dst_account[0] == constants.ACCOUNT_EQUITY_T
                and src_account[0] == constants.ACCOUNT_EQUITY_T)
            if both_equity:
                dst_kind, dst_name = dst_account
                src_kind, src_name = src_account

                company = this_shares['company']
                if company not in accounts[dst_kind][dst_name]['shares']:
                    accounts[dst_kind][dst_name]['shares'][company] = {
                        'shares': 0,
                        'price_per_share': decimal.Decimal(),
                        'fees': decimal.Decimal(),
                        'dividends': decimal.Decimal(),
                        'txs': [],
                        # FIXME are these fields below really needed?
                        'balance': decimal.Decimal(),
                        'paid': decimal.Decimal(),
                        'value': decimal.Decimal(),
                        'total_return': decimal.Decimal(),
                    }

                accounts[dst_kind][dst_name]['shares'][company]['txs'].append(this_tx)
                accounts[dst_kind][dst_name]['shares'][company]['price_per_share'] = pps
                accounts[dst_kind][dst_name]['companies'].add(company)

                this_tx = {
                    'base': each,
                    'value': inflow,
                    'shares': {
                        'company': company,
                        'no': -decimal.Decimal(shares[1]),
                        'fee': {
                            'currency': fee_currency,
                            'amount': decimal.Decimal(),
                        },
                    },
                }
                accounts[src_kind][src_name]['shares'][company]['txs'].append(this_tx)
                accounts[src_kind][src_name]['shares'][company]['price_per_share'] = pps
                accounts[src_kind][src_name]['companies'].add(company)
            else:
                kind, name = dst_account
                if kind != constants.ACCOUNT_EQUITY_T:
                    kind, name = src_account
                if kind != constants.ACCOUNT_EQUITY_T:
                    fmt = 'no equity account in transfer of {} shares'
                    sys.stderr.write(('{}: {}: ' + fmt + '\n').format(
                        util.colors.colorise(
                            'white',
                            each.to_location(),
                        ),
                        util.colors.colorise(
                            'red',
                            'error',
                        ),
                        util.colors.colorise(
                            'white',
                            company,
                        ),
                    ))
                    exit(1)
                company = this_shares['company']
                if company not in accounts[kind][name]['shares']:
                    accounts[kind][name]['shares'][company] = {
                        'shares': 0,
                        'price_per_share': decimal.Decimal(),
                        'fees': decimal.Decimal(),
                        'dividends': decimal.Decimal(),
                        'txs': [],
                        # FIXME are these fields below really needed?
                        'balance': decimal.Decimal(),
                        'paid': decimal.Decimal(),
                        'value': decimal.Decimal(),
                        'total_return': decimal.Decimal(),
                    }

                accounts[kind][name]['shares'][company]['txs'].append(this_tx)
                accounts[kind][name]['shares'][company]['price_per_share'] = pps
                accounts[kind][name]['companies'].add(company)
        if type(each) is ir.Dividend_tx:
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]['balance'] += a.value[0]
            for a in each.ins:
                kind, name = a.account
                company, value, _ = a.value
                shares = accounts[kind][name]['shares']
                shares[company]['dividends'] += value

        # FIXME dividends

def calculate_equity_values(accounts, book, default_currency):
    eq_accounts = accounts['equity']

    book, currency_basket = book

    for name, account in eq_accounts.items():
        account['balance'] = decimal.Decimal()
        account['paid'] = decimal.Decimal()
        account['value'] = decimal.Decimal()
        account['dividends'] = decimal.Decimal()
        account['worth'] = decimal.Decimal()

        for company, shares in account['shares'].items():
            share_price = shares['price_per_share']
            dividends = shares['dividends']

            # Fees paid to acquire the shares.
            fees = decimal.Decimal()

            # Total amount of money paid for the shares: share price plus any
            # fees to intermediaries.
            paid = decimal.Decimal()

            shares_no = 0
            for each in shares['txs']:
                paid += each['value']
                fee = each['shares']['fee']['amount']
                paid -= fee
                fees -= fee
                shares_no += each['shares']['no']

            # Shares worth at the time.
            worth = (shares_no * share_price)

            # Value of the shares; ie, the value that they represent to the
            # owner after subtracting fees and adding dividends.
            value = (worth - fees + dividends)

            gain_nominal = (worth - paid)
            gain_percent = ((worth / paid * 100) - 100)

            tr_nominal = (worth - paid + dividends)
            tr_percent = ((tr_nominal / paid) * 100)
            tr = {
                'relevant': (dividends != 0),
                'nominal': tr_nominal,
                'percent': tr_percent,
            }

            shares['shares'] = shares_no
            shares['balance'] = worth
            shares['paid'] = paid
            shares['value'] = value
            shares['total_return'] = tr
            shares['gain'] = {
                'nominal': gain_nominal,
                'percent': gain_percent,
            }

            if shares_no:
                account['balance'] += worth
                account['paid'] += paid
                account['value'] += value
            account['dividends'] += dividends

            continue

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
                    x['value']
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
                    * (x['shares']['no'] / abs(x['shares']['no']))
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
        nominal_profit = (nominal_value - account['paid'])
        percent_profit = decimal.Decimal()
        if account['paid']:  # beware zero division!
            percent_profit = (((nominal_value / account['paid']) - 1) * 100)
        account['gain'] = {
            'nominal': nominal_profit,
            'percent': percent_profit,
        }
