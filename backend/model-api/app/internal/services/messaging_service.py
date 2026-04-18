import aio_pika
import json
from aio_pika.abc import AbstractRobustConnection, AbstractChannel
from ...config.config import environment

class MessagingService:

    def __init__(self, connection: AbstractRobustConnection, channel: AbstractChannel):
        self.connection: AbstractRobustConnection = connection
        self.channel: AbstractChannel = channel 

    async def consume_data(self, callback): # from forecast queue
        queue = await self.channel.declare_queue("forecast", durable=True)
        await queue.consume(callback)
    
    async def publish_prediction(self, payload):
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload.model_dump()).encode("utf-8"),
                content_type="application/json",
            ),
            routing_key="predictions",
        )

    async def close(self):
        # invoke after use
        await self.connection.close()

    @classmethod
    async def create(cls):
        connection: AbstractRobustConnection =  await aio_pika.connect_robust(environment.broker_url)
        channel: AbstractChannel = await connection.channel()
        await channel.declare_queue("predictions", durable=True)
        await channel.declare_queue("forecast", durable=True)
        return cls(connection, channel)