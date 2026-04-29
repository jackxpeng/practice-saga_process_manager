import pika
import os
import json
import logging
import time
from trip_booking.infrastructure.database import SessionLocal, init_db
from trip_booking.infrastructure.sql_repository import SqlAlchemyTripRepository
from trip_booking.application.service import TripApplicationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

def callback(ch, method, properties, body):
    try:
        event = json.loads(body)
        event_type = method.routing_key
        
        with SessionLocal() as db:
            repo = SqlAlchemyTripRepository(db)
            service = TripApplicationService(repo)
            
            try:
                service.process_external_event(event_type, event)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except ValueError as e:
                logger.error(f"Validation error: {e}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
    except Exception as e:
        logger.error(f"Error processing event: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def consume_events():
    init_db() # ensure db is mapped
    while True:
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.exchange_declare(exchange='trip_exchange', exchange_type='topic', durable=True)
            
            result = channel.queue_declare(queue='manager_queue', durable=True)
            queue_name = result.method.queue
            
            # Bind to all relevant events
            events = ["RouteGeneratedEvent", "FlightBookedEvent", "HotelBookedEvent", "HotelFailedEvent"]
            for evt in events:
                channel.queue_bind(exchange='trip_exchange', queue=queue_name, routing_key=evt)
            
            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            logger.info("Process Manager Consumer started...")
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ for consumer: {e}")
            time.sleep(5)

if __name__ == "__main__":
    consume_events()
