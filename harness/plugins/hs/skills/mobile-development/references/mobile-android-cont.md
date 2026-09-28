# Android Native Development (continued 2/3)

## Dependency Injection

### Hilt (Recommended for Large Apps)

**Setup:**
```kotlin
// App class
@HiltAndroidApp
class MyApplication : Application()

// Activity
@AndroidEntryPoint
class MainActivity : ComponentActivity()

// ViewModel
@HiltViewModel
class UserViewModel @Inject constructor(
    private val repository: UserRepository,
    private val analytics: Analytics
) : ViewModel()

// Module
@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    @Provides
    @Singleton
    fun provideRetrofit(): Retrofit = Retrofit.Builder()
        .baseUrl("https://api.example.com")
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    @Provides
    @Singleton
    fun provideUserApi(retrofit: Retrofit): UserApi =
        retrofit.create(UserApi::class.java)
}
```

### Koin (Lightweight Alternative)

**Setup:**
```kotlin
// Module definition
val appModule = module {
    single { UserRepository(get()) }
    viewModel { UserViewModel(get()) }
}

// Application
class MyApp : Application() {
    override fun onCreate() {
        super.onCreate()
        startKoin {
            androidContext(this@MyApp)
            modules(appModule)
        }
    }
}

// Usage
class UserViewModel(
    private val repository: UserRepository
) : ViewModel()
```

**Hilt vs Koin:**
- **Hilt**: Compile-time, type-safe, Google-backed, complex setup
- **Koin**: Runtime, simple DSL, 50% faster setup, reflection-based

## Performance Optimization

### R8 Optimization

**Automatic optimizations:**
- Code shrinking (remove unused)
- Obfuscation (rename classes/methods)
- Optimization (method inlining)

```groovy
// build.gradle
android {
    buildTypes {
        release {
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt')
        }
    }
}
```

**Impact:**
- 10-20% app size reduction
- 20% faster startup
- Harder to reverse engineer

### Baseline Profiles

**Performance boost:**
- 10-20% faster startup
- Reduced jank in critical paths
- AOT compilation of hot code

```gradle
// build.gradle
dependencies {
    implementation "androidx.profileinstaller:profileinstaller:1.3.1"
}
```

### Compose Performance

**1. Stability annotations:**
```kotlin
// Mark stable classes
@Stable
data class User(val name: String, val age: Int)

// Immutable collections
@Immutable
data class UserList(val users: List<User>)
```

**2. Avoid recomposition:**
```kotlin
// ❌ Bad: Recomposes every render
@Composable
fun UserList(users: List<User>) {
    LazyColumn {
        items(users) { user ->
            Text(user.name)  // Recreated every time
        }
    }
}

// ✅ Good: Use keys
@Composable
fun UserList(users: List<User>) {
    LazyColumn {
        items(users, key = { it.id }) { user ->
            Text(user.name)
        }
    }
}
```

**3. Remember expensive computations:**
```kotlin
@Composable
fun ExpensiveList(items: List<Item>) {
    val sortedItems = remember(items) {
        items.sortedBy { it.priority }
    }

    LazyColumn {
        items(sortedItems) { item ->
            ItemCard(item)
        }
    }
}
```

## Testing

### Unit Testing (JUnit + MockK)

```kotlin
class UserViewModelTest {
    private lateinit var viewModel: UserViewModel
    private val mockRepository = mockk<UserRepository>()

    @Before
    fun setup() {
        viewModel = UserViewModel(mockRepository)
    }

    @Test
    fun `loadUsers should update state with users`() = runTest {
        // Given
        val users = listOf(User("1", "Test", "test@example.com"))
        coEvery { mockRepository.getUsers() } returns flowOf(Result.success(users))

        // When
        viewModel.loadUsers()

        // Then
        val state = viewModel.uiState.value
        assertEquals(users, state.users)
        assertFalse(state.isLoading)
    }
}
```

### Compose Testing

```kotlin
class UserListScreenTest {
    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun displayUsers() {
        val users = listOf(User("1", "John", "john@example.com"))

        composeTestRule.setContent {
            UserListScreen(
                users = users,
                onUserClick = {}
            )
        }

        composeTestRule.onNodeWithText("John").assertIsDisplayed()
    }
}
```

### Instrumented Testing (Espresso)

```kotlin
@RunWith(AndroidJUnit4::class)
class LoginActivityTest {
    @get:Rule
    val activityRule = ActivityScenarioRule(LoginActivity::class.java)

    @Test
    fun loginFlow() {
        onView(withId(R.id.emailField))
            .perform(typeText("test@example.com"))

        onView(withId(R.id.passwordField))
            .perform(typeText("password123"))

        onView(withId(R.id.loginButton))
            .perform(click())

        onView(withText("Welcome"))
            .check(matches(isDisplayed()))
    }
}
```


---

Continued in [mobile-android-cont2.md](mobile-android-cont2.md)
