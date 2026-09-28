# iOS Native Development (continued 2/2)

## Testing Strategies

### XCTest (Unit Testing)

```swift
import XCTest
@testable import MyApp

final class UserViewModelTests: XCTestCase {
    var viewModel: UserViewModel!
    var mockRepository: MockUserRepository!

    override func setUp() {
        super.setUp()
        mockRepository = MockUserRepository()
        viewModel = UserViewModel(repository: mockRepository)
    }

    func testLoadUsers() async throws {
        // Given
        let expectedUsers = [User(id: "1", name: "Test", email: "test@example.com")]
        mockRepository.usersToReturn = expectedUsers

        // When
        await viewModel.loadUsers()

        // Then
        XCTAssertEqual(viewModel.users, expectedUsers)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.error)
    }
}
```

### XCUITest (UI Testing)

```swift
import XCTest

final class LoginUITests: XCTestCase {
    let app = XCUIApplication()

    override func setUp() {
        super.setUp()
        app.launch()
    }

    func testLoginFlow() {
        let emailField = app.textFields["emailField"]
        emailField.tap()
        emailField.typeText("test@example.com")

        let passwordField = app.secureTextFields["passwordField"]
        passwordField.tap()
        passwordField.typeText("password123")

        app.buttons["loginButton"].tap()

        XCTAssertTrue(app.staticTexts["Welcome"].waitForExistence(timeout: 5))
    }
}
```

**Target Coverage:**
- Unit tests: 70-80%+
- Critical paths: 100%
- UI tests: Key user flows only (slow)

## iOS-Specific Features

### WidgetKit

```swift
import WidgetKit
import SwiftUI

struct SimpleWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "SimpleWidget", provider: Provider()) { entry in
            SimpleWidgetView(entry: entry)
        }
        .configurationDisplayName("My Widget")
        .description("This is my widget")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}
```

### Live Activities (iOS 16.1+)

```swift
import ActivityKit

struct OrderAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var status: String
        var estimatedTime: Date
    }

    var orderId: String
}

// Start activity
let attributes = OrderAttributes(orderId: "123")
let initialState = OrderAttributes.ContentState(
    status: "Preparing",
    estimatedTime: Date().addingTimeInterval(1800)
)

let activity = try Activity.request(
    attributes: attributes,
    contentState: initialState
)
```

### App Clips

**Characteristics:**
- <10MB size limit
- Fast, lightweight experiences
- No installation required
- Invoked via NFC, QR, Safari, Maps

## Human Interface Guidelines (HIG)

### Navigation Patterns

**Tab Bar:**
- 2-5 top-level sections
- Bottom placement
- Always visible
- Immediate navigation

**Navigation Bar:**
- Hierarchical navigation
- Back button automatic
- Title and actions
- Large/inline title modes

**Modal Presentation:**
- Interrupting tasks
- Self-contained flow
- Clear dismiss action
- Use sparingly

### Design Principles

**Clarity:**
- Legible text (minimum 11pt)
- Sufficient contrast (WCAG AA)
- Precise icons

**Deference:**
- Content first, UI second
- Translucent backgrounds
- Minimal UI elements

**Depth:**
- Layering (sheets, overlays)
- Visual hierarchy
- Motion provides meaning

### Colors

**System Colors:**
```swift
Color.primary      // Adaptive black/white
Color.secondary    // Gray
Color.accentColor  // App tint color
Color(uiColor: .systemBlue)
Color(uiColor: .label)
```

**Dark Mode:**
```swift
// Automatic
Color.primary  // Adapts to light/dark

// Custom
Color("CustomColor")  // Define in Assets.xcassets
```

### SF Symbols

```swift
Image(systemName: "star.fill")
    .foregroundColor(.yellow)
    .font(.title)

// Rendering modes
Image(systemName: "heart.fill")
    .symbolRenderingMode(.multicolor)
```

## App Store Requirements (2024-2025)

### SDK Requirements
- **Current**: Xcode 15+ with iOS 17 SDK (required as of April 2024)
- **Upcoming**: Xcode 16+ with iOS 18 SDK (recommended for 2025 submissions)

### Privacy
- **Privacy manifest**: Required for third-party SDKs
- **Tracking permission**: ATT framework for advertising
- **Privacy nutrition labels**: Accurate data collection info
- **Account deletion**: In-app deletion required

### Capabilities
- **Sandbox**: All apps sandboxed
- **Entitlements**: Request only needed capabilities
- **Background modes**: Justify background usage
- **HealthKit**: Privacy-sensitive, strict review

### Submission Checklist
✅ App icons (all required sizes)
✅ Screenshots (all device sizes)
✅ App description and keywords
✅ Privacy policy URL
✅ Support URL
✅ Age rating questionnaire
✅ Export compliance
✅ Test on real devices
✅ No crashes or major bugs

## Common Pitfalls

1. **Strong reference cycles**: Use `[weak self]` in closures
2. **Main thread blocking**: Use async/await, avoid sync operations
3. **Large images**: Resize before displaying
4. **Unhandled errors**: Always handle async throws
5. **Ignoring safe areas**: Use `.ignoresSafeArea()` intentionally
6. **Not testing dark mode**: Design for both appearances
7. **Hardcoded strings**: Use localization from start
8. **Memory leaks**: Profile with Instruments regularly

## Resources

**Official:**
- Swift Documentation: https://swift.org/documentation/
- SwiftUI Tutorials: https://developer.apple.com/tutorials/swiftui
- HIG: https://developer.apple.com/design/human-interface-guidelines/
- WWDC Videos: https://developer.apple.com/videos/

**Community:**
- Hacking with Swift: https://www.hackingwithswift.com/
- Swift by Sundell: https://www.swiftbysundell.com/
- objc.io: https://www.objc.io/
- iOS Dev Weekly: https://iosdevweekly.com/
