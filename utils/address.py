from eth_account import Account
import os

def get_address_from_private_key() -> str:
    """Derive Ethereum address from private key in environment variables"""
    private_key = os.getenv('PRIVATE_KEY')
    if not private_key:
        raise ValueError("PRIVATE_KEY environment variable is not set")
        
    if not private_key.startswith('0x'):
        private_key = f'0x{private_key}'
        
    account = Account.from_key(private_key)
    return account.address
