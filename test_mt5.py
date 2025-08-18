import MetaTrader5 as mt5

print('MT5 package version:', mt5.__version__)
print('Initializing MT5...')

result = mt5.initialize(
    login=5039201565,
    password="ElEdOzl5",
    server="MetaQuotes-Demo"
)

print('Init result:', result)

if result:
    print('Successfully connected!')
    account_info = mt5.account_info()
    if account_info:
        print(f'Account: {account_info.login}')
        print(f'Server: {account_info.server}')
        print(f'Balance: {account_info.balance}')
        print(f'Equity: {account_info.equity}')
    mt5.shutdown()
else:
    error = mt5.last_error()
    print(f'Error: {error}')
    print('\nPossible issues:')
    print('1. MetaTrader 5 terminal is not installed or not running')
    print('2. Login credentials are incorrect')
    print('3. Server name might be different')
    print('\nPlease ensure MT5 terminal is installed and running')