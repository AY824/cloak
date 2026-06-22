

require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

const SEPOLIA_RPC_URL = process.env.SEPOLIA_RPC_URL || "https://sepolia.infura.io/v3/your-infura-key";
const GOERLI_RPC_URL = process.env.GOERLI_RPC_URL || "https://goerli.infura.io/v3/your-infura-key";
const MAINNET_RPC_URL = process.env.MAINNET_RPC_URL || "https://mainnet.infura.io/v3/your-infura-key";

const PRIVATE_KEY = process.env.PRIVATE_KEY || "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80";

const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY || "";


module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      },
      viaIR: true
    }
  },

  networks: {
    hardhat: {
      chainId: 31337,
      accounts: {
        count: 10,
        balance: "10000000000000000000000"
      }
    },

    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337
    },

    sepolia: {
      url: SEPOLIA_RPC_URL,
      accounts: [PRIVATE_KEY],
      chainId: 11155111,
      gas: "auto",
      gasPrice: "auto"
    },

    goerli: {
      url: GOERLI_RPC_URL,
      accounts: [PRIVATE_KEY],
      chainId: 5,
      gas: "auto",
      gasPrice: "auto"
    },

    mainnet: {
      url: MAINNET_RPC_URL,
      accounts: [PRIVATE_KEY],
      chainId: 1,
      gas: "auto",
      gasPrice: "auto"
    }
  },

  etherscan: {
    apiKey: ETHERSCAN_API_KEY
  },

  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts"
  },

  mocha: {
    timeout: 200000
  },

  gasReporter: {
    enabled: process.env.REPORT_GAS === "true",
    currency: "USD",
    outputFile: "gas-report.txt",
    noColors: true,
    coinmarketcap: process.env.COINMARKETCAP_API_KEY || ""
  }
};
