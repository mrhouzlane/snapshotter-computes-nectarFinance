import asyncio
from decimal import Decimal

from redis import asyncio as aioredis
from snapshotter.utils.default_logger import logger
from snapshotter.utils.rpc import get_contract_abi_dict
from snapshotter.utils.rpc import RpcHelper
from snapshotter.utils.snapshot_utils import (
    get_block_details_in_block_range,
)
from web3 import Web3

from .constants import AAVE_CORE_EVENTS
from .constants import HALF_RAY
from .constants import pool_data_provider_contract_obj
from .constants import RAY
from .constants import SECONDS_IN_YEAR
from .helpers import get_asset_metadata
from .helpers import get_debt_burn_mint_events
from .helpers import get_pool_data_events
from .models.data_models import data_provider_reserve_data
from .pricing import get_asset_price_in_block_range

core_logger = logger.bind(module='PowerLoom|AaveCore')


async def get_asset_supply_and_debt(
    asset_address,
    from_block,
    to_block,
    redis_conn: aioredis.Redis,
    rpc_helper: RpcHelper,
    fetch_timestamp=False,
):
    core_logger.debug(
        f'Starting asset total supply query for: {asset_address}',
    )
    asset_address = Web3.toChecksumAddress(asset_address)

    asset_metadata = await get_asset_metadata(
        asset_address=asset_address,
        redis_conn=redis_conn,
        rpc_helper=rpc_helper,
    )

    if fetch_timestamp:
        try:
            block_details_dict = await get_block_details_in_block_range(
                from_block,
                to_block,
                redis_conn=redis_conn,
                rpc_helper=rpc_helper,
            )
        except Exception as err:
            core_logger.opt(exception=True).error(
                (
                    'Error attempting to get block details of block-range'
                    ' {}-{}: {}, retrying again'
                ),
                from_block,
                to_block,
                err,
            )
            raise err

        # aave supply is computed using block timestamps
        # if we are fetching timestamps, we can save rpc calls by computing event data
        # fetching timestamps is better for multi-asset projects as assets can share block data
        # otherwise, batching calls is more efficient

        asset_data: list = await calculate_asset_event_data(
            rpc_helper=rpc_helper,
            redis_conn=redis_conn,
            from_block=from_block,
            to_block=to_block,
            asset_address=asset_address,
            block_details_dict=block_details_dict,
            asset_metadata=asset_metadata,
        )

    else:
        block_details_dict = dict()
        asset_data = list()

    core_logger.debug(
        (
            'get asset supply fetched block details for epoch for:'
            f' {asset_address}'
        ),
    )

    asset_price_map = await get_asset_price_in_block_range(
        asset_metadata=asset_metadata,
        from_block=from_block,
        to_block=to_block,
        redis_conn=redis_conn,
        rpc_helper=rpc_helper,
        debug_log=False,
    )

    if not asset_data:

        data_contract_abi_dict = get_contract_abi_dict(pool_data_provider_contract_obj.abi)

        asset_data = await rpc_helper.batch_eth_call_on_block_range(
            abi_dict=data_contract_abi_dict,
            function_name='getReserveData',
            contract_address=pool_data_provider_contract_obj.address,
            from_block=from_block,
            to_block=to_block,
            redis_conn=redis_conn,
            params=[asset_address],
        )

        asset_data = [data_provider_reserve_data(*data) for data in asset_data]

    asset_supply_debt_dict = dict()

    for i, block_num in enumerate(range(from_block, to_block + 1)):
        total_supply = asset_data[i].totalAToken / (10 ** int(asset_metadata['decimals']))
        total_supply_usd = total_supply * asset_price_map.get(block_num, 0)

        total_stable_debt = asset_data[i].totalStableDebt / (10 ** int(asset_metadata['decimals']))
        total_variable_debt = asset_data[i].totalVariableDebt / (10 ** int(asset_metadata['decimals']))
        total_stable_debt_usd = total_stable_debt * asset_price_map.get(block_num, 0)
        total_variable_debt_usd = total_variable_debt * asset_price_map.get(block_num, 0)

        asset_supply_debt_dict[block_num] = {
            'total_supply': {'token_supply': total_supply, 'usd_supply': total_supply_usd},
            'total_stable_debt': {'token_debt': total_stable_debt, 'usd_debt': total_stable_debt_usd},
            'total_variable_debt': {'token_debt': total_variable_debt, 'usd_debt': total_variable_debt_usd},
            'liquidity_rate': asset_data[i].liquidityRate,
            'liquidity_index': asset_data[i].liquidityIndex,
            'variable_borrow_rate': asset_data[i].variableBorrowRate,
            'stable_borrow_rate': asset_data[i].stableBorrowRate,
            'variable_borrow_index': asset_data[i].variableBorrowIndex,
            'last_update_timestamp': int(asset_data[i].lastUpdateTimestamp),
            'timestamp': asset_data[i].timestamp,
        }

    core_logger.debug(
        (
            'Calculated asset total supply and debt for epoch-range:'
            f' {from_block} - {to_block} | asset_contract: {asset_address}'
        ),
    )

    return asset_supply_debt_dict


# TODO: add debt calculation, add unbacked calculation
async def calculate_asset_event_data(
    rpc_helper: RpcHelper,
    redis_conn: aioredis.Redis,
    from_block: int,
    to_block: int,
    asset_address: str,
    block_details_dict: dict,
    asset_metadata: dict,
):
    pool_contract_abi_dict = get_contract_abi_dict(pool_data_provider_contract_obj.abi)

    [initial_data, data_events, debt_events] = await asyncio.gather(
        # get initial asset supply data from the AavePoolV3 contract
        rpc_helper.batch_eth_call_on_block_range(
            abi_dict=pool_contract_abi_dict,
            function_name='getReserveData',
            contract_address=pool_data_provider_contract_obj.address,
            from_block=from_block,
            to_block=from_block,
            redis_conn=redis_conn,
            params=[asset_address],
        ),
        # get all events from the pool contract ignoring initial block
        get_pool_data_events(
            rpc_helper=rpc_helper,
            from_block=from_block + 1,
            to_block=to_block,
            redis_conn=redis_conn,
        ),
        # get burn and mint events for each of the stable and variable debt tokens
        get_debt_burn_mint_events(
            asset_address=asset_address,
            asset_metadata=asset_metadata,
            rpc_helper=rpc_helper,
            from_block=from_block + 1,
            to_block=to_block,
            redis_conn=redis_conn,
        ),
    )

    data_events = {
        key: filter(lambda x: x['args']['reserve'] == asset_address, value)
        for key, value in data_events.items()
    }

    initial_data = data_provider_reserve_data(*initial_data[0])

    # Init supply variables for calc
    liquidity_rate = initial_data.liquidityRate
    liquidity_index = initial_data.liquidityIndex
    last_update = initial_data.lastUpdateTimestamp
    supply = initial_data.totalAToken

    variable_debt = initial_data.totalVariableDebt
    variable_rate = initial_data.variableBorrowRate
    variable_index = initial_data.variableBorrowIndex

    stable_debt = initial_data.totalStableDebt
    stable_rate = initial_data.stableBorrowRate
    average_stable_rate = initial_data.averageStableBorrowRate

    current_block_details = block_details_dict.get(from_block, None)
    timestamp = current_block_details.get('timestamp', None)

    scaled_supply = calculate_initial_scaled_supply(
        supply=supply,
        current_timestamp=timestamp,
        last_update=last_update,
        liquidity_rate=liquidity_rate,
        liquidity_index=liquidity_index,
    )

    scaled_variable_debt = calculate_initial_scaled_variable(
        variable_debt=variable_debt,
        variable_rate=variable_rate,
        variable_index=variable_index,
        current_timestamp=timestamp,
        last_update=last_update,
    )

    scaled_stable_debt = calculate_initial_scaled_stable(
        stable_debt=stable_debt,
        avg_stable_rate=average_stable_rate,
        current_timestamp=timestamp,
        last_update=last_update,
    )

    computed_supply_debt_list = list()

    # add known from_block data to return list
    computed_supply_debt_list.append({
        'totalAToken': supply,
        'liquidityRate': liquidity_rate,
        'liquidityIndex': liquidity_index,
        'totalStableDebt': stable_debt,
        'totalVariableDebt': variable_debt,
        'variableBorrowRate': variable_rate,
        'stableBorrowRate': initial_data.stableBorrowRate,
        'variableBorrowIndex': variable_index,
        'lastUpdateTimestamp': last_update,
        'timestamp': current_block_details.get('timestamp', None),
        'unbacked': initial_data.unbacked,  # using initial data for unbacked until calculation implemented
        'accruedToTreasuryScaled': 0,  # not used in current snapshot
        'averageStableBorrowRate': average_stable_rate,
    })

    # calculate supply for each block excluding from block
    for block_num in range(from_block + 1, to_block + 1):
        current_block_details = block_details_dict.get(block_num, None)

        timestamp = current_block_details.get('timestamp', None)
        update_scaled_sp_flag = False
        update_scaled_vr_flag = False
        update_scaled_st_flag = False

        supply_adj = 0
        variable_debt_adj = 0
        stable_debt_adj = 0

        # adjust supply data with retrieved events
        # TODO: Test with multiple events in same block
        for event in data_events.get(block_num, None):
            if event['event'] == 'Withdraw':
                supply_adj -= event['args']['amount']
                update_scaled_sp_flag = True
            elif event['event'] == 'Supply':
                supply_adj += event['args']['amount']
                update_scaled_sp_flag = True
            elif event['event'] == 'ReserveDataUpdated':
                liquidity_rate = event['args']['liquidityRate']
                liquidity_index = event['args']['liquidityIndex']
                variable_rate = event['args']['variableBorrowRate']
                variable_index = event['args']['variableBorrowIndex']
                stable_rate = event['args']['stableBorrowRate']
                last_update = timestamp

        for event in debt_events.get(block_num, None):
            if event['address'] == asset_metadata['reserve_addresses']['variable_debt_token']:
                update_scaled_vr_flag = True
                if event['event'] == 'Mint':
                    variable_debt_adj += event['args']['value'] - event['args']['balanceIncrease']
                elif event['event'] == 'Burn':
                    variable_debt_adj -= event['args']['value'] + event['args']['balanceIncrease']
            else:
                update_scaled_st_flag = True
                if event['event'] == 'Mint':
                    stable_debt_adj += event['args']['amount'] - event['args']['balanceIncrease']
                    average_stable_rate = event['args']['avgStableRate']
                elif event['event'] == 'Burn':
                    stable_debt_adj -= event['args']['amount'] + event['args']['balanceIncrease']
                    average_stable_rate = event['args']['avgStableRate']

        supply_interest = calculate_linear_interest(
            liquidity_rate=liquidity_rate,
            last_update_timestamp=last_update,
            current_timestamp=timestamp,
        )

        variable_interest = calculate_compound_interest(
            rate=variable_rate,
            last_update_timestamp=last_update,
            current_timestamp=timestamp,
        )

        stable_interest = calculate_compound_interest(
            rate=average_stable_rate,
            current_timestamp=timestamp,
            last_update_timestamp=last_update,
        )

        supply = calculate_current_from_scaled(
            scaled_value=scaled_supply,
            interest=supply_interest,
            index=liquidity_index,
        )

        variable_debt = calculate_current_from_scaled(
            scaled_value=scaled_variable_debt,
            interest=variable_interest,
            index=variable_index,
        )

        stable_debt = rayMul(stable_interest, scaled_stable_debt)

        supply += supply_adj
        variable_debt += variable_debt_adj
        stable_debt += stable_debt_adj

        # scaled supply must be updated after supply is calculated
        if update_scaled_sp_flag:
            scaled_supply = calculate_scaled_from_current(supply, supply_interest, liquidity_index)
        if update_scaled_vr_flag:
            scaled_variable_debt = calculate_scaled_from_current(variable_debt, variable_interest, variable_index)
        if update_scaled_st_flag:
            scaled_stable_debt = rayDiv(stable_debt, stable_interest)

        computed_supply_debt_list.append({
            'totalAToken': supply,
            'liquidityRate': liquidity_rate,
            'liquidityIndex': liquidity_index,
            'totalStableDebt': stable_debt,
            'totalVariableDebt': variable_debt,
            'variableBorrowRate': variable_rate,
            'stableBorrowRate': stable_rate,
            'variableBorrowIndex': variable_index,
            'lastUpdateTimestamp': last_update,
            'timestamp': current_block_details.get('timestamp', None),
            'unbacked': initial_data.unbacked,
            'accruedToTreasuryScaled': 0,
            'averageStableBorrowRate': average_stable_rate,
        })

    core_logger.debug(
        (
            'Calculated asset total supply for epoch-range:'
            f' {from_block} - {to_block} | asset_contract: {asset_address}'
        ),
    )

    return [data_provider_reserve_data(**data) for data in computed_supply_debt_list]


def calculate_initial_scaled_supply(
    supply: int,
    current_timestamp: dict,
    last_update: int,
    liquidity_rate: int,
    liquidity_index: int,
) -> int:
    interest = calculate_linear_interest(
        last_update_timestamp=last_update,
        current_timestamp=current_timestamp,
        liquidity_rate=liquidity_rate,
    )
    normalized = calculate_normalized_value(
        interest=interest,
        index=liquidity_index,
    )
    return rayDiv(supply, normalized)


def calculate_initial_scaled_variable(
    variable_debt: int,
    variable_rate: int,
    variable_index: int,
    current_timestamp: int,
    last_update: int,
) -> int:
    variable_interest = calculate_compound_interest(
        rate=variable_rate,
        current_timestamp=current_timestamp,
        last_update_timestamp=last_update,
    )
    normalized_variable_debt = calculate_normalized_value(
        interest=variable_interest,
        index=variable_index,
    )
    return rayDiv(variable_debt, normalized_variable_debt)


def calculate_initial_scaled_stable(
    stable_debt: int,
    avg_stable_rate: int,
    current_timestamp: int,
    last_update: int,
) -> int:
    stable_interest = calculate_compound_interest(
        rate=avg_stable_rate,
        current_timestamp=current_timestamp,
        last_update_timestamp=last_update,
    )
    return rayDiv(stable_debt, stable_interest)


def calculate_scaled_from_current(current_value: int, interest: int, index: int) -> int:
    normalized = calculate_normalized_value(
        interest=interest,
        index=index,
    )
    return rayDiv(current_value, normalized)


def calculate_current_from_scaled(scaled_value: int, interest: int, index: int) -> int:
    normalized = calculate_normalized_value(
        interest=interest,
        index=index,
    )
    return rayMul(scaled_value, normalized)


def rayMul(a: int, b: int):
    x = Decimal(a) * Decimal(b)
    y = x + Decimal(HALF_RAY)
    z = y / Decimal(RAY)
    return int(z)


def rayDiv(a: int, b: int):
    x = Decimal(b) / 2
    y = Decimal(a) * Decimal(RAY)
    z = (x + y) / b
    return int(z)


def calculate_normalized_value(interest: int, index: int) -> int:
    return rayMul(interest, index)

# https://github.com/aave/aave-v3-core/blob/master/contracts/protocol/libraries/math/MathUtils.sol


def calculate_linear_interest(
    last_update_timestamp: int,
    current_timestamp: int,
    liquidity_rate: int,
):
    time_dif = current_timestamp - last_update_timestamp
    return ((liquidity_rate * time_dif) / SECONDS_IN_YEAR) + RAY

# https://github.com/aave/aave-v3-core/blob/master/contracts/protocol/libraries/math/MathUtils.sol line 50


def calculate_compound_interest(rate: int, current_timestamp: int, last_update_timestamp: int) -> int:
    exp = current_timestamp - last_update_timestamp

    if exp == 0:
        return int(RAY)

    expMinusOne = exp - 1
    expMinusTwo = max(0, exp - 2)

    basePowerTwo = int(rayMul(rate, rate) / (SECONDS_IN_YEAR * SECONDS_IN_YEAR))
    basePowerThree = int(rayMul(basePowerTwo, rate) / SECONDS_IN_YEAR)

    secondTerm = (exp * expMinusOne * basePowerTwo) / 2
    thirdTerm = (exp * expMinusOne * expMinusTwo * basePowerThree) / 6

    interest = Decimal(RAY) + Decimal(rate * exp) / Decimal(SECONDS_IN_YEAR) + Decimal(secondTerm + thirdTerm)

    return interest
