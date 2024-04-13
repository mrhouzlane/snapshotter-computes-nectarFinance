from snapshotter.settings.config import settings

uniswap_pair_contract_tokens_addresses = (
    "uniswap:pairContract:" + settings.namespace + ":{}:PairContractTokensAddresses"
)
uniswap_pair_contract_tokens_data = (
    "uniswap:pairContract:" + settings.namespace + ":{}:PairContractTokensData"
)

uinswap_token_pair_contract_mapping = (
    "uniswap:tokens:" + settings.namespace + ":PairContractAddress"
)

uniswap_V3_summarized_snapshots_zset = (
    "uniswap:V3PairsSummarySnapshot:" + settings.namespace + ":snapshotsZset"
)
uniswap_V3_snapshot_at_blockheight = (
    "uniswap:V3PairsSummarySnapshot:" + settings.namespace + ":snapshot:{}"
)  # block_height
uniswap_V3_daily_stats_snapshot_zset = (
    "uniswap:V3DailyStatsSnapshot:" + settings.namespace + ":snapshotsZset"
)
uniswap_V3_daily_stats_at_blockheight = (
    "uniswap:V3DailyStatsSnapshot:" + settings.namespace + ":snapshot:{}"
)  # block_height
uniswap_V3_tokens_snapshot_zset = (
    "uniswap:V3TokensSummarySnapshot:" + settings.namespace + ":snapshotsZset"
)
uniswap_V3_tokens_at_blockheight = (
    "uniswap:V3TokensSummarySnapshot:" + settings.namespace + ":{}"
)  # block_height

uniswap_pair_cached_recent_logs = (
    "uniswap:pairContract:" + settings.namespace + ":{}:recentLogs"
)

uniswap_tokens_pair_map = (
    "uniswap:pairContract:" + settings.namespace + ":tokensPairMap"
)

uniswap_ticks_pair_map = (
    "uniswap:pairContract:" + settings.namespace + ":ticksPairMap"
)

uniswap_pair_cached_block_height_token_price = (
    "uniswap:pairContract:" + settings.namespace + ":{}:cachedPairBlockHeightTokenPrice"
)

uniswap_token_derived_eth_cached_block_height = (
    "uniswap:token:" + settings.namespace + ":{}:cachedDerivedEthBlockHeight"
)

# to build modules grabbing data from multiple protocols all token eth prices can be stored in the same place
uniswap_cached_block_height_token_eth_price = (
    "uniswap:pairContract:" + settings.namespace + ":{}:cachedBlockHeightTokenEthPrice"
)

uniswap_cached_tick_data_block_height = (
    "uniswap:pairContract:" + settings.namespace + ":{}:cachedBlockHeightTickData"
)
uniswap_pair_cached_block_height_reserves = (
    "uniswap:pairContract:" + settings.namespace + ":{}:cachedBlockHeightReserves"
)

uniswap_v3_monitored_pairs = 'uniswap:monitoredPairs'

uniswap_v3_best_pair_map = (
    "uniswap:pairContract:" + settings.namespace + ":bestPairMap"
)

uniswap_v3_token_stable_pair_map = (
    f"uniswap:pairContract:" + settings.namespace + ":{}:tokenStablePairMap"
)
