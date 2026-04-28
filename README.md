# Trip Booking Process Manager

A distributed, event-driven Process Manager handling a multi-step Trip Booking workflow. It demonstrates resilient cross-boundary communication using the Transactional Outbox pattern, preventing partial failures.

## Prerequisites
- A local Kubernetes cluster running via `kind`.
- `kubectl` configured to point to your `kind` cluster.
- Docker installed locally.

## Build and Load Images

Since the deployment manifests pull images locally (`imagePullPolicy: Never`), you must build and load all Docker images into the `kind` cluster first. Run these commands from the root of the project:

```bash
# Build images
docker build -t trip-booking-manager:latest ./trip-booking-manager
docker build -t flight-routing-service:latest ./flight-routing-service
docker build -t flight-booking-service:latest ./flight-booking-service
docker build -t hotel-booking-service:latest ./hotel-booking-service
docker build -t api-gateway:latest ./api-gateway

# Load images into kind cluster (assuming your cluster is named 'kind')
kind load docker-image trip-booking-manager:latest
kind load docker-image flight-routing-service:latest
kind load docker-image flight-booking-service:latest
kind load docker-image hotel-booking-service:latest
kind load docker-image api-gateway:latest
```

## Deployment

Apply all Kubernetes manifests. Note that PostgreSQL and RabbitMQ use `local-path-provisioner` PVCs.

```bash
kubectl apply -f infra/
```

Verify that all pods are running (it may take a minute for RabbitMQ and PostgreSQL to initialize and the services to connect).

```bash
kubectl get pods
```

## Interactive Testing Guide

The API Gateway is exposed via a NodePort on `30080`. You can access it locally at `http://localhost:30080` (or the IP of your kind node).

### Role 1: The Employee (The Happy Path)
1. **Initiate a trip:**
   ```bash
   curl -X POST http://localhost:30080/trips \
        -H "Content-Type: application/json" \
        -d '{"destination": "Seattle", "travelerId": "emp-123"}'
   ```
   *Note the `bookingId` from the response.*

2. **Query the state:**
   ```bash
   curl http://localhost:30080/trips/<BOOKING_ID>
   ```
   *The state should progress to `AwaitingApproval`.*

3. **Approve Route:**
   ```bash
   curl -X POST http://localhost:30080/trips/<BOOKING_ID>/approve
   ```
   
4. **Verification:**
   Check the state again. It will automatically transition through `BookingFlights`, `BookingHotels`, and eventually `Completed` (or `Compensating` if the 10% chance of hotel failure hits).

### Role 2: The Picky Employee (The Workflow Loop)
1. **Initiate a trip:**
   ```bash
   curl -X POST http://localhost:30080/trips \
        -H "Content-Type: application/json" \
        -d '{"destination": "New York", "travelerId": "emp-456"}'
   ```

2. **Reject Route:**
   Wait for it to reach `AwaitingApproval`, then reject:
   ```bash
   curl -X POST http://localhost:30080/trips/<BOOKING_ID>/reject
   ```

3. **Verification:**
   Check the state. The `rejected_routes` array should increase, and a new route should be proposed (state returns to `AwaitingApproval`).

### Role 3: The Infrastructure Chaos Engineer (Resilience Testing)
1. Initiate a trip and let it reach `AwaitingApproval`.
2. Before approving, scale down the Process Manager:
   ```bash
   kubectl scale deploy trip-booking-manager --replicas=0
   ```
3. Check the logs or database. Since it's down, no processing happens. 
4. If you approve the route via direct database manipulation (or scale it up and quickly scale it down right after approving), the `BookFlightCommand` will be written to the `outbox_events` table but not published.
5. Bring the service back up:
   ```bash
   kubectl scale deploy trip-booking-manager --replicas=1
   ```
6. **Verification:** The Outbox Relay will wake up, use `SKIP LOCKED` to safely lock the unpublished event in Postgres, and publish it to RabbitMQ, proving resilience.
