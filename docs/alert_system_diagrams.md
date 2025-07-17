# Home Depot Workshop Alert System

This document explains the workshop alert system using diagrams to visualize the flow and components.

## 1. Overall System Flow

```mermaid
flowchart TD
    A[Start Script] --> B{Check for Workshops}
    B -->|No Workshops Available| C[Exit]
    B -->|Workshops Found| D{Filter Workshops}
    D -->|Not Kid Workshop| C
    D -->|Not Active| C
    D -->|No Seats Left| C
    D -->|Kid Workshop Available| E{Already Alerted Today?}
    E -->|Yes| C
    E -->|No| F[Send Multiple Alert Types]
    F -->|1. Standard Alert| G[Send Slack Message]
    F -->|2. High Priority| H[Send Urgent Workshop Alert]
    F -->|3. Registration| I{Auto-Register?}
    I -->|Yes| J[Register Workshop]
    J -->|Success| K[Send Success Alert]
    J -->|Failure| L[Send Failure Alert]
    I -->|No| C
```

## 2. Alert Types Hierarchy

```mermaid
classDiagram
    class AlertSystem {
        +send_slack_message()
        +send_urgent_workshop_alert()
        +send_api_error_alert()
        +update_last_alert_date()
    }
    
    class StandardAlert {
        +Simple Slack message
        +Basic formatting
        +Lower visibility
    }
    
    class UrgentWorkshopAlert {
        +Bright red header
        +Direct registration button
        +Pinned to channel
        +@channel notification
        +Detailed workshop info
    }
    
    class APIErrorAlert {
        +Error details
        +Technical information
        +Error emoji indicators
    }
    
    AlertSystem <|-- StandardAlert
    AlertSystem <|-- UrgentWorkshopAlert 
    AlertSystem <|-- APIErrorAlert
```

## 3. Workshop Detection & Alert Process

```mermaid
sequenceDiagram
    participant Script as Home Depot Script
    participant API as Home Depot API
    participant Filter as Workshop Filter
    participant Alert as Alert System
    participant Slack as Slack Channel
    participant AutoReg as Auto Registration
    
    Script->>API: Request workshop data
    API-->>Script: Return workshop data
    Script->>Filter: Process workshops
    
    Filter->>Filter: Check workshop type (KID)
    Filter->>Filter: Check seats availability
    Filter->>Filter: Check status (ACTIVE)
    
    Filter->>Alert: Send available workshop
    
    Alert->>Alert: Check if already alerted today
    
    Note right of Alert: If not already alerted
    
    Alert->>Slack: Send standard notification
    Alert->>Slack: Send urgent high-visibility alert
    
    opt Auto Registration for KWTM
        Alert->>AutoReg: Register for workshop
        AutoReg->>API: Submit registration
        API-->>AutoReg: Registration response
        
        alt Registration Success
            AutoReg->>Slack: Send success alert
        else Registration Failure
            AutoReg->>Slack: Send failure alert
        end
    end
```

## 4. Alert Components Visual Hierarchy

```mermaid
graph TD
    subgraph "Alert Components"
        A[Standard Alert] --> B[Basic Message]
        A --> C[Workshop Title]
        A --> D[Date Information]
        
        E[Urgent Alert] --> F[Red Header Banner]
        E --> G[Workshop Title]
        E --> H[Date Information]
        E --> I[Event Code]
        E --> J[Seats Left]
        E --> K["Register Now" Button]
        E --> L[Channel Notification]
        E --> M[Pinned Message]
        
        N[API Error Alert] --> O[Error Message]
        N --> P[Technical Details]
        N --> Q[Timestamp]
        
        R[Registration Alert] --> S[Success/Failure Indicator]
        R --> T[Workshop Details]
        R --> U[Response Information]
    end
```

## 5. Error Handling Flow

```mermaid
flowchart TD
    A[API Request] --> B{Response Valid?}
    B -->|No| C[Send API Error Alert]
    B -->|Yes| D{JSON Parsing}
    D -->|Error| E[Send JSON Error Alert]
    D -->|Success| F{Expected Data Structure?}
    F -->|No| G[Send Structure Error Alert]
    F -->|Yes| H[Process Workshops]
    
    subgraph "Registration Process"
    I[Submit Registration] --> J{Request Success?}
    J -->|Network Error| K[Send Request Error Alert]
    J -->|Yes| L{Response Code OK?}
    L -->|No| M[Send Registration Failure Alert]
    L -->|Yes| N[Send Registration Success Alert]
    end
```

## 6. Alert System Data Flow

```mermaid
flowchart LR
    A[Workshop Data] --> B[Alert Creator]
    
    B --> C[Standard Alert]
    C --> C1[Format Basic Message]
    C1 --> C2[Send to Slack]
    
    B --> D[Urgent Alert]
    D --> D1[Create Rich Formatted Message]
    D1 --> D2[Add Registration Button]
    D2 --> D3[Send to Slack]
    D3 --> D4[Pin Message]
    D3 --> D5[Send @channel Notification]
    
    B --> E{Workshop Type == KWTM?}
    E -->|Yes| F[Auto Registration]
    F --> F1[Create Registration Request]
    F1 --> F2[Submit to API]
    F2 --> F3{Success?}
    F3 -->|Yes| F4[Send Success Alert]
    F3 -->|No| F5[Send Failure Alert]
    
    G[Error Detection] --> H[API Error]
    H --> H1[Format Error Message]
    H1 --> H2[Add Technical Details]
    H2 --> H3[Send to Slack]
```

## 7. Component Relationship Diagram

```mermaid
erDiagram
    SCRIPT ||--o{ WORKSHOP : detects
    WORKSHOP }|--|| ALERT-SYSTEM : triggers
    ALERT-SYSTEM ||--o{ SLACK-NOTIFICATION : sends
    WORKSHOP ||--o{ AUTO-REGISTRATION : attempts
    AUTO-REGISTRATION }|--|| SLACK-NOTIFICATION : reports
    
    WORKSHOP {
        string title
        string code
        datetime startDate
        int seatsLeft
        string status
        string type
    }
    
    ALERT-SYSTEM {
        function standardAlert
        function urgentAlert
        function apiErrorAlert
        function registrationAlert
    }
    
    SLACK-NOTIFICATION {
        string message
        boolean isPinned
        boolean channelNotify
        string formattingLevel
    }
    
    AUTO-REGISTRATION {
        string eventCode
        string customerName
        string email
        int participants
        boolean success
    }
```
