import asyncio
import random
import string
from eth_account import Account
from loguru import logger
from primp import AsyncClient
from web3 import AsyncWeb3
from typing import Dict, Optional, Tuple

from src.utils.config import Config
from src.utils.constants import RPC_URL, EXPLORER_URL
from src.model.nad_domains.constants import NAD_CONTRACT_ADDRESS, NAD_API_URL, NAD_ABI, NAD_NFT_ADDRESS, NAD_NFT_ABI


class NadDomains:
    def __init__(
        self,
        account_index: int,
        proxy: str,
        private_key: str,
        config: Config,
        session: AsyncClient,
    ):
        self.account_index = account_index
        self.proxy = proxy
        self.private_key = private_key
        self.config = config
        self.session = session

        self.account: Account = Account.from_key(private_key=private_key)
        self.web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))
        
        # Initialize contract using constants
        self.contract = self.web3.eth.contract(
            address=self.web3.to_checksum_address(NAD_CONTRACT_ADDRESS),
            abi=NAD_ABI
        )
        
        # Initialize NAD NFT contract
        self.nft_contract = self.web3.eth.contract(
            address=self.web3.to_checksum_address(NAD_NFT_ADDRESS),
            abi=NAD_NFT_ABI
        )

    async def get_gas_params(self) -> Dict[str, int]:
        """Get current gas parameters from the network."""
        latest_block = await self.web3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        max_priority_fee = await self.web3.eth.max_priority_fee

        # Calculate maxFeePerGas (base fee + priority fee)
        max_fee = base_fee + max_priority_fee

        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }

    def generate_random_name(self, min_length=6, max_length=12) -> str:
        """Generate a random domain name."""
        # Choose a random length between min and max
        length = random.randint(min_length, max_length)
        
        # Generate random string with letters and numbers
        characters = string.ascii_lowercase + string.digits
        name = ''.join(random.choice(characters) for _ in range(length))
        
        # Ensure it starts with a letter
        if name[0].isdigit():
            name = random.choice(string.ascii_lowercase) + name[1:]
        
        return name

    async def get_signature(self, name: str) -> Optional[Dict]:
        """Get signature from API for domain registration."""
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'origin': 'https://app.nad.domains',
            'referer': 'https://app.nad.domains/',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
        }
        print(name)
        params = {
            'name': name,
            'nameOwner': self.account.address,
            'setAsPrimaryName': 'true',
            'referrer': '0x0000000000000000000000000000000000000000',
            'discountKey': '0x0000000000000000000000000000000000000000000000000000000000000000',
            'discountClaimProof': '0x0000000000000000000000000000000000000000000000000000000000000000',
            'chainId': '10143',
        }
        
        try:
            response = await self.session.get(NAD_API_URL, params=params, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"[{self.account_index}] API error: Status code {response.status_code}")
                return None
            
            data = response.json()
            if data.get('success'):
                logger.info(f"[{self.account_index}] Got signature for domain {name}")
                # Store the signature exactly as returned from API
                return {
                    'signature': data['signature'],  # Keep as is, web3.py will handle the format
                    'nonce': int(data['nonce']),     # Make sure we have it as an integer
                    'deadline': int(data['deadline'])
                }
            else:
                logger.error(f"[{self.account_index}] API error: {data.get('message', 'Unknown error')}")
                return None
                
        except Exception as e:
            logger.error(f"[{self.account_index}] Error getting signature: {str(e)}")
            return None

    async def is_name_available(self, name: str) -> bool:
        """Check if domain name is available."""
        try:
            signature_data = await self.get_signature(name)
            return signature_data is not None
        except Exception as e:
            logger.error(f"[{self.account_index}] Error checking name availability: {str(e)}")
            return False

    async def register_domain(self, name: str) -> bool:
        """Register a domain name using the NAD Domains smart contract."""
        try:
            # Get signature from API
            signature_data = await self.get_signature(name)
            if not signature_data:
                logger.error(f"[{self.account_index}] Could not get signature for {name}")
                return False
            
            # Use fixed fee of 0.02 MON
            fee = self.web3.to_wei(0.02, 'ether')
            logger.info(f"[{self.account_index}] Using fixed registration fee of 0.02 MON for {name}")
            
            # Debug log the signature and parameters
            logger.debug(f"[{self.account_index}] Signature: {signature_data['signature']}")
            logger.debug(f"[{self.account_index}] Nonce: {signature_data['nonce']}")
            logger.debug(f"[{self.account_index}] Deadline: {signature_data['deadline']}")
            
            register_data = [
                name,                                 # name
                self.account.address,                # nameOwner
                True,                                # setAsPrimaryName
                "0x0000000000000000000000000000000000000000",  # referrer
                "0x0000000000000000000000000000000000000000000000000000000000000000", # discountKey
                "0x0000000000000000000000000000000000000000000000000000000000000000", # discountClaimProof - use the same value from API
                signature_data['nonce'],              # nonce
                signature_data['deadline']            # deadline
            ]
            
            # Pass the signature exactly as received from API
            signature = signature_data['signature']
            
            # Get gas parameters
            gas_params = await self.get_gas_params()
            
            # Estimate gas for the transaction
            try:
                gas_estimate = await self.contract.functions.registerWithSignature(
                    register_data,
                    signature
                ).estimate_gas({
                    'from': self.account.address,
                    'value': fee
                })
                # Add 20% buffer to gas estimate to ensure transaction doesn't run out of gas
                gas_with_buffer = int(gas_estimate * 1.2)
                logger.info(f"[{self.account_index}] Estimated gas: {gas_estimate}, with buffer: {gas_with_buffer}")
            except Exception as e:
                # If gas estimation fails, log error and return false
                logger.error(f"[{self.account_index}] Gas estimation failed: {str(e)}. Cannot proceed with registration.")
                return False
            
            # Build the transaction
            transaction = await self.contract.functions.registerWithSignature(
                register_data,
                signature
            ).build_transaction({
                'from': self.account.address,
                'value': fee,
                'gas': gas_with_buffer,
                'nonce': await self.web3.eth.get_transaction_count(self.account.address),
                'chainId': 10143,
                'type': 2,
                **gas_params
            })
            
            # Sign the transaction
            signed_txn = self.web3.eth.account.sign_transaction(transaction, self.private_key)
            
            # Send the transaction
            tx_hash = await self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
            logger.info(f"[{self.account_index}] Registering {name} - Transaction sent: {EXPLORER_URL}{tx_hash.hex()}")
            
            # Wait for transaction receipt
            receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
            success = receipt['status'] == 1
            
            if success:
                logger.success(f"[{self.account_index}] Successfully registered {name}! TX: {EXPLORER_URL}{tx_hash.hex()}")
            else:
                logger.error(f"[{self.account_index}] Failed to register {name}. TX: {EXPLORER_URL}{tx_hash.hex()}")
            
            return success
        
        except Exception as e:
            logger.error(f"[{self.account_index}] Error registering {name}: {str(e)}")
            return False

    async def has_domain(self) -> bool:
        """Check if wallet already owns a NAD domain."""
        try:
            balance = await self.nft_contract.functions.balanceOf(self.account.address).call()
            if balance > 0:
                logger.info(f"[{self.account_index}] Wallet already owns {balance} NAD domain(s)")
                return True
            return False
        except Exception as e:
            logger.error(f"[{self.account_index}] Error checking NAD domain balance: {str(e)}")
            return False

    async def register_random_domain(self) -> bool:
        """Register a random domain name with retry logic."""
        try:
            # First check if wallet already has a domain
            if await self.has_domain():
                logger.success(f"[{self.account_index}] Wallet already has a NAD domain, skipping registration")
                return True
                
            # Continue with registration if no domain is owned
            for retry in range(self.config.SETTINGS.ATTEMPTS):
                try:
                    # Generate a random name
                    name = self.generate_random_name()
                    logger.info(f"[{self.account_index}] Generated random domain name: {name}")
                    
                    # Check if the name is available
                    if await self.is_name_available(name):
                        logger.info(f"[{self.account_index}] Domain {name} is available, registering...")
                        
                        # Register the domain
                        if await self.register_domain(name):
                            return True
                    else:
                        logger.warning(f"[{self.account_index}] Domain {name} is not available, trying another...")
                        continue
                    
                except Exception as e:
                    random_pause = random.randint(
                        self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
                        self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1]
                    )
                    logger.error(f"[{self.account_index}] Error registering domain (attempt {retry+1}/{self.config.SETTINGS.ATTEMPTS}): {str(e)}. Sleeping for {random_pause} seconds")
                    await asyncio.sleep(random_pause)
            
            return False
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in register_random_domain: {str(e)}")
            return False

