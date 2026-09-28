# Mobile Debugging Strategies (continued 5/6)

## Crash Debugging

### Crash Reporting Services

**Firebase Crashlytics (Recommended)**

**React Native:**
```javascript
import crashlytics from '@react-native-firebase/crashlytics';

// Log custom events
crashlytics().log('User pressed purchase button');

// Set user identifier
crashlytics().setUserId(userId);

// Record non-fatal error
try {
  await fetchData();
} catch (error) {
  crashlytics().recordError(error);
}

// Force crash for testing
crashlytics().crash();
```

**Flutter:**
```dart
import 'package:firebase_crashlytics/firebase_crashlytics.dart';

// Catch errors
FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterError;

// Catch async errors
runZonedGuarded(() {
  runApp(MyApp());
}, (error, stackTrace) {
  FirebaseCrashlytics.instance.recordError(error, stackTrace);
});

// Log custom events
FirebaseCrashlytics.instance.log('User pressed purchase');

// Set user ID
FirebaseCrashlytics.instance.setUserIdentifier(userId);
```

**iOS Native:**
```swift
import FirebaseCrashlytics

// Log event
Crashlytics.crashlytics().log("User tapped button")

// Set user ID
Crashlytics.crashlytics().setUserID(userId)

// Record error
Crashlytics.crashlytics().record(error: error)
```

**Android Native:**
```kotlin
import com.google.firebase.crashlytics.FirebaseCrashlytics

// Log event
FirebaseCrashlytics.getInstance().log("User tapped button")

// Set user ID
FirebaseCrashlytics.getInstance().setUserId(userId)

// Record exception
FirebaseCrashlytics.getInstance().recordException(exception)
```

### Analyzing Crash Reports

**iOS (Xcode Organizer):**
```
Window → Organizer → Crashes
- Symbolicated crash logs
- Stack traces
- Crash counts
```

**Android (Play Console):**
```
Play Console → Quality → Crashes & ANRs
- Crash stack traces
- Affected devices
- OS versions
```

**Reading Stack Traces:**
```
Fatal Exception: java.lang.NullPointerException
Attempt to invoke virtual method 'java.lang.String User.getName()' on a null object reference
    at com.example.app.UserService.displayUser(UserService.kt:42)
    at com.example.app.MainActivity.onCreate(MainActivity.kt:23)

Fix:
1. Check line UserService.kt:42
2. User object is null
3. Add null check before accessing getName()
```

## Common Debugging Scenarios

### 1. App Crashes on Startup

**Steps:**
1. Check crash logs
2. Look for initialization errors
3. Verify dependencies loaded
4. Check permissions

**Example:**
```javascript
// React Native: Missing native dependency
// Error: Invariant Violation: Native module cannot be null

// Fix: Link native module
npx react-native link <module-name>
# or
cd ios && pod install
```

### 2. UI Not Updating

**React Native:**
```javascript
// ❌ Bad: Mutating state directly
this.state.users.push(newUser); // Won't trigger re-render

// ✅ Good: Create new state
this.setState({ users: [...this.state.users, newUser] });
```

**Flutter:**
```dart
// ❌ Bad: Not calling setState
void addUser(User user) {
  users.add(user); // Won't rebuild
}

// ✅ Good: Call setState
void addUser(User user) {
  setState(() {
    users.add(user);
  });
}
```

### 3. Image Not Loading

**Common causes:**
1. Wrong URL
2. CORS issues
3. SSL certificate issues
4. Network timeout

**Debugging:**
```javascript
// React Native
<Image
  source={{ uri: imageUrl }}
  onError={(error) => console.log('Image error:', error)}
  onLoad={() => console.log('Image loaded')}
/>

// Check network tab for 404, 403, etc.
```

### 4. Keyboard Covering Input

**React Native:**
```javascript
import { KeyboardAvoidingView } from 'react-native';

<KeyboardAvoidingView
  behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
  style={{ flex: 1 }}
>
  <TextInput placeholder="Email" />
</KeyboardAvoidingView>
```

**Flutter:**
```dart
// Automatically handled by Scaffold
Scaffold(
  resizeToAvoidBottomInset: true, // Default
  body: TextField(),
)
```

### 5. Navigation Not Working

**React Navigation:**
```javascript
// ❌ Bad: Navigation prop not available
function MyComponent() {
  navigation.navigate('Home'); // Error
}

// ✅ Good: Use hook or prop
function MyComponent({ navigation }) {
  // or
  // const navigation = useNavigation();

  navigation.navigate('Home');
}
```

## Production Debugging

### Remote Logging

**LogRocket (Session Replay)**
```javascript
import LogRocket from '@logrocket/react-native';

LogRocket.init('your-app-id');

// Identify users
LogRocket.identify(userId, {
  name: user.name,
  email: user.email,
});

// Replays user sessions with:
// - Console logs
// - Network requests
// - UI interactions
// - Redux actions
```

### Feature Flags for Debugging

```javascript
import { useFlags } from 'launchdarkly-react-native-client-sdk';

function MyComponent() {
  const { debugMode } = useFlags();

  if (debugMode) {
    console.log('Debug info:', userData);
  }

  return <View>...</View>;
}

// Enable debug mode remotely for specific users
```

### A/B Testing for Bug Investigation

```javascript
// Gradually roll out fix
if (abTest.variant === 'fixed') {
  return <FixedComponent />;
} else {
  return <OriginalComponent />;
}

// Monitor crash rates per variant
```


---

Continued in [mobile-debugging-cont5.md](mobile-debugging-cont5.md)
