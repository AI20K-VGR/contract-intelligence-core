# Mobile Development Playbook (2024-2025)

Quick-reference: performance targets, decision matrices, checklists, platform guidelines for mobile builds. Companion detail for core `mobile-development` skill.

## Key Best Practices (2024-2025)

**Performance Targets:**
- App launch: <2 seconds (70% abandon if >3s)
- Memory usage: <100MB for typical screens
- Network requests: Batch and cache aggressively
- Battery impact: Respect Doze Mode and background restrictions
- Animation: 60 FPS (16.67ms per frame)

**Architecture:**
- MVVM for small-medium apps (clean separation, testable)
- MVVM + Clean Architecture for large enterprise apps
- Offline-first with hybrid sync (push + pull)
- State management: Zustand (React Native), Riverpod 3 (Flutter), StateFlow (Android)

**Security (OWASP Mobile Top 10):**
- OAuth 2.0 + JWT + Biometrics for authentication
- Keychain (iOS) / KeyStore (Android) for sensitive data
- Certificate pinning for network security
- Never hardcode credentials or API keys
- Implement proper session management

**Testing Strategy:**
- Unit tests: 70%+ coverage for business logic
- Integration tests: Critical user flows
- E2E tests: Detox (React Native), Appium (cross-platform), XCUITest (iOS), Espresso (Android)
- Real device testing mandatory before release

**Deployment:**
- Fastlane for automation across platforms
- Staged rollouts: Internal → Closed → Open → Production
- Mandatory: iOS 17 SDK (2024), Android 15 API 35 (Aug 2025)
- CI/CD saves 20% development time

## Quick Decision Matrix

| Need | Choose |
|------|--------|
| JavaScript team, web code sharing | React Native |
| Performance-critical, complex animations | Flutter |
| Maximum iOS performance, latest features | Swift/SwiftUI native |
| Maximum Android performance, Material 3 | Kotlin/Compose native |
| Rapid prototyping | React Native + Expo |
| Desktop + mobile | Flutter |
| Enterprise with JavaScript skills | React Native |
| Startup with limited resources | Flutter or React Native |
| Gaming or heavy graphics | Native (Swift/Kotlin) or Unity |

## Framework Quick Comparison (2024-2025)

| Criterion | React Native | Flutter | Swift/SwiftUI | Kotlin/Compose |
|-----------|--------------|---------|---------------|----------------|
| **Stars** | 121K | 170K | N/A | N/A |
| **Adoption** | 35% | 46% | iOS only | Android only |
| **Performance** | 80-90% native | 85-95% native | 100% native | 100% native |
| **Dev Speed** | Fast (hot reload) | Very fast (hot reload) | Fast (Xcode Previews) | Fast (Live Edit) |
| **Learning Curve** | Easy (JavaScript) | Medium (Dart) | Medium (Swift) | Medium (Kotlin) |
| **UI Paradigm** | Component-based | Widget-based | Declarative | Declarative |
| **Community** | Huge (npm) | Growing | Apple ecosystem | Android ecosystem |
| **Best For** | JS teams, web sharing | Performance, animations | iOS-only apps | Android-only apps |

## Implementation Checklist

**Project Setup:**
- Choose framework → Initialize project → Configure dev environment → Setup version control → Configure CI/CD → Team standards

**Architecture:**
- Choose pattern (MVVM/Clean) → Setup folders → State management → Navigation → API layer → Error handling → Logging

**Core Features:**
- Authentication → Data persistence → API integration → Offline sync → Push notifications → Deep linking → Analytics

**UI/UX:**
- Design system → Platform guidelines → Accessibility → Responsive layouts → Dark mode → Localization → Animations

**Performance:**
- Image optimization → Lazy loading → Memory profiling → Network optimization → Battery testing → Launch time optimization

**Quality:**
- Unit tests (70%+) → Integration tests → E2E tests → Accessibility testing → Performance testing → Security audit

**Security:**
- Secure storage → Authentication flow → Network security → Input validation → Session management → Encryption

**Deployment:**
- App icons/splash → Screenshots → Store listings → Privacy policy → TestFlight/Internal testing → Staged rollout → Monitoring

## Platform-Specific Guidelines

**iOS (Human Interface Guidelines):**
- Native navigation patterns (tab bar, navigation bar)
- iOS design patterns (pull to refresh, swipe actions)
- San Francisco font, iOS color system
- Haptic feedback, 3D Touch/Haptic Touch
- Respect safe areas and notch

**Android (Material Design 3):**
- Material navigation (bottom nav, navigation drawer)
- Floating action buttons, material components
- Roboto font, Material You dynamic colors
- Touch feedback (ripple effects)
- Respect system bars and gestures

## Common Pitfalls to Avoid

1. **Testing only on simulators** - Real devices show true performance
2. **Ignoring platform conventions** - Users expect platform-specific patterns
3. **No offline handling** - Network failures will happen
4. **Poor memory management** - Leads to crashes and poor UX
5. **Hardcoded credentials** - Security vulnerability
6. **No accessibility** - Excludes 15%+ of users
7. **Premature optimization** - Optimize based on metrics, not assumptions
8. **Over-engineering** - Start simple, scale as needed
9. **Skipping real device testing** - Simulators don't show battery/network issues
10. **Not respecting battery** - Background processing must be justified

## Performance Budgets

**Recommended Targets:**
- **App size**: <50MB initial download, <200MB total
- **Launch time**: <2 seconds to interactive
- **Screen load**: <1 second for cached data
- **Network request**: <3 seconds for API calls
- **Memory**: <100MB for typical screens, <200MB peak
- **Battery**: <5% drain per hour of active use
- **Frame rate**: 60 FPS (16.67ms per frame)
