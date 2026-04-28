import pika
import os
import json
import logging
import uuid
import time
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

def callback(ch, method, properties, body):
    try:
        command = json.loads(body)
        logger.info(f"Received BookHotelCommand: {command}")
        
        booking_id = command.get("bookingId")
        destination = command.get("destination")
        
        fail = random.random() < 0.1
        
        if not fail:
            hotel_confirmation = f"HTL-{uuid.uuid4().hex[:8].upper()}"
            response_event = {
                "bookingId": booking_id,
                "hotelConfirmation": hotel_confirmation
            }
            routing_key = 'HotelBookedEvent'
            logger.info(f"Published HotelBookedEvent: {response_event}")
        else:
            response_event = {
                "bookingId": booking_id,
                "reason": "No rooms available"
            }
            routing_key = 'HotelFailedEvent'
            logger.info(f"Published HotelFailedEvent: {response_event}")
            
        ch.basic_publish(
            exchange='trip_exchange',
            routing_key=routing_key,
            body=json.dumps(response_event)
        )
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
            
            result = channel.queue_declare(queue='hotel_booking_queue', durable=True)
            queue_name = result.method.queue
            
            channel.queue_bind(exchange='trip_exchange', queue=queue_name, routing_key='BookHotelCommand')
            
            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            logger.info("Hotel Booking Service waiting for BookHotelCommand...")
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
