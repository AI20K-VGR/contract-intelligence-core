# Android Native Development

Guide: Android dev with Kotlin/Jetpack Compose (2024-2025).

## Kotlin 2.1 Overview

### Key Features
- **Null safety**: No more NullPointerExceptions
- **Coroutines**: Structured concurrency
- **Extension functions**: Extend classes without inheritance
- **Sealed classes**: Type-safe state management
- **Data classes**: Automatic equals/hashCode/toString

### Modern Kotlin Patterns

**Coroutines:**
```kotlin
// Suspend function
suspend fun fetchUser(id: String): User {
    return withContext(Dispatchers.IO) {
        api.getUser(id)
    }
}

// Usage in ViewModel
viewModelScope.launch {
    try {
        val user = fetchUser("123")
        _uiState.update { it.copy(user = user) }
    } catch (e: Exception) {
        _uiState.update { it.copy(error = e.message) }
    }
}
```

**Flow (Reactive streams):**
```kotlin
class UserRepository {
    fun observeUsers(): Flow<List<User>> = flow {
        while (true) {
            emit(database.getUsers())
            delay(5000)  // Poll every 5 seconds
        }
    }.flowOn(Dispatchers.IO)
}

// Collect in ViewModel
init {
    viewModelScope.launch {
        repository.observeUsers().collect { users ->
            _uiState.update { it.copy(users = users) }
        }
    }
}
```

**Sealed classes (Type-safe states):**
```kotlin
sealed class UiState {
    object Loading : UiState()
    data class Success(val data: List<User>) : UiState()
    data class Error(val message: String) : UiState()
}

// Pattern matching
when (uiState) {
    is UiState.Loading -> ShowLoader()
    is UiState.Success -> ShowData(uiState.data)
    is UiState.Error -> ShowError(uiState.message)
}
```

## Jetpack Compose

### Why Compose?
- **Declarative**: Describe UI state, not imperative commands
- **60% adoption**: In top 1,000 apps (2024)
- **Less code**: 40% reduction vs Views
- **Modern**: Built for Kotlin and coroutines
- **Material 3**: First-class support

### Compose Basics

```kotlin
@Composable
fun UserListScreen(viewModel: UserViewModel = viewModel()) {
    val uiState by viewModel.uiState.collectAsState()

    Column(modifier = Modifier.fillMaxSize()) {
        when (val state = uiState) {
            is UiState.Loading -> {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.CenterHorizontally)
                )
            }
            is UiState.Success -> {
                LazyColumn {
                    items(state.data) { user ->
                        UserItem(user)
                    }
                }
            }
            is UiState.Error -> {
                Text(
                    text = state.message,
                    color = MaterialTheme.colorScheme.error
                )
            }
        }
    }
}

@Composable
fun UserItem(user: User) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        Text(
            text = user.name,
            style = MaterialTheme.typography.bodyLarge
        )
    }
}
```

**Key Composables:**
- `Column/Row/Box`: Layout
- `LazyColumn/LazyRow`: Recycler equivalent (virtualized)
- `Text/Image/Icon`: Content
- `Button/TextField`: Input
- `Card/Surface`: Containers

## Architecture Patterns

### MVVM with Clean Architecture

```kotlin
// Domain Layer - Use Case
class GetUsersUseCase @Inject constructor(
    private val repository: UserRepository
) {
    operator fun invoke(): Flow<Result<List<User>>> =
        repository.getUsers()
}

// Data Layer - Repository
interface UserRepository {
    fun getUsers(): Flow<Result<List<User>>>
}

class UserRepositoryImpl @Inject constructor(
    private val api: UserApi,
    private val dao: UserDao
) : UserRepository {
    override fun getUsers(): Flow<Result<List<User>>> = flow {
        // Local cache first
        val cachedUsers = dao.getUsers()
        emit(Result.success(cachedUsers))

        // Then fetch from network
        try {
            val networkUsers = api.getUsers()
            dao.insertUsers(networkUsers)
            emit(Result.success(networkUsers))
        } catch (e: Exception) {
            emit(Result.failure(e))
        }
    }.flowOn(Dispatchers.IO)
}

// Presentation Layer - ViewModel
@HiltViewModel
class UserViewModel @Inject constructor(
    private val getUsersUseCase: GetUsersUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(UserUiState())
    val uiState: StateFlow<UserUiState> = _uiState.asStateFlow()

    init {
        loadUsers()
    }

    private fun loadUsers() {
        viewModelScope.launch {
            getUsersUseCase().collect { result ->
                result.onSuccess { users ->
                    _uiState.update { it.copy(users = users, isLoading = false) }
                }.onFailure { error ->
                    _uiState.update { it.copy(error = error.message, isLoading = false) }
                }
            }
        }
    }
}

// UI State
data class UserUiState(
    val users: List<User> = emptyList(),
    val isLoading: Boolean = true,
    val error: String? = null
)
```

### MVI (Model-View-Intent)

**When to use:**
- Unidirectional data flow needed
- Complex state management
- Time-travel debugging
- Predictable state updates

```kotlin
// State
data class UserScreenState(
    val users: List<User> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null
)

// Events (User intentions)
sealed class UserEvent {
    object LoadUsers : UserEvent()
    data class DeleteUser(val id: String) : UserEvent()
    object RetryLoad : UserEvent()
}

// ViewModel
class UserViewModel : ViewModel() {
    private val _state = MutableStateFlow(UserScreenState())
    val state: StateFlow<UserScreenState> = _state.asStateFlow()

    fun onEvent(event: UserEvent) {
        when (event) {
            is UserEvent.LoadUsers -> loadUsers()
            is UserEvent.DeleteUser -> deleteUser(event.id)
            is UserEvent.RetryLoad -> loadUsers()
        }
    }
}
```


---

Continued in [mobile-android-cont.md](mobile-android-cont.md)
