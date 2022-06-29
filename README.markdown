# Maelkum's ledger

A simple tool to keep track of expenses and revnues.
Based on accounts and transactions.

    # Open accounts
    open account 2019-08-01 asset bank.main_account
        balance: 0.00 PLN
    with
        main
        overview
    end
    open account 2019-08-01 asset bank.savings_account
        balance: 100.00 PLN
    with
        overview
    end

    # Set a balance on them
    balance 2019-08-01
        asset/bank.main_account 1000.00 PLN
    end

    # Set a spending limit to keep you expenses in check
    set budget 50.0 %

    # Record revenues :-)
    rx 2019-08-01T09:42 Salary
        EMPLOYER
        asset/bank.main_account 1000.00 PLN
    end

    # Record expenses :-(
    ex 2019-08-01T12:48
        asset/bank.main_account -15.00 PLN
        BEST ASIAN FOOD PLACE IN TOWN
    end

    # Record transfers between your own accounts :-|
    tx 2019-08-01T13:37
        asset/bank.main_account    -100.00 PLN
        asset/bank.savings_account  100.00 PLN
    end

    # Record revenues in the future
    rx 2022-06-14T12:00 Summer bonus
        asset/bank.main_account 1.00 PLN
        EMPLOYER
    with
        effective_date: 2022-07-01T00:00
    end

    # Record currency changes
    tx 2022-06-29T12:00
        asset/bank.eur -1.00 EUR
        asset/bank.pln  4.69 PLN
    with
        rate: EUR/PLN 4.6900
    end

    # Record equity transactions...
    tx 2022-06-29T12:00
        asset/broker.usd       -3.00 USD
        equity/broker.EXCHANGE  2.00 USD
    with
        shares: COMPANY 1
        fee: -1.00 USD
        intermediary: BROKER INC.
    end

    # dividends...
    dividend 2022-06-29T12:01
        asset/broker.usd 1.00 USD
        equity/broker.EXCHANGE COMPANY
    end

    # ...and share price changes.
    balance 2022-06-29T12:02
        equity/broker.EXCHANGE COMPANY 1.00 USD
    end

--------------------------------------------------------------------------------

# Copyright and license

Copyright (C) 2019-2022 Marek Marecki

This is Free Software published under GNU GPL v3 license. See LICENSE for full
text of the license and educate yourself about your rights.
