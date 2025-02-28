import random
from typing import Dict
from eth_account import Account
from primp import AsyncClient
from web3 import AsyncWeb3
import asyncio

from src.model.orbiter.constants import SEPOLIA_EXPLORER_URL, SEPOLIA_RPC_URL, MONAD_SEPOLIA_ETHEREUM_ADDRESS, SEPOLIA_BRIDGE_ADDRESS
from src.utils.client import create_client
from src.utils.config import Config
from loguru import logger
from src.utils.constants import RPC_URL, ERC20_ABI


class Orbiter:
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
        self.web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(SEPOLIA_RPC_URL))
        self.monad_web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))
        
        # Initialize ERC20 contract
        self.monad_sepolia = self.monad_web3.eth.contract(
            address=self.monad_web3.to_checksum_address(MONAD_SEPOLIA_ETHEREUM_ADDRESS),
            abi=ERC20_ABI
        )
        
    async def get_gas_params(self) -> Dict[str, int]:
        latest_block = await self.web3.eth.get_block('latest')
        base_fee = latest_block['baseFeePerGas']
        max_priority_fee = await self.web3.eth.max_priority_fee
        
        # Multiply both fees by 1.5
        max_priority_fee = int(max_priority_fee * 1.5)
        max_fee = int((base_fee + max_priority_fee) * 1.5)
        
        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }
    
    # 等待资金到达 Monad 网络。
    async def wait_for_funds(self, initial_balance: int):
        """Wait for funds to arrive in Monad network."""
        max_attempts = self.config.ORBITER.MAX_WAIT_TIME // 10  # 将总等待时间转换为 10 秒尝试次数
        
        logger.info(f"[{self.account_index}] Waiting for funds to arrive in Monad (max wait time: {self.config.ORBITER.MAX_WAIT_TIME} seconds)...")
        for attempt in range(max_attempts):
            try:
                current_balance = await self.monad_sepolia.functions.balanceOf(
                    self.account.address
                ).call()
                
                if current_balance > initial_balance:
                    logger.success(f"[{self.account_index}] Funds arrived in Monad!")
                    return True
                
                logger.info(f"[{self.account_index}] Still waiting for funds... (attempt {attempt + 1}/{max_attempts}, {(max_attempts - attempt) * 10} seconds remaining)")
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"[{self.account_index}] Error checking token balance: {str(e)}")
                await asyncio.sleep(10)
                
        logger.warning(f"[{self.account_index}] Timeout waiting for funds after {self.config.ORBITER.MAX_WAIT_TIME} seconds")
        return False

    # 通过 Orbiter 将 ETH 从 Sepolia 桥接到 Monad。
    async def bridge(self):
        """Bridge ETH from Sepolia to Monad via Orbiter."""
        try:
            # 如果我们需要等待资金，请获取 Monad 上的初始余额
            initial_monad_balance = 0
            if self.config.ORBITER.WAIT_FOR_FUNDS_TO_ARRIVE:
                initial_monad_balance = await self.monad_sepolia.functions.balanceOf(
                    self.account.address
                ).call()

            # Get current balance in Wei
            balance_wei = await self.web3.eth.get_balance(self.account.address)
            
            # Get gas parameters for fee estimation
            gas_params = await self.get_gas_params()
            gas_cost_wei = gas_params['maxFeePerGas'] * 21000
            
            # 确定桥接金额数量
            if self.config.ORBITER.BRIDGE_ALL:  # 全部桥接
                # 桥接全部余额减去 gas，确保我们留出足够的 gas
                gas_cost_with_buffer = int(gas_cost_wei * 1.05)
                if balance_wei <= gas_cost_with_buffer:
                    logger.error(f"[{self.account_index}] Balance too low to cover gas costs")
                    return False
                    
                # Leave some extra buffer for gas (5%)
                amount_wei = balance_wei - gas_cost_with_buffer # 留一些额外的gas（5%）
                
                # 转换为 ETH 字符串
                base_amount = self.web3.from_wei(amount_wei, 'ether')
                amount_str = str(base_amount)
                
            else:
                # 配置范围中的随机金额，具有随机精度（5-12 位小数）
                base_amount = random.uniform(
                    self.config.ORBITER.AMOUNT_TO_BRIDGE[0],
                    self.config.ORBITER.AMOUNT_TO_BRIDGE[1]
                )
                # 四舍五入为 5 至 12 位小数之间的随机精度
                precision = random.randint(5, 12)
                amount_str = f"{base_amount:.{precision}f}"

            # 确保精确到小数点后 14 位 + 9596
            if '.' not in amount_str:
                amount_str += '.'
            whole, decimal = amount_str.split('.')
            # 用零填充以获得恰好 14 位小数
            decimal = (decimal + '0' * 14)[:14]
            formatted_amount = f"{whole}.{decimal}9596"
            
            amount_wei = self.web3.to_wei(formatted_amount, 'ether')
            logger.info(f"[{self.account_index}] Bridging amount: {formatted_amount} ETH")

            # 准备交易
            transaction = {
                'from': self.account.address,
                'to': SEPOLIA_BRIDGE_ADDRESS,  # 调整成配置文件获取跨链桥地址，合约地址的合法性有待验证 "0xB5AADef97d81A77664fcc3f16Bfe328ad6CEc7ac",   #   bridge address
                'value': amount_wei,
                'nonce': await self.web3.eth.get_transaction_count(self.account.address),
                'chainId': 11155111,
                'type': 2,
                'gas': 21000,   # 这里用了固定的gas
                **gas_params
            }

            # 签署并发送交易
            try:
                signed_txn = self.web3.eth.account.sign_transaction(transaction, self.private_key)
                tx_hash = await self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
                tx_hash_str = tx_hash.hex()
                if tx_hash_str.startswith('0x'):
                    tx_hash_str = tx_hash_str[2:]  # Remove '0x' prefix if present
                
                logger.info(f"[{self.account_index}] Waiting for bridge transaction confirmation...")
                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt['status'] == 1:
                    logger.success(f"[{self.account_index}] Successfully initiated bridge to Monad. TX: {SEPOLIA_EXPLORER_URL}{tx_hash_str}")
                    
                    if self.config.ORBITER.WAIT_FOR_FUNDS_TO_ARRIVE:
                        return await self.wait_for_funds(initial_monad_balance)
                    return True
                else:
                    logger.error(f"[{self.account_index}] Bridge transaction failed! TX: {SEPOLIA_EXPLORER_URL}{tx_hash_str}")
                    return False
                    
            except Exception as e:
                logger.error(f"[{self.account_index}] Failed to send or confirm transaction: {str(e)}")
                return False

        except Exception as e:
            if "insufficient funds" in str(e).lower():
                logger.error(f"[{self.account_index}] Insufficient funds to cover bridge and gas costs")
                return False
            
            logger.error(f"[{self.account_index}] Error in bridge: {str(e)}")
            return False
