# Mobile Debugging Strategies (continued 3/6)

open "rndebugger://set-debugger-loc?host=localhost&port=8081"

# Features:
# - Redux DevTools
# - React DevTools
# - Network Inspector
# - Console
```

**5. Performance Monitor**

```javascript
// Show in-app performance overlay
// Shake device → "Show Perf Monitor"

// Shows:
// - RAM usage
// - JS frame rate
// - UI frame rate
// - Views count
```

**6. LogBox**

```javascript
// Ignore specific warnings
import { LogBox } from 'react-native';

LogBox.ignoreLogs([
  'Warning: componentWillReceiveProps',
]);

// Ignore all logs (NOT recommended)
LogBox.ignoreAllLogs();
```

### Flutter Debugging

**1. DevTools**

```bash
# Launch from VS Code
# Debug → Open DevTools

# Or from command line
flutter pub global activate devtools
flutter pub global run devtools

# Features:
# - Widget inspector
# - Timeline view
# - Memory profiler
# - Network profiler
# - Logging view
```

**2. Widget Inspector**

```dart
// In DevTools: Inspector tab

// Debug paint (show layout borders)
// Ctrl+Shift+P → "Toggle Debug Painting"

// Print widget tree
debugDumpApp();

// Print render tree
debugDumpRenderTree();

// Print layer tree
debugDumpLayerTree();
```

**3. Performance Overlay**

```dart
void main() {
  runApp(
    MaterialApp(
      showPerformanceOverlay: true, // FPS counter
      debugShowCheckedModeBanner: false,
      home: MyApp(),
    ),
  );
}
```

**4. Logging**

```dart
import 'dart:developer' as developer;

// Simple print
print('User ID: $userId');

// Structured logging
developer.log(
  'User logged in',
  name: 'app.auth',
  error: error,
  stackTrace: stackTrace,
);

// Timeline events
developer.Timeline.startSync('fetchUsers');
await fetchUsers();
developer.Timeline.finishSync();
```

**5. Breakpoint Debugging**

```dart
// Set breakpoints in VS Code or Android Studio
Future<User> fetchUser(String id) async {
  // Breakpoint here
  final response = await http.get(Uri.parse('https://api.example.com/users/$id'));

  // Debugger console commands:
  // p variable - print variable
  // Step over: F10
  // Step into: F11
  // Continue: F5
  return User.fromJson(jsonDecode(response.body));
}
```

## UI Debugging

### Layout Issues

**iOS (SwiftUI):**
```swift
struct ContentView: View {
    var body: some View {
        VStack {
            Text("Hello")
        }
        .border(Color.red) // Debug border
        .background(Color.yellow.opacity(0.3)) // Debug background
    }
}

// Print layout info
Text("Hello")
    .onAppear {
        print("Frame: \(UIScreen.main.bounds)")
    }
```

**Android (Jetpack Compose):**
```kotlin
@Composable
fun DebugLayout() {
    Column(
        modifier = Modifier
            .border(2.dp, Color.Red) // Debug border
            .background(Color.Yellow.copy(alpha = 0.3f)) // Debug background
    ) {
        Text("Hello")
    }
}

// Show layout bounds in developer options
// Settings → Developer Options → Show layout bounds
```

**React Native:**
```javascript
// Debug borders
<View style={{ borderWidth: 1, borderColor: 'red' }}>
  <Text>Hello</Text>
</View>

// Layout animation debugging
import { LayoutAnimation, UIManager } from 'react-native';

UIManager.setLayoutAnimationEnabledExperimental &&
  UIManager.setLayoutAnimationEnabledExperimental(true);

// Inspector
// Shake device → "Toggle Inspector"
// Shows element hierarchy and styles
```

**Flutter:**
```dart
// Debug paint
void main() {
  debugPaintSizeEnabled = true; // Show layout guides
  debugPaintBaselinesEnabled = true; // Show text baselines
  debugPaintLayerBordersEnabled = true; // Show layer borders
  runApp(MyApp());
}

// Widget boundaries
Container(
  decoration: BoxDecoration(
    border: Border.all(color: Colors.red, width: 2),
  ),
  child: Text('Hello'),
)
```

### Animation Debugging

**Slow Animations:**
```dart
// Flutter: Slow down animations
timeDilation = 5.0; // 5x slower

// React Native: Slow animations
import { Animated } from 'react-native';
Animated.timing(value, {
  toValue: 1,
  duration: 3000, // Increase duration
});
```

**Animation Performance:**
```swift
// iOS: Core Animation Instrument
// Instruments → Core Animation
// Check for:
// - Dropped frames
// - Off-screen rendering
// - Blending layers
```


---

Continued in [mobile-debugging-cont3.md](mobile-debugging-cont3.md)
