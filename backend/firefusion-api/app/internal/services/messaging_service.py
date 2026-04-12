import aio_pika
import json
from aio_pika.abc import AbstractRobustConnection
from aio_pika.abc import AbstractChannel
from ...config.config import environment

class MessagingService:

    def __init__(self, connection: AbstractRobustConnection, channel: AbstractChannel):
        self.connection: AbstractRobustConnection = connection
        self.channel: AbstractChannel = channel 

    async def consume_predictions(self, callback):
        queue = await self.channel.declare_queue("predictions", durable=True)
        await queue.consume(callback)

    async def close(self):
        # invoke after use
        await self.connection.close()

    @classmethod
    async def create(cls):
        connection: AbstractRobustConnection =  await aio_pika.connect_robust(environment.broker_url)
        channel: AbstractChannel = await connection.channel()
        await channel.declare_queue("predictions", durable=True)
        return cls(connection, channel)