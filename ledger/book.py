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
                sys.stderr.write(
                    "{}: error: {} account `{}` already exists\n".format(
                        each.text[0].location,
                        kind,
                        name,
                    )
                )
                sys.stderr.write(
                    "note: {} account `{}` is defined at {}\n".format(
                        kind,
                        name,
                        accounts[kind][name]["~"].text[0].location,
                    )
                )
                exit(1)

            account_data = {
                "active": True,
                "balance": each.balance[0],
                "currency": each.balance[1],
                "created": each.timestamp,
                "tags": each.tags,
                "~": each,
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
                account_data["shares"] = {}

                # We also need to track the list of companies that are held in
                # shares. This is useful where the amount of shares reaches zero
                # and profit-loss calculations must be reset.
                account_data["companies"] = set()

                # We also need to track profits (or, hopefully not, losses).
                # Profits are tracked as "nominal" ie, measured in monetary
                # units (eg, USD, EUR) and "percent" ie, measured in a
                # percentage increase (or decrease) in value of shares held.
                account_data["gain"] = {
                    "nominal": decimal.Decimal(),
                    "percent": decimal.Decimal(),
                }

            accounts[kind][name] = account_data
        if type(each) is ir.Account_close:
            kind = each.kind
            name = each.name

            if name not in accounts[kind]:
                sys.stderr.write(
                    "{}: error: {} account `{}` does not exists\n".format(
                        each.text[0].location,
                        kind,
                        name,
                    )
                )
                exit(1)

            accounts[kind][name]["active"] = False


def calculate_balances(accounts, book, default_currency):
    book_ir, currency_basket = book

    def currency_matches(accounts, a):
        kind, name = a.account
        account_currency = accounts[kind][name]["currency"]
        tx_currency = a.value[1]
        return account_currency == tx_currency

    def ensure_currency_match(accounts, a):
        kind, name = a.account
        if kind is None:
            fmt = "no currency for non-owned account {}"
            sys.stdout.write(
                ("{}: {}: " + fmt + "\n").format(
                    util.colors.colorise(
                        "white",
                        a.text.location,
                    ),
                    util.colors.colorise(
                        "red",
                        "error",
                    ),
                    util.colors.colorise(
                        "white",
                        "{}/{}".format(kind, name),
                    ),
                )
            )
            exit(1)
        if name not in accounts[kind]:
            fmt = "account {} does not exist"
            sys.stdout.write(
                ("{}: {}: " + fmt + "\n").format(
                    util.colors.colorise(
                        "white",
                        a.to_location(),
                    ),
                    util.colors.colorise(
                        "red",
                        "error",
                    ),
                    util.colors.colorise(
                        "white",
                        "{}/{}".format(kind, name),
                    ),
                )
            )
            exit(1)
        account_currency = accounts[kind][name]["currency"]
        tx_currency = a.value[1]
        if account_currency != tx_currency:
            fmt = "mismatched currency: account {} is in {}, but value is in {}"
            sys.stdout.write(
                ("{}: {}: " + fmt + "\n").format(
                    util.colors.colorise(
                        "white",
                        a.text.location,
                    ),
                    util.colors.colorise(
                        "red",
                        "error",
                    ),
                    util.colors.colorise(
                        "white",
                        "{}/{}".format(kind, name),
                    ),
                    util.colors.colorise(
                        "light_green",
                        account_currency,
                    ),
                    util.colors.colorise(
                        "red_1",
                        tx_currency,
                    ),
                )
            )
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
                lhs = str(r.src)
                rhs = str(r.dst)

                base = (
                    lhs,
                    rhs,
                )
                rev = (
                    rhs,
                    lhs,
                )

                currency_basket["rates"].pop(base, None)
                currency_basket["rates"].pop(rev, None)

                currency_basket["rates"][base] = r
            continue

        if each.effective_date() > this_moment_in_time:
            continue

        if type(each) is ir.Balance_record:
            for b in each.accounts:
                kind, name = b.account
                if kind == constants.ACCOUNT_EQUITY_T:
                    company, share_price, _ = b.value
                    shares = accounts[kind][name]["shares"]
                    shares[company]["price_per_share"] = share_price
                else:
                    ensure_currency_match(accounts, b)
                    accounts[kind][name]["balance"] = b.value[0]
        if type(each) is ir.Revenue_tx:
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]["balance"] += a.value[0]
        elif type(each) is ir.Expense_tx:
            for a in each.ins:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]["balance"] += a.value[0]
        elif type(each) is ir.Transfer_tx:
            for a in each.ins:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]["balance"] += a.value[0]
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                accounts[kind][name]["balance"] += a.value[0]

            fee_value = decimal.Decimal()
            fee_currency = default_currency
            for t in each.tags:
                s = str(t).strip()
                if s.startswith("fee:"):
                    fee = s.split()[1:]
                    fee_currency = fee[1]
                    fee_value = decimal.Decimal(fee[0])
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
                accounts[kind][name]["balance"] += a.value[0]
                inflow += a.value[0]
                src_account = a.account
            for a in each.outs:
                ensure_currency_match(accounts, a)
                kind, name = a.account
                outflow += a.value[0]
                accounts[kind][name]["balance"] += a.value[0]
                dst_account = a.account

            fee_value = decimal.Decimal()
            fee_currency = default_currency
            for t in each.tags:
                s = str(t).strip()
                if s.startswith("fee:"):
                    fee = s.split()[1:]
                    fee_currency = fee[1]
                    fee_value = decimal.Decimal(fee[0])

            # FIXME fee currency

            this_shares = None
            for t in each.tags:
                s = str(t).strip()
                if s.startswith("shares:"):
                    shares = s.split()[1:]

                    company = shares[0]
                    this_shares = {
                        "company": company,
                        "no": decimal.Decimal(shares[1]),
                        "fee": {
                            "currency": fee_currency,
                            "amount": fee_value,
                        },
                    }

            pps = abs(outflow / this_shares["no"])

            this_tx = {
                "base": each,
                "value": outflow,
                "shares": this_shares,
            }

            # Do not consider fee_value like this:
            #
            #   if -outflow != (inflow - fee_value):
            #
            # as it was already handled. During the parsing stage the transfer
            # transaction was split into transfer itself, and an extra expense
            # transaction representing the fee.
            if -outflow != inflow:
                fmt = "inflow {} from {} does not equal outflow {} to {} plus fees {}"
                sys.stderr.write(
                    ("{}: {}: " + fmt + "\n").format(
                        util.colors.colorise(
                            "white",
                            each.to_location(),
                        ),
                        util.colors.colorise(
                            "red",
                            "error",
                        ),
                        util.colors.colorise(
                            "white",
                            inflow,
                        ),
                        util.colors.colorise(
                            "white",
                            "/".join(src_account),
                        ),
                        util.colors.colorise(
                            "white",
                            "/".join(dst_account),
                        ),
                        util.colors.colorise(
                            "white",
                            outflow,
                        ),
                        util.colors.colorise(
                            "white",
                            fee_value,
                        ),
                    )
                )
                exit(1)

            both_equity = (
                dst_account[0] == constants.ACCOUNT_EQUITY_T
                and src_account[0] == constants.ACCOUNT_EQUITY_T
            )
            if both_equity:
                dst_kind, dst_name = dst_account
                src_kind, src_name = src_account

                company = this_shares["company"]
                if company not in accounts[dst_kind][dst_name]["shares"]:
                    accounts[dst_kind][dst_name]["shares"][company] = {
                        "shares": 0,
                        "price_per_share": decimal.Decimal(),
                        "fees": decimal.Decimal(),
                        "dividends": decimal.Decimal(),
                        "txs": [],
                        # FIXME are these fields below really needed?
                        "balance": decimal.Decimal(),
                        "paid": decimal.Decimal(),
                        "value": decimal.Decimal(),
                        "total_return": decimal.Decimal(),
                    }

                accounts[dst_kind][dst_name]["shares"][company]["txs"].append(this_tx)
                accounts[dst_kind][dst_name]["shares"][company]["price_per_share"] = pps
                accounts[dst_kind][dst_name]["companies"].add(company)

                this_tx = {
                    "base": each,
                    "value": -inflow,
                    "shares": {
                        "company": company,
                        "no": -decimal.Decimal(shares[1]),
                        "fee": {
                            "currency": fee_currency,
                            "amount": decimal.Decimal(),
                        },
                    },
                }
                accounts[src_kind][src_name]["shares"][company]["txs"].append(this_tx)
                accounts[src_kind][src_name]["shares"][company]["price_per_share"] = pps
                accounts[src_kind][src_name]["companies"].add(company)
            else:
                kind, name = dst_account
                if kind != constants.ACCOUNT_EQUITY_T:
                    kind, name = src_account
                if kind != constants.ACCOUNT_EQUITY_T:
                    fmt = "no equity account in transfer of {} shares"
                    sys.stderr.write(
                        ("{}: {}: " + fmt + "\n").format(
                            util.colors.colorise(
                                "white",
                                each.to_location(),
                            ),
                            util.colors.colorise(
                                "red",
                                "error",
                            ),
                            util.colors.colorise(
                                "white",
                                company,
                            ),
                        )
                    )
                    exit(1)
                company = this_shares["company"]
                if company not in accounts[kind][name]["shares"]:
                    accounts[kind][name]["shares"][company] = {
                        "shares": 0,
                        "price_per_share": decimal.Decimal(),
                        "fees": decimal.Decimal(),
                        "dividends": decimal.Decimal(),
                        "txs": [],
                        # FIXME are these fields below really needed?
                        "balance": decimal.Decimal(),
                        "paid": decimal.Decimal(),
                        "value": decimal.Decimal(),
                        "total_return": decimal.Decimal(),
                    }

                accounts[kind][name]["shares"][company]["txs"].append(this_tx)
                accounts[kind][name]["shares"][company]["price_per_share"] = pps
                accounts[kind][name]["companies"].add(company)
        if type(each) is ir.Dividend_tx:
            for a in each.ins:
                kind, name = a.account

                value, currency = each.outs[0].value
                synth = each.outs[0]
                synth = ir.Account_mod(
                    synth.text,
                    synth.timestamp,
                    a.account,
                    synth.value,
                )
                if not currency_matches(accounts, synth):
                    wanted_currency = accounts[kind][name]["currency"]

                    pair = (
                        currency,
                        default_currency,
                    )
                    rev = False
                    try:
                        rate = currency_basket["rates"][pair]
                    except KeyError:
                        try:
                            pair = (
                                default_currency,
                                currency,
                            )
                            rate = currency_basket["rates"][pair]
                            rev = True
                        except KeyError:
                            fmt = "no currency pair {}/{} for {} account named {}"
                            sys.stderr.write(
                                ("{}: {}: " + fmt + "\n").format(
                                    util.colors.colorise(
                                        "white",
                                        acc["~"].text[0].location,
                                    ),
                                    util.colors.colorise(
                                        "red",
                                        "error",
                                    ),
                                    util.colors.colorise(
                                        "white",
                                        currency,
                                    ),
                                    util.colors.colorise(
                                        "white",
                                        default_currency,
                                    ),
                                    t,
                                    util.colors.colorise(
                                        "white",
                                        name,
                                    ),
                                )
                            )
                            exit(1)

                    rate = rate.rate
                    if rev:
                        value = value / rate
                    else:
                        value = value * rate

                company = a.value[0]
                shares = accounts[kind][name]["shares"]
                shares[company]["dividends"] += value


def calculate_equity_values(accounts, book, default_currency):
    eq_accounts = accounts["equity"]

    book, currency_basket = book

    for name, account in eq_accounts.items():
        for company, shares in account["shares"].items():
            dividends: decimal.Decimal = shares["dividends"]
            share_price: decimal.Decimal = shares["price_per_share"]
            shares_held: int = 0

            # Total amount of money used to acquire the current holding of
            # shares. This value increases when buying shares, and decreases
            # when selling them.
            cost_basis = decimal.Decimal()

            # Total amount of fees incurred on the position. This value
            # increases when buying and selling shares.
            fees = decimal.Decimal()

            for tx in shares["txs"]:
                tx_fee = abs(tx["shares"]["fee"]["amount"])
                tx_value = tx["value"]
                tx_shares = tx["shares"]["no"]

                shares_held += tx_shares

                transaction_sign = tx_shares / abs(tx_shares)
                v = (transaction_sign * tx_value) + tx_fee
                if tx_shares < 0 and v > 0:
                    raise Exception(
                        name,
                        company,
                        tx_shares,
                        (tx_value, tx_fee),
                        transaction_sign,
                        v,
                    )
                cost_basis += v

                fees += tx_fee

            shares["v2_shares_held"] = shares_held
            shares["v2_cost_basis"] = cost_basis
            shares["v2_fees"] = fees

            market_value = shares_held * share_price
            shares["v2_market_value"] = market_value

            total_return = market_value - cost_basis + dividends
            shares["v2_total_return"] = total_return

        # Market value
        #
        # This is a value representing the account's worth on the market, or its
        # liquidation value. It is a simple sum of each position's market value.
        account["v2_market_value"] = decimal.Decimal()

        # Cost basis
        #
        # This is the sum of each position's cost ie, what you had to pay to
        # acquire the shares.
        # This value increases when buying shares, and decreases when selling
        # them by the value of the transaction. In both cases, the cost basis is
        # increased by the fees incurred.
        #
        # If you bought 100 shares of FOO for 1 EUR each, and incurred a 1 EUR
        # fee your cost basis would be 101 EUR for 100 shares.
        # If you then sold 50 shares for 1 EUR each, and incurred another 1 EUR
        # fee your cost basis would be 52 EUR for 50 shares.
        account["v2_cost_basis"] = decimal.Decimal()

        # Total return
        #
        # Total return is calculated as current market value minus cost basis,
        # plus any dividends. For the whole account it can be trivially
        # calculated as a sum of total return of each position.
        account["v2_total_return"] = decimal.Decimal()

        for stats in account["shares"].values():
            account["v2_cost_basis"] += stats["v2_cost_basis"]
            account["v2_market_value"] += stats["v2_market_value"]
            account["v2_total_return"] += stats["v2_total_return"]
