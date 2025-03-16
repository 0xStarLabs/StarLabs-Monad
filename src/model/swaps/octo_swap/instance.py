import time
import json
import random
import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Union, Tuple
from web3 import AsyncWeb3, Web3
from web3.contract import Contract
from web3.types import TxParams, Wei, ChecksumAddress
from eth_account import Account
from loguru import logger
from primp import AsyncClient

from src.utils.config import Config
from src.utils.constants import EXPLORER_URL, RPC_URL

from .constants import (
    ROUTER_CONTRACT,
    WMON_CONTRACT,
    USDC_CONTRACT,
    USDT_CONTRACT,
    TEST1_CONTRACT,
    TEST2_CONTRACT,
    DAK_CONTRACT,
    ABI,
    AVAILABLE_TOKENS,
)


class OctoSwap:
    def __init__(
        self,
        account_index: int,
        proxy: str,
        private_key: str,
        config: Config,
        session: AsyncClient,
    ):
        """
        Инициализация OctoSwap

        Args:
            account_index: Индекс аккаунта для логирования
            proxy: Прокси для подключения
            private_key: Приватный ключ кошелька
            config: Конфигурация
            session: HTTP сессия
        """
        self.account_index = account_index
        self.proxy = proxy
        self.private_key = private_key
        self.config = config
        self.session = session

        # Создаем аккаунт из приватного ключа
        self.account: Account = Account.from_key(private_key=private_key)

        # Создаем настроенный Web3 клиент с middleware для повторных попыток
        self.web3 = AsyncWeb3(
            AsyncWeb3.AsyncHTTPProvider(
                RPC_URL,
                request_kwargs={"proxy": (f"http://{proxy}"), "ssl": False},
            )
        )

    async def get_gas_params(self) -> Dict[str, int]:
        """Получить текущие параметры газа из сети."""
        latest_block = await self.web3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        max_priority_fee = await self.web3.eth.max_priority_fee

        # Рассчитываем maxFeePerGas (базовая комиссия + приоритетная комиссия)
        max_fee = base_fee + max_priority_fee

        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }

    async def estimate_gas(self, transaction: dict) -> int:
        """Оценить газ для транзакции и добавить буфер."""
        try:
            estimated = await self.web3.eth.estimate_gas(transaction)
            # Добавляем 10% к estimated gas для безопасности
            return int(estimated * 1.1)
        except Exception as e:
            logger.warning(
                f"[{self.account_index}] Error estimating gas: {e}. Using default gas limit"
            )
            raise e

    async def get_token_contract(self, token_address: str) -> Contract:
        """
        Получить контракт токена

        Args:
            token_address: Адрес контракта токена

        Returns:
            Contract: Объект контракта токена
        """
        return self.web3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=ABI["token"]
        )

    async def get_token_balance(self, wallet_address: str, token: Dict) -> float:
        """
        Получить баланс токена для указанного кошелька

        Args:
            wallet_address: Адрес кошелька
            token: Информация о токене

        Returns:
            float: Баланс токена
        """
        max_retries = 15
        retries = 0
        last_exception = None

        while retries <= max_retries:
            try:
                wallet_address = Web3.to_checksum_address(wallet_address)

                if token["native"]:
                    balance_wei = await self.web3.eth.get_balance(wallet_address)
                    return float(Web3.from_wei(balance_wei, "ether"))
                else:
                    token_contract = await self.get_token_contract(token["address"])
                    balance_wei = await token_contract.functions.balanceOf(
                        wallet_address
                    ).call()
                    return float(balance_wei) / (10 ** token["decimals"])
            except Exception as e:
                retries += 1
                last_exception = e
                await asyncio.sleep(1)

        logger.error(
            f"[{self.account_index}] All {max_retries} retry attempts failed when checking balance. Last error: {last_exception}"
        )
        return 0

    async def check_allowance(
        self, token_address: str, spender_address: str, amount_wei: int
    ) -> bool:
        """Проверить, достаточно ли allowance для токена."""
        token_contract = await self.get_token_contract(token_address)
        current_allowance = await token_contract.functions.allowance(
            self.account.address, spender_address
        ).call()
        return current_allowance >= amount_wei

    async def approve_token(self, token: Dict, amount_wei: int) -> Optional[str]:
        """
        Проверить и при необходимости выполнить approve для токена

        Args:
            token: Информация о токене
            amount_wei: Сумма в wei для approve

        Returns:
            Optional[str]: Хеш транзакции approve или None, если approve не требуется
        """
        if token["native"]:
            return None

        # Проверяем текущий allowance
        if await self.check_allowance(token["address"], ROUTER_CONTRACT, amount_wei):
            return None

        logger.info(
            f"[{self.account_index}] 🔑 [APPROVAL] Approving {token['name']}..."
        )

        # Максимальное значение для approve (uint256 max)
        max_uint256 = 2**256 - 1

        # Создаем контракт токена
        token_contract = await self.get_token_contract(token["address"])

        # Подготовка функции approve
        approve_func = token_contract.functions.approve(ROUTER_CONTRACT, max_uint256)

        # Получаем параметры газа
        gas_params = await self.get_gas_params()

        # Создаем транзакцию
        transaction = {
            "from": self.account.address,
            "to": token["address"],
            "data": approve_func._encode_transaction_data(),
            "chainId": 10143,
            "type": 2,
            "nonce": await self.web3.eth.get_transaction_count(
                self.account.address, "latest"
            ),
        }

        # Оценка газа
        try:
            estimated_gas = await self.estimate_gas(transaction)
            transaction.update({"gas": estimated_gas, **gas_params})
        except Exception as e:
            logger.error(
                f"[{self.account_index}] Failed to estimate gas for approval: {str(e)}"
            )
            raise ValueError(
                f"Gas estimation failed for {token['name']} approval: {str(e)}"
            )

        # Подписание и отправка транзакции
        signed_tx = self.web3.eth.account.sign_transaction(
            transaction, self.private_key
        )
        tx_hash = await self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Ожидание подтверждения транзакции
        receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt["status"] == 1:
            logger.success(
                f"[{self.account_index}] ✅ [APPROVAL] {token['name']} approved. TX: {EXPLORER_URL}{tx_hash.hex()}"
            )
            return Web3.to_hex(tx_hash)
        else:
            logger.error(f"[{self.account_index}] Approval transaction failed.")
            return None

    async def swap(
        self,
        token_from: str,
        token_to: str,
        amount: float,
        slippage: float = 0.5,
    ) -> Dict:
        """
        Выполнить обмен токенов

        Args:
            token_from: Символ токена, который нужно обменять (например, 'MON')
            token_to: Символ токена, который нужно получить (например, 'USDC')
            amount: Количество токена token_from для обмена
            slippage: Допустимое проскальзывание в процентах (по умолчанию 0.5%)

        Returns:
            Dict: Результат обмена с информацией о транзакции
        """
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                # Получаем информацию о токенах
                token_a = AVAILABLE_TOKENS.get(token_from)
                token_b = AVAILABLE_TOKENS.get(token_to)

                if not token_a or not token_b:
                    raise ValueError(
                        f"Invalid token symbols: {token_from} or {token_to}"
                    )

                # Проверяем баланс
                balance = await self.get_token_balance(self.account.address, token_a)
                if balance < amount:
                    raise ValueError(
                        f"Insufficient balance. Have {balance} {token_a['name']}, need {amount}"
                    )

                # Конвертируем amount в wei
                if token_a["native"]:
                    amount_in_wei = Web3.to_wei(amount, "ether")
                else:
                    amount_in_wei = int(amount * (10 ** token_a["decimals"]))

                # Особые случаи: MON -> WMON и WMON -> MON
                if token_a["native"] and token_b["name"] == "WMON":
                    return await self._deposit_mon_to_wmon(amount_in_wei)

                if token_a["name"] == "WMON" and token_b["native"]:
                    return await self._withdraw_wmon_to_mon(amount_in_wei)

                # Для обычных свапов
                # Определяем путь обмена
                path = [
                    WMON_CONTRACT if token_a["native"] else token_a["address"],
                    WMON_CONTRACT if token_b["native"] else token_b["address"],
                ]

                # Создаем контракт роутера
                router_contract = self.web3.eth.contract(
                    address=Web3.to_checksum_address(ROUTER_CONTRACT),
                    abi=ABI["router"],
                )

                # Получаем ожидаемое количество выходных токенов
                amounts_out = await router_contract.functions.getAmountsOut(
                    amount_in_wei, path
                ).call()
                expected_out = amounts_out[-1]

                # Применяем slippage
                min_amount_out = int(expected_out * (1 - slippage / 100))

                # Устанавливаем deadline (текущее время + 1 час)
                deadline = int(time.time()) + 3600

                # Если токен не нативный, делаем approve
                if not token_a["native"]:
                    await self.approve_token(token_a, amount_in_wei)

                # Получаем параметры газа
                gas_params = await self.get_gas_params()

                # Подготавливаем транзакцию в зависимости от типов токенов
                if token_a["native"]:  # MON -> Token
                    tx_func = router_contract.functions.swapExactETHForTokens(
                        min_amount_out, path, self.account.address, deadline
                    )

                    transaction = {
                        "from": self.account.address,
                        "to": ROUTER_CONTRACT,
                        "value": amount_in_wei,
                        "data": tx_func._encode_transaction_data(),
                        "chainId": 10143,
                        "type": 2,
                        "nonce": await self.web3.eth.get_transaction_count(
                            self.account.address, "latest"
                        ),
                    }
                elif token_b["native"]:  # Token -> MON
                    tx_func = router_contract.functions.swapExactTokensForETH(
                        amount_in_wei,
                        min_amount_out,
                        path,
                        self.account.address,
                        deadline,
                    )

                    transaction = {
                        "from": self.account.address,
                        "to": ROUTER_CONTRACT,
                        "data": tx_func._encode_transaction_data(),
                        "chainId": 10143,
                        "type": 2,
                        "nonce": await self.web3.eth.get_transaction_count(
                            self.account.address, "latest"
                        ),
                    }
                else:  # Token -> Token
                    tx_func = router_contract.functions.swapExactTokensForTokens(
                        amount_in_wei,
                        min_amount_out,
                        path,
                        self.account.address,
                        deadline,
                    )

                    transaction = {
                        "from": self.account.address,
                        "to": ROUTER_CONTRACT,
                        "data": tx_func._encode_transaction_data(),
                        "chainId": 10143,
                        "type": 2,
                        "nonce": await self.web3.eth.get_transaction_count(
                            self.account.address, "latest"
                        ),
                    }

                # Оценка газа
                try:
                    estimated_gas = await self.estimate_gas(transaction)
                    transaction.update({"gas": estimated_gas, **gas_params})
                except Exception as e:
                    logger.error(
                        f"[{self.account_index}] Failed to estimate gas for swap: {str(e)}"
                    )
                    raise ValueError(f"Gas estimation failed for swap: {str(e)}")

                # Строим, подписываем и отправляем транзакцию
                signed_tx = self.web3.eth.account.sign_transaction(
                    transaction, self.private_key
                )
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_tx.raw_transaction
                )

                logger.info(
                    f"[{self.account_index}] 🔄 [SWAP] Executing swap [{token_a['name']} -> {token_b['name']}]..."
                )
                logger.info(
                    f"[{self.account_index}] 🚀 [TX SENT] Transaction hash: {EXPLORER_URL}{tx_hash.hex()}"
                )

                # Ожидаем подтверждения транзакции
                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
                block_number = receipt["blockNumber"]

                if receipt["status"] == 1:
                    # Возвращаем информацию о транзакции
                    return {
                        "success": True,
                        "tx_hash": Web3.to_hex(tx_hash),
                        "block_number": block_number,
                        "from_token": token_a["name"],
                        "to_token": token_b["name"],
                        "amount_in": amount,
                        "expected_out": expected_out / (10 ** token_b["decimals"]),
                        "gas_used": receipt["gasUsed"],
                    }
                else:
                    logger.error(f"[{self.account_index}] Swap transaction failed.")
                    continue

            except Exception as e:
                random_pause = random.randint(
                    self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                    self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
                )
                logger.error(
                    f"[{self.account_index}] Error in swap: {e}. "
                    f"Sleeping for {random_pause} seconds"
                )
                await asyncio.sleep(random_pause)

        return {"success": False, "error": "Max retry attempts reached"}

    async def _deposit_mon_to_wmon(self, amount_wei: int) -> Dict:
        """
        Конвертировать MON в WMON через функцию deposit

        Args:
            amount_wei: Количество MON в wei для конвертации

        Returns:
            Dict: Результат операции
        """
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                # Создаем контракт WMON
                wmon_contract = self.web3.eth.contract(
                    address=Web3.to_checksum_address(WMON_CONTRACT),
                    abi=ABI["weth"],
                )

                # Подготавливаем функцию deposit
                deposit_func = wmon_contract.functions.deposit()

                # Получаем параметры газа
                gas_params = await self.get_gas_params()

                # Создаем транзакцию
                transaction = {
                    "from": self.account.address,
                    "to": WMON_CONTRACT,
                    "value": amount_wei,
                    "data": deposit_func._encode_transaction_data(),
                    "chainId": 10143,
                    "type": 2,
                    "nonce": await self.web3.eth.get_transaction_count(
                        self.account.address, "latest"
                    ),
                }

                # Оценка газа
                try:
                    estimated_gas = await self.estimate_gas(transaction)
                    transaction.update({"gas": estimated_gas, **gas_params})
                except Exception as e:
                    logger.error(
                        f"[{self.account_index}] Failed to estimate gas for deposit: {str(e)}"
                    )
                    raise ValueError(f"Gas estimation failed for deposit: {str(e)}")

                logger.info(
                    f"[{self.account_index}] 💰 [DEPOSIT] Converting MON to WMON via deposit..."
                )

                # Подписываем и отправляем транзакцию
                signed_tx = self.web3.eth.account.sign_transaction(
                    transaction, self.private_key
                )
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_tx.raw_transaction
                )
                logger.info(
                    f"[{self.account_index}] 🚀 [TX SENT] Transaction hash: {EXPLORER_URL}{tx_hash.hex()}"
                )

                # Ожидаем подтверждения транзакции
                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
                block_number = receipt["blockNumber"]

                if receipt["status"] == 1:
                    return {
                        "success": True,
                        "tx_hash": Web3.to_hex(tx_hash),
                        "block_number": block_number,
                        "from_token": "MON",
                        "to_token": "WMON",
                        "amount_in": Web3.from_wei(amount_wei, "ether"),
                        "expected_out": Web3.from_wei(amount_wei, "ether"),
                        "gas_used": receipt["gasUsed"],
                    }
                else:
                    logger.error(f"[{self.account_index}] Deposit transaction failed.")
                    continue

            except Exception as e:
                random_pause = random.randint(
                    self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                    self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
                )
                logger.error(
                    f"[{self.account_index}] Error in deposit_mon_to_wmon: {e}. "
                    f"Sleeping for {random_pause} seconds"
                )
                await asyncio.sleep(random_pause)

        return {"success": False, "error": "Max retry attempts reached"}

    async def _withdraw_wmon_to_mon(self, amount_wei: int) -> Dict:
        """
        Конвертировать WMON в MON через функцию withdraw

        Args:
            amount_wei: Количество WMON в wei для конвертации

        Returns:
            Dict: Результат операции
        """
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                # Создаем контракт WMON
                wmon_contract = self.web3.eth.contract(
                    address=Web3.to_checksum_address(WMON_CONTRACT),
                    abi=ABI["weth"],
                )

                # Подготавливаем функцию withdraw
                withdraw_func = wmon_contract.functions.withdraw(amount_wei)

                # Получаем параметры газа
                gas_params = await self.get_gas_params()

                # Создаем транзакцию
                transaction = {
                    "from": self.account.address,
                    "to": WMON_CONTRACT,
                    "data": withdraw_func._encode_transaction_data(),
                    "chainId": 10143,
                    "type": 2,
                    "nonce": await self.web3.eth.get_transaction_count(
                        self.account.address, "latest"
                    ),
                }

                # Оценка газа
                try:
                    estimated_gas = await self.estimate_gas(transaction)
                    transaction.update({"gas": estimated_gas, **gas_params})
                except Exception as e:
                    logger.error(
                        f"[{self.account_index}] Failed to estimate gas for withdraw: {str(e)}"
                    )
                    raise ValueError(f"Gas estimation failed for withdraw: {str(e)}")

                logger.info(
                    f"[{self.account_index}] 💸 [WITHDRAW] Converting WMON to MON via withdraw..."
                )

                # Подписываем и отправляем транзакцию
                signed_tx = self.web3.eth.account.sign_transaction(
                    transaction, self.private_key
                )
                tx_hash = await self.web3.eth.send_raw_transaction(
                    signed_tx.raw_transaction
                )
                logger.info(
                    f"[{self.account_index}] 🚀 [TX SENT] Transaction hash: {EXPLORER_URL}{tx_hash.hex()}"
                )

                # Ожидаем подтверждения транзакции
                receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
                block_number = receipt["blockNumber"]

                if receipt["status"] == 1:
                    return {
                        "success": True,
                        "tx_hash": Web3.to_hex(tx_hash),
                        "block_number": block_number,
                        "from_token": "WMON",
                        "to_token": "MON",
                        "amount_in": Web3.from_wei(amount_wei, "ether"),
                        "expected_out": Web3.from_wei(amount_wei, "ether"),
                        "gas_used": receipt["gasUsed"],
                    }
                else:
                    logger.error(f"[{self.account_index}] Withdraw transaction failed.")
                    continue

            except Exception as e:
                random_pause = random.randint(
                    self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                    self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
                )
                logger.error(
                    f"[{self.account_index}] Error in withdraw_wmon_to_mon: {e}. "
                    f"Sleeping for {random_pause} seconds"
                )
                await asyncio.sleep(random_pause)

        return {"success": False, "error": "Max retry attempts reached"}

    async def pick_random_tokens(self) -> Tuple[str, str, float]:
        """
        Выбрать случайную пару токенов для свапа и сумму

        Returns:
            Tuple[str, str, float]: (token_from, token_to, amount)
        """
        # Получаем балансы всех токенов
        available_tokens = []

        for symbol, token_info in AVAILABLE_TOKENS.items():
            balance = await self.get_token_balance(self.account.address, token_info)
            if balance > 0.01:  # Минимальный баланс для свапа
                available_tokens.append((symbol, balance))

        if not available_tokens:
            logger.warning(
                f"[{self.account_index}] No tokens with sufficient balance found"
            )
            return None, None, 0

        # Выбираем случайный токен для свапа
        token_from, balance = random.choice(available_tokens)

        # Выбираем случайный токен для получения (не тот же самый)
        possible_tokens_to = [
            symbol for symbol in AVAILABLE_TOKENS.keys() if symbol != token_from
        ]
        token_to = random.choice(possible_tokens_to)

        # Определяем случайную сумму для свапа (30-70% от баланса)
        amount = balance * random.uniform(0.3, 0.7)

        logger.info(
            f"[{self.account_index}] Selected swap: {token_from} -> {token_to}, amount: {amount}"
        )

        return token_from, token_to, amount

    async def swap_all_to_monad(self):
        """
        Обменивает все токены на MON (нативный токен).
        Аналог функции liquidateWallet из JS-кода.
        """
        target_token = AVAILABLE_TOKENS["MON"]
        logger.info(f"[{self.account_index}] 🔄 Swapping all tokens to MON")

        # Перебираем все доступные токены
        for symbol, token in AVAILABLE_TOKENS.items():
            # Пропускаем MON, так как это целевой токен
            if token["native"]:
                continue

            # Получаем баланс токена
            balance = await self.get_token_balance(self.account.address, token)

            # Если баланс слишком мал, пропускаем
            if balance <= 0.01:
                logger.info(
                    f"[{self.account_index}] Skipping {symbol} - balance too low: {balance}"
                )
                continue

            # Логируем балансы до свапа
            mon_balance_before = await self.get_token_balance(
                self.account.address, target_token
            )
            logger.info(
                f"[{self.account_index}] Balance {symbol} before swap: {balance}"
            )
            logger.info(
                f"[{self.account_index}] Balance MON before swap: {mon_balance_before}"
            )

            try:
                # Особый случай: WMON -> MON через withdraw
                if symbol == "WMON":
                    amount_wei = int(balance * (10 ** token["decimals"]))
                    result = await self._withdraw_wmon_to_mon(amount_wei)
                else:
                    # Для остальных токенов используем обычный свап
                    result = await self.swap(symbol, "MON", balance)

                if result["success"]:
                    logger.success(
                        f"[{self.account_index}] Successfully swapped {balance} {symbol} to MON. "
                        f"TX: {EXPLORER_URL}{result['tx_hash']}"
                    )
                else:
                    logger.error(
                        f"[{self.account_index}] Failed to swap {symbol} to MON: {result.get('error', 'Unknown error')}"
                    )

            except Exception as e:
                logger.error(
                    f"[{self.account_index}] Error swapping {symbol} to MON: {str(e)}"
                )

            # Логируем балансы после свапа
            token_balance_after = await self.get_token_balance(
                self.account.address, token
            )
            mon_balance_after = await self.get_token_balance(
                self.account.address, target_token
            )
            logger.info(
                f"[{self.account_index}] Balance {symbol} after swap: {token_balance_after}"
            )
            logger.info(
                f"[{self.account_index}] Balance MON after swap: {mon_balance_after}"
            )

            # Пауза между свапами
            await asyncio.sleep(random.randint(2, 5))

        logger.success(f"[{self.account_index}] 🎉 All tokens have been swapped to MON")
        return True

    async def execute(self):
        """
        Выполнить операции OctoSwap на основе настроек конфигурации.
        Выполняет несколько случайных свапов в соответствии с настройками.
        Если включена опция SWAP_ALL_TO_MONAD, обменивает все токены на MON.
        """
        logger.info(f"[{self.account_index}] Starting OctoSwap operations")

        # Проверяем, нужно ли обменять все токены на MON
        if (
            hasattr(self.config.OCTO_SWAP, "SWAP_ALL_TO_MONAD")
            and self.config.OCTO_SWAP.SWAP_ALL_TO_MONAD
        ):
            logger.info(
                f"[{self.account_index}] SWAP_ALL_TO_MONAD is enabled, swapping all tokens to MON"
            )
            await self.swap_all_to_monad()
            return

        # Определяем количество свапов для выполнения
        if (
            hasattr(self.config.FLOW, "NUMBER_OF_SWAPS")
            and isinstance(self.config.FLOW.NUMBER_OF_SWAPS, list)
            and len(self.config.FLOW.NUMBER_OF_SWAPS) == 2
        ):
            min_swaps, max_swaps = self.config.FLOW.NUMBER_OF_SWAPS
            num_swaps = random.randint(min_swaps, max_swaps)
        else:
            # Если настройка отсутствует или некорректна, выполняем один свап
            num_swaps = 1

        logger.info(f"[{self.account_index}] Will perform {num_swaps} swaps")

        # Выполняем указанное количество свапов
        for swap_num in range(1, num_swaps + 1):
            logger.info(f"[{self.account_index}] Executing swap {swap_num}/{num_swaps}")

            # Выбираем случайную пару токенов для свапа
            token_from, token_to, _ = await self.pick_random_tokens()

            if not token_from or not token_to:
                logger.warning(
                    f"[{self.account_index}] No suitable tokens found for swap {swap_num}. Skipping."
                )
                continue

            # Получаем баланс выбранного токена
            token_info = AVAILABLE_TOKENS.get(token_from)
            balance = await self.get_token_balance(self.account.address, token_info)

            # Определяем процент баланса для свапа из настроек
            random_percent = random.randint(
                self.config.FLOW.PERCENT_OF_BALANCE_TO_SWAP[0],
                self.config.FLOW.PERCENT_OF_BALANCE_TO_SWAP[1],
            )

            # Рассчитываем сумму для свапа
            amount = balance * (random_percent / 100)

            logger.info(
                f"[{self.account_index}] Swap {swap_num}: {token_from} -> {token_to}, "
                f"amount: {amount} ({random_percent:.2f}% of balance)"
            )

            # Проверяем, что сумма достаточна для свапа
            if amount <= 0.01:
                logger.warning(
                    f"[{self.account_index}] Amount too small for swap {swap_num}. Skipping."
                )
                continue

            # Выполняем свап
            swap_result = await self.swap(token_from, token_to, amount)

            if swap_result["success"]:
                logger.success(
                    f"[{self.account_index}] Swap {swap_num} completed successfully: "
                    f"{swap_result['amount_in']} {swap_result['from_token']} -> "
                    f"{swap_result['expected_out']} {swap_result['to_token']}"
                )

                # Если это не последний свап, делаем паузу перед следующим
                if swap_num < num_swaps:
                    pause_time = random.randint(
                        self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
                        self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
                    )
                    logger.info(
                        f"[{self.account_index}] Pausing for {pause_time} seconds before next swap"
                    )
                    await asyncio.sleep(pause_time)
            else:
                logger.error(
                    f"[{self.account_index}] Swap {swap_num} failed: {swap_result.get('error', 'Unknown error')}"
                )

                # Если свап не удался, делаем паузу перед следующей попыткой
                if swap_num < num_swaps:
                    pause_time = random.randint(
                        self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                        self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
                    )
                    logger.info(
                        f"[{self.account_index}] Pausing for {pause_time} seconds before next swap attempt"
                    )
                    await asyncio.sleep(pause_time)

        logger.success(
            f"[{self.account_index}] Completed all {num_swaps} OctoSwap operations"
        )
