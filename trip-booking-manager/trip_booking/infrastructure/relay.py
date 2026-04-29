import time
import json
import pika
import os
import logging
from sqlalchemy import text
from trip_booking.infrastructure.database import SessionLocal, init_db
from trip_booking.domain.domain import OutboxEvent

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
    init_db() # ensure db is mapped
    while True:
        try:
            connection, channel = get_rabbitmq_channel()
            break
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ for relay: {e}")
            time.sleep(5)

    logger.info("Outbox Relay started...")
    while True:
        try:
            with SessionLocal() as db:
                sql = text("""
                    UPDATE outbox_events 
                    SET published = true 
                    WHERE id IN (
                        SELECT id FROM outbox_events 
                        WHERE published = false 
                        ORDER BY created_at ASC 
                        LIMIT 5 
                        FOR UPDATE SKIP LOCKED
                    ) 
                    RETURNING id, event_type, payload;
                """)
                result = db.execute(sql)
                rows = result.fetchall()
                
                if not rows:
                    db.commit()
                    time.sleep(1)
                    continue
                
                for row in rows:
                    event_id, event_type, payload = row
                    message = json.dumps(payload)
                    channel.basic_publish(
                        exchange='trip_exchange',
                        routing_key=event_type,
                        body=message,
                        properties=pika.BasicProperties(
                            delivery_mode=2 # persistent
                        )
                    )
                
                db.commit()
        except Exception as e:
            logger.error(f"Error in relay: {e}")
            time.sleep(2)
            try:
                if connection.is_closed or channel.is_closed:
                    connection, channel = get_rabbitmq_channel()
            except Exception:
                pass

if __name__ == "__main__":
    relay_outbox_events()
