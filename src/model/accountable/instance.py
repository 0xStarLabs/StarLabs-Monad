import asyncio
import random
from typing import Dict
from eth_account import Account
from primp import AsyncClient
from web3 import AsyncWeb3
from web3.contract import Contract

from src.utils.constants import EXPLORER_URL, RPC_URL
from src.utils.client import create_client
from src.utils.config import Config
from loguru import logger
from src.model.accountable.constants import ACCOUNTABLE_ABI


class Accountable:
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

        self.nft_contract_address = "0xfa67a16ccC5d2C3d80e5DaF692DDfbb53F8D7Cfd"
        self.nft_contract = self.web3.eth.contract(
            address=self.nft_contract_address,
            abi=ACCOUNTABLE_ABI
        )

    async def get_gas_params(self) -> Dict[str, int]:
        latest_block = await self.web3.eth.get_block('latest')
        base_fee = latest_block['baseFeePerGas']
        max_priority_fee = await self.web3.eth.max_priority_fee
        max_fee = base_fee + max_priority_fee
        
        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }
    
    async def get_mint_signature(self, token_id: int):
        """Get signature for minting NFT."""
        max_retries = 5
        json_data = {
            'userAddress': self.account.address.lower(),
            'tokenId': token_id,
        }

        for attempt in range(max_retries):
            try:
                response = await self.session.post(
                    'https://game.accountable.capital/api/generate-signature-mint',
                    json=json_data,
                )
                
                if response.status_code != 200:
                    raise Exception(f"Failed to get signature. Status code: {response.status_code}")

                data = response.json()
                nonce = data.get("nonce", 0)
                
                # Check if account reached NFT limit
                if nonce >= self.config.ACCOUNTABLE.NFT_PER_ACCOUNT_LIMIT:
                    logger.warning(f"[{self.account_index}] Account already minted {nonce} NFTs (limit: {self.config.ACCOUNTABLE.NFT_PER_ACCOUNT_LIMIT})")
                    return None
                
                logger.success(f"[{self.account_index}] Successfully got mint signature for token #{token_id} (minted: {nonce})")
                return data["signature"]

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[{self.account_index}] Failed to get signature after {max_retries} attempts: {str(e)}")
                    return None
                logger.error(f"[{self.account_index}] Attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(random.randint(
                    self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                    self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1]
                ))
    
    async def get_nft_balances(self) -> list:
        """Check balances of all NFT IDs (1-7) for the wallet."""
        try:
            balances = []
            for token_id in range(1, 8):  # Check IDs 1 through 7
                balance = await self.nft_contract.functions.balanceOf(
                    self.account.address,
                    token_id
                ).call()
                if balance > 0:
                    balances.append(token_id)
                    logger.info(f"[{self.account_index}] Already owns NFT #{token_id}")
            
            return balances
        except Exception as e:
            logger.error(f"[{self.account_index}] Error checking NFT balances: {str(e)}")
            return []

    async def mint(self):
        """Execute NFT minting with signature."""
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                # Get currently owned NFTs
                owned_nfts = await self.get_nft_balances()
                
                # Get available NFTs to mint (ones we don't own)
                available_nfts = [i for i in range(1, 8) if i not in owned_nfts]
                
                if not available_nfts:
                    logger.success(f"[{self.account_index}] Already own all available NFTs")
                    return True

                # Pick random NFT from available ones
                token_id = random.choice(available_nfts)
                logger.info(f"[{self.account_index}] Selected token ID {token_id} for minting from available IDs: {available_nfts}")
                
                signature = await self.get_mint_signature(token_id)
                if not signature:
                    logger.success(f"[{self.account_index}] Skipping mint - NFT limit reached (CHECK LIMIT IN CONFIG)")
                    return True

                logger.info(f"[{self.account_index}] Minting NFT #{token_id} with signature")

                # Convert hex signature to bytes
                signature_bytes = bytes.fromhex(signature.replace('0x', ''))

                # Estimate gas for the mint transaction
                gas_estimate = await self.nft_contract.functions.mint(
                    token_id,
                    signature_bytes
                ).estimate_gas({
                    'from': self.account.address
                })

                # Get gas parameters
                gas_params = await self.get_gas_params()

                # Prepare mint transaction
                mint_txn = await self.nft_contract.functions.mint(
                    token_id,
                    signature_bytes
                ).build_transaction({
                    'from': self.account.address,
                    'nonce': await self.web3.eth.get_transaction_count(self.account.address),
                    'gas': int(gas_estimate * 1.1),
                    'chainId': 10143,
                    'type': 2,
                    **gas_params
                })

                # Sign and send transaction
                signed_txn = self.web3.eth.account.sign_transaction(mint_txn, self.private_key)
                tx_hash = await self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)

                logger.info(f"[{self.account_index}] Waiting for mint transaction confirmation...")
                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt['status'] == 1:
                    logger.success(f"[{self.account_index}] Successfully minted NFT #{token_id}. TX: {EXPLORER_URL}{tx_hash.hex()}")
                    return True
                else:
                    logger.error(f"[{self.account_index}] Mint transaction failed! TX: {EXPLORER_URL}{tx_hash.hex()}")
                    return False

            except Exception as e:
                if "insufficient funds" in str(e).lower():
                    logger.error(f"[{self.account_index}] Insufficient funds to cover gas costs")
                    return False
                
                random_pause = random.randint(
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1]
                )
                logger.error(f"[{self.account_index}] Error minting NFT: {str(e)}. Sleeping for {random_pause} seconds")
                await asyncio.sleep(random_pause)

        return False
