import pika
import os
import json
import logging
import time
from database import SessionLocal, init_db
from domain import ProcessState, OutboxEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

def callback(ch, method, properties, body):
    try:
        event = json.loads(body)
        event_type = method.routing_key
        booking_id = event.get("bookingId")
        
        if not booking_id:
            logger.error("No bookingId in event payload")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        import uuid
        booking_uuid = uuid.UUID(booking_id)

        with SessionLocal() as db:
            # Hydration Step: Load state from DB
            state = db.query(ProcessState).filter(ProcessState.id == booking_uuid).first()
            if not state:
                logger.error(f"State not found for bookingId: {booking_id}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            outbox_evt = None
            if event_type == "RouteGeneratedEvent":
                outbox_evt = state.handle_route_generated(event.get("route"))
            elif event_type == "FlightBookedEvent":
                outbox_evt = state.handle_flight_booked(event.get("flightConfirmation"))
            elif event_type == "HotelBookedEvent":
                state.handle_hotel_booked(event.get("hotelConfirmation"))
            elif event_type == "HotelFailedEvent":
                outbox_evt = state.handle_hotel_failed(event.get("reason"))
                
            if outbox_evt:
                db.add(outbox_evt)
            
            db.commit()
            
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
