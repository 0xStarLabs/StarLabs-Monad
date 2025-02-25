from loguru import logger
import primp
import random
import asyncio

from src.model.orbiter.instance import Orbiter
from src.model.accountable.instance import Accountable
from src.model.shmonad.instance import Shmonad
from src.model.gaszip.instance import Gaszip
from src.model.monadverse_mint.instance import MonadverseMint
from src.model.thirdweb.instance import ThirdWeb
from src.model.bima.instance import Bima
from src.model.owlto.instance import Owlto
from src.model.magma.instance import Magma
from src.model.apriori import Apriori
from src.model.monad_xyz.instance import MonadXYZ
from src.utils.client import create_client
from src.utils.config import Config
from src.model.help.stats import WalletStats


class Start:
    def __init__(
        self,
        account_index: int,
        proxy: str,
        private_key: str,
        discord_token: str,
        email: str,
        config: Config,
    ):
        self.account_index = account_index
        self.proxy = proxy
        self.private_key = private_key
        self.discord_token = discord_token
        self.email = email
        self.config = config

        self.session: primp.AsyncClient | None = None

    async def initialize(self):
        try:
            self.session = await create_client(self.proxy)

            return True
        except Exception as e:
            logger.error(f"[{self.account_index}] | Error: {e}")
            return False

    async def flow(self):
        try:
            monad = MonadXYZ(
                self.account_index,
                self.proxy,
                self.private_key,
                self.discord_token,
                self.config,
                self.session,
            )

            if "farm_faucet" in self.config.FLOW.TASKS:
                await monad.faucet()
                return True

            # Заранее определяем все задачи
            planned_tasks = []
            task_plan_msg = []
            for i, task_item in enumerate(self.config.FLOW.TASKS, 1):
                if isinstance(task_item, list):
                    selected_task = random.choice(task_item)
                    planned_tasks.append((i, selected_task, task_item))
                    task_plan_msg.append(f"{i}. {selected_task}")
                else:
                    planned_tasks.append((i, task_item, None))
                    task_plan_msg.append(f"{i}. {task_item}")

            # Выводим план выполнения одним сообщением
            logger.info(
                f"[{self.account_index}] Task execution plan: {' | '.join(task_plan_msg)}"
            )

            # Выполняем задачи по плану
            for _, task, _ in planned_tasks:
                # Выполняем выбранную задачу
                if task == "connect_discord":
                    await monad.connect_discord()
                    await self.sleep("connect_discord")

                elif task == "faucet":
                    if self.config.FAUCET.MONAD_XYZ:
                        await monad.faucet()
                        await self.sleep("monad_faucet")

                    # if self.config.FAUCET.THIRDWEB:
                    #     thirdweb = ThirdWeb(
                    #         self.account_index,
                    #         self.proxy,
                    #         self.private_key,
                    #         self.email,
                    #         self.config,
                    #         self.session,
                    #     )
                    #     await thirdweb.faucet()
                    #     await self.sleep("thirdweb_faucet")

                elif task == "swaps":
                    await monad.swaps(type="swaps")
                    await self.sleep("swaps")

                elif task == "ambient":
                    await monad.swaps(type="ambient")
                    await self.sleep("ambient")

                elif task == "bean":
                    await monad.swaps(type="bean")
                    await self.sleep("bean")

                elif task == "collect_all_to_monad":
                    await monad.swaps(type="collect_all_to_monad")
                    await self.sleep("collect_all_to_monad")

                # elif task == "gaszip":
                #     gaszip = Gaszip(
                #         self.account_index,
                #         self.proxy,
                #         self.private_key,
                #         self.config,
                #     )
                #     await gaszip.refuel()
                #     await self.sleep("gaszip")

                elif task == "apriori":
                    apriori = Apriori(
                        self.account_index,
                        self.proxy,
                        self.private_key,
                        self.config,
                        self.session,
                    )
                    await apriori.stake_mon()
                    await self.sleep("apriori")

                elif task == "magma":
                    magma = Magma(
                        self.account_index,
                        self.proxy,
                        self.private_key,
                        self.config,
                        self.session,
                    )
                    await magma.stake_mon()
                    await self.sleep("magma")

                elif task == "owlto":
                    owlto = Owlto(
                        self.account_index,
                        self.proxy,
                        self.private_key,
                        self.config,
                        self.session,
                    )
                    await owlto.deploy_contract()
                    await self.sleep("owlto")

                elif task == "bima":
                    bima = Bima(
                        self.account_index,
                        self.proxy,
                        self.private_key,
                        self.config,
                        self.session,
                    )
                    await bima.get_faucet_tokens()
                    await self.sleep("bima_faucet")

                    if self.config.BIMA.LEND:
                        await bima.lend()
                        await self.sleep("bima_lend")

                elif task == "monadverse_mint":
                    monadverse_mint = MonadverseMint(
                        self.account_index,
                        self.proxy,
                        self.private_key,
                        self.config,
                        self.session,
                    )
                    await monadverse_mint.mint()
                    await self.sleep("monadverse_mint")

                elif task == "shmonad":
                    shmonad = Shmonad(
                        self.account_index,
                        self.proxy,
                        self.private_key,
                        self.config,
                        self.session,
                    )
                    await shmonad.swaps()
                    await self.sleep("shmonad")

                elif task == "accountable":
                    accountable = Accountable(
                        self.account_index,
                        self.proxy,
                        self.private_key,
                        self.config,
                        self.session,
                    )
                    await accountable.mint()
                    await self.sleep("accountable")

                elif task == "orbiter":
                    orbiter = Orbiter(
                        self.account_index,
                        self.proxy,
                        self.private_key,
                        self.config,
                        self.session,
                    )
                    await orbiter.bridge()
                    await self.sleep("orbiter")

                elif task == "logs":
                    wallet_stats = WalletStats(self.config)
                    await wallet_stats.get_wallet_stats(
                        self.private_key, self.account_index
                    )
                    await self.sleep("logs")

            return True
        except Exception as e:
            logger.error(f"[{self.account_index}] | Error: {e}")
            return False

    async def sleep(self, task_name: str):
        """Делает рандомную паузу между действиями"""
        pause = random.randint(
            self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
            self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
        )
        logger.info(
            f"[{self.account_index}] Sleeping {pause} seconds after {task_name}"
        )
        await asyncio.sleep(pause)
