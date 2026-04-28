# Booking Process Manager Walkthrough

This document visualizes the operation of the `BookingProcessManager` using architectural flow diagrams, sequence diagrams, and state machine diagrams.

## 1. The Architectural Flow

These diagrams illustrate the structural relationship between the code and the system.

### Generic Pattern (Figure 9-14)
The Process Manager acts as a central processing unit sitting between the application and multiple external services. It is the sole component responsible for communicating with the state database.

```mermaid
flowchart TD
    App[Application] --> PM[Process Manager]
    PM --> S[(State Database)]
    PM --> T1[Target 1]
    PM --> T2[Target 2]
    PM --> T3[Target 3]
    
    classDef default fill:#f9f9f9,stroke:#333,stroke-width:2px;
    classDef pm fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    class PM pm;
```

### Specific Implementation (Figure 9-15)
This diagram maps directly to the implementation details. The `Initialize` method starts the process, tracking state variables like `_id`, `_destination`, and `_rejectedRoutes`, and issuing commands to various targets.

```mermaid
flowchart TD
    Start((Start new<br/>booking process)) -->|Initialize| PM[Trip Booking Process Manager<br/>State: _id, _destination, _rejectedRoutes]
    PM --> Flight[Flight Routing Target]
    PM --> Hotel[Hotel Booking Target]
    PM --> Car[Car Rental Target]
    PM <--> State[(State Database)]
    
    classDef default fill:#f9f9f9,stroke:#333,stroke-width:2px;
    classDef pm fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    class PM pm;
```

## 2. The Logic Sequence

This sequence diagram illustrates how the `Process` method executes in a distributed environment when an event occurs.

```mermaid
sequenceDiagram
    autonumber
    participant Ext as External Service
    participant PM as BookingProcessManager
    participant State as Internal State (_events)
    participant Outbox as Outbox Relay
    participant Target as Target Endpoint

    Ext->>PM: Send Event (e.g., FlightBooked)
    activate PM
    PM->>State: Append(Event)
    Note over PM: Logic determines next step
    PM->>State: Append(CommandIssuedEvent)
    deactivate PM
    
    Outbox->>State: Observe CommandIssuedEvent
    activate Outbox
    Outbox->>Target: Execute Command (e.g., BookHotel)
    deactivate Outbox
```

## 3. The State Transition

The Process Manager acts as a persistent object that "wakes up" to handle events based on its saved history. This diagram shows its lifecycle and loop-back mechanisms.

```mermaid
stateDiagram-v2
    [*] --> Initialized : Initialize
    Initialized --> AwaitingApproval : Trip Requested
    AwaitingApproval --> AwaitingFlightBooking : Trip Approved
    AwaitingFlightBooking --> AwaitingHotelBooking : Flight Booked
    
    %% Loop-back transition
    AwaitingFlightBooking --> AwaitingFlightBooking : RouteRejected<br/>(Loop back to routing stage)
    
    AwaitingHotelBooking --> Completed : Hotel Booked
    Completed --> [*]
```

## 4. Code Architecture and Design

The implementation of the `BookingProcessManager` is designed around **Hexagonal Architecture (Ports and Adapters)**, ensuring the core business logic is completely isolated from infrastructure concerns like HTTP APIs, database implementations, and message brokering.

### Decoupled Components
The system is divided into highly isolated microservices:
- **`trip-booking-manager` (The Core):** Maintains the `ProcessState` and implements the Transactional Outbox pattern.
- **Worker Services:** `flight-routing-service`, `flight-booking-service`, and `hotel-booking-service`. These are stateless background workers that only know how to consume specific RabbitMQ commands and publish events in response.
- **`api-gateway`:** A REST API entrypoint. It does not touch the state database directly. Instead, it acts as a proxy, forwarding requests to the manager's driving port to enforce bounded contexts.

### The Transactional Outbox Pattern
To prevent partial failures (e.g., saving state to Postgres but crashing before publishing to RabbitMQ), the `trip-booking-manager` leverages the Transactional Outbox pattern.
- **Atomicity:** When a domain action occurs, the updated `process_state` and a new `outbox_events` record are saved to the database in a single transaction.
- **Relay Worker (`SKIP LOCKED`):** A background thread constantly polls the `outbox_events` table for unpublished events. It uses a Postgres `FOR UPDATE SKIP LOCKED` query, which provides robust concurrency control. This allows the system to be scaled to multiple replicas safely without workers deadlocking or duplicating message publishing.

### State Hydration
When the `trip-booking-manager` receives an event from RabbitMQ (like `FlightBookedEvent`), the infrastructure layer extracts the `bookingId`, queries the Postgres database to retrieve the current state, and reconstructs (hydrates) the Process Manager in memory before passing the event payload directly into the pure domain logic.

## 5. DDD Context Diagram

```mermaid
flowchart TD
    %% Define the Bounded Contexts
    TripBC[/"Trip Booking Context<br/>(Core)"/]
    RouteBC[/"Flight Routing Context<br/>(Supporting)"/]
    FlightBC[/"Flight Booking Context<br/>(Supporting)"/]
    HotelBC[/"Hotel Booking Context<br/>(Supporting)"/]

    %% Define the External Systems (Also treated as Bounded Contexts)
    ExtRoute[/"External Routing Service"/]
    ExtAirline[/"External Airline Systems"/]
    ExtHotel[/"External Hotel Systems"/]

    %% Internal Integration (Process Manager to Workers)
    %% Trip Manager is UPSTREAM (U). It exposes a Published Language (PL).
    %% Workers are DOWNSTREAM (D). They Conform (CF) to the language.
    TripBC -- "U (OHS/PL)<br/>Event Schema" ---> RouteBC
    RouteBC -- "D (CF)" ---> TripBC

    TripBC -- "U (OHS/PL)<br/>Event Schema" ---> FlightBC
    FlightBC -- "D (CF)" ---> TripBC

    TripBC -- "U (OHS/PL)<br/>Event Schema" ---> HotelBC
    HotelBC -- "D (CF)" ---> TripBC

    %% External Integration (Workers to 3rd Party APIs)
    %% External APIs are UPSTREAM (U). They dictate the terms.
    %% Workers are DOWNSTREAM (D). They use an Anti-Corruption Layer (ACL).
    ExtRoute -- "U" ---> RouteBC
    RouteBC -- "D (ACL)" ---> ExtRoute

    ExtAirline -- "U" ---> FlightBC
    FlightBC -- "D (ACL)" ---> ExtAirline

    ExtHotel -- "U" ---> HotelBC
    HotelBC -- "D (ACL)" ---> ExtHotel

    %% Styling
    classDef internal fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,stroke-dasharray: 5 5
    classDef external fill:#f5f5f5,stroke:#9e9e9e,stroke-width:2px,stroke-dasharray: 5 5
    
    class TripBC,RouteBC,FlightBC,HotelBC internal
    class ExtRoute,ExtAirline,ExtHotel external
```