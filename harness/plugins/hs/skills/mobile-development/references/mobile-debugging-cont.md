# Mobile Debugging Strategies (continued 2/6)

## Platform-Specific Debugging Tools

### iOS Debugging

**1. Xcode Debugger**

```swift
// Breakpoint debugging
func fetchUserData(userId: String) {
    // Set breakpoint here
    let url = URL(string: "https://api.example.com/users/\(userId)")!

    // LLDB commands:
    // po userId - print object
    // p url - print variable
    // bt - backtrace
    // c - continue
    // step - step into
    // next - step over
}
```

**LLDB Advanced Commands:**
```bash
# Conditional breakpoint
breakpoint set --name fetchUserData --condition userId == "123"

# Watchpoint (break on value change)
watchpoint set variable self.counter

# Print view hierarchy
po UIApplication.shared.keyWindow?.value(forKey: "recursiveDescription")

# Print all properties
po self.value(forKey: "description")
```

**2. Instruments (Performance Profiling)**

**Time Profiler** - CPU usage
```
1. Xcode → Product → Profile
2. Select "Time Profiler"
3. Record while using app
4. Identify hot methods (high self time)
```

**Allocations** - Memory usage
```
1. Select "Allocations" instrument
2. Look for memory growth
3. Filter by object type
4. Find allocation stack trace
```

**Leaks** - Memory leaks
```
1. Select "Leaks" instrument
2. Leaks shown in red
3. Click leak for stack trace
4. Fix retain cycles
```

**Network** - API debugging
```
1. Select "Network" instrument
2. See all HTTP requests
3. Response times, sizes
4. Failed requests highlighted
```

**3. View Debugging**

```swift
// View hierarchy in Xcode
// Debug → View Debugging → Capture View Hierarchy

// Runtime inspection
#if DEBUG
import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack {
            Text("Hello")
        }
        .onAppear {
            // Print view tree for debugging
            print(Mirror(reflecting: self.body))
        }
    }
}
#endif
```

**4. Console.app (System Logs)**

```bash
# Filter logs by process
log stream --predicate 'processImagePath contains "YourApp"' --level debug

# Filter by subsystem
log stream --predicate 'subsystem == "com.yourcompany.yourapp"'

# Show only errors
log stream --predicate 'processImagePath contains "YourApp"' --level error
```

**5. Network Link Conditioner**

```
Settings → Developer → Network Link Conditioner

Simulate:
- 3G, LTE, WiFi
- High latency
- Packet loss
- Bandwidth limits
```

### Android Debugging

**1. Android Studio Debugger**

```kotlin
// Breakpoint debugging
fun fetchUserData(userId: String) {
    // Set breakpoint here
    val url = "https://api.example.com/users/$userId"

    // Debugger commands:
    // Evaluate expression: Alt+F8 (Windows) / Cmd+F8 (Mac)
    // Step over: F8
    // Step into: F7
    // Resume: F9
}
```

**Advanced Debugger Features:**
```kotlin
// Conditional breakpoint
// Right-click breakpoint → Condition: userId == "123"

// Logpoint (log without stopping)
// Right-click breakpoint → More → Check "Evaluate and log"

// Exception breakpoint
// Run → View Breakpoints → + → Java Exception Breakpoints
```

**2. Android Profiler**

**CPU Profiler:**
```
View → Tool Windows → Profiler → CPU
- Record trace
- Identify slow methods
- Flame chart shows call hierarchy
```

**Memory Profiler:**
```
View → Tool Windows → Profiler → Memory
- Track allocations
- Heap dump analysis
- Find memory leaks
```

**Network Profiler:**
```
View → Tool Windows → Profiler → Network
- All HTTP requests
- Request/response details
- Timeline view
```

**3. Layout Inspector**

```
Tools → Layout Inspector

Features:
- 3D view hierarchy
- Live layout updates
- View properties
- Constraints visualization
```

**4. ADB (Android Debug Bridge)**

```bash
# View device logs
adb logcat

# Filter by app
adb logcat | grep com.yourcompany.yourapp

# Filter by tag
adb logcat MyTag:D *:S

# Clear logs
adb logcat -c

# Install APK
adb install app-debug.apk

# Uninstall app
adb uninstall com.yourcompany.yourapp

# Take screenshot
adb shell screencap -p /sdcard/screenshot.png
adb pull /sdcard/screenshot.png

# Screen recording
adb shell screenrecord /sdcard/demo.mp4
adb pull /sdcard/demo.mp4
```

**5. Network Simulation**

```bash
# Emulator network throttling
# Settings → Network → Network Profile

# Or via ADB
adb shell setprop net.dns1 8.8.8.8
```

### React Native Debugging

**1. React DevTools**

```bash
# Install
npm install -g react-devtools

# Launch
react-devtools

# In app: Shake device → "Debug with React DevTools"
```

**2. Flipper (Recommended)**

```bash
# Install
npm install -g flipper

# Configure in app
# Add flipper packages to your app
npm install --save-dev react-native-flipper

# Features:
# - Layout inspector
# - Network inspector
# - Redux DevTools
# - Database viewer
# - Shared Preferences viewer
```

**3. Chrome DevTools**

```javascript
// In app: Shake device → "Debug"
// Opens Chrome DevTools

// Console.log appears in Chrome
console.log('User data:', userData);

// Set breakpoints in source code
debugger; // Pauses execution

// Network tab shows API calls
fetch('https://api.example.com/users')
  .then(res => res.json())
  .then(data => console.log(data));
```

**4. React Native Debugger (Standalone)**

```bash
# Install
brew install --cask react-native-debugger

# Launch

---

Continued in [mobile-debugging-cont2.md](mobile-debugging-cont2.md)
