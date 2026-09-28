---
name: hs:mobile-development
injectable: true
description: Build mobile apps with React Native, Flutter, Swift/SwiftUI, Kotlin/Jetpack Compose. Use for iOS/Android, mobile UX, performance optimization, offline-first, app store deployment.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch]
argument-hint: "[platform] [feature]"
metadata:
  compliance-tier: knowledge
---

# Mobile Development Skill

Production-ready mobile development: modern frameworks, best practices, mobile-first thinking patterns.

## When to Use

- Building mobile applications (iOS, Android, or cross-platform)
- Implementing mobile-first design and UX patterns
- Optimizing for mobile constraints (battery, memory, network, small screens)
- Making native vs cross-platform technology decisions
- Implementing offline-first architecture and data sync
- Following platform-specific guidelines (iOS HIG, Material Design)
- Optimizing mobile app performance and user experience
- Implementing mobile security and authentication
- Testing mobile applications (unit, integration, E2E)
- Deploying to App Store and Google Play

## Technology Selection Guide

**Cross-Platform Frameworks:**
- **React Native**: JavaScript expertise, web code sharing, mature ecosystem (121K stars, 67% familiarity)
- **Flutter**: Performance-critical apps, complex animations, fastest-growing (170K stars, 46% adoption)

**Native Development:**
- **iOS (Swift/SwiftUI)**: Maximum iOS performance, latest features, Apple ecosystem integration
- **Android (Kotlin/Jetpack Compose)**: Maximum Android performance, Material Design 3, platform optimization

## Mobile Development Mindset

10 mobile-dev principles (performance-first, offline-first, platform-aware, test-on-real-devices, etc.) — see `references/mobile-mindset.md` for full list (Reality/Mindset/Action).

## Reference Navigation

**Core Technologies:**
- `references/mobile-frameworks.md` - React Native, Flutter, Swift, Kotlin, framework comparison matrices, when to use each
- `mobile-ios.md` - Swift 6, SwiftUI, iOS architecture patterns, HIG, App Store requirements, platform capabilities
- `mobile-android.md` - Kotlin, Jetpack Compose, Material Design 3, Play Store, Android-specific features

**Best Practices & Development Mindset:**
- `mobile-best-practices.md` - Mobile-first design, performance optimization, offline-first architecture, security, testing, accessibility, deployment, analytics
- `mobile-debugging.md` - Debugging tools, performance profiling, crash analysis, network debugging, platform-specific debugging
- `mobile-mindset.md` - Thinking patterns, decision frameworks, platform-specific thinking, common pitfalls, debugging strategies
- `mobile-playbook.md` - Performance targets, architecture/security/testing/deployment practices, decision matrices, framework comparison, implementation checklist, platform guidelines, pitfalls, budgets

## Resources

**Official Documentation:**
- React Native: https://reactnative.dev/
- Flutter: https://flutter.dev/
- iOS HIG: https://developer.apple.com/design/human-interface-guidelines/
- Material Design: https://m3.material.io/
- OWASP Mobile: https://owasp.org/www-project-mobile-top-10/

**Tools & Testing:**
- Detox E2E: https://wix.github.io/Detox/
- Appium: https://appium.io/
- Fastlane: https://fastlane.tools/
- Firebase: https://firebase.google.com/

**Community:**
- React Native Directory: https://reactnative.directory/
- Pub.dev (Flutter packages): https://pub.dev/
- Awesome React Native: https://github.com/jondot/awesome-react-native
- Awesome Flutter: https://github.com/Solido/awesome-flutter
