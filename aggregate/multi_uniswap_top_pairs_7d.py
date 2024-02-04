import asyncio
from typing import List

from ipfs_client.main import AsyncIPFSClient
from redis import asyncio as aioredis
from snapshotter.utils.callback_helpers import GenericProcessorAggregate
from snapshotter.utils.data_utils import get_submission_data_bulk
from snapshotter.utils.default_logger import logger
from snapshotter.utils.models.message_models import CalculateAggregateMessage
from snapshotter.utils.rpc import RpcHelper

from ..utils.helpers import get_pair_metadata
from ..utils.models.message_models import UniswapTopPair7dSnapshot
from ..utils.models.message_models import UniswapTopPairs7dSnapshot
from ..utils.models.message_models import UniswapTradesAggregateSnapshot


class AggregateTopPairsProcessor(GenericProcessorAggregate):

    def __init__(self) -> None:
        self._logger = logger.bind(module='AggregateTopPairsProcessor')

    async def compute(
        self,
        msg_obj: CalculateAggregateMessage,
        redis: aioredis.Redis,
        rpc_helper: RpcHelper,
        anchor_rpc_helper: RpcHelper,
        ipfs_reader: AsyncIPFSClient,
        protocol_state_contract,
        project_ids: List[str],

    ):
        self._logger.info(f'Calculating 7d top pairs trade volume data for {msg_obj}')
        project_id = project_ids[0]
        epoch_id = msg_obj.epochId

        snapshot_mapping = {}
        all_pair_metadata = {}

        snapshot_data = await get_submission_data_bulk(
            redis, [msg.snapshotCid for msg in msg_obj.messages[0].snapshotsSubmitted], ipfs_reader, [
                msg.projectId for msg in msg_obj.messages[0].snapshotsSubmitted
            ],
        )
        pair_metadata_tasks = []
        complete_flags = []
        for msg, data in zip(msg_obj.messages[0].snapshotsSubmitted, snapshot_data):
            if not data:
                continue
            snapshot = UniswapTradesAggregateSnapshot.parse_obj(data)
            complete_flags.append(snapshot.complete)
            snapshot_mapping[msg.projectId] = snapshot

            contract_address = msg.projectId.split(':')[-2]
            if contract_address not in all_pair_metadata:
                pair_metadata_tasks.append(get_pair_metadata(
                    pair_address=contract_address,
                    rpc_helper=rpc_helper,
                    redis_conn=redis,
                ))
        pair_metadata_lists = await asyncio.gather(*pair_metadata_tasks)
        for msg, pair_metadata in zip(msg_obj.messages[0].snapshotsSubmitted, pair_metadata_lists):
            contract_address = msg.projectId.split(':')[-2]
            all_pair_metadata[contract_address] = pair_metadata     

        # iterate over all snapshots and generate pair data
        pair_data = {}
        cids = snapshot_mapping.keys()
        self._logger.info(f'Calculating 7d top pairs trade volume data for {cids}')

        for snapshot_project_id in snapshot_mapping.keys():
            snapshot = snapshot_mapping[snapshot_project_id]
            contract = snapshot_project_id.split(':')[-2]
            pair_metadata = all_pair_metadata[contract]

            if contract not in pair_data:
                pair_data[contract] = {
                    'address': contract,
                    'name': pair_metadata['pair']['symbol'],
                    'volume7d': 0,
                    'fee7d': 0,
                }

            pair_data[contract]['volume7d'] += snapshot.totalTrade
            pair_data[contract]['fee7d'] += snapshot.totalFee

        top_pairs = []
        for pair in pair_data.values():
            top_pairs.append(UniswapTopPair7dSnapshot.parse_obj(pair))

        top_pairs = sorted(top_pairs, key=lambda x: x.address, reverse=True)
        top_pairs = sorted(top_pairs, key=lambda x: x.volume7d, reverse=True)

        top_pairs_snapshot = UniswapTopPairs7dSnapshot(
            epochId=epoch_id,
            pairs=top_pairs,
        )

        if not all(complete_flags):
            self._logger.debug(f'Not all snapshots are complete for {project_id}')
            top_pairs_snapshot.complete = False

        return [(project_id, top_pairs_snapshot)]