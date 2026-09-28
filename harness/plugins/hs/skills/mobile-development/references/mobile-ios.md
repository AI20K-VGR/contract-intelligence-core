# iOS Native Development

Guide: iOS dev with Swift/SwiftUI (2024-2025).

## Swift 6 Overview

### Key Features
- **Data race safety**: Compile-time detection (default in Swift 6)
- **Concurrency**: async/await, actors, @MainActor
- **Macro system**: Code generation at compile time
- **Move semantics**: Ownership optimization
- **Enhanced generics**: More powerful type system

### Modern Swift Patterns

**Async/Await:**
```swift
func fetchUser(id: String) async throws -> User {
    let (data, _) = try await URLSession.shared.data(from: url)
    return try JSONDecoder().decode(User.self, from: data)
}

// Usage
Task {
    do {
        let user = try await fetchUser(id: "123")
        self.user = user
    } catch {
        self.error = error
    }
}
```

**Actors (Thread-safe classes):**
```swift
actor UserCache {
    private var cache: [String: User] = [:]

    func get(_ id: String) -> User? {
        cache[id]
    }

    func set(_ id: String, user: User) {
        cache[id] = user
    }
}
```

## SwiftUI vs UIKit

### When to Use SwiftUI
✅ New projects (iOS 13+)
✅ Declarative UI preferred
✅ Fast iteration needed
✅ Cross-platform (macOS, watchOS, tvOS)
✅ 40% less code vs UIKit

### When to Use UIKit
✅ Legacy app maintenance
✅ Complex customizations
✅ Fine-grained control needed
✅ Specific UIKit features required
✅ Pre-iOS 13 support

### SwiftUI Basics

```swift
struct ContentView: View {
    @State private var count = 0

    var body: some View {
        VStack(spacing: 20) {
            Text("Count: \(count)")
                .font(.title)

            Button("Increment") {
                count += 1
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}
```

**Property Wrappers:**
- `@State`: View-local state
- `@Binding`: Two-way binding
- `@StateObject`: Observable object owner
- `@ObservedObject`: Observable object reference
- `@EnvironmentObject`: Dependency injection
- `@Published`: Observable property

## Architecture Patterns

### MVVM (Most Popular)

```swift
// Model
struct User: Identifiable, Codable {
    let id: String
    let name: String
    let email: String
}

// ViewModel
@MainActor
class UserViewModel: ObservableObject {
    @Published var users: [User] = []
    @Published var isLoading = false
    @Published var error: Error?

    private let repository: UserRepository

    init(repository: UserRepository = UserRepository()) {
        self.repository = repository
    }

    func loadUsers() async {
        isLoading = true
        defer { isLoading = false }

        do {
            users = try await repository.fetchUsers()
        } catch {
            self.error = error
        }
    }
}

// View
struct UserListView: View {
    @StateObject private var viewModel = UserViewModel()

    var body: some View {
        List(viewModel.users) { user in
            Text(user.name)
        }
        .task {
            await viewModel.loadUsers()
        }
    }
}
```

### TCA (The Composable Architecture)

**When to use:**
- Complex state management
- Predictable state updates
- Excellent testing
- Enterprise apps

**Trade-offs:**
- Steeper learning curve
- More boilerplate
- Excellent for large teams

## Performance Optimization

### Compiler Optimizations

**1. Use `final` classes:**
```swift
final class FastClass {
    // Compiler can optimize (no dynamic dispatch)
}
```

**2. Private methods:**
```swift
private func optimize() {
    // Compiler can inline
}
```

**3. Whole-module optimization:**
```bash
# Build Settings
SWIFT_WHOLE_MODULE_OPTIMIZATION = YES
```

### Memory Management

**ARC (Automatic Reference Counting):**
```swift
class Parent {
    var child: Child?
}

class Child {
    weak var parent: Parent?  // Weak to avoid retain cycle
}
```

**Common Retain Cycles:**
```swift
// ❌ Bad: Retain cycle
class ViewController: UIViewController {
    var completion: (() -> Void)?

    func setup() {
        completion = {
            self.doSomething()  // Strong capture
        }
    }
}

// ✅ Good: Weak self
class ViewController: UIViewController {
    var completion: (() -> Void)?

    func setup() {
        completion = { [weak self] in
            self?.doSomething()
        }
    }
}
```

### SwiftUI Performance

**1. Use const modifiers:**
```swift
Text("Hello")  // Recreated on every render

vs

Text("Hello")
    .font(.title)  // Modifier creates new view

// Better: Extract static views
let titleText = Text("Hello").font(.title)
```

**2. Avoid expensive computations:**
```swift
struct ExpensiveView: View {
    let data: [Item]

    // Computed every render
    var sortedData: [Item] {
        data.sorted()  // ❌ Bad
    }

    // Better: Cache with @State or pass sorted
}
```


---

Continued in [mobile-ios-cont.md](mobile-ios-cont.md)
