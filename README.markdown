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
        BEST CHINESE PLACE IN TOWN
    end

    # Record transfers between your own accounts :-|
    tx 2019-08-01T13:37
        asset/bank.main_account    -100.00 PLN
        asset/bank.savings_account  100.00 PLN
    end

--------------------------------------------------------------------------------

# Copyright and license

Copyright (C) 2019 Marek Marecki

This is Free Software published under GNU GPL v3 license. See LICENSE for full
text of the license and educate yourself about your rights.
