import pika
import os
import json
import logging
import uuid
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

def callback(ch, method, properties, body):
    try:
        command = json.loads(body)
        logger.info(f"Received {method.routing_key}: {command}")
        
        booking_id = command.get("bookingId")
        event_type = method.routing_key
        
        if event_type == 'BookFlightCommand':
            flight_confirmation = f"FL-{uuid.uuid4().hex[:8].upper()}"
            response_event = {
                "bookingId": booking_id,
                "flightConfirmation": flight_confirmation
            }
            ch.basic_publish(
                exchange='trip_exchange',
                routing_key='FlightBookedEvent',
                body=json.dumps(response_event)
            )
            logger.info(f"Published FlightBookedEvent: {response_event}")
        elif event_type == 'CancelFlightCommand':
            logger.info(f"Flight Cancelled for bookingId: {booking_id}")
            
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Error processing command: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    while True:
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.exchange_declare(exchange='trip_exchange', exchange_type='topic', durable=True)
            
            result = channel.queue_declare(queue='flight_booking_queue', durable=True)
            queue_name = result.method.queue
            
            channel.queue_bind(exchange='trip_exchange', queue=queue_name, routing_key='BookFlightCommand')
            channel.queue_bind(exchange='trip_exchange', queue=queue_name, routing_key='CancelFlightCommand')
            
            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            logger.info("Flight Booking Service waiting for commands...")
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
