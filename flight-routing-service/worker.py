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
        logger.info(f"Received CalculateRouteCommand: {command}")
        
        booking_id = command.get("bookingId")
        destination = command.get("destination")
        rejected_routes = command.get("rejectedRoutes", [])
        
        logger.info(f"Searching for flights to {destination}...")
        
        airlines = ["Delta", "United", "American Airlines", "JetBlue"]
        chosen_airline = None
        for airline in airlines:
            if airline not in rejected_routes:
                chosen_airline = airline
                break
                
        if not chosen_airline:
            chosen_airline = "Southwest"
            
        route_id = f"{chosen_airline}-to-{destination}"
        
        response_event = {
            "bookingId": booking_id,
            "route": {
                "routeId": route_id,
                "airline": chosen_airline,
                "cost": 350.00
            }
        }
        
        ch.basic_publish(
            exchange='trip_exchange',
            routing_key='RouteGeneratedEvent',
            body=json.dumps(response_event)
        )
        logger.info(f"Published RouteGeneratedEvent: {response_event}")
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
            
            result = channel.queue_declare(queue='routing_queue', durable=True)
            queue_name = result.method.queue
            
            channel.queue_bind(exchange='trip_exchange', queue=queue_name, routing_key='CalculateRouteCommand')
            
            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            logger.info("Flight Routing Service waiting for CalculateRouteCommand...")
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
