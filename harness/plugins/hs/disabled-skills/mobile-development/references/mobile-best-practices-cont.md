# Mobile Development Best Practices (continued 2/2)

## Push Notifications Best Practices

### Platforms
- **iOS**: APNs (Apple Push Notification service)
- **Android**: FCM (Firebase Cloud Messaging)
- **Cross-platform**: OneSignal, Firebase, AWS SNS

### Best Practices

**1. Permission Request Strategy**
```
❌ Bad: Request permission on app launch
✅ Good: Request after user sees value

Flow:
1. User interacts with feature
2. Show custom modal explaining benefits
3. Request system permission
4. Handle denial gracefully
```

**2. Personalization**
- Segment users by behavior
- Send at optimal times (time zones)
- Personalize content
- A/B test messaging

**3. Frequency**
- Avoid notification spam
- Respect user preferences
- Implement quiet hours
- Group related notifications

**4. Deep Linking**
```javascript
// React Native
import messaging from '@react-native-firebase/messaging';

messaging().onNotificationOpenedApp(remoteMessage => {
  const { screen, params } = remoteMessage.data;
  navigation.navigate(screen, params);
});
```

**Impact:**
- 25% revenue increase with proper personalization
- 88% opt-in rate with pre-permission modal (vs 40% without)

## Authentication & Authorization

### Modern Auth Stack (2024-2025)

**Standard Pattern:**
```
OAuth 2.0 (Authorization)
├─ JWT (Stateless auth tokens)
├─ Refresh tokens (Long-term access)
└─ Biometric (Convenient re-auth)
```

### Implementation

**Biometric Authentication (iOS)**
```swift
import LocalAuthentication

let context = LAContext()
var error: NSError?

if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
    context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics,
                          localizedReason: "Unlock your account") { success, error in
        if success {
            // Authenticated
        }
    }
}
```

**Biometric Authentication (Android)**
```kotlin
import androidx.biometric.BiometricPrompt

val promptInfo = BiometricPrompt.PromptInfo.Builder()
    .setTitle("Biometric login")
    .setSubtitle("Log in using your biometric credential")
    .setNegativeButtonText("Use account password")
    .build()

val biometricPrompt = BiometricPrompt(this, executor,
    object : BiometricPrompt.AuthenticationCallback() {
        override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
            // Authenticated
        }
    })

biometricPrompt.authenticate(promptInfo)
```

### Secure Token Storage

**iOS: Keychain**
```swift
import Security

func saveToken(_ token: String, for key: String) {
    let data = token.data(using: .utf8)!
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrAccount as String: key,
        kSecValueData as String: data,
        kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
    ]
    SecItemAdd(query as CFDictionary, nil)
}
```

**Android: EncryptedSharedPreferences**
```kotlin
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

val masterKey = MasterKey.Builder(context)
    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
    .build()

val sharedPreferences = EncryptedSharedPreferences.create(
    context,
    "secure_prefs",
    masterKey,
    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
)

sharedPreferences.edit().putString("auth_token", token).apply()
```

**React Native: react-native-keychain**
```javascript
import * as Keychain from 'react-native-keychain';

// Save credentials
await Keychain.setGenericPassword('username', token, {
  accessControl: Keychain.ACCESS_CONTROL.BIOMETRY_CURRENT_SET,
  accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
});

// Retrieve credentials
const credentials = await Keychain.getGenericPassword();
const token = credentials.password;
```

## App Store Deployment

### App Store (iOS)

**Requirements (2024-2025):**
- Xcode 15+ with iOS 17 SDK (minimum)
- Xcode 16+ with iOS 18 SDK (recommended for 2025)
- Privacy manifest required
- Account deletion in-app mandatory

**Release Process:**
1. Archive in Xcode
2. Upload to App Store Connect
3. Submit for review
4. Phased release (7-day rollout)

**Review Time:**
- Average: 1-2 days
- Expedited: 1-2 hours (emergencies only)

**Rejection Reasons:**
- Crashes (50%)
- Privacy violations (25%)
- Incomplete information (15%)
- Guideline violations (10%)

### Google Play (Android)

**Requirements (2024-2025):**
- Target Android 14 (API 34) now
- Target Android 15 (API 35) by Aug 31, 2025
- Privacy policy required
- Data safety form required

**Release Process:**
1. Build signed AAB (Android App Bundle)
2. Upload to Play Console
3. Submit to production track
4. Staged rollout (10% → 50% → 100%)

**Review Time:**
- Average: 1-3 days
- Updates: 1-2 days

### Staged Rollout Strategy

**Week 1:**
- 10% of users
- Monitor crash-free rate
- Watch for critical bugs

**Week 2:**
- 50% of users
- Validate performance metrics
- Check user feedback

**Week 3:**
- 100% of users
- Full release if metrics healthy

**Rollback Triggers:**
- Crash-free rate drops >5%
- Critical bug discovered
- Major user complaints

## Cross-Platform Comparison

### Flutter vs React Native (2024-2025)

| Metric | React Native | Flutter |
|--------|--------------|---------|
| **Adoption** | 35% | 46% |
| **Performance** | 80-90% | 85-95% |
| **App Size** | 40-50MB | 15-20MB |
| **Dev Speed** | Fast | Very Fast |
| **Commercial** | 12.57% | 5.24% |
| **Developers** | 20:1 ratio | 1 ratio |
| **Best For** | JS teams | Performance |

### Architecture Comparison

**MVVM (Small Apps):**
```
View
 ↓
ViewModel (business logic)
 ↓
Model (data)
```

**Clean Architecture (Large Apps):**
```
Presentation (UI)
 ↓
Domain (business logic, use cases)
 ↓
Data (repositories, APIs, DB)
```

## Resources

**Performance:**
- iOS: https://developer.apple.com/documentation/xcode/improving-your-app-s-performance
- Android: https://developer.android.com/topic/performance
- React Native: https://reactnative.dev/docs/performance

**Analytics:**
- Firebase: https://firebase.google.com/docs/analytics
- Sentry: https://docs.sentry.io/platforms/react-native/
- Amplitude: https://amplitude.com/docs

**Security:**
- OWASP Mobile: https://owasp.org/www-project-mobile-top-10/
- iOS Security: https://support.apple.com/guide/security/
- Android Security: https://source.android.com/docs/security

**Testing:**
- Detox: https://wix.github.io/Detox/
- Appium: https://appium.io/docs/en/latest/
- XCTest: https://developer.apple.com/documentation/xctest
- Espresso: https://developer.android.com/training/testing/espresso
