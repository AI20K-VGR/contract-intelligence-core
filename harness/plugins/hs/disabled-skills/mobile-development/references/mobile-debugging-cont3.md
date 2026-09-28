# Mobile Debugging Strategies (continued 4/6)

## Performance Debugging

### Frame Rate Issues (< 60 FPS)

**Diagnosis:**

**React Native:**
```javascript
// Enable performance monitor
// Shows JS and UI thread FPS

// Common issues:
// 1. Heavy computations in render
// 2. Large lists without virtualization
// 3. Unnecessary re-renders
```

**Solutions:**
```javascript
// ❌ Bad: Heavy computation in render
function UserList({ users }) {
  const sortedUsers = users.sort((a, b) => a.name.localeCompare(b.name));
  return <FlatList data={sortedUsers} />;
}

// ✅ Good: Memoize expensive operations
function UserList({ users }) {
  const sortedUsers = useMemo(
    () => users.sort((a, b) => a.name.localeCompare(b.name)),
    [users]
  );
  return <FlatList data={sortedUsers} />;
}

// ❌ Bad: ScrollView with large data
<ScrollView>
  {users.map(user => <UserCard key={user.id} user={user} />)}
</ScrollView>

// ✅ Good: FlatList with virtualization
<FlatList
  data={users}
  renderItem={({ item }) => <UserCard user={item} />}
  keyExtractor={item => item.id}
  windowSize={5}
  initialNumToRender={10}
/>
```

**Flutter:**
```dart
// Check for:
// - Build phase too long
// - Layout phase too long
// - Paint phase too long

// Use const constructors
// ❌ Bad
Widget build(BuildContext context) {
  return Container(child: Text('Hello'));
}

// ✅ Good
Widget build(BuildContext context) {
  return const Text('Hello');
}

// Avoid expensive builds
// Use keys for stateful widgets
ListView.builder(
  itemBuilder: (context, index) {
    return UserCard(
      key: ValueKey(users[index].id), // Preserve state
      user: users[index],
    );
  },
)
```

### Memory Issues

**Detection:**

**iOS:**
```
Xcode → Debug Navigator → Memory
- Watch memory graph
- Look for continuous growth
```

**Android:**
```
Android Studio → Profiler → Memory
- Take heap dump
- Analyze retained objects
```

**Common Causes:**

```javascript
// React Native: Memory leaks

// ❌ Bad: Event listener not removed
useEffect(() => {
  EventEmitter.on('data', handleData);
  // Missing cleanup
}, []);

// ✅ Good: Cleanup
useEffect(() => {
  EventEmitter.on('data', handleData);
  return () => {
    EventEmitter.off('data', handleData);
  };
}, []);

// ❌ Bad: Timer not cleared
useEffect(() => {
  setInterval(() => {
    console.log('tick');
  }, 1000);
}, []);

// ✅ Good: Clear timer
useEffect(() => {
  const timer = setInterval(() => {
    console.log('tick');
  }, 1000);
  return () => clearInterval(timer);
}, []);
```

```dart
// Flutter: Dispose controllers
class MyWidget extends StatefulWidget {
  @override
  _MyWidgetState createState() => _MyWidgetState();
}

class _MyWidgetState extends State<MyWidget> {
  late TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
  }

  @override
  void dispose() {
    _controller.dispose(); // Must dispose
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return TextField(controller: _controller);
  }
}
```

## Network Debugging

### HTTP Debugging

**iOS (Proxyman / Charles)**
```
1. Install Proxyman (free) or Charles
2. Configure device proxy
3. Install SSL certificate
4. View all HTTP traffic
```

**Android (Charles / Flipper)**
```
1. Install Charles Proxy
2. Configure device proxy: Settings → WiFi → Modify → Proxy
3. Install Charles certificate
4. View all HTTP requests/responses
```

**React Native (Flipper Network Plugin)**
```javascript
// Automatically captures all fetch/axios requests
fetch('https://api.example.com/users')
  .then(res => res.json())
  .then(data => console.log(data));

// View in Flipper:
// - Request/response headers
// - Request/response body
// - Timing information
```

**Flutter (DevTools Network Tab)**
```dart
// Automatically captures HTTP requests
final response = await http.get(
  Uri.parse('https://api.example.com/users')
);

// View in DevTools Network tab:
// - All HTTP requests
// - Headers and body
// - Response times
```

### Network Simulation

**Test scenarios:**
- Slow network (3G, 2G)
- High latency (500ms+)
- Packet loss (10%)
- Offline mode

**iOS:**
```
Settings → Developer → Network Link Conditioner
```

**Android:**
```
Emulator: Settings → Network → Network Profile
```


---

Continued in [mobile-debugging-cont4.md](mobile-debugging-cont4.md)
