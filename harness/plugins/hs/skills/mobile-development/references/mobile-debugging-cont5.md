# Mobile Debugging Strategies (continued 6/6)

## Debugging Checklist

**Before Filing Bug:**
- [ ] Reproduce on real device
- [ ] Check both iOS and Android
- [ ] Test on multiple OS versions
- [ ] Verify network connectivity
- [ ] Check app permissions
- [ ] Review recent code changes
- [ ] Check crash logs

**Investigation:**
- [ ] Enable debug logging
- [ ] Use platform debugger
- [ ] Profile performance if slow
- [ ] Monitor memory usage
- [ ] Check network requests
- [ ] Inspect UI hierarchy

**Production Issues:**
- [ ] Check crash reporting dashboard
- [ ] Review user-reported issues
- [ ] Analyze affected OS versions
- [ ] Check affected devices
- [ ] Review recent app releases
- [ ] Compare crash-free rates

**After Fix:**
- [ ] Test on real devices
- [ ] Verify on affected OS versions
- [ ] Add regression test
- [ ] Staged rollout (10% → 100%)
- [ ] Monitor crash rates

## Resources

**General:**
- React Native Debugging: https://reactnative.dev/docs/debugging
- Flutter DevTools: https://docs.flutter.dev/tools/devtools
- iOS Debugging: https://developer.apple.com/documentation/xcode/debugging
- Android Debugging: https://developer.android.com/studio/debug

**Crash Reporting:**
- Firebase Crashlytics: https://firebase.google.com/docs/crashlytics
- Sentry: https://docs.sentry.io/platforms/react-native/
- Bugsnag: https://docs.bugsnag.com/

**Performance:**
- iOS Instruments: https://developer.apple.com/instruments/
- Android Profiler: https://developer.android.com/studio/profile
- Flipper: https://fbflipper.com/

**Network:**
- Proxyman: https://proxyman.io/
- Charles Proxy: https://www.charlesproxy.com/
- Flipper Network Plugin: https://fbflipper.com/docs/features/network-plugin/
