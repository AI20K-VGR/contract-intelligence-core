# Android Native Development (continued 3/3)

## Material Design 3

### Theme Setup

```kotlin
@Composable
fun AppTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context)
            else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
```

### Material Components

```kotlin
// Cards
Card(
    modifier = Modifier.fillMaxWidth(),
    elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
) {
    Text("Content")
}

// FAB
FloatingActionButton(onClick = { /* Do something */ }) {
    Icon(Icons.Default.Add, contentDescription = "Add")
}

// Navigation
NavigationBar {
    items.forEach { item ->
        NavigationBarItem(
            icon = { Icon(item.icon, contentDescription = null) },
            label = { Text(item.label) },
            selected = selectedItem == item,
            onClick = { selectedItem = item }
        )
    }
}
```

## Google Play Requirements (2024-2025)

### SDK Requirements
- **Current**: Target Android 14 (API 34)
- **Mandatory (Aug 31, 2025)**: Target Android 15 (API 35)

### Privacy & Security
- **Privacy policy**: Required for apps collecting data
- **Data safety**: Form in Play Console
- **Permissions**: Request only needed, justify dangerous permissions
- **Encryption**: HTTPS for network, KeyStore for sensitive data

### AAB (Android App Bundle)
```gradle
android {
    bundle {
        density {
            enableSplit true
        }
        abi {
            enableSplit true
        }
        language {
            enableSplit true
        }
    }
}
```

**Benefits:**
- 15-30% smaller downloads
- Dynamic feature modules
- Instant apps support

## Common Pitfalls

1. **Main thread blocking**: Use coroutines with Dispatchers.IO
2. **Memory leaks**: Unregister listeners, cancel coroutines
3. **Configuration changes**: Use ViewModel, avoid Activity references
4. **Large images**: Use Coil/Glide for caching and resizing
5. **Forgetting permissions**: Runtime permission requests
6. **Ignoring Android versions**: Test on multiple API levels
7. **Not handling back press**: OnBackPressedDispatcher
8. **Hardcoded strings**: Use strings.xml for localization
9. **Not using Proguard/R8**: Enable in release builds
10. **Ignoring battery**: Use WorkManager for background tasks

## Resources

**Official:**
- Kotlin Docs: https://kotlinlang.org/docs/home.html
- Compose Docs: https://developer.android.com/jetpack/compose
- Material 3: https://m3.material.io/
- Android Guides: https://developer.android.com/guide

**Community:**
- Android Weekly: https://androidweekly.net/
- Kt.Academy: https://kt.academy/
- Coding in Flow: https://codinginflow.com/
- Philipp Lackner: https://pl-coding.com/
