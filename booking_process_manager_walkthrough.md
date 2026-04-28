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
