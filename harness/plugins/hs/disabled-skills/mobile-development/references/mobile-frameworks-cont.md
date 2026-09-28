# Mobile Frameworks Reference (continued 2/2)

## Native iOS (Swift/SwiftUI)

### Core Concepts

**Swift 6 (2024-2025)**
- Compile-time data race detection
- Enhanced concurrency: async/await, actors, @MainActor
- Powerful macro system
- Move semantics for performance

**SwiftUI vs UIKit**
- **SwiftUI**: Declarative, 40% less code, iOS 13+, modern approach
- **UIKit**: Imperative, fine-grained control, legacy support, complex customizations
- Both work together in same project

### Architecture Patterns

**MVVM (Most Popular)**
```swift
// ViewModel (ObservableObject)
class LoginViewModel: ObservableObject {
    @Published var email = ""
    @Published var password = ""
    @Published var isLoading = false

    func login() async {
        isLoading = true
        // Login logic
        isLoading = false
    }
}

// View
struct LoginView: View {
    @StateObject private var viewModel = LoginViewModel()

    var body: some View {
        VStack {
            TextField("Email", text: $viewModel.email)
            SecureField("Password", text: $viewModel.password)
            Button("Login") {
                Task { await viewModel.login() }
            }
        }
    }
}
```

**TCA (The Composable Architecture)**
- Growing adoption (v1.13+)
- Excellent for complex apps
- Steeper learning curve
- Predictable state management

### When to Choose Native iOS

**✅ Best For:**
- iOS-only applications
- Maximum performance required
- Latest Apple features (WidgetKit, Live Activities, App Clips)
- Deep iOS ecosystem integration
- Team with Swift/iOS expertise

## Native Android (Kotlin/Jetpack Compose)

### Core Concepts

**Kotlin 2.1 (2024-2025)**
- Null safety by design
- Coroutines for async
- Sealed classes for type-safe states
- Extension functions

**Jetpack Compose**
- Declarative UI (like SwiftUI/React)
- 60% adoption in top 1,000 apps
- Material Design 3 integration
- Compose compiler with Kotlin 2.0+

### Architecture Patterns

**MVVM + Clean Architecture**
```kotlin
// ViewModel
class LoginViewModel(
    private val loginUseCase: LoginUseCase
) : ViewModel() {
    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    fun login(email: String, password: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            loginUseCase(email, password)
                .onSuccess { /* Navigate */ }
                .onFailure { /* Show error */ }
            _uiState.update { it.copy(isLoading = false) }
        }
    }
}

// Composable
@Composable
fun LoginScreen(viewModel: LoginViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsState()

    Column {
        TextField(
            value = uiState.email,
            onValueChange = { /* update */ }
        )
        Button(onClick = { viewModel.login() }) {
            Text("Login")
        }
    }
}
```

### When to Choose Native Android

**✅ Best For:**
- Android-only applications
- Maximum performance required
- Material Design 3 implementation
- Deep Android ecosystem integration
- Team with Kotlin/Android expertise

## Framework Comparison Matrix

| Feature | React Native | Flutter | Native iOS | Native Android |
|---------|--------------|---------|------------|----------------|
| **Language** | JavaScript/TS | Dart | Swift | Kotlin |
| **Learning Curve** | Easy | Medium | Medium | Medium |
| **Performance** | 80-90% | 85-95% | 100% | 100% |
| **Hot Reload** | Yes | Yes (fastest) | Previews | Live Edit |
| **Code Sharing** | Web (React) | Web/Desktop | No | No |
| **Community Size** | Huge | Growing | iOS only | Android only |
| **UI Paradigm** | Components | Widgets | Declarative | Declarative |
| **Third-party** | npm (3M+) | pub.dev (23K+) | SPM | Maven |
| **App Size** | 40-50MB | 15-20MB | 10-15MB | 10-15MB |
| **Build Time** | Medium | Fast | Slow (Xcode) | Medium |
| **Debugging** | Chrome/Safari | DevTools | Xcode | Android Studio |
| **Platform Feel** | Needs work | Needs work | Native | Native |
| **Startup Time** | Medium | Fast | Fastest | Fastest |
| **Best For** | JS teams | Performance | iOS-only | Android-only |

## Migration Paths

### React Native → Flutter
- **Effort**: High (complete rewrite)
- **Timeline**: 3-6 months for medium app
- **Benefits**: Better performance, smaller app size
- **Challenges**: New language (Dart), different ecosystem

### Flutter → React Native
- **Effort**: High (complete rewrite)
- **Timeline**: 3-6 months for medium app
- **Benefits**: Larger community, web code sharing
- **Challenges**: Lower performance, larger app size

### Cross-Platform → Native
- **Effort**: Very High (separate iOS and Android apps)
- **Timeline**: 6-12 months for medium app
- **Benefits**: Maximum performance, platform features
- **Challenges**: Maintain two codebases, 2x team size

### Native → Cross-Platform
- **Effort**: High (consolidate to one codebase)
- **Timeline**: 4-8 months for medium app
- **Benefits**: Single codebase, faster development
- **Challenges**: Performance tradeoffs, platform differences

## Decision Framework

### Start Here: Do you need native performance?
- **No** → Cross-platform (React Native or Flutter)
- **Yes** → Native (Swift or Kotlin)

### If Cross-Platform: Does team know JavaScript?
- **Yes** → React Native
- **No** → Flutter

### If Native: iOS-only or Android-only?
- **iOS-only** → Swift/SwiftUI
- **Android-only** → Kotlin/Compose
- **Both** → Reconsider cross-platform

### Additional Factors:
- **Existing codebase**: Use same technology
- **Web app exists**: React Native (code sharing)
- **Desktop needed**: Flutter (multi-platform)
- **Budget constrained**: Cross-platform
- **Performance critical**: Native
- **Complex animations**: Flutter or Native
- **Commercial focus**: React Native (larger market share)

## Resources

**React Native:**
- Official Docs: https://reactnative.dev/
- New Architecture: https://reactnative.dev/docs/the-new-architecture/landing-page
- Expo: https://expo.dev/ (recommended framework)
- Directory: https://reactnative.directory/

**Flutter:**
- Official Docs: https://flutter.dev/
- Pub.dev: https://pub.dev/
- Codelabs: https://flutter.dev/codelabs
- Widget Catalog: https://flutter.dev/widgets

**Native iOS:**
- Swift Docs: https://swift.org/documentation/
- SwiftUI Tutorials: https://developer.apple.com/tutorials/swiftui
- iOS HIG: https://developer.apple.com/design/human-interface-guidelines/

**Native Android:**
- Kotlin Docs: https://kotlinlang.org/docs/home.html
- Compose Docs: https://developer.android.com/jetpack/compose
- Material 3: https://m3.material.io/
- Android Guides: https://developer.android.com/guide
