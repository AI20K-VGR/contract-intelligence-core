# Mobile Frameworks Reference

Guide to mobile frameworks: React Native, Flutter, native dev.

## Framework Overview (2024-2025)

### React Native
- **Language**: JavaScript/TypeScript
- **Stars**: 121,000+ on GitHub
- **Adoption**: 35% of mobile developers, 67% familiarity
- **Performance**: 80-90% native performance
- **Architecture**: Bridge-based (legacy) → New Architecture (JSI, Fabric, Codegen)
- **Rendering**: Native components
- **Hot Reload**: Yes
- **Community**: Huge (npm ecosystem, 3M+ downloads/week)

### Flutter
- **Language**: Dart
- **Stars**: 170,000+ on GitHub (fastest-growing)
- **Adoption**: 46% of mobile developers
- **Performance**: 85-95% native performance
- **Architecture**: "Everything is a widget"
- **Rendering**: Custom Impeller rendering engine (eliminates jank)
- **Hot Reload**: Yes (fastest in industry)
- **Community**: Growing rapidly (23,000+ packages on pub.dev)

### Native iOS (Swift/SwiftUI)
- **Language**: Swift
- **Performance**: 100% native
- **UI Framework**: SwiftUI (declarative) or UIKit (imperative)
- **Latest**: Swift 6 with compile-time data race detection
- **Tooling**: Xcode 16, Swift Package Manager
- **Concurrency**: async/await, actors, @MainActor

### Native Android (Kotlin/Jetpack Compose)
- **Language**: Kotlin
- **Performance**: 100% native
- **UI Framework**: Jetpack Compose (declarative) or Views (imperative)
- **Latest**: Kotlin 2.1, Compose 1.7
- **Tooling**: Android Studio Hedgehog+
- **Coroutines**: Kotlin coroutines for async

## React Native Deep Dive

### Core Concepts

**New Architecture (0.82+ Mandatory)**
- **JSI (JavaScript Interface)**: Direct JS-to-native communication, eliminating bridge
- **Fabric**: New rendering system with synchronous layout
- **Codegen**: Static type safety between JS and native code
- **Turbo Modules**: Lazy-loaded native modules

**Performance Optimizations**
- **Hermes Engine**: 30-40% faster startup, reduced memory
- **Native Driver Animations**: Offloaded to UI thread (60 FPS)
- **FlatList Virtualization**: Renders only visible items
- **Image Optimization**: FastImage library, progressive loading

### Best Practices

**Project Structure (Feature-Based)**
```
src/
├── features/
│   ├── auth/
│   ├── profile/
│   └── dashboard/
├── shared/
│   ├── components/
│   ├── hooks/
│   └── utils/
├── navigation/
├── services/
└── stores/
```

**State Management (2024-2025)**
1. **Zustand** (Rising Star): Minimal boilerplate, 3KB, excellent TypeScript
2. **Redux Toolkit**: Enterprise apps, time-travel debugging, DevTools
3. **Recoil**: Meta-built, atom-based, experimental
4. **Context API**: Simple apps, avoid prop drilling

**Navigation**
- **React Navigation**: Industry standard, 80%+ adoption
- Type-safe navigation with TypeScript
- Deep linking configuration
- Tab, stack, drawer navigators

**TypeScript Adoption**
- 85%+ of new React Native projects use TypeScript
- Type safety prevents 15% of runtime errors
- Better IDE support and autocomplete

### Testing Strategy

**Unit Testing**
- **Jest**: Default test runner
- **React Native Testing Library**: Component testing, best practices
- Target: 70-80%+ code coverage

**E2E Testing**
- **Detox**: Gray-box testing, fast, reliable (recommended)
- **Appium**: Cross-platform, WebDriver-based
- **Maestro**: New player, simple YAML-based tests

**Example (React Native Testing Library)**
```javascript
import { render, fireEvent, waitFor } from '@testing-library/react-native';

test('login button should be enabled when form is valid', async () => {
  const { getByTestId } = render(<LoginScreen />);
  const emailInput = getByTestId('email-input');
  const passwordInput = getByTestId('password-input');
  const loginButton = getByTestId('login-button');

  fireEvent.changeText(emailInput, 'test@example.com');
  fireEvent.changeText(passwordInput, 'password123');

  await waitFor(() => {
    expect(loginButton).not.toBeDisabled();
  });
});
```

### When to Choose React Native

**✅ Best For:**
- JavaScript/TypeScript expertise in team
- Code sharing with web (React)
- Rapid prototyping and MVPs
- Strong community support needed
- npm ecosystem integration
- Commercial apps (12.57% market share)

**❌ Not Ideal For:**
- Heavy graphics/gaming (use native or Unity)
- Maximum performance critical
- Deep platform-specific integrations
- Team unfamiliar with JavaScript

## Flutter Deep Dive

### Core Concepts

**"Everything is a Widget"**
- UI built from composable widgets
- Immutable widget tree
- Reactive updates with setState/state management

**Rendering Engine**
- **Impeller**: New rendering engine (iOS stable, Android preview)
- Eliminates shader jank
- 120 FPS capable on capable devices
- Custom Skia-based rendering (full control)

**Performance Features**
- **Const widgets**: Compile-time optimization
- **RepaintBoundary**: Isolate expensive repaints
- **ListView.builder**: Lazy loading for long lists
- **Cached network images**: Image optimization

### Best Practices

**Project Structure (Feature-First)**
```
lib/
├── features/
│   ├── auth/
│   │   ├── data/
│   │   ├── domain/
│   │   └── presentation/
│   └── profile/
├── core/
│   ├── theme/
│   ├── utils/
│   └── widgets/
├── routing/
└── main.dart
```

**State Management (2024-2025)**
1. **Riverpod 3**: Modern, compile-safe, recommended by Flutter team
2. **Bloc**: Enterprise apps, event-driven, predictable state
3. **Provider**: Beginners, simple apps
4. **GetX**: All-in-one (state + routing + DI), opinionated

**Navigation**
- **GoRouter**: Official recommendation (2024+), declarative routing
- Type-safe routes with code generation
- Deep linking built-in
- Replaces Navigator 2.0 for most use cases

**Priority Levels (Official)**
1. **P0**: Fix immediately (crashes, data loss)
2. **P1**: Fix within days (major features broken)
3. **P2**: Fix within weeks (annoyances)
4. **P3**: Nice to have

### Testing Strategy

**Unit Testing**
- **flutter_test**: Built-in testing package
- **Mockito**: Mocking dependencies
- Target: 80%+ code coverage

**Widget Testing**
- **WidgetTester**: Test UI and interactions
- **Golden Tests**: Visual regression testing

**Integration Testing**
- **integration_test**: End-to-end testing
- Run on real devices or emulators

**Example (Widget Testing)**
```dart
testWidgets('Counter increments', (WidgetTester tester) async {
  await tester.pumpWidget(MyApp());

  expect(find.text('0'), findsOneWidget);
  expect(find.text('1'), findsNothing);

  await tester.tap(find.byIcon(Icons.add));
  await tester.pump();

  expect(find.text('0'), findsNothing);
  expect(find.text('1'), findsOneWidget);
});
```

### When to Choose Flutter

**✅ Best For:**
- Performance-critical applications
- Complex animations and custom UI
- Multi-platform (mobile, web, desktop)
- Consistent UI across platforms
- Growing team/startup (fastest development)
- Apps with heavy visual requirements

**❌ Not Ideal For:**
- Team unfamiliar with Dart
- Heavy reliance on native platform features
- Existing large JavaScript/native codebase
- Small app size critical (<20MB)


---

Continued in [mobile-frameworks-cont.md](mobile-frameworks-cont.md)
