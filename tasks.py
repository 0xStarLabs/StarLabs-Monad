TASKS = [
    "FAUCET",
]

# MAGICEDEN WORKS ONLY WITH THESE NFT https://magiceden.io/mint-terminal/monad-testnet

FAUCET = [
    "faucet",
]

DUSTED = [
    "dusted",
]
"""
EN:
You can create your own task with the modules you need 
and add it to the TASKS list or use our ready-made preset tasks.

( ) - Means that all of the modules inside the brackets will be executed 
in random order
[ ] - Means that only one of the modules inside the brackets will be executed 
on random
SEE THE EXAMPLE BELOW:

RU:
Вы можете создать свою задачу с модулями, которые вам нужны, 
и добавить ее в список TASKS, см. пример ниже:

( ) - означает, что все модули внутри скобок будут выполнены в случайном порядке
[ ] - означает, что будет выполнен только один из модулей внутри скобок в случайном порядке
СМОТРИТЕ ПРИМЕР НИЖЕ:

CHINESE:
你可以创建自己的任务，使用你需要的模块，
并将其添加到TASKS列表中，请参见下面的示例：

( ) - 表示括号内的所有模块将按随机顺序执行
[ ] - 表示括号内的模块将按随机顺序执行

--------------------------------
!!! IMPORTANT !!!
EXAMPLE | ПРИМЕР | 示例:

TASKS = [
    "CREATE_YOUR_OWN_TASK",
]
CREATE_YOUR_OWN_TASK = [
    "memebridge",
    ("apriori", "magma", "shmonad"),
    ["ambient", "izumi", "bean"],
    "collect_all_to_monad",
]
--------------------------------


BELOW ARE THE READY-MADE TASKS THAT YOU CAN USE:
СНИЗУ ПРИВЕДЕНЫ ГОТОВЫЕ ПРИМЕРЫ ЗАДАЧ, КОТОРЫЕ ВЫ МОЖЕТЕ ИСПОЛЬЗОВАТЬ:
以下是您可以使用的现成任务：
"""


BRIDGE_AND_SWAPS = [
    "memebridge",
    ("izumi", "ambient", "bean", "swaps"),
    "collect_all_to_monad",
]


FULL_TASK = [
    ["izumi", "swaps", "ambient", "bean", "skip"],
    ["izumi", "swaps", "ambient", "bean", "skip", "skip", "skip"],
    ["izumi", "swaps", "ambient", "bean", "skip", "skip", "skip"],
    ["izumi", "aircraft", "lilchogstars", "bean", "swaps", "skip"],
    ["ambient", "izumi", "bean", "skip", "skip"],
    "collect_all_to_monad",
    ["apriori", "magma", "shmonad", "kintsu", "skip", "skip"],
    ["apriori", "magma", "shmonad", "kintsu", "skip"],
    ["ambient", "izumi", "bean", "magiceden", "monadking", "skip"],
    ["magiceden", "monadking", "aircraft", "skip", "skip"],
    "collect_all_to_monad",
    ["ambient", "izumi", "bean", "magiceden", "monadking", "skip"],
    ["izumi", "swaps", "ambient", "bean", "skip", "skip", "skip"],
    ["owlto", "skip", "skip"],
    ["izumi", "swaps", "ambient", "bean", "skip", "skip"],
    "logs",
]

BRIDGE_SEPOLIA_AND_CONVERT_TO_MON = [
    "testnet_bridge",
    "orbiter",
    "collect_all_to_monad",
]

SWAPS_TASK = [
    ("izumi", "ambient", "bean", "swaps"),
    "collect_all_to_monad",
]

STAKING_TASK = [
    ("apriori", "magma", "shmonad", "kintsu"),
]

EXCHANGE_TASK = [
    "cex_withdrawal",
]

EXCHANGE_AND_TESTNET_BRIDGE_TASK = [
    "cex_withdrawal",
    "testnet_bridge",
    "orbiter",
    "collect_all_to_monad",
]

EXCHANGE_AND_MEMEBRIDGE_TASK = [
    "cex_withdrawal",
    "memebridge",
]

# FAUCETS
# "disperse_farm_accounts" - disperse tokens from farm accounts to main accounts | keys_for_faucet.txt -> private_keys.txt
# "disperse_from_one_wallet" - disperse tokens from one wallet to all other wallets | keys_for_faucet.txt (first wallet) -> private_keys.txt

# SWAPS
# "collect_all_to_monad" - swap all tokens to native token (MON)
# "swaps" - testnet.monad.xyz/ page token swaps
# "bean" - swap tokens on Bean DEX
# "ambient" - swap tokens on Ambient DEX
# "izumi" - swap tokens on Izumi DEX
# "octo_swap" - swap tokens on octo.exchange/swap

# STAKES
# "apriori" - stake MON token
# "magma" - stake MON token on Magma
# "shmonad" - buy and stake shmon on shmonad.xyz | LOOK SETTINGS BELOW
# "kintsu" - stake MON token on kintsu.xyz/
# "nostra" - deposit, borrow, repay, withdraw

# MINT
# "magiceden" - mint NFT on magiceden.io
# "owlto" - deploy contract on Owlto
# "lilchogstars" - mint NFT on testnet.lilchogstars.com/
# "demask" - mint NFT on app.demask.finance/launchpad/0x2cdd146aa75ffa605ff7c5cc5f62d3b52c140f9c/0
# "monadking" - mint NFT on nerzo.xyz/monadking
# "monadking_unlocked" - mint NFT on www.nerzo.xyz/unlocked
# "monaiyakuza_mint" - mint NFT on monai.gg/nft
# "easynode_deploy" - deploy contract on easynode.xyz

# REFUEL
# "gaszip" - gaszip refuel from arbitrum, optimism, base to monad
# "orbiter" - bridge ETH from Sepolia to Monad via Orbiter
# "memebridge" - memebridge refuel from arbitrum, optimism, base to monad

# CEX WITHDRAWAL
# "cex_withdrawal" - withdraw tokens from cex

# GAMES
# "frontrunner" - play frontrunner game

# OTHER
# "logs" - show logs: MON balance | number of transactions | avarage balance | avarage number of transactions
# "nad_domains" - register random domain on nad.domains
# "aircraft" - mint NFT on aircraft.fun
