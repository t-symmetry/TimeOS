# TimeOS iOS Development Plan

## Overview

Native iOS port of TimeOS using SwiftUI. Full temporal physics engine running locally on device, with optional remote connection to ROS2/hardware servers.

**Target:** iOS 17+ / iPadOS 17+ (Swift 5.9, SwiftUI)

**Build Machine:** Mac Mini M1 with Xcode 15+

---

## Architecture

```
TimeOSiOS/
├── TimeOSiOS.xcodeproj
├── TimeOSCore/              # Swift Package - shared logic
│   ├── Sources/
│   │   ├── Messages/        # ChronoStamp, TimelineEvent, etc.
│   │   ├── Physics/         # Spacetime, Lorentz, Causality
│   │   ├── Timeline/        # EventLog, Branch management
│   │   ├── Clocks/          # NTP, GPS, System, Composite
│   │   ├── Uncertainty/     # Drift models, Allan variance
│   │   └── Correlation/     # Stream alignment, resampling
│   └── Tests/
├── TimeOSApp/               # iOS App
│   ├── Views/
│   │   ├── MainView.swift
│   │   ├── TimelineView.swift
│   │   ├── ClockStatusView.swift
│   │   ├── DriftPlotView.swift
│   │   ├── EventDetailView.swift
│   │   └── SettingsView.swift
│   ├── ViewModels/
│   │   └── MachineModel.swift
│   ├── Services/
│   │   ├── ClockManager.swift
│   │   └── RemoteConnection.swift
│   └── Resources/
└── TimeOSWidgets/           # Optional: Home screen widgets
```

---

## Phase 1: Core Framework (Swift Package)

Port the Python core to Swift. This becomes a reusable Swift Package.

### 1.1 Messages

| Python | Swift |
|--------|-------|
| `ChronoStamp` | `struct ChronoStamp: Codable, Identifiable` |
| `TemporalFrame` | `struct TemporalFrame: Codable` |
| `TimelineEvent` | `struct TimelineEvent: Codable, Identifiable` |

```swift
struct ChronoStamp: Codable, Identifiable, Hashable {
    let id: UUID
    var frameId: String
    var t: Double
    var tUncertainty: Double
    var clockClass: ClockClass

    enum ClockClass: String, Codable {
        case atomic, gps, ptp, ntp, system, simulated
    }
}
```

### 1.2 Physics Engine

| Python Module | Swift Equivalent |
|---------------|------------------|
| `physics/spacetime.py` | `Physics/FourVector.swift`, `Physics/SpacetimeInterval.swift` |
| `physics/lorentz.py` | `Physics/LorentzTransform.swift` |
| `physics/frames.py` | `Physics/ReferenceFrame.swift` |
| `physics/causality.py` | `Physics/LightCone.swift`, `Physics/CausalRelation.swift` |

**Dependencies:**
- `Accelerate` framework for SIMD/matrix ops
- `simd` types for vectors

```swift
import Accelerate
import simd

struct FourVector {
    var t: Double  // Time component (ct)
    var x: Double
    var y: Double
    var z: Double

    var spacetimeInterval: Double {
        t * t - x * x - y * y - z * z
    }

    func lorentzBoost(velocity: SIMD3<Double>) -> FourVector {
        // Accelerate framework for fast matrix multiply
    }
}

func lorentzFactor(_ v: Double) -> Double {
    1.0 / sqrt(1.0 - (v * v) / (C * C))
}
```

### 1.3 Timeline & EventLog

SQLite via `GRDB.swift` or native `SQLite3`:

```swift
import GRDB

struct EventLog {
    private let dbQueue: DatabaseQueue

    func createEvent(_ stamp: ChronoStamp, type: String, parents: [UUID]) throws -> TimelineEvent
    func slice(start: Double, end: Double, branch: String?) throws -> [TimelineEvent]
    func causalAncestors(of eventId: UUID, maxDepth: Int) throws -> [TimelineEvent]
}
```

### 1.4 Clocks

| Python | Swift | Notes |
|--------|-------|-------|
| `SystemClock` | `SystemClock` | `mach_absolute_time()` for monotonic |
| `NTPClock` | `NTPClock` | Use `TrueTime` library or custom NTP client |
| `GPSClock` | `GPSClock` | `CoreLocation` + `CLLocationManager` |
| `CompositeClock` | `CompositeClock` | Kalman filter fusion |

```swift
protocol ClockSource {
    var id: String { get }
    func now() -> ChronoStamp
    func getOffset() -> (offset: Double, uncertainty: Double)
    var quality: ClockQuality { get }
}

class GPSClock: ClockSource, CLLocationManagerDelegate {
    private let locationManager = CLLocationManager()

    func now() -> ChronoStamp {
        // Use location.timestamp with uncertainty
    }
}
```

### 1.5 Uncertainty Math

| Python | Swift |
|--------|-------|
| `uncertainty/models.py` | `Uncertainty/DriftModel.swift` |
| `uncertainty/allan.py` | `Uncertainty/AllanVariance.swift` |
| `uncertainty/propagation.py` | `Uncertainty/Propagation.swift` |

```swift
import Accelerate

func allanDeviation(phases: [Double], rate: Double, taus: [Double]) -> [Double] {
    // Use vDSP for fast computation
    var result = [Double](repeating: 0, count: taus.count)
    // ... Accelerate framework FFT and stats
    return result
}
```

### 1.6 Correlation

| Python | Swift |
|--------|-------|
| `correlation/align.py` | `Correlation/CrossCorrelation.swift` |
| `correlation/resample.py` | `Correlation/Resample.swift` |

```swift
import Accelerate

func crossCorrelate(_ a: [Double], _ b: [Double]) -> [Double] {
    // vDSP_conv for fast cross-correlation
}

func findOffset(series1: TimeSeries, series2: TimeSeries, maxOffset: Double) -> OffsetResult {
    // Cross-correlation peak finding
}
```

---

## Phase 2: SwiftUI App

### 2.1 Main Views

```swift
struct MainView: View {
    @StateObject var model = MachineModel()

    var body: some View {
        NavigationSplitView {
            // Sidebar: Status panels
            StatusSidebar(model: model)
        } detail: {
            // Main content: Timeline + Event log
            VStack {
                TimelineView(model: model)
                EventLogView(model: model)
            }
        }
    }
}
```

### 2.2 Timeline Visualization

Use `Charts` framework (iOS 16+):

```swift
import Charts

struct TimelineView: View {
    @ObservedObject var model: MachineModel

    var body: some View {
        Chart(model.events) { event in
            PointMark(
                x: .value("Time", event.stamp.t),
                y: .value("Branch", event.branchId)
            )
            .foregroundStyle(by: .value("Type", event.eventType))

            // Uncertainty bars
            RectangleMark(
                xStart: .value("Start", event.stamp.t - event.stamp.tUncertainty),
                xEnd: .value("End", event.stamp.t + event.stamp.tUncertainty),
                y: .value("Branch", event.branchId)
            )
            .opacity(0.3)
        }
    }
}
```

### 2.3 Clock Status Panel

```swift
struct ClockStatusView: View {
    @ObservedObject var clockManager: ClockManager

    var body: some View {
        List(clockManager.sources) { source in
            HStack {
                StatusLED(status: source.status)
                VStack(alignment: .leading) {
                    Text(source.id).font(.headline)
                    Text(source.quality.description).font(.caption)
                }
                Spacer()
                Text(formatOffset(source.offset))
                    .monospacedDigit()
            }
        }
    }
}
```

### 2.4 Drift Plot

```swift
struct DriftPlotView: View {
    @ObservedObject var model: MachineModel

    var body: some View {
        Chart {
            ForEach(model.clockHistories) { history in
                ForEach(history.samples) { sample in
                    LineMark(
                        x: .value("Time", sample.timestamp),
                        y: .value("Offset", sample.offset * 1e6)  // µs
                    )
                    .foregroundStyle(by: .value("Source", history.sourceId))
                }
            }
        }
        .chartYAxisLabel("Offset (µs)")
        .chartXAxisLabel("Time (s)")
    }
}
```

### 2.5 Settings & Mode Selection

```swift
struct SettingsView: View {
    @AppStorage("mode") var mode: OperatingMode = .demo
    @AppStorage("remoteHost") var remoteHost: String = ""

    var body: some View {
        Form {
            Picker("Mode", selection: $mode) {
                Text("Demo").tag(OperatingMode.demo)
                Text("Local").tag(OperatingMode.local)
                Text("Remote").tag(OperatingMode.remote)
            }

            if mode == .remote {
                TextField("Server Address", text: $remoteHost)
                    .keyboardType(.URL)
            }
        }
    }
}
```

---

## Phase 3: Remote Connection (Optional)

WebSocket connection to desktop TimeOS for ROS2/hardware control:

```swift
class RemoteConnection: ObservableObject {
    @Published var isConnected = false
    private var webSocket: URLSessionWebSocketTask?

    func connect(to host: String) {
        let url = URL(string: "ws://\(host):8765/timeos")!
        webSocket = URLSession.shared.webSocketTask(with: url)
        webSocket?.resume()
        receiveMessage()
    }

    func sendCommand(_ command: RemoteCommand) {
        let data = try? JSONEncoder().encode(command)
        webSocket?.send(.data(data!)) { _ in }
    }
}
```

Desktop side (Python) would need a WebSocket server:

```python
# timeos/server/websocket.py
import asyncio
import websockets

async def handle_client(websocket):
    async for message in websocket:
        command = json.loads(message)
        result = execute_command(command)
        await websocket.send(json.dumps(result))
```

---

## Phase 4: iOS-Specific Features

### 4.1 GPS Clock Source

```swift
class GPSClock: NSObject, ClockSource, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var lastLocation: CLLocation?

    var quality: ClockQuality {
        guard let loc = lastLocation else { return .unavailable }
        return ClockQuality(
            offset: 0,  // GPS is reference
            uncertainty: loc.horizontalAccuracy / C,  // Position uncertainty → time
            stratum: 1
        )
    }
}
```

### 4.2 Home Screen Widgets

```swift
struct ClockOffsetWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "ClockOffset", provider: ClockProvider()) { entry in
            VStack {
                Text("NTP Offset")
                    .font(.caption)
                Text(entry.formattedOffset)
                    .font(.title)
                    .monospacedDigit()
            }
        }
        .configurationDisplayName("Clock Offset")
        .description("Current NTP offset from your best clock source")
        .supportedFamilies([.systemSmall])
    }
}
```

### 4.3 Shortcuts Integration

```swift
struct CheckCausalityIntent: AppIntent {
    static var title: LocalizedStringResource = "Check Causality"

    @Parameter(title: "Event ID")
    var eventId: String

    func perform() async throws -> some IntentResult {
        let status = TimeOSCore.checkCausality(eventId: eventId)
        return .result(dialog: "Causality: \(status)")
    }
}
```

---

## Dependencies (Swift Package Manager)

```swift
// Package.swift
dependencies: [
    .package(url: "https://github.com/groue/GRDB.swift", from: "6.0.0"),
    .package(url: "https://github.com/instacart/TrueTime.swift", from: "5.0.0"),
]
```

---

## Build & Deploy

### Initial Setup (on Mac Mini)

```bash
ssh <your-username>@<your-mac-ip>

# Create project
mkdir -p ~/Development/TimeOSiOS
cd ~/Development/TimeOSiOS

# Initialize Xcode project (or use Xcode GUI)
swift package init --name TimeOSCore --type library

# Open in Xcode
open TimeOSCore.xcodeproj
```

### Build Commands

```bash
# Build for simulator
xcodebuild -scheme TimeOSiOS -destination 'platform=iOS Simulator,name=iPhone 15 Pro'

# Build for device
xcodebuild -scheme TimeOSiOS -destination 'generic/platform=iOS'

# Run tests
xcodebuild test -scheme TimeOSCore -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
```

---

## Migration Checklist

### Core (Python → Swift)

- [ ] `ChronoStamp` struct
- [ ] `TimelineEvent` struct
- [ ] `FourVector` with SIMD
- [ ] `LorentzTransform`
- [ ] `SpacetimeInterval`
- [ ] `LightCone` causality checks
- [ ] `EventLog` with GRDB/SQLite
- [ ] `Timeline` branch management
- [ ] `SystemClock`
- [ ] `NTPClock` (TrueTime)
- [ ] `GPSClock` (CoreLocation)
- [ ] `CompositeClock` (Kalman)
- [ ] `DriftModel`
- [ ] `AllanVariance`
- [ ] `CrossCorrelation`
- [ ] `Resample`

### UI (PySide6 → SwiftUI)

- [ ] Main navigation structure
- [ ] Timeline visualization (Charts)
- [ ] Event log list
- [ ] Clock status panel
- [ ] Drift plot
- [ ] Settings/mode selector
- [ ] Disclaimer dialog
- [ ] Event detail sheet

### Optional

- [ ] WebSocket remote connection
- [ ] Home screen widgets
- [ ] Shortcuts integration
- [ ] Watch complication

---

## Timeline Estimate

| Phase | Scope | Estimate |
|-------|-------|----------|
| Phase 1 | Core Swift Package | 2-3 weeks |
| Phase 2 | SwiftUI App | 2-3 weeks |
| Phase 3 | Remote Connection | 1 week |
| Phase 4 | iOS Features | 1 week |
| **Total** | **MVP** | **6-8 weeks** |

---

## Notes

- All physics runs locally — no network required for core functionality
- GPS clock gives ~10-50ns accuracy on modern iPhones
- `mach_absolute_time()` provides nanosecond monotonic clock
- Charts framework handles uncertainty bands natively
- GRDB is mature, performant SQLite wrapper
- TrueTime library handles NTP with Google/Apple server pools
