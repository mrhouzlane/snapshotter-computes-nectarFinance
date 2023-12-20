from pydantic import BaseModel
from pydantic import Field
from typing import List

class UniswapContractAbis(BaseModel):
    factory: str = Field(
        ...,
        example='snapshotter/modules/computes/static/abis/IUniswapV3Factory.json',
    )
    router: str = Field(
        ...,
        example='snapshotter/modules/computes/static/abis/UniswapV3Router.json',
    )
    quoter: str = Field(
        ...,
        example='snapshotter/modules/computes/static/abis/Quoter.json',
    )
    multicall: str = Field(
        ...,
        example='snapshotter/modules/computes/static/abis/UniswapV3Multicall.json',
    )
    pair_contract: str = Field(
        ...,
        example='snapshotter/modules/computes/static/abis/UniswapV3Pool.json',
    )
    erc20: str = Field(
        ...,
        example='snapshotter/modules/computes/static/abis/IERC20.json',
    )
    trade_events: str = Field(
        ...,
        example='snapshotter/modules/computes/static/abis/UniswapTradeEvents.json',
    )
    quoter_1inch: str = Field(
        ...,
        example='snapshotter/modules/computes/static/abis/OneInchQuoter.json',
    )


class ContractAddresses(BaseModel):
    uniswap_v3_factory: str = Field(
        ...,
        example='0x1F98431c8aD98523631AE4a59f267346ea31F984',
    )
    uniswap_v3_router: str = Field(
        ...,
        example='0xE592427A0AEce92De3Edee1F18E0157C05861564',
    )
    uniswap_v3_quoter: str = Field(
        ...,
        example='0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6',
    )
    uniswap_v3_multicall: str = Field(
        ...,
        example='0x5BA1e12693Dc8F9c48aAD8770482f4739bEeD696',
    )
    WETH: str = Field(
        ...,
        example='0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
    )
    MAKER_POOLS: List[str] = Field(
        ...,
        example=[
            '0xe8c6c9227491c0a8156a0106a0204d881bb7e531',
            '0x3afdc5e6dfc0b0a507a8e023c9dce2cafc310316',
        ],
    )
    QUOTER_1INCH: str = Field(
        ...,
        example='0x07D91f5fb9Bf7798734C3f606dB065549F6893bb',
    )


class Settings(BaseModel):
    uniswap_contract_abis: UniswapContractAbis
    contract_addresses: ContractAddresses
