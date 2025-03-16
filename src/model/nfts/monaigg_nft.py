import asyncio
import random
from eth_account import Account
from primp import AsyncClient
from web3 import AsyncWeb3
from web3.contract import Contract

from src.utils.constants import EXPLORER_URL, RPC_URL
from src.utils.config import Config
from loguru import logger

# Обновляем ABI для ERC1155
# Обновляем ABI для MonAI Yakuza NFT
MONAI_YAKUZA_ABI = [
    {
        "type": "function",
        "name": "mint",
        "inputs": [
            {"name": "quantity", "type": "uint256", "internalType": "uint256"},
            {"name": "refer", "type": "address", "internalType": "address"},
        ],
        "outputs": [],
        "stateMutability": "payable",
    },
    {
        "type": "function",
        "name": "balanceOf",
        "inputs": [{"name": "owner", "type": "address", "internalType": "address"}],
        "outputs": [{"name": "", "type": "uint256", "internalType": "uint256"}],
        "stateMutability": "view",
    },
]


class MonAIYakuzaMint:
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
        self.web3 = AsyncWeb3(
            AsyncWeb3.AsyncHTTPProvider(
                RPC_URL,
                request_kwargs={"proxy": (f"http://{proxy}"), "ssl": False},
            )
        )
        
        self.nft_contract_address = (
            "0x2742937d49D4ef6DFb8073ad7D33b203d6232a88"  # MonAI Yakuza контракт
        )
        self.nft_contract: Contract = self.web3.eth.contract(
            address=self.nft_contract_address, abi=MONAI_YAKUZA_ABI
        )
        # Адрес для реферала (можно использовать нулевой адрес или другой адрес)
        self.refer_address = "0x0000000000000000000000000000000000000000"

    async def get_nft_balance(self) -> int:
        """
        Проверяет баланс NFT для текущего аккаунта
        Returns:
            int: количество NFT
        """
        try:
            balance = await self.nft_contract.functions.balanceOf(
                self.account.address
            ).call()

            return balance
        except Exception as e:
            logger.error(f"[{self.account_index}] Error checking NFT balance: {e}")
            return 0

    async def mint(self):
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                random_nft_amount = random.randint(
                    self.config.MONAIYAKUZA.MAX_PER_ACCOUNT[0],
                    self.config.MONAIYAKUZA.MAX_PER_ACCOUNT[1],
                )
                balance = await self.get_nft_balance()

                if balance >= random_nft_amount:
                    logger.success(
                        f"[{self.account_index}] MonAI Yakuza NFT already minted"
                    )
                    return True

                logger.info(f"[{self.account_index}] Minting MonAI Yakuza NFT")

                # Подготавливаем транзакцию минта
                mint_txn = await self.nft_contract.functions.mint(
                    1,  # quantity - минтим 1 NFT
                    self.refer_address,  # refer - адрес реферала
                ).build_transaction(
                    {
                        "from": self.account.address,
                        "value": self.web3.to_wei(0.2, "ether"),  # 0.2 MON для минта
                        "nonce": await self.web3.eth.get_transaction_count(
                            self.account.address
                        ),
                        "maxFeePerGas": await self.web3.eth.gas_price,
                        "maxPriorityFeePerGas": await self.web3.eth.gas_price,
                    }
                )

                # Подписываем транзакцию
                signed_txn = self.web3.eth.account.sign_transaction(
                    mint_txn, self.private_key
                )

                # Отправляем транзакцию
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_txn.raw_transaction
                )

                # Ждем подтверждения
                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)

                if receipt["status"] == 1:
                    logger.success(
                        f"[{self.account_index}] Successfully minted MonAI Yakuza NFT. TX: {EXPLORER_URL}{tx_hash.hex()}"
                    )
                    return True
                else:
                    logger.error(
                        f"[{self.account_index}] Failed to mint MonAI Yakuza NFT. TX: {EXPLORER_URL}{tx_hash.hex()}"
                    )
                    return False

            except Exception as e:
                random_pause = random.randint(
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
                )
                logger.error(
                    f"[{self.account_index}] Error in mint on MonAI Yakuza: {e}. Sleeping for {random_pause} seconds"
                )
                await asyncio.sleep(random_pause)

        return False
