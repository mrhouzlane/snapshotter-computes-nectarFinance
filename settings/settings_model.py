from typing import List

from pydantic import BaseModel
from pydantic import Field


class AaveContractAbis(BaseModel):
    pool_contract: str = Field(
        ..., example='snapshotter/modules/computes/static/abis/AaveV3Pool.json',
    )
    pool_data_provider_contract: str = Field(
        ..., example='snapshotter/modules/computes/static/abis/AaveProtocolDataProvider.json',
    )
    erc20: str = Field(
        ..., example='snapshotter/modules/computes/static/abis/IERC20.json',
    )
    a_token: str = Field(
        ..., example='snapshotter/modules/computes/static/abis/AToken.json',
    )
    one_inch_quoter: str = Field(
        ..., example='snapshotter/modules/computes/static/abis/OneInchQuoter.json',
    )


class ContractAddresses(BaseModel):
    WETH: str = Field(..., example='0x853d955aCEf822Db058eb8505911ED77F175b99e')
    one_inch_quoter: str = Field(..., example='0x853d955aCEf822Db058eb8505911ED77F175b99e')
    aave_v3_pool: str = Field(..., example='0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2')
    pool_data_provider: str = Field(..., example='0x7B4EB56E7CD4b454BA8ff71E4518426369a138a3')


class Settings(BaseModel):
    aave_contract_abis: AaveContractAbis
    contract_addresses: ContractAddresses
