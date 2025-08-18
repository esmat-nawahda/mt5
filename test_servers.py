import MetaTrader5 as mt5

login = 7924280
password = "2ZZ9j$zp"

# Common MT5 demo server names to try
servers = [
    "MetaQuotes-Demo",
    "MetaQuotes-Demo",
    "ICMarkets-Demo",
    "ICMarkets-Demo01", 
    "ICMarkets-Demo02",
    "ICMarkets-Demo03",
    "Pepperstone-Demo",
    "Pepperstone-Demo01",
    "XMGlobal-Demo",
    "XMGlobal-Demo 3",
    "FTMO-Demo",
    "FTMO-Demo2",
    "Demo",
    None  # Try without specifying server
]

print(f"Testing login {login} with different servers...\n")

for server in servers:
    if server:
        print(f"Trying server: {server}")
        result = mt5.initialize(login=login, password=password, server=server)
    else:
        print("Trying without server specification")
        result = mt5.initialize(login=login, password=password)
    
    if result:
        print(f"✓ SUCCESS! Connected to {server if server else 'default server'}")
        account = mt5.account_info()
        if account:
            print(f"  Account: {account.login}")
            print(f"  Server: {account.server}")
            print(f"  Balance: {account.balance}")
            print(f"  Currency: {account.currency}")
        mt5.shutdown()
        break
    else:
        error = mt5.last_error()
        print(f"  Failed: {error}")
        
if not result:
    print("\nCould not connect with any of the tested servers.")
    print("Please check:")
    print("1. Your MT5 terminal is running")
    print("2. The account number and password are correct")
    print("3. You know the exact server name for this account")