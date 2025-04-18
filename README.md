# Monad Testnet Automation

This tool automates interactions with the Monad testnet, including various DeFi operations and token interactions.

TUTORIAL - https://star-labs.gitbook.io/star-labs/monad-ru

## Features
# All features are available in config.yaml
- 💎 MagicEden
- 💱 Perform token swaps
- 🏦 Stake MON on Apriori, Magma, Kintsu, Shmonad, Bima
- 📄 Mint NFT: accountable, lilchogstars, demask, monadking, monadking_unlocked
- 🦉 Deploy contract on Owlto
- 🌋 Gaszip
- 🌐 Orbiter
- 📄 Logs
- 📄 Nad domains
- And much more...

## Features Description

### Faucet
Using official Monad testnet faucet.

### Swaps
Performs random swaps between available tokens with configurable amounts.

### Apriori Staking
Stakes MON tokens on Apriori platform with configurable amounts.

### Magma Staking
Stakes MON tokens on Magma platform with configurable amounts.

### Owlto Contract Deployment
Deploys smart contracts on Owlto platform.

### Bima Operations
- Claims tokens from Bima faucet
- Performs lending operations with configurable percentage of balance

## Requirements
- Python 3.11 or higher

## Installation

1. Clone the repository
```bash
git clone https://github.com/0xStarLabs/StarLabs-Monad.git
cd StarLabs-Monad
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure the bot in `config.yaml`

```yaml
SETTINGS:
# number of concurrent threads
THREADS: 1
# number of retries for ANY action
ATTEMPTS: 5
# pause between attempts
PAUSE_BETWEEN_ATTEMPTS: [5, 15]
# pause in seconds between accounts
RANDOM_PAUSE_BETWEEN_ACCOUNTS: [3, 10]
# pause in seconds between actions
RANDOM_PAUSE_BETWEEN_ACTIONS: [2, 5]
FLOW:
# Available tasks:
# "connect_discord" - connect discord account
# "swaps" - swaps tokens
# "apriori" - stake MON token
# "magma" - stake MON token on Magma
# "owlto" - deploy contract on Owlto
# "bima" - lending and faucet
TASKS: ["connect_discord", "swaps", "apriori", "magma", "owlto", "bima"]
# number of swaps
NUMBER_OF_SWAPS: [1, 3]
# percent of balance to swap
PERCENT_OF_BALANCE_TO_SWAP: [10, 15]

```

4. Add your data to the following files:
- `data/private_keys.txt` - One private key per line
- `data/proxies.txt` - One proxy per line (format: `user:pass@ip:port`)


5. Run the bot
```bash
python main.py
```

## Support
- Telegram: https://t.me/StarLabsTech
- Chat: https://t.me/StarLabsChat
## Only for commit
- commit nothing
