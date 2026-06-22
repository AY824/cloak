

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("=".repeat(60));
  console.log("Cloak - 智能合约部署");
  console.log("Cloak - Smart Contract Deployment");
  console.log("=".repeat(60));
  console.log();

  const [deployer] = await hre.ethers.getSigners();
  console.log("部署者地址:", deployer.address);

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("部署者余额:", hre.ethers.formatEther(balance), "ETH");
  console.log();

  const FEE_RECEIVER = deployer.address;

  console.log("部署参数:");
  console.log("  - 平台手续费接收地址:", FEE_RECEIVER);
  console.log();

  console.log("正在部署 RiskAssetNFT...");

  const RiskAssetNFT = await hre.ethers.getContractFactory("RiskAssetNFT");
  const riskAssetNFT = await RiskAssetNFT.deploy();
  await riskAssetNFT.waitForDeployment();

  const riskAssetNFTAddress = await riskAssetNFT.getAddress();
  console.log("RiskAssetNFT 部署成功!");
  console.log("   地址:", riskAssetNFTAddress);
  console.log();

  console.log("正在部署 TradeEscrow...");

  const TradeEscrow = await hre.ethers.getContractFactory("TradeEscrow");
  const tradeEscrow = await TradeEscrow.deploy(FEE_RECEIVER);
  await tradeEscrow.waitForDeployment();

  const tradeEscrowAddress = await tradeEscrow.getAddress();
  console.log("TradeEscrow 部署成功!");
  console.log("   地址:", tradeEscrowAddress);
  console.log();

  console.log("正在部署 RevenueSplit...");

  const RevenueSplit = await hre.ethers.getContractFactory("RevenueSplit");
  const revenueSplit = await RevenueSplit.deploy();
  await revenueSplit.waitForDeployment();

  const revenueSplitAddress = await revenueSplit.getAddress();
  console.log("RevenueSplit 部署成功!");
  console.log("   地址:", revenueSplitAddress);
  console.log();

  const deploymentInfo = {
    network: hre.network.name,
    chainId: (await hre.ethers.provider.getNetwork()).chainId.toString(),
    deployer: deployer.address,
    deploymentTime: new Date().toISOString(),
    contracts: {
      RiskAssetNFT: {
        address: riskAssetNFTAddress,
        blockNumber: (await riskAssetNFT.deploymentTransaction()).blockNumber
      },
      TradeEscrow: {
        address: tradeEscrowAddress,
        blockNumber: (await tradeEscrow.deploymentTransaction()).blockNumber,
        constructorArgs: [FEE_RECEIVER]
      },
      RevenueSplit: {
        address: revenueSplitAddress,
        blockNumber: (await revenueSplit.deploymentTransaction()).blockNumber
      }
    }
  };

  const outputDir = path.join(__dirname, "..", "deployments");
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const outputFile = path.join(outputDir, `${hre.network.name}.json`);
  fs.writeFileSync(outputFile, JSON.stringify(deploymentInfo, null, 2));

  console.log("部署信息已保存到:", outputFile);
  console.log();

  console.log("=".repeat(60));
  console.log("部署完成! Deployment Complete!");
  console.log("=".repeat(60));
  console.log();
  console.log("合约地址:");
  console.log("  RiskAssetNFT :", riskAssetNFTAddress);
  console.log("  TradeEscrow  :", tradeEscrowAddress);
  console.log("  RevenueSplit :", revenueSplitAddress);
  console.log();
  console.log("下一步:");
  console.log("  1. 验证合约: npx hardhat verify --network sepolia <address> [args]");
  console.log("  2. 配置前端和后端的合约地址");
  console.log("  3. 进行功能测试");
  console.log();

  return deploymentInfo;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("部署失败!");
    console.error(error);
    process.exit(1);
  });
