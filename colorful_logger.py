"""
Enhanced colorful logging for MT5 bot with detailed trade information
"""

import os
import sys
from datetime import datetime

# ANSI color codes for terminal output
class Colors:
    # Basic colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Background colors
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'
    
    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    HIDDEN = '\033[8m'
    STRIKETHROUGH = '\033[9m'
    
    # Reset
    RESET = '\033[0m'
    
# Enable ANSI colors on Windows
if os.name == 'nt':
    os.system('color')
    # Enable ANSI escape sequences on Windows 10+
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

def print_header():
    """Print colorful header"""
    print(f"\n{Colors.BRIGHT_CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}{Colors.BOLD}       MT5 MULTI-PAIR AI TRADING BOT - POWERED BY DEEPSEEK{Colors.RESET}")
    print(f"{Colors.BRIGHT_CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BRIGHT_GREEN}Trading Pairs: {Colors.WHITE}XAUUSD, BTCUSD{Colors.RESET}")
    print(f"{Colors.BRIGHT_GREEN}Volume: {Colors.WHITE}1.00 Lots{Colors.RESET}")
    print(f"{Colors.BRIGHT_GREEN}Min Confidence: {Colors.WHITE}78%{Colors.RESET}")
    print(f"{Colors.BRIGHT_CYAN}{'='*80}{Colors.RESET}\n")

def print_cycle_start(cycle_num):
    """Print cycle start"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{Colors.BRIGHT_MAGENTA}{'-'*80}{Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}{Colors.BOLD}[CYCLE #{cycle_num}] {timestamp}{Colors.RESET}")
    print(f"{Colors.BRIGHT_MAGENTA}{'-'*80}{Colors.RESET}")

def print_market_data(symbol, price, rates_info=None):
    """Print current market data"""
    print(f"\n{Colors.BRIGHT_CYAN}[MARKET DATA] - {symbol}{Colors.RESET}")
    print(f"  {Colors.WHITE}Current Price: {Colors.BRIGHT_GREEN}${price:.5f}{Colors.RESET}")
    if rates_info:
        print(f"  {Colors.WHITE}High: {Colors.GREEN}${rates_info['high']:.5f}{Colors.RESET}")
        print(f"  {Colors.WHITE}Low: {Colors.RED}${rates_info['low']:.5f}{Colors.RESET}")
        print(f"  {Colors.WHITE}Volume: {Colors.YELLOW}{rates_info['volume']}{Colors.RESET}")

def print_ai_analysis(symbol, action, confidence, entry=None, sl=None, tp=None):
    """Print AI analysis results"""
    print(f"\n{Colors.BRIGHT_BLUE}[AI ANALYSIS] - {symbol}{Colors.RESET}")
    
    # Confidence with color coding
    conf_color = Colors.BRIGHT_GREEN if confidence >= 78 else Colors.BRIGHT_YELLOW if confidence >= 50 else Colors.BRIGHT_RED
    print(f"  {Colors.WHITE}Confidence: {conf_color}{confidence:.1f}%{Colors.RESET}")
    
    # Action with color coding
    if action == "BUY":
        action_color = Colors.BRIGHT_GREEN
        action_icon = "[BUY]"
    elif action == "SELL":
        action_color = Colors.BRIGHT_RED
        action_icon = "[SELL]"
    else:
        action_color = Colors.BRIGHT_YELLOW
        action_icon = "[WAIT]"
    
    print(f"  {Colors.WHITE}Signal: {action_color}{action_icon} {action}{Colors.RESET}")
    
    if entry and sl and tp:
        print(f"  {Colors.WHITE}Entry Price: {Colors.BRIGHT_CYAN}${entry:.5f}{Colors.RESET}")
        print(f"  {Colors.WHITE}Stop Loss: {Colors.RED}${sl:.5f}{Colors.RESET}")
        print(f"  {Colors.WHITE}Take Profit: {Colors.GREEN}${tp:.5f}{Colors.RESET}")
        
        # Calculate risk/reward
        if action == "BUY":
            risk = entry - sl
            reward = tp - entry
        else:
            risk = sl - entry
            reward = entry - tp
        
        if risk > 0:
            rr_ratio = reward / risk
            rr_color = Colors.BRIGHT_GREEN if rr_ratio >= 2 else Colors.YELLOW if rr_ratio >= 1 else Colors.RED
            print(f"  {Colors.WHITE}Risk/Reward: {rr_color}1:{rr_ratio:.2f}{Colors.RESET}")
            print(f"  {Colors.WHITE}Risk Amount: {Colors.RED}${risk:.5f}{Colors.RESET}")
            print(f"  {Colors.WHITE}Reward Amount: {Colors.GREEN}${reward:.5f}{Colors.RESET}")

def print_trade_decision(symbol, decision, reason=""):
    """Print trade decision"""
    print(f"\n{Colors.BRIGHT_YELLOW}[TRADE DECISION] - {symbol}{Colors.RESET}")
    
    if decision == "OPEN":
        print(f"  {Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} >> OPENING TRADE << {Colors.RESET}")
    elif decision == "SKIP":
        print(f"  {Colors.BG_YELLOW}{Colors.BLACK}{Colors.BOLD} -- SKIPPING TRADE -- {Colors.RESET}")
    elif decision == "BLOCKED":
        print(f"  {Colors.BG_RED}{Colors.WHITE}{Colors.BOLD} !! BLOCKED BY NEWS !! {Colors.RESET}")
    elif decision == "UPDATE":
        print(f"  {Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD} ~~ UPDATING SL/TP ~~ {Colors.RESET}")
    
    if reason:
        print(f"  {Colors.DIM}Reason: {reason}{Colors.RESET}")

def print_position_status(positions):
    """Print current open positions"""
    if positions:
        print(f"\n{Colors.BRIGHT_MAGENTA}[OPEN POSITIONS]{Colors.RESET}")
        for symbol, pos in positions.items():
            profit_color = Colors.BRIGHT_GREEN if pos.profit >= 0 else Colors.BRIGHT_RED
            print(f"  {Colors.WHITE}{symbol}:{Colors.RESET}")
            print(f"    Type: {Colors.CYAN}{pos.type_description}{Colors.RESET}")
            print(f"    Volume: {Colors.YELLOW}{pos.volume} lots{Colors.RESET}")
            print(f"    Open Price: {Colors.WHITE}${pos.price_open:.5f}{Colors.RESET}")
            print(f"    Current P/L: {profit_color}${pos.profit:.2f}{Colors.RESET}")
    else:
        print(f"\n{Colors.DIM}No open positions{Colors.RESET}")

def print_news_status(blocked_pairs):
    """Print news filter status"""
    if blocked_pairs:
        print(f"\n{Colors.BRIGHT_RED}[NEWS ALERTS]{Colors.RESET}")
        for pair, event in blocked_pairs.items():
            print(f"  {Colors.RED}[!] {pair}: {event}{Colors.RESET}")
    else:
        print(f"\n{Colors.BRIGHT_GREEN}[OK] No high-impact news events{Colors.RESET}")

def print_next_cycle(seconds):
    """Print next cycle timing"""
    minutes = seconds // 60
    secs = seconds % 60
    print(f"\n{Colors.DIM}Next cycle in {minutes}m {secs}s...{Colors.RESET}")
    print(f"{Colors.BRIGHT_MAGENTA}{'-'*80}{Colors.RESET}")

def print_error(error_msg):
    """Print error message"""
    print(f"\n{Colors.BG_RED}{Colors.WHITE}{Colors.BOLD} [X] ERROR {Colors.RESET}")
    print(f"{Colors.BRIGHT_RED}{error_msg}{Colors.RESET}")

def print_success(success_msg):
    """Print success message"""
    print(f"\n{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} [OK] SUCCESS {Colors.RESET}")
    print(f"{Colors.BRIGHT_GREEN}{success_msg}{Colors.RESET}")

def print_warning(warning_msg):
    """Print warning message"""
    print(f"\n{Colors.BG_YELLOW}{Colors.BLACK}{Colors.BOLD} [!] WARNING {Colors.RESET}")
    print(f"{Colors.BRIGHT_YELLOW}{warning_msg}{Colors.RESET}")

def print_info(info_msg):
    """Print info message"""
    print(f"{Colors.BRIGHT_CYAN}[i] {info_msg}{Colors.RESET}")

def print_separator():
    """Print a separator line"""
    print(f"{Colors.DIM}{'-'*80}{Colors.RESET}")