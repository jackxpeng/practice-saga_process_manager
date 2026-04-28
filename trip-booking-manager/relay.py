import time
import json
import pika
import os
import threading
import logging
from sqlalchemy import text
from database import SessionLocal
from domain import OutboxEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

def get_rabbitmq_channel():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange='trip_exchange', exchange_type='topic', durable=True)
    return connection, channel

def relay_outbox_events():
    while True:
        try:
            connection, channel = get_rabbitmq_channel()
            break
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ for relay: {e}")
            time.sleep(5)

    while True:
        try:
            with SessionLocal() as db:
                sql = text("""
                    SELECT id FROM outbox_events 
                    WHERE published = False 
                    FOR UPDATE SKIP LOCKED 
                    LIMIT 5
                """)
                result = db.execute(sql)
                event_ids = [row[0] for row in result]
                
                if not event_ids:
                    time.sleep(1)
                    continue
                
                events = db.query(OutboxEvent).filter(OutboxEvent.id.in_(event_ids)).all()
                for event in events:
                    routing_key = event.event_type
                    message = json.dumps(event.payload)
                    channel.basic_publish(
                        exchange='trip_exchange',
                        routing_key=routing_key,
                        body=message,
                        properties=pika.BasicProperties(
                            delivery_mode=2 # persistent
                        )
                    )
                    event.published = True
                
                db.commit()
        except Exception as e:
            logger.error(f"Error in relay: {e}")
            time.sleep(2)
            try:
                if connection.is_closed or channel.is_closed:
                    connection, channel = get_rabbitmq_channel()
            except Exception:
                pass

def start_relay():
    thread = threading.Thread(target=relay_outbox_events, daemon=True)
    thread.start()
