# NAD Domains contract address
NAD_CONTRACT_ADDRESS = "0x758D80767a751fc1634f579D76e1CcaAb3485c9c"

# NAD Domains API URL
NAD_API_URL = "https://api.nad.domains/register/signature"

# NAD Name Service ERC721 Token address
NAD_NFT_ADDRESS = "0x3019BF1dfB84E5b46Ca9D0eEC37dE08a59A41308"

# Basic ERC721 ABI for balance checking
NAD_NFT_ABI = [
    {
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Contract ABI for NAD Domains
NAD_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "name", "type": "string"},
                    {"name": "nameOwner", "type": "address"},
                    {"name": "setAsPrimaryName", "type": "bool"},
                    {"name": "referrer", "type": "address"},
                    {"name": "discountKey", "type": "bytes32"},
                    {"name": "discountClaimProof", "type": "bytes"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"}
                ],
                "name": "params",
                "type": "tuple"
            },
            {"name": "signature", "type": "bytes"}
        ],
        "name": "registerWithSignature",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "components": [
                    {"name": "name", "type": "string"},
                    {"name": "nameOwner", "type": "address"},
                    {"name": "setAsPrimaryName", "type": "bool"},
                    {"name": "referrer", "type": "address"},
                    {"name": "discountKey", "type": "bytes32"},
                    {"name": "discountClaimProof", "type": "bytes"}
                ],
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "calculateRegisterFee",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]
