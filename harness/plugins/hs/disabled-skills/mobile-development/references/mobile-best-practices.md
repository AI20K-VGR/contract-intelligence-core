# Mobile Development Best Practices

Cross-platform mobile best practices (2024-2025).

## Mobile-First Design Principles

### Core Principles
1. **Content First**: Remove chrome, focus on content
2. **Progressive Disclosure**: Hide complexity behind layers
3. **Thumb-Friendly**: Primary actions within reach
4. **Performance Budget**: <2s launch, <1s screen load
5. **Offline-First**: Design for unreliable networks

### Touch Targets
- **iOS**: 44x44px minimum (HIG guideline)
- **Android**: 48x48px minimum (Material Design)
- **Optimal**: 44-57px for important actions
- **Spacing**: 8px minimum between targets

### Typography
- **iOS**: San Francisco (system font)
- **Android**: Roboto (Material)
- **Minimum**: 16px body text (accessibility)
- **Line height**: 1.5x for readability

## Performance Optimization

### Launch Time Optimization
**Targets:**
- Cold start: <2s
- Warm start: <1s
- Hot start: <0.5s

**Techniques:**
- Defer non-critical initialization
- Lazy load dependencies
- Preload critical data only
- Show UI before data ready

### Memory Management
**Targets:**
- Typical screen: <100MB
- Peak usage: <200MB

**Techniques:**
- Image pagination/virtualization
- Release resources in background
- Profile with Instruments/Profiler
- Avoid retain cycles/memory leaks

**React Native Example:**
```javascript
// Use FlatList instead of ScrollView for long lists
<FlatList
  data={items}
  renderItem={({ item }) => <ItemCard item={item} />}
  keyExtractor={(item) => item.id}
  initialNumToRender={10}
  maxToRenderPerBatch={10}
  windowSize={5}
/>
```

### Network Optimization
**Techniques:**
- Batch API requests
- Cache aggressively
- Compress images (WebP, AVIF)
- Use CDN for static assets
- Implement request deduplication

**Example Strategy:**
```
User opens screen
├─ Show cached data immediately (stale-while-revalidate)
├─ Fetch fresh data in background
└─ Update UI when fresh data arrives
```

### Battery Optimization
**Techniques:**
- Batch network requests
- Reduce GPS accuracy when possible
- Use push instead of polling
- Respect Doze Mode (Android)
- Background App Refresh (iOS)

**Targets:**
- Active use: <5% per hour
- Background: <1% per hour

## Offline-First Architecture

### Local Storage Options
**React Native:**
- AsyncStorage (small data, <6MB)
- Realm (complex objects, relationships)
- SQLite (relational data)
- MMKV (fastest key-value)

**Flutter:**
- SharedPreferences (small data)
- Hive (NoSQL, fast)
- Drift (SQLite wrapper)
- ObjectBox (object database)

**iOS:**
- UserDefaults (small data)
- Core Data (complex objects)
- SwiftData (modern replacement)
- Realm

**Android:**
- SharedPreferences (small data)
- Room (SQLite ORM)
- Realm
- DataStore (Preferences + Proto)

### Data Synchronization Strategies

**1. Write-Through Cache**
```
User makes change
├─ Update local database immediately
├─ Update UI optimistically
├─ Queue sync operation
└─ Sync to server in background
```

**2. Hybrid Sync (Push + Pull)**
```
Push Sync (Real-time)
├─ WebSocket connection for critical updates
└─ Immediate notification of changes

Pull Sync (Periodic)
├─ Periodic polling for non-critical data
├─ Pull on app foreground
└─ Incremental sync (only changes since last sync)
```

**3. Conflict Resolution**
- **Last-write-wins**: Use timestamps
- **Operational transformation**: Merge changes
- **CRDT**: Conflict-free replicated data
- **Manual resolution**: User chooses

### Example: Offline-First Comments

```typescript
// React Native + TypeScript
class CommentService {
  async postComment(text: string, postId: string) {
    const tempId = generateTempId();
    const comment = {
      id: tempId,
      text,
      postId,
      synced: false,
      timestamp: Date.now()
    };

    // 1. Save locally immediately
    await db.comments.insert(comment);

    // 2. Update UI (optimistic)
    eventBus.emit('comment:added', comment);

    // 3. Sync to server in background
    try {
      const serverComment = await api.postComment(text, postId);
      // Replace temp ID with server ID
      await db.comments.update(tempId, {
        id: serverComment.id,
        synced: true
      });
    } catch (error) {
      // Mark as pending sync, retry later
      await db.comments.update(tempId, {
        syncError: error.message
      });
      syncQueue.add({ type: 'comment', id: tempId });
    }
  }
}
```

## Mobile Analytics & Monitoring

### Analytics Platforms (2024-2025)

**Firebase Analytics (Recommended)**
- Free tier generous
- Mobile-specific events
- Integrated with Crashlytics
- AI-powered insights
- Supports all platforms

**Sentry**
- Error tracking + performance
- Cross-platform support
- Source map upload
- Release tracking
- Custom breadcrumbs

**Amplitude**
- Product analytics
- User behavior tracking
- Cohort analysis
- A/B testing integration

### Essential Events to Track

**User Journey:**
- App opened
- Screen viewed
- Feature used
- Conversion events
- User retention

**Performance:**
- App launch time
- Screen load time
- API latency
- Crash-free rate
- ANR rate (Android)

**Business:**
- Purchases
- Subscriptions
- Ad impressions
- Feature adoption
- Referrals

### Crashlytics Integration

**React Native:**
```javascript
import crashlytics from '@react-native-firebase/crashlytics';

// Log events
crashlytics().log('User tapped purchase button');

// Set user attributes
crashlytics().setUserId(user.id);

// Log non-fatal errors
try {
  await riskyOperation();
} catch (error) {
  crashlytics().recordError(error);
}
```

**Flutter:**
```dart
import 'package:firebase_crashlytics/firebase_crashlytics.dart';

// Log events
FirebaseCrashlytics.instance.log('User tapped purchase');

// Set user ID
FirebaseCrashlytics.instance.setUserIdentifier(userId);

// Record errors
await FirebaseCrashlytics.instance.recordError(
  error,
  stackTrace,
  reason: 'API call failed',
);
```


---

Continued in [mobile-best-practices-cont.md](mobile-best-practices-cont.md)
