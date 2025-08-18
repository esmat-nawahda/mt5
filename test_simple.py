import MetaTrader5 as mt5

# Try connecting to already running terminal without credentials
print("Attempting to connect to running MT5 terminal...")
if mt5.initialize():
    print("Connected successfully!")
    account = mt5.account_info()
    if account:
        print(f"Account: {account.login}")
        print(f"Server: {account.server}")
        print(f"Balance: {account.balance}")
    mt5.shutdown()
else:
    error = mt5.last_error()
    print(f"Connection failed: {error}")
    
    print("\nTrying with credentials from .env...")
    if mt5.initialize(login=7924280, password="2ZZ9j$zp", server="MetaQuotes-Demo"):
        print("Connected with credentials!")
        account = mt5.account_info()
        if account:
            print(f"Account: {account.login}")
            print(f"Server: {account.server}") 
        mt5.shutdown()
    else:
        print(f"Still failed: {mt5.last_error()}")