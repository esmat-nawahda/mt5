import MetaTrader5 as mt5

# Initialize MT5
if mt5.initialize(login=7924280, password="2ZZ9j$zp", server="Eightcap-Demo"):
    print("Connected to MT5!")
    
    # Check each symbol
    symbols_to_check = ["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD"]
    available_symbols = []
    
    for symbol in symbols_to_check:
        info = mt5.symbol_info(symbol)
        if info:
            print(f"[OK] {symbol} - Available")
            available_symbols.append(symbol)
            # Try to select it
            if not info.visible:
                if mt5.symbol_select(symbol, True):
                    print(f"  - Selected {symbol}")
                else:
                    print(f"  - Could not select {symbol}")
        else:
            print(f"[X] {symbol} - Not found")
            # Try alternative names
            alternatives = [
                symbol.lower(),
                symbol + ".a",
                symbol + ".raw", 
                symbol + ".",
                symbol + "m",
                symbol.replace("USD", "")
            ]
            for alt in alternatives:
                if mt5.symbol_info(alt):
                    print(f"  Found as: {alt}")
                    available_symbols.append(alt)
                    break
    
    print(f"\nAvailable symbols: {available_symbols}")
    
    # List all forex symbols
    print("\nAll available symbols containing 'EUR' or 'GBP' or 'XAU' or 'BTC':")
    all_symbols = mt5.symbols_get()
    for sym in all_symbols:
        name = sym.name.upper()
        if 'EUR' in name or 'GBP' in name or 'XAU' in name or 'BTC' in name:
            print(f"  {sym.name}")
    
    mt5.shutdown()
else:
    print(f"Failed to connect: {mt5.last_error()}")